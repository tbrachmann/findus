"""Database models for the Chat application.

Contains the Conversation and ChatMessage ORM models used by the *findus*
project, plus language learning models for proficiency tracking.
"""

# ---------------------------------------------------------------------------
# Django
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
from typing import List
from .fields import VectorField, VectorManager


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


# ---------------------------------------------------------------------------
# Language Learning Models
# ---------------------------------------------------------------------------


class UserProfile(models.Model):
    """
    General user profile with account-wide preferences.

    Stores user-wide settings and preferences that apply across all languages.
    Individual language progress is tracked in LanguageProfile.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        help_text="Associated user account",
    )
    native_language = models.CharField(
        max_length=2,
        choices=Conversation.LANGUAGE_CHOICES,
        default='en',
        help_text="User's native language",
    )
    timezone = models.CharField(
        max_length=50, default='UTC', help_text="User's timezone for scheduling"
    )
    daily_goal_minutes = models.IntegerField(
        default=15, help_text="Daily practice goal in minutes"
    )
    preferences = models.JSONField(
        default=dict, help_text="User preferences and settings"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self) -> str:
        return f"{self.user.username} Profile"


class LanguageProfile(models.Model):
    """
    Language-specific learning profile for tracking progress per language.

    Each user can have multiple LanguageProfiles - one for each language
    they are learning. Tracks proficiency, progress, and learning statistics
    for a specific target language.
    """

    CEFR_LEVELS = [
        ('A1', 'A1 - Beginner'),
        ('A2', 'A2 - Elementary'),
        ('B1', 'B1 - Intermediate'),
        ('B2', 'B2 - Upper-Intermediate'),
        ('C1', 'C1 - Advanced'),
        ('C2', 'C2 - Proficient'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="language_profiles",
        help_text="User learning this language",
    )
    target_language = models.CharField(
        max_length=2,
        choices=Conversation.LANGUAGE_CHOICES,
        help_text="Language being learned",
    )
    current_level = models.CharField(
        max_length=2,
        choices=CEFR_LEVELS,
        default='A1',
        help_text="Current estimated CEFR level",
    )
    total_messages = models.IntegerField(
        default=0, help_text="Total messages sent in this language"
    )
    total_practice_time = models.IntegerField(
        default=0, help_text="Total practice time in minutes"
    )
    study_streak_days = models.IntegerField(
        default=0, help_text="Current consecutive days of practice"
    )
    longest_streak = models.IntegerField(
        default=0, help_text="Longest study streak achieved"
    )
    last_activity = models.DateTimeField(
        null=True, blank=True, help_text="Last time user practiced this language"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether user is actively learning this language"
    )
    proficiency_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Overall proficiency score (0.0-1.0)",
    )
    confidence_level = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence in proficiency assessment",
    )
    vocabulary_size = models.IntegerField(
        default=0, help_text="Estimated vocabulary size"
    )
    grammar_accuracy = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Grammar accuracy score",
    )
    fluency_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Fluency assessment score",
    )
    weak_areas = models.JSONField(
        default=list, help_text="List of grammar areas needing improvement"
    )
    strong_areas = models.JSONField(
        default=list, help_text="List of grammar areas showing strength"
    )
    learning_goals = models.JSONField(
        default=list, help_text="User's learning goals for this language"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Language Profile"
        verbose_name_plural = "Language Profiles"
        unique_together = ['user', 'target_language']
        indexes = [
            models.Index(fields=['user', 'target_language']),
            models.Index(fields=['current_level']),
            models.Index(fields=['last_activity']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self) -> str:
        return (
            f"{self.user.username} - {self.get_target_language_display()} "
            f"({self.get_current_level_display()})"
        )

    def update_streak(self) -> None:
        """Update study streak based on last activity."""
        if not self.last_activity:
            self.study_streak_days = 1
            self.longest_streak = max(self.longest_streak, 1)
            return

        today = timezone.now().date()
        last_activity_date = self.last_activity.date()

        if last_activity_date == today:
            return  # Already updated today
        elif last_activity_date == today - timedelta(days=1):
            self.study_streak_days += 1
            self.longest_streak = max(self.longest_streak, self.study_streak_days)
        else:
            self.study_streak_days = 1 if last_activity_date == today else 0

    def get_proficiency_score(self) -> float:
        """Calculate overall proficiency score (0.0-1.0) based on CEFR level."""
        level_scores = {
            'A1': 0.1,
            'A2': 0.25,
            'B1': 0.45,
            'B2': 0.65,
            'C1': 0.8,
            'C2': 0.95,
        }
        return level_scores.get(self.current_level, 0.1)

    def update_proficiency_metrics(self) -> None:
        """Update proficiency metrics based on recent performance."""
        # Calculate grammar accuracy from recent concept masteries
        recent_masteries = self.user.concept_masteries.filter(
            concept__language=self.target_language,
            last_practiced__gte=timezone.now() - timedelta(days=30),
        )

        if recent_masteries.exists():
            self.grammar_accuracy = (
                recent_masteries.aggregate(avg_mastery=models.Avg('mastery_score'))[
                    'avg_mastery'
                ]
                or 0.0
            )

            # Update overall proficiency score based on multiple factors
            base_score = self.get_proficiency_score()
            grammar_bonus = (self.grammar_accuracy - 0.5) * 0.2  # Up to ±20% adjustment
            self.proficiency_score = max(0.0, min(1.0, base_score + grammar_bonus))

    def get_next_level(self) -> str:
        """Get the next CEFR level to progress to."""
        level_progression = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        try:
            current_index = level_progression.index(self.current_level)
            if current_index < len(level_progression) - 1:
                return level_progression[current_index + 1]
        except ValueError:
            pass
        return self.current_level  # Already at highest level or invalid level

    def is_ready_for_next_level(self, threshold: float = 0.8) -> bool:
        """Check if user is ready to progress to next CEFR level."""
        if self.current_level == 'C2':
            return False  # Already at highest level

        # Check if proficiency score meets threshold
        if self.proficiency_score < threshold:
            return False

        # Check if key concepts for current level are mastered
        current_level_concepts = GrammarConcept.objects.filter(
            language=self.target_language, cefr_level=self.current_level
        )

        mastered_concepts = 0
        total_concepts = current_level_concepts.count()

        if total_concepts == 0:
            return True  # No concepts defined for this level

        for concept in current_level_concepts:
            mastery = self.user.concept_masteries.filter(concept=concept).first()
            if mastery and mastery.is_mastered():
                mastered_concepts += 1

        mastery_percentage = mastered_concepts / total_concepts
        return mastery_percentage >= threshold

    def get_personalized_concepts_for_practice(
        self, limit: int = 5
    ) -> List['GrammarConcept']:
        """
        Get personalized concept recommendations using vector similarity and mastery data.

        Prioritizes:
        1. Concepts due for spaced repetition review
        2. Similar concepts to ones the user struggles with
        3. Prerequisites to concepts the user wants to learn
        """
        # ConceptMastery will be used via related manager

        recommendations = []

        # 1. Get concepts due for review
        due_masteries = self.user.concept_masteries.filter(
            concept__language=self.target_language, next_review__lte=timezone.now()
        ).order_by('next_review')[:3]

        review_concepts = [mastery.concept for mastery in due_masteries]
        recommendations.extend(review_concepts)

        # 2. Find similar concepts to ones user struggles with (low mastery score)
        struggling_masteries = self.user.concept_masteries.filter(
            concept__language=self.target_language,
            mastery_score__lt=0.6,
            attempts_count__gte=3,
        ).order_by('mastery_score')[:2]

        for mastery in struggling_masteries:
            if mastery.concept.embedding:
                similar_concepts = mastery.concept.find_similar_concepts(
                    limit=2, threshold=0.6
                ).filter(cefr_level__in=[self.current_level, self.get_previous_level()])
                recommendations.extend(similar_concepts)

        # 3. Get next level concepts the user might be ready for
        next_level = self.get_next_level()
        if next_level != self.current_level:
            next_level_concepts = GrammarConcept.objects.filter(
                language=self.target_language, cefr_level=next_level
            ).exclude(id__in=[concept.id for concept in recommendations])[:2]

            recommendations.extend(next_level_concepts)

        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for concept in recommendations:
            if concept.id not in seen:
                seen.add(concept.id)
                unique_recommendations.append(concept)

        return unique_recommendations[:limit]

    def get_previous_level(self) -> str:
        """Get the previous CEFR level."""
        level_progression = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        try:
            current_index = level_progression.index(self.current_level)
            if current_index > 0:
                return level_progression[current_index - 1]
        except ValueError:
            pass
        return 'A1'  # Default to A1 if invalid level


class GrammarConcept(models.Model):
    """
    Represents a grammar concept that can be tracked and practiced.

    Each concept has an embedding vector for similarity searches and
    metadata about its difficulty level and prerequisites.
    """

    name = models.CharField(
        max_length=200, help_text="Human-readable name of the grammar concept"
    )
    description = models.TextField(
        help_text="Detailed description of the grammar concept"
    )
    language = models.CharField(
        max_length=2,
        choices=Conversation.LANGUAGE_CHOICES,
        help_text="Language this concept applies to",
    )
    cefr_level = models.CharField(
        max_length=2,
        choices=LanguageProfile.CEFR_LEVELS,
        help_text="CEFR level where this concept is typically learned",
    )
    complexity_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)],
        help_text="Complexity rating from 0 (simple) to 10 (complex)",
    )
    embedding = VectorField(
        dimensions=768,
        null=True,
        blank=True,
        help_text="Vector embedding for similarity searches",
    )
    prerequisite_concepts = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='dependent_concepts',
        help_text="Concepts that should be learned before this one",
    )
    tags = models.JSONField(
        default=list,
        help_text="Tags for categorizing concepts (e.g., ['verbs', 'tenses'])",
    )
    example_sentences = models.JSONField(
        default=list, help_text="Example sentences demonstrating the concept"
    )
    common_errors = models.JSONField(
        default=list, help_text="Common mistakes learners make with this concept"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = VectorManager()

    class Meta:
        verbose_name = "Grammar Concept"
        verbose_name_plural = "Grammar Concepts"
        unique_together = ['name', 'language']
        indexes = [
            models.Index(fields=['language', 'cefr_level']),
            models.Index(fields=['complexity_score']),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_cefr_level_display()}) - {self.get_language_display()}"

    def get_embedding_vector(self) -> List[float] | None:
        """Get the embedding vector as a list of floats."""
        return self.embedding if self.embedding else None

    def set_embedding_vector(self, vector: List[float]) -> None:
        """Set the embedding vector from a list of floats."""
        self.embedding = vector

    def find_similar_concepts(
        self, limit: int = 5, threshold: float = 0.5
    ) -> models.QuerySet['GrammarConcept']:
        """Find similar concepts using vector similarity."""
        if not self.embedding:
            return GrammarConcept.objects.none()

        # Get similarity results and exclude self, then limit
        similar_queryset = GrammarConcept.objects.extra(
            select={'similarity': '1 - (embedding <=> %s)'},
            select_params=['[' + ','.join(str(float(x)) for x in self.embedding) + ']'],
            where=['1 - (embedding <=> %s) >= %s'],
            params=[
                '[' + ','.join(str(float(x)) for x in self.embedding) + ']',
                threshold,
            ],
            order_by=['-similarity'],
        ).exclude(id=self.id)[:limit]

        return similar_queryset

    def find_prerequisites_by_similarity(
        self, threshold: float = 0.7
    ) -> models.QuerySet['GrammarConcept']:
        """Find potential prerequisite concepts using vector similarity and CEFR levels."""
        if not self.embedding:
            return GrammarConcept.objects.none()

        # Find similar concepts at lower CEFR levels
        cefr_order = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        current_index = (
            cefr_order.index(self.cefr_level) if self.cefr_level in cefr_order else 0
        )
        lower_levels = cefr_order[:current_index]

        if not lower_levels:
            return GrammarConcept.objects.none()

        return (
            GrammarConcept.objects.filter(
                language=self.language, cefr_level__in=lower_levels
            )
            .exclude(id=self.id)
            .extra(
                select={'similarity': '1 - (embedding <=> %s)'},
                select_params=[
                    '[' + ','.join(str(float(x)) for x in self.embedding) + ']'
                ],
                where=['1 - (embedding <=> %s) >= %s'],
                params=[
                    '[' + ','.join(str(float(x)) for x in self.embedding) + ']',
                    threshold,
                ],
                order_by=['-similarity'],
            )[:10]
        )

    def find_learning_path(self, limit: int = 5) -> List['GrammarConcept']:
        """Find a suggested learning path based on concept similarity and CEFR progression."""
        if not self.embedding:
            return []

        # Find next level concepts that are similar
        cefr_order = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        current_index = (
            cefr_order.index(self.cefr_level) if self.cefr_level in cefr_order else 0
        )

        learning_path = []

        # Look for similar concepts at the same level first
        same_level_base = (
            GrammarConcept.objects.filter(
                language=self.language, cefr_level=self.cefr_level
            )
            .exclude(id=self.id)
            .extra(
                select={'similarity': '1 - (embedding <=> %s)'},
                select_params=[
                    '[' + ','.join(str(float(x)) for x in self.embedding) + ']'
                ],
                where=['1 - (embedding <=> %s) >= %s'],
                params=[
                    '[' + ','.join(str(float(x)) for x in self.embedding) + ']',
                    0.6,
                ],
                order_by=['-similarity'],
            )[:2]
        )

        same_level = list(same_level_base)

        learning_path.extend(same_level)

        # Then look at next levels
        next_levels = cefr_order[current_index + 1 : current_index + 3]  # Next 2 levels
        if next_levels:
            next_concepts_base = (
                GrammarConcept.objects.filter(
                    language=self.language, cefr_level__in=next_levels
                )
                .exclude(id=self.id)
                .extra(
                    select={'similarity': '1 - (embedding <=> %s)'},
                    select_params=[
                        '[' + ','.join(str(float(x)) for x in self.embedding) + ']'
                    ],
                    where=['1 - (embedding <=> %s) >= %s'],
                    params=[
                        '[' + ','.join(str(float(x)) for x in self.embedding) + ']',
                        0.5,
                    ],
                    order_by=['-similarity'],
                )[:3]
            )

            next_concepts = list(next_concepts_base)
            learning_path.extend(next_concepts)

        return learning_path[:limit]


class ConceptMastery(models.Model):
    """
    Tracks a user's mastery level for specific grammar concepts.

    Implements spaced repetition scheduling and tracks performance
    over time for adaptive learning.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="concept_masteries",
        help_text="User learning this concept",
    )
    concept = models.ForeignKey(
        GrammarConcept,
        on_delete=models.CASCADE,
        related_name="user_masteries",
        help_text="Grammar concept being tracked",
    )
    mastery_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.0,
        help_text="Current mastery level (0.0 = not learned, 1.0 = mastered)",
    )
    confidence_level = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.0,
        help_text="Confidence in the mastery assessment",
    )
    attempts_count = models.IntegerField(
        default=0, help_text="Total number of practice attempts"
    )
    correct_attempts = models.IntegerField(
        default=0, help_text="Number of correct attempts"
    )
    last_practiced = models.DateTimeField(
        null=True, blank=True, help_text="Last time this concept was practiced"
    )
    last_seen_correct = models.DateTimeField(
        null=True, blank=True, help_text="Last time user got this concept correct"
    )
    next_review = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this concept should be reviewed next (spaced repetition)",
    )
    repetition_interval = models.IntegerField(
        default=1, help_text="Current spaced repetition interval in days"
    )
    ease_factor = models.FloatField(
        default=2.5,
        validators=[MinValueValidator(1.0), MaxValueValidator(4.0)],
        help_text="Ease factor for spaced repetition algorithm",
    )
    performance_history = models.JSONField(
        default=list, help_text="History of performance scores over time"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Concept Mastery"
        verbose_name_plural = "Concept Masteries"
        unique_together = ['user', 'concept']
        indexes = [
            models.Index(fields=['user', 'mastery_score']),
            models.Index(fields=['next_review']),
            models.Index(fields=['last_practiced']),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.concept.name} ({self.mastery_score:.2f})"

    def get_success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.attempts_count == 0:
            return 0.0
        return (self.correct_attempts / self.attempts_count) * 100

    def update_performance(self, is_correct: bool, difficulty: float = 1.0) -> None:
        """
        Update performance metrics and spaced repetition scheduling.

        Args:
            is_correct: Whether the user got the concept correct
            difficulty: Difficulty rating of the attempt (0.0-1.0)
        """
        now = timezone.now()
        self.attempts_count += 1
        self.last_practiced = now

        if is_correct:
            self.correct_attempts += 1
            self.last_seen_correct = now

            # Update ease factor based on performance
            if difficulty < 0.3:  # Easy
                self.ease_factor = min(4.0, self.ease_factor + 0.1)
            elif difficulty > 0.7:  # Hard
                self.ease_factor = max(1.3, self.ease_factor - 0.15)

            # Increase interval for spaced repetition
            if self.repetition_interval == 1:
                self.repetition_interval = 6
            else:
                self.repetition_interval = int(
                    self.repetition_interval * self.ease_factor
                )
        else:
            # Reset interval on failure
            self.repetition_interval = 1
            self.ease_factor = max(1.3, self.ease_factor - 0.2)

        # Update mastery score
        success_rate = self.get_success_rate()
        recency_factor = min(1.0, self.attempts_count / 10.0)  # Cap at 10 attempts
        self.mastery_score = (success_rate / 100.0) * recency_factor

        # Schedule next review
        self.next_review = now + timedelta(days=self.repetition_interval)

        # Update performance history
        performance_entry = {
            'timestamp': now.isoformat(),
            'correct': is_correct,
            'difficulty': difficulty,
            'mastery_score': self.mastery_score,
            'success_rate': success_rate,
        }
        self.performance_history.append(performance_entry)

        # Keep only last 100 entries
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-100:]

    def needs_review(self) -> bool:
        """Check if this concept is due for review."""
        if not self.next_review:
            return True
        return timezone.now() >= self.next_review

    def is_mastered(self, threshold: float = 0.8) -> bool:
        """Check if concept is considered mastered."""
        return self.mastery_score >= threshold and self.attempts_count >= 5


class ErrorPattern(models.Model):
    """
    Tracks recurring error patterns for individual users.

    Helps identify systematic issues in language learning
    and provides targeted practice opportunities.
    """

    ERROR_CATEGORIES = [
        ('grammar', 'Grammar'),
        ('spelling', 'Spelling'),
        ('vocabulary', 'Vocabulary'),
        ('syntax', 'Syntax'),
        ('punctuation', 'Punctuation'),
        ('word_order', 'Word Order'),
        ('verb_tense', 'Verb Tense'),
        ('articles', 'Articles'),
        ('prepositions', 'Prepositions'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="error_patterns",
        help_text="User who made these errors",
    )
    error_type = models.CharField(
        max_length=20, choices=ERROR_CATEGORIES, help_text="Category of error"
    )
    error_description = models.TextField(
        help_text="Description of the specific error pattern"
    )
    related_concepts = models.ManyToManyField(
        GrammarConcept,
        blank=True,
        related_name="related_errors",
        help_text="Grammar concepts related to this error",
    )
    frequency = models.IntegerField(
        default=1, help_text="How many times this error has occurred"
    )
    first_seen = models.DateTimeField(
        auto_now_add=True, help_text="When this error pattern was first identified"
    )
    last_seen = models.DateTimeField(
        auto_now=True, help_text="When this error was last observed"
    )
    is_resolved = models.BooleanField(
        default=False, help_text="Whether this error pattern has been resolved"
    )
    example_errors = models.JSONField(
        default=list, help_text="Example sentences where this error occurred"
    )
    correction_suggestions = models.JSONField(
        default=list, help_text="Suggested corrections and explanations"
    )

    class Meta:
        verbose_name = "Error Pattern"
        verbose_name_plural = "Error Patterns"
        indexes = [
            models.Index(fields=['user', 'error_type']),
            models.Index(fields=['frequency']),
            models.Index(fields=['last_seen']),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.get_error_type_display()} ({self.frequency}x)"

    def add_occurrence(self, example: str, correction: str | None = None) -> None:
        """Add a new occurrence of this error pattern."""
        self.frequency += 1
        self.last_seen = timezone.now()

        # Add example if not already present
        if example not in self.example_errors:
            self.example_errors.append(example)

            # Keep only last 10 examples
            if len(self.example_errors) > 10:
                self.example_errors = self.example_errors[-10:]

        # Add correction if provided
        if correction and correction not in self.correction_suggestions:
            self.correction_suggestions.append(correction)

            # Keep only last 5 corrections
            if len(self.correction_suggestions) > 5:
                self.correction_suggestions = self.correction_suggestions[-5:]

    def is_recent(self, days: int = 7) -> bool:
        """Check if error was seen recently."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.last_seen >= cutoff

    def is_persistent(self, threshold: int = 3) -> bool:
        """Check if error occurs frequently enough to be considered persistent."""
        return self.frequency >= threshold and not self.is_resolved
