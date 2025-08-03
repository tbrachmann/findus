"""
chat.urls module.

URL configuration for the chat application.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Landing page -> start a fresh conversation
    path('', views.new_conversation, name='home'),
    # Explicit endpoint to begin a new conversation
    path('new/', views.new_conversation, name='new_conversation'),
    # Chat interface for a given conversation id
    path('conversation/<int:conversation_id>/', views.chat_view, name='chat'),
    # API endpoint for sending messages to Gemini
    path('send/', views.send_message, name='send_message'),
    # Polling endpoint to fetch grammar analysis results
    path(
        'check-grammar/<int:message_id>/',
        views.check_grammar_status,
        name='check_grammar_status',
    ),
]
