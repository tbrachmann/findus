"""
chat.urls module.

URL configuration for the chat application.
"""

from django.urls import path
from . import views
from . import auth_views  # New import for authentication endpoints

urlpatterns = [
    # Authentication
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('register/', auth_views.register_view, name='register'),
    # Landing page -> language selection
    path('', views.language_selection, name='home'),
    # Language selection page
    path('select-language/', views.language_selection, name='language_selection'),
    # Explicit endpoint to begin a new conversation
    path('new/', views.new_conversation, name='new_conversation'),
    # Chat interface for a given conversation id
    path('conversation/<int:conversation_id>/', views.chat_view, name='chat'),
    # After-action report for a finished conversation
    path(
        'conversation/<int:conversation_id>/analysis/',
        views.conversation_analysis,
        name='conversation_analysis',
    ),
    # API endpoint for sending messages to Gemini
    path('send/', views.send_message, name='send_message'),
    # Polling endpoint to fetch grammar analysis results
    path(
        'check-grammar/<int:message_id>/',
        views.check_grammar_status,
        name='check_grammar_status',
    ),
]
