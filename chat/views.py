"""
chat/views.py.

Views for the chat application that integrates with Gemini API.
"""

from typing import Optional, Callable, TypeVar, Any
import random
import asyncio

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect, aget_object_or_404
from django.urls import reverse
from django.utils import timezone

from .models import ChatMessage, Conversation, AfterActionReport
from .ai_service import ai_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Type variables for view function annotations
F = TypeVar('F', bound=Callable[..., Any])

# Conversation starter prompts - elementary language textbook style
CONVERSATION_STARTERS = [
    "Tell me about your family?",
    "What did you do today?",
    "What do you like doing for fun?",
    "What did you do this weekend?",
    "What's your favorite food?",
    "Do you have any pets?",
    "What's your favorite season and why?",
    "What do you like to do after school or work?",
    "Tell me about your best friend?",
    "What's your favorite holiday?",
    "What kind of music do you like?",
    "Do you play any sports?",
    "What's your favorite subject in school?",
    "Tell me about your hometown?",
    "What are your hobbies?",
]


async def analyze_grammar_async(message_id: int, user_message: str) -> None:
    """
    Async grammar analysis using Django's async ORM.

    1. Ask AI to analyse ``user_message`` for grammar / spelling issues using Pydantic AI.
    2. Persist the feedback to ``ChatMessage.grammar_analysis``.

    Args:
        message_id: Primary-key of the ``ChatMessage`` row to update
        user_message: The original user prompt
    """
    try:
        analysis_text = await ai_service.analyze_grammar(user_message)
        # Update only the grammar_analysis column to avoid race-conditions
        await ChatMessage.objects.filter(pk=message_id).aupdate(
            grammar_analysis=analysis_text
        )
    except Exception as exc:  # pragma: no cover – best-effort background task
        # In production you might log this.
        await ChatMessage.objects.filter(pk=message_id).aupdate(
            grammar_analysis=f"Analysis failed: {exc}"
        )


@login_required  # type: ignore
async def chat_view(
    request: HttpRequest, conversation_id: int | None = None
) -> HttpResponse:
    """
    Render the main chat interface with message history.

    Args:
        request: The HTTP request object

    Returns:
        Rendered chat.html template with message history
    """
    # If no conversation id – start a fresh one
    if conversation_id is None:
        return redirect("new_conversation")

    conversation = await aget_object_or_404(
        Conversation, pk=conversation_id, user=request.user
    )
    messages = [
        msg async for msg in conversation.messages.all()
    ]  # ordering defined in Meta

    # Select a random conversation starter for new conversations
    conversation_starter = random.choice(CONVERSATION_STARTERS)

    return render(
        request,
        "chat/chat.html",
        {
            "messages": messages,
            "conversation": conversation,
            "conversation_starter": conversation_starter,
        },
    )


@login_required  # type: ignore
async def new_conversation(request: HttpRequest) -> HttpResponse:
    """Create a new conversation and redirect to its chat view."""
    convo = await Conversation.objects.acreate(user=request.user)
    return redirect(reverse("chat", args=[convo.id]))


@login_required  # type: ignore
async def send_message(request: HttpRequest) -> JsonResponse:
    """
    Process a user message, send to Gemini API, and return the response.

    Args:
        request: The HTTP request object containing the user message

    Returns:
        JsonResponse with the AI response and status
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

    # Get the user message and conversation ID from the request
    user_message = request.POST.get('message', '').strip()
    conversation_id = request.POST.get('conversation_id')

    if not user_message:
        return JsonResponse({'error': 'Message cannot be empty'}, status=400)

    if not conversation_id:
        return JsonResponse({'error': 'Conversation ID is required'}, status=400)

    try:
        # Look up the conversation
        conversation = await aget_object_or_404(
            Conversation, pk=conversation_id, user=request.user
        )

        # ------------------------------------------------------------------
        # 1. Use Pydantic AI service to generate response with Logfire tracking
        # 2. This automatically logs input/output to Logfire for observability
        # ------------------------------------------------------------------

        ai_response = await ai_service.generate_chat_response(user_message)

        # Save the message and response to the database with conversation
        chat_message = await ChatMessage.objects.acreate(
            conversation=conversation, message=user_message, response=ai_response
        )

        # Update the conversation's last updated timestamp
        conversation.updated_at = timezone.now()
        
        # --------------------------------------------------------------
        # Run conversation save and grammar analysis concurrently
        # This ensures the grammar analysis actually completes
        # --------------------------------------------------------------
        await asyncio.gather(
            conversation.asave(update_fields=['updated_at']),
            analyze_grammar_async(chat_message.id, user_message)
        )

        # Return the response as JSON
        return JsonResponse(
            {
                'message': user_message,
                'response': ai_response,
                'timestamp': chat_message.created_at.isoformat(),
                'message_id': chat_message.id,  # ← allows client-side polling
                'conversation_id': conversation.id,
            }
        )

    except Exception as e:
        # Handle any errors that occur during the API call
        return JsonResponse(
            {
                'error': f'Error communicating with Gemini API: {str(e)}',
            },
            status=500,
        )


@login_required  # type: ignore
async def check_grammar_status(request: HttpRequest, message_id: int) -> JsonResponse:
    """
    Return grammar analysis for a given ``ChatMessage``.

    Expected by the front-end polling code.  The endpoint is read-only.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Only GET requests are allowed"}, status=405)

    message: ChatMessage = await aget_object_or_404(ChatMessage, pk=message_id)

    # Return analysis (may be empty string / None)
    return JsonResponse(
        {
            "grammar_analysis": message.grammar_analysis or "",
        }
    )


# --------------------------------------------------------------------------- #
# After-action report                                                         #
# --------------------------------------------------------------------------- #


@login_required  # type: ignore
async def conversation_analysis(
    request: HttpRequest,
    conversation_id: int,
) -> HttpResponse:
    """
    Display an *after-action* report for a finished conversation.

    The function fetches every :class:`chat.models.ChatMessage` belonging to
    the conversation, pairs each user prompt with its grammar feedback, and
    asks Gemini for a holistic assessment:

    1. Recurring grammar / spelling issues
    2. Notable strengths
    3. 3-5 concrete recommendations or exercises to improve

    The generated analysis is rendered via *chat/analysis.html*.
    """
    # ------------------------------------------------------------------ #
    # 1. Fetch conversation & ensure it has messages                     #
    # ------------------------------------------------------------------ #
    conversation: Conversation = await aget_object_or_404(
        Conversation, pk=conversation_id, user=request.user
    )
    messages_qs = conversation.messages.all()  # ordering in model.Meta

    # Redirect to chat view when there is nothing to analyse yet.
    if not await messages_qs.aexists():
        return redirect(reverse("chat", args=[conversation.id]))

    # ------------------------------------------------------------------ #
    # 1b. If we've already generated a report, re-use it                 #
    # ------------------------------------------------------------------ #
    existing_report: Optional[AfterActionReport] = await conversation.reports.afirst()

    if existing_report:
        return render(
            request,
            "chat/analysis.html",
            {
                "conversation": conversation,
                "analysis": existing_report.analysis_content,
                "report": existing_report,
            },
        )

    # ------------------------------------------------------------------ #
    # 2. Build prompt for Gemini                                         #
    # ------------------------------------------------------------------ #
    prompt_parts: list[str] = [
        "You are an experienced English teacher creating a short "
        "after-action report for your student.\n",
        "Below is the full conversation in pairs of user text followed by "
        "the grammar feedback they already received.\n\n",
    ]

    async for msg in messages_qs:
        feedback = msg.grammar_analysis or "No feedback available."
        prompt_parts.append(f"User: {msg.message}\nFeedback: {feedback}\n---\n")

    prompt_parts.append(
        "\nBased on the entire dialogue:\n"
        "• Identify recurring grammar / spelling issues.\n"
        "• Highlight their strengths.\n"
        "• Provide 3-5 concrete exercises or recommendations to improve.\n"
        "Respond in concise bullet-points."
    )

    # ------------------------------------------------------------------ #
    # 3. Call AI service for conversation analysis                       #
    # ------------------------------------------------------------------ #
    messages_data = []
    async for msg in messages_qs:
        messages_data.append({'message': msg.message, 'feedback': msg.grammar_analysis})

    analysis_text: str = await ai_service.analyze_conversation(messages_data)

    # ------------------------------------------------------------------ #
    # 4. Persist after-action report                                     #
    # ------------------------------------------------------------------ #
    report = await AfterActionReport.objects.acreate(
        conversation=conversation,
        analysis_content=analysis_text,
    )

    # ------------------------------------------------------------------ #
    # 5. Render template                                                 #
    # ------------------------------------------------------------------ #
    return render(
        request,
        "chat/analysis.html",
        {
            "conversation": conversation,
            "analysis": analysis_text,
            "report": report,
        },
    )
