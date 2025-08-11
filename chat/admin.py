"""
chat.admin module.

Django-admin registrations for the *findus* chat application.
"""

from django.contrib import admin

# Import both models directly so ChatMessage is available at import-time for
# the ``@admin.register`` decorator.
from .models import Conversation, ChatMessage, AfterActionReport, UserProfile

# ---------------------------------------------------------------------------
# Admin registrations
# ---------------------------------------------------------------------------


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin configuration for :class:`chat.models.Conversation`."""

    list_display = ("id", "title", "user", "created_at", "updated_at")
    search_fields = ("title", "user__username")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-updated_at",)
    list_filter = ("user",)


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
        msg: str = str(obj.message)
        return msg[:60] + ("…" if len(msg) > 60 else "")

# --------------------------------------------------------------------------- #
# User profile admin                                                          #
# --------------------------------------------------------------------------- #


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin configuration for :class:`chat.models.UserProfile`."""

    list_display = (
        "id",
        "user",
        "level",
        "level_updated_at",
        "short_weaknesses",
    )
    search_fields = ("user__username", "level")
    readonly_fields = ("level_updated_at",)
    list_filter = ("level",)
    ordering = ("-level_updated_at",)

    @staticmethod
    def short_weaknesses(obj: "UserProfile") -> str:
        """
        Return a human-readable, truncated representation of weakness keys.

        Shows up to 60 characters composed of comma-separated weakness names.
        """

        if not obj.weaknesses:
            return "—"

        # Extract just the keys/names of weaknesses
        keys = list(obj.weaknesses.keys())
        joined = ", ".join(keys)
        return joined[:60] + ("…" if len(joined) > 60 else "")

    short_weaknesses.short_description = "Weaknesses"

# --------------------------------------------------------------------------- #
# After-action report admin                                                   #
# --------------------------------------------------------------------------- #


@admin.register(AfterActionReport)
class AfterActionReportAdmin(admin.ModelAdmin):
    """Admin configuration for :class:`chat.models.AfterActionReport`."""

    list_display = (
        "id",
        "conversation",
        "created_at",
    )
    search_fields = ("analysis_content", "conversation__title")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
