"""
chat/views.py.

Views for the chat application that integrates with Gemini API.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.http import HttpRequest, HttpResponse
from django.conf import settings
import threading
import google.genai as genai

from django.urls import reverse
from django.utils import timezone

from .models import ChatMessage, Conversation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def analyze_grammar_async(message_id: int, user_message: str) -> None:
    """
    Run in a background thread.

    1. Ask Gemini to analyse ``user_message`` for grammar / spelling issues.
    2. Persist the feedback to ``ChatMessage.grammar_analysis``.

    Args:
        message_id: Primary-key of the ``ChatMessage`` row to update
        user_message: The original user prompt
    """
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = (
            "Analyze this text for grammatical errors and spelling mistakes. "
            "Provide brief, helpful feedback. If there are no issues, "
            "respond with 'No issues found.'\n\n"
            f"Text:\n\"\"\"\n{user_message}\n\"\"\""
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        analysis_text = response.text

        # Update only the grammar_analysis column to avoid race-conditions
        ChatMessage.objects.filter(pk=message_id).update(grammar_analysis=analysis_text)
    except Exception as exc:  # pragma: no cover – best-effort background task
        # In production you might log this.
        ChatMessage.objects.filter(pk=message_id).update(
            grammar_analysis=f"Analysis failed: {exc}"
        )


def chat_view(request: HttpRequest, conversation_id: int | None = None) -> HttpResponse:
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

    conversation = get_object_or_404(Conversation, pk=conversation_id)
    messages = conversation.messages.all()  # ordering defined in Meta

    return render(
        request,
        "chat/chat.html",
        {
            "messages": messages,
            "conversation": conversation,
        },
    )


def new_conversation(request: HttpRequest) -> HttpResponse:
    """Create a new conversation and redirect to its chat view."""
    convo = Conversation.objects.create()
    return redirect(reverse("chat", args=[convo.id]))


def send_message(request: HttpRequest) -> JsonResponse:
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
        conversation = get_object_or_404(Conversation, pk=conversation_id)

        # ------------------------------------------------------------------
        # 1. Build the Google GenAI client with the project's API key
        # 2. Call the `generate_content` helper on the client's `models`
        #    collection (per official docs) to fetch a response from the
        #    `gemini-2.5-flash-lite` model.
        # ------------------------------------------------------------------

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=user_message,
        )

        # Extract the text from the API response
        ai_response = response.text

        # Save the message and response to the database with conversation
        chat_message = ChatMessage.objects.create(
            conversation=conversation, message=user_message, response=ai_response
        )

        # Update the conversation's last updated timestamp
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=['updated_at'])

        # --------------------------------------------------------------
        # Kick-off background grammar / spelling analysis so the user
        # gets the main AI answer immediately.  We mark the thread as
        # *daemon* so it won't block server shutdown.
        # --------------------------------------------------------------
        threading.Thread(
            target=analyze_grammar_async,
            args=(chat_message.id, user_message),
            daemon=True,
        ).start()

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


def check_grammar_status(request: HttpRequest, message_id: int) -> JsonResponse:
    """
    Return grammar analysis for a given ``ChatMessage``.

    Expected by the front-end polling code.  The endpoint is read-only.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Only GET requests are allowed"}, status=405)

    message: ChatMessage = get_object_or_404(ChatMessage, pk=message_id)

    # Return analysis (may be empty string / None)
    return JsonResponse(
        {
            "grammar_analysis": message.grammar_analysis or "",
        }
    )
