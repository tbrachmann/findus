"""
chat/models.py

Database models for the Chat application.
"""

# ---------------------------------------------------------------------------
# Django
from django.db import models


class Conversation(models.Model):
    """
    Represents a single chat thread that groups many ChatMessage rows.
    """

    title = models.CharField(
        max_length=255,
        default="New Conversation",
        help_text="Conversation title (can be renamed later).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"

    def __str__(self) -> str:  # noqa: D401
        friendly_date: str = self.created_at.strftime("%Y-%m-%d %H:%M")
        # Explicit str(...) casts silence static-type checkers complaining
        # about the Django model fields being `Any`.
        return f"{str(self.title)} ({friendly_date})"


class ChatMessage(models.Model):
    """
    Stores a single chat interaction consisting of:
      • message  – the raw user prompt
      • response – Gemini’s answer
      • created_at – timestamp when interaction was stored
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
        # Group by conversation, then chronological order within each.
        ordering = ["conversation_id", "created_at"]
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"

    # Display first 50 characters of the user message for admin/list view
    def __str__(self) -> str:  # noqa: D401  (simple-return)
        msg: str = str(self.message)
        return msg[:50] + ("…" if len(msg) > 50 else "")
