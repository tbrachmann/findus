"""
chat.admin module.

Django-admin registrations for the *findus* chat application.
"""

from django.contrib import admin

# Import both models directly so ChatMessage is available at import-time for
# the ``@admin.register`` decorator.
from .models import (
    Conversation,
    ChatMessage,
    AfterActionReport,
    UserProfile,
    LanguageProfile,
    GrammarConcept,
    ConceptMastery,
    ErrorPattern,
)

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
        # Explicit `str()` cast ensures a concrete ``str`` return type for MyPy.
        msg: str = str(obj.message)
        return msg[:60] + ("…" if len(msg) > 60 else "")


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


# ---------------------------------------------------------------------------
# Language Learning Admin
# ---------------------------------------------------------------------------


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin configuration for :class:`chat.models.UserProfile`."""

    list_display = ("user", "native_language", "daily_goal_minutes", "created_at")
    list_filter = ("native_language", "daily_goal_minutes")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(LanguageProfile)
class LanguageProfileAdmin(admin.ModelAdmin):
    """Admin configuration for :class:`chat.models.LanguageProfile`."""

    list_display = (
        "user",
        "target_language",
        "current_level",
        "proficiency_score",
        "total_messages",
        "is_active",
        "last_activity",
    )
    list_filter = ("target_language", "current_level", "is_active", "last_activity")
    search_fields = ("user__username", "user__email")
    readonly_fields = (
        "created_at",
        "updated_at",
        "proficiency_score",
        "confidence_level",
    )
    ordering = ("-last_activity",)

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user')


@admin.register(GrammarConcept)
class GrammarConceptAdmin(admin.ModelAdmin):
    """Admin configuration for :class:`chat.models.GrammarConcept`."""

    list_display = ("name", "language", "cefr_level", "complexity_score", "created_at")
    list_filter = ("language", "cefr_level", "complexity_score")
    search_fields = ("name", "description", "tags")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("prerequisite_concepts",)
    ordering = ("language", "cefr_level", "complexity_score")


@admin.register(ConceptMastery)
class ConceptMasteryAdmin(admin.ModelAdmin):
    """Admin configuration for :class:`chat.models.ConceptMastery`."""

    list_display = (
        "user",
        "concept",
        "mastery_score",
        "success_rate_display",
        "last_practiced",
        "needs_review_display",
    )
    list_filter = (
        "concept__language",
        "concept__cefr_level",
        "mastery_score",
        "last_practiced",
    )
    search_fields = ("user__username", "concept__name", "concept__description")
    readonly_fields = (
        "created_at",
        "updated_at",
        "success_rate_display",
        "needs_review_display",
    )
    ordering = ("-mastery_score", "-last_practiced")

    @staticmethod
    def success_rate_display(obj: "ConceptMastery") -> str:
        """Display success rate as percentage."""
        return f"{obj.get_success_rate():.1f}%"

    success_rate_display.short_description = "Success Rate"

    @staticmethod
    def needs_review_display(obj: "ConceptMastery") -> str:
        """Display whether concept needs review."""
        return "Yes" if obj.needs_review() else "No"

    needs_review_display.short_description = "Needs Review"


@admin.register(ErrorPattern)
class ErrorPatternAdmin(admin.ModelAdmin):
    """Admin configuration for :class:`chat.models.ErrorPattern`."""

    list_display = (
        "user",
        "error_type",
        "frequency",
        "is_persistent_display",
        "is_resolved",
        "last_seen",
    )
    list_filter = ("error_type", "is_resolved", "frequency", "last_seen")
    search_fields = ("user__username", "error_description", "example_errors")
    readonly_fields = ("first_seen", "last_seen")
    filter_horizontal = ("related_concepts",)
    ordering = ("-frequency", "-last_seen")

    @staticmethod
    def is_persistent_display(obj: "ErrorPattern") -> str:
        """Display whether error is persistent."""
        return "Yes" if obj.is_persistent() else "No"

    is_persistent_display.short_description = "Persistent"
