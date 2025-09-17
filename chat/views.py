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
from django.views.decorators.csrf import csrf_protect
from django_ratelimit.decorators import ratelimit

from .models import ChatMessage, Conversation, AfterActionReport
from .ai_service import ai_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Type variables for view function annotations
F = TypeVar('F', bound=Callable[..., Any])

# Conversation starter prompts - elementary language textbook style
CONVERSATION_STARTERS = {
    'en': [
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
    ],
    'es': [
        "Háblame de tu familia?",
        "¿Qué hiciste hoy?",
        "¿Qué te gusta hacer por diversión?",
        "¿Qué hiciste este fin de semana?",
        "¿Cuál es tu comida favorita?",
        "¿Tienes mascotas?",
        "¿Cuál es tu estación favorita y por qué?",
        "¿Qué te gusta hacer después del trabajo o la escuela?",
        "Háblame de tu mejor amigo?",
        "¿Cuál es tu día festivo favorito?",
        "¿Qué tipo de música te gusta?",
        "¿Practicas algún deporte?",
        "¿Cuál es tu materia favorita en la escuela?",
        "Háblame de tu ciudad natal?",
        "¿Cuáles son tus pasatiempos?",
    ],
    'de': [
        "Erzähl mir von deiner Familie?",
        "Was hast du heute gemacht?",
        "Was machst du gerne zum Spaß?",
        "Was hast du am Wochenende gemacht?",
        "Was ist dein Lieblingsessen?",
        "Hast du Haustiere?",
        "Was ist deine Lieblingsjahreszeit und warum?",
        "Was machst du gerne nach der Schule oder Arbeit?",
        "Erzähl mir von deinem besten Freund?",
        "Was ist dein Lieblingsfeiertag?",
        "Welche Art von Musik magst du?",
        "Treibst du Sport?",
        "Was ist dein Lieblingsfach in der Schule?",
        "Erzähl mir von deiner Heimatstadt?",
        "Was sind deine Hobbys?",
    ],
}


async def analyze_grammar_async(
    message_id: int,
    user_message: str,
    analysis_language: str = 'en',
    language_code: str = 'en',
) -> None:
    """
    Async grammar analysis using Django's async ORM.

    1. Ask AI to analyse ``user_message`` for grammar / spelling issues using Pydantic AI.
    2. Persist the feedback to ``ChatMessage.grammar_analysis``.

    Args:
        message_id: Primary-key of the ``ChatMessage`` row to update
        user_message: The original user prompt
        analysis_language: Language code for the grammar analysis feedback
        language_code: Language code for the conversation being analyzed
    """
    try:
        analysis_text = await ai_service.analyze_grammar(
            user_message, analysis_language, language_code
        )
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
        msg async for msg in conversation.messages.select_related('conversation').all()
    ]

    # Select a random conversation starter for new conversations
    starters = CONVERSATION_STARTERS.get(
        conversation.language, CONVERSATION_STARTERS['en']
    )
    conversation_starter = random.choice(starters)

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
async def language_selection(request: HttpRequest) -> HttpResponse:
    """Display language selection page for new conversations."""
    user = await request.auser()

    return render(request, "chat/language_selection.html", {'user': user})


@login_required  # type: ignore
async def new_conversation(request: HttpRequest) -> HttpResponse:
    """Create a new conversation with selected language and redirect to its chat view."""
    # Get languages from POST or default to English
    language = request.POST.get('language', 'en') if request.method == 'POST' else 'en'
    analysis_language = (
        request.POST.get('analysis_language', 'en')
        if request.method == 'POST'
        else 'en'
    )

    # Validate language choices
    valid_languages = dict(Conversation.LANGUAGE_CHOICES).keys()
    if language not in valid_languages:
        language = 'en'
    if analysis_language not in valid_languages:
        analysis_language = 'en'

    convo = await Conversation.objects.acreate(
        user=request.user, language=language, analysis_language=analysis_language
    )
    return redirect(reverse("chat", args=[convo.id]))


@login_required  # type: ignore
@ratelimit(key='ip', rate='10/h', method='POST')  # type: ignore
@ratelimit(key='ip', rate='100/d', method='POST')  # type: ignore
@ratelimit(key='session', rate='5/h', method='POST')  # type: ignore
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

    # Look up the conversation
    conversation = await aget_object_or_404(
        Conversation, pk=conversation_id, user=request.user
    )

    # ------------------------------------------------------------------
    # 1. Build conversation history for memory
    # ------------------------------------------------------------------
    conversation_history = []
    async for msg in conversation.messages.all().order_by('created_at'):
        conversation_history.extend(
            [
                {'role': 'user', 'content': msg.message},
                {'role': 'assistant', 'content': msg.response},
            ]
        )

    # ------------------------------------------------------------------
    # 2. Use Pydantic AI service to generate response with conversation memory
    # 3. This automatically logs input/output to Logfire for observability
    # ------------------------------------------------------------------

    try:
        ai_response = await ai_service.generate_chat_response(
            user_message, conversation.language, conversation_history
        )
    except Exception as e:
        return JsonResponse(
            {'error': f'Error communicating with AI service: {str(e)}'}, status=500
        )

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
        analyze_grammar_async(
            chat_message.id,
            user_message,
            conversation.analysis_language,
            conversation.language,
        ),
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
    # 2. Build messages data for analysis                                #
    # ------------------------------------------------------------------ #
    messages_data = []
    async for msg in messages_qs:
        messages_data.append({'message': msg.message, 'feedback': msg.grammar_analysis})

    # ------------------------------------------------------------------ #
    # 3. Call AI service for conversation analysis                       #
    # ------------------------------------------------------------------ #

    analysis_text: str = await ai_service.analyze_conversation(
        messages_data, conversation.analysis_language, conversation.language
    )

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


# ---------------------------------------------------------------------------
# Demo Mode Views (No Authentication Required)
# ---------------------------------------------------------------------------


async def demo_language_selection(request: HttpRequest) -> HttpResponse:
    """Display language selection page for demo mode."""
    return render(request, "chat/demo_language_selection.html")


async def demo_chat_view(request: HttpRequest) -> HttpResponse:
    """
    Render the demo chat interface that uses session storage.

    Clears any existing conversation history to start fresh on page load.

    Args:
        request: The HTTP request object

    Returns:
        Rendered demo_chat.html template or redirect to language selection
    """
    # Get language and analysis language from URL parameters
    language = request.GET.get('language')
    analysis_language = request.GET.get('analysis_language')

    # If no language provided, redirect to language selection
    if not language:
        return redirect(reverse('demo_language_selection'))

    # Validate language choices
    if language not in CONVERSATION_STARTERS:
        return redirect(reverse('demo_language_selection'))

    # Default analysis language to English if not provided
    if not analysis_language or analysis_language not in CONVERSATION_STARTERS:
        analysis_language = 'en'

    # Clear any existing conversation history to start fresh
    await request.session.apop('demo_conversation_history', None)

    # Select a random conversation starter for demo based on language
    conversation_starter = random.choice(CONVERSATION_STARTERS[language])

    return render(
        request,
        "chat/demo_chat.html",
        {
            "conversation_starter": conversation_starter,
            "language": language,
            "analysis_language": analysis_language,
        },
    )


@csrf_protect  # type: ignore[misc]
@ratelimit(key='ip', rate='10/h', method='POST')  # type: ignore
@ratelimit(key='ip', rate='100/d', method='POST')  # type: ignore
@ratelimit(key='session', rate='5/h', method='POST')  # type: ignore
async def demo_send_message(request: HttpRequest) -> JsonResponse:
    """Process a demo message, send to AI API, and return the response.

    Uses session storage instead of database persistence.

    Args:
        request: The HTTP request object containing the user message

    Returns:
        JsonResponse with the AI response and status
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

    # Get the user message and languages from the request
    user_message = request.POST.get('message', '').strip()
    language = request.POST.get('language', 'en')
    analysis_language = request.POST.get('analysis_language', 'en')

    if not user_message:
        return JsonResponse({'error': 'Message cannot be empty'}, status=400)

    # ------------------------------------------------------------------
    # 1. Get conversation history from session storage using Django's async session methods
    # ------------------------------------------------------------------
    conversation_history = await request.session.aget('demo_conversation_history', [])

    # ------------------------------------------------------------------
    # 2. Generate chat response and grammar analysis concurrently
    # ------------------------------------------------------------------
    try:
        ai_response, grammar_analysis = await asyncio.gather(
            ai_service.generate_chat_response(
                user_message, language, conversation_history
            ),
            ai_service.analyze_grammar(user_message, analysis_language, language),
        )
    except Exception as e:
        return JsonResponse(
            {'error': f'Error communicating with AI service: {str(e)}'}, status=500
        )

    # ------------------------------------------------------------------
    # 3. Update session with new message and response using Django's async session methods
    # ------------------------------------------------------------------
    new_conversation_history = conversation_history + [
        {'role': 'user', 'content': user_message},
        {'role': 'assistant', 'content': ai_response},
    ]
    await request.session.aset('demo_conversation_history', new_conversation_history)

    # Return the response as JSON
    return JsonResponse(
        {
            'message': user_message,
            'response': ai_response,
            'grammar_analysis': grammar_analysis,
            'timestamp': timezone.now().isoformat(),
        }
    )


async def demo_clear_conversation(request: HttpRequest) -> JsonResponse:
    """Clear the demo conversation history from session storage."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

    # Clear the conversation history from session using Django's async session methods
    await request.session.apop('demo_conversation_history', None)

    return JsonResponse(
        {'status': 'success', 'message': 'Conversation history cleared'}
    )
