"""Database models for the Chat application.

Contains the Conversation and ChatMessage ORM models used by the *findus*
project.
"""

# ---------------------------------------------------------------------------
# Django
from django.db import models
from django.contrib.auth.models import User


class Conversation(models.Model):
    """Represents a single chat thread that groups many ChatMessage rows."""

    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('es', 'Spanish'),
        ('de', 'German'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="conversations",
        help_text="Owner of this conversation",
    )
    title = models.CharField(
        max_length=255,
        default="New Conversation",
        help_text="Conversation title (can be renamed later).",
    )
    language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default='en',
        help_text="Language for this conversation",
    )
    analysis_language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default='en',
        help_text="Language for grammar analysis feedback",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Django model metadata."""

        ordering = ["-updated_at"]
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"

    def __str__(self) -> str:
        """Return a human-readable representation for admin & debugging."""
        friendly_date: str = self.created_at.strftime("%Y-%m-%d %H:%M")
        # Explicit str(...) casts silence static-type checkers complaining
        # about the Django model fields being `Any`.
        username: str = str(self.user.username)
        return f"{str(self.title)} – {username} ({friendly_date})"


class ChatMessage(models.Model):
    """
    Stores a single chat interaction.

    Details:
      • ``message``  – the raw user prompt
      • ``response`` – Gemini's answer
      • ``created_at`` – timestamp when interaction was stored
    """

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        help_text="Conversation this message belongs to",
    )
    message = models.TextField(help_text="Raw user prompt")
    response = models.TextField(help_text="Gemini response")
    # Added in v2: grammar/spelling analysis returned asynchronously
    grammar_analysis = models.TextField(
        help_text="Grammar and spelling analysis from Gemini",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Django model metadata."""

        # Group by conversation, then chronological order within each.
        ordering = ["conversation_id", "created_at"]
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"

    # Display first 50 characters of the user message for admin/list view
    def __str__(self) -> str:
        """Return a truncated preview of the user prompt."""
        msg: str = str(self.message)
        return msg[:50] + ("…" if len(msg) > 50 else "")


class AfterActionReport(models.Model):
    """
    Stores an AI-generated after-action report for a completed conversation.

    These reports analyze the user's language patterns across an entire conversation,
    identifying recurring grammar/spelling issues, highlighting strengths, and
    providing concrete recommendations for improvement.

    Each report is linked to a specific conversation and is generated when the
    user clicks the "End Conversation" button.
    """

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="reports",
        help_text="Conversation this report analyzes",
    )
    analysis_content = models.TextField(
        help_text="AI-generated analysis of language patterns and recommendations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Django model metadata."""

        ordering = ["-created_at"]
        verbose_name = "After-Action Report"
        verbose_name_plural = "After-Action Reports"

    def __str__(self) -> str:
        """Return the conversation title and date of the report."""
        friendly_date: str = self.created_at.strftime("%Y-%m-%d %H:%M")
        # Explicit str(...) cast for static type checking
        conversation_title: str = str(self.conversation.title)
        return f"Report for {conversation_title} ({friendly_date})"
