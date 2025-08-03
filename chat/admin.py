"""
chat.admin module.

Django-admin registrations for the *findus* chat application.
"""

from django.contrib import admin

# Import both models directly so ChatMessage is available at import-time for
# the ``@admin.register`` decorator.
from .models import Conversation, ChatMessage

# ---------------------------------------------------------------------------
# Admin registrations
# ---------------------------------------------------------------------------


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin configuration for :class:`chat.models.Conversation`."""

    list_display = ("id", "title", "created_at", "updated_at")
    search_fields = ("title",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-updated_at",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Admin configuration for :class:`chat.models.ChatMessage`."""

    list_display = ("id", "short_message", "conversation", "created_at")
    list_filter = ("conversation",)
    search_fields = ("message", "response")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    @staticmethod
    def short_message(obj: "ChatMessage") -> str:
        """Return a truncated preview of the user message."""
        # Explicit `str()` cast ensures a concrete ``str`` return type for MyPy.
        msg: str = str(obj.message)
        return msg[:60] + ("…" if len(msg) > 60 else "")
