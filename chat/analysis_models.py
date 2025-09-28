"""
Pydantic models for structured grammar analysis and language learning feedback.

These models define the structured output format for LLM-based grammar analysis,
ensuring consistent and parseable feedback for the language learning system.
"""

from pydantic import BaseModel, Field
from typing import List
from enum import Enum


class CEFRLevel(str, Enum):
    """CEFR proficiency levels."""

    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class ErrorSeverity(str, Enum):
    """Severity levels for grammatical errors."""

    MINOR = "minor"  # Doesn't affect comprehension
    MODERATE = "moderate"  # May cause confusion
    SEVERE = "severe"  # Significantly impacts comprehension


class ConceptUsage(BaseModel):
    """Analysis of how well a specific grammar concept was used."""

    concept_name: str = Field(
        ..., description="Title of the grammar concept (e.g., 'Present Perfect Tense')"
    )
    concept_description: str = Field(
        ..., description="Brief description of what this concept involves"
    )
    attempted: bool = Field(..., description="Whether the user attempted this concept")
    correct: bool = Field(..., description="Whether the usage was correct")
    user_rating: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="User's proficiency rating for this concept (0-1)",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in assessment (0-1)"
    )
    examples: List[str] = Field(
        default=[], description="Examples of usage from the text"
    )
    errors: List[str] = Field(default=[], description="Specific errors found")
    feedback: str = Field(..., description="Constructive feedback for this concept")


class GrammarError(BaseModel):
    """Detailed information about a specific grammatical error."""

    error_type: str = Field(
        ..., description="Category of error (e.g., 'verb_tense', 'article')"
    )
    severity: ErrorSeverity = Field(..., description="How serious this error is")
    original_text: str = Field(..., description="The incorrect text")
    corrected_text: str = Field(..., description="The corrected version")
    explanation: str = Field(..., description="Why this is incorrect and how to fix it")
    related_concepts: List[str] = Field(
        default=[], description="Grammar concepts related to this error"
    )
    cefr_level: CEFRLevel = Field(
        ..., description="CEFR level where this concept is taught"
    )


class ProficiencyAssessment(BaseModel):
    """Overall proficiency assessment for the analyzed text."""

    estimated_level: CEFRLevel = Field(
        ..., description="Estimated CEFR level based on this text"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in level assessment"
    )
    vocabulary_level: CEFRLevel = Field(..., description="Vocabulary complexity level")
    grammar_level: CEFRLevel = Field(..., description="Grammar complexity level")
    fluency_score: float = Field(
        ..., ge=0.0, le=1.0, description="Text fluency/naturalness score"
    )
    coherence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Logical flow and coherence"
    )


class StructuredGrammarAnalysis(BaseModel):
    """Comprehensive structured analysis of text for language learning."""

    # Overall assessment
    proficiency: ProficiencyAssessment = Field(
        ..., description="Overall proficiency assessment"
    )

    # Concept analysis
    concepts_used: List[ConceptUsage] = Field(
        ..., description="Analysis of grammar concepts attempted"
    )

    # Error analysis
    errors: List[GrammarError] = Field(
        default=[], description="Detailed grammatical errors found"
    )
    total_errors: int = Field(..., description="Total number of errors found")
    error_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Error rate as percentage of total words"
    )
    accuracy_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall accuracy score (1 - error_rate)"
    )

    # Strengths and weaknesses
    strengths: List[str] = Field(..., description="Areas where user performed well")
    weaknesses: List[str] = Field(..., description="Areas needing improvement")
    next_concepts: List[str] = Field(
        ..., description="Recommended concepts to learn next"
    )
    practice_suggestions: List[str] = Field(
        ..., description="Specific practice recommendations"
    )

    # Metadata
    analysis_language: str = Field(..., description="Language used for feedback")
    target_language: str = Field(..., description="Language being learned")
    text_length: int = Field(..., description="Length of analyzed text")
    word_count: int = Field(..., description="Number of words analyzed")

    async def update_user_proficiency(self, user, language_code: str) -> None:
        """
        Update user's proficiency metrics and concept masteries based on this analysis.

        Args:
            user: User to update
            language_code: Target language
        """
        from .models import (
            LanguageProfile,
            ConceptMastery,
            GrammarConcept,
            ErrorPattern,
        )
        from django.utils import timezone

        # Get or create language profile
        language_profile, created = await LanguageProfile.objects.aget_or_create(
            user=user,
            target_language=language_code,
            defaults={
                'current_level': self.proficiency.estimated_level.value,
                'proficiency_score': self.accuracy_score,
                'grammar_accuracy': self.accuracy_score,
                'fluency_score': self.proficiency.fluency_score,
            },
        )

        if not created:
            # Update existing profile with weighted average
            language_profile.grammar_accuracy = (
                language_profile.grammar_accuracy * 0.8 + self.accuracy_score * 0.2
            )
            language_profile.fluency_score = (
                language_profile.fluency_score * 0.8
                + self.proficiency.fluency_score * 0.2
            )

            # Update proficiency score
            language_profile.proficiency_score = (
                language_profile.grammar_accuracy * 0.6
                + language_profile.fluency_score * 0.4
            )
        else:
            # For new profiles, set initial values (defaults were already set in aget_or_create)
            # Just need to calculate proficiency score
            language_profile.proficiency_score = (
                language_profile.grammar_accuracy * 0.6
                + language_profile.fluency_score * 0.4
            )

        # Update weak/strong areas for both new and existing profiles
        language_profile.weak_areas = list(
            set(language_profile.weak_areas + self.weaknesses)
        )[
            :10
        ]  # Keep only top 10

        language_profile.strong_areas = list(
            set(language_profile.strong_areas + self.strengths)
        )[
            :10
        ]  # Keep only top 10

        await language_profile.asave()

        # Update concept masteries
        for concept_usage in self.concepts_used:
            await self._update_concept_mastery(user, concept_usage, language_code)

        # Create error patterns for persistent errors
        for error in self.errors:
            await self._create_or_update_error_pattern(user, error)

    async def _update_concept_mastery(
        self, user, concept_usage: ConceptUsage, language_code: str
    ) -> None:
        """Update or create concept mastery based on usage analysis."""
        from .models import GrammarConcept, ConceptMastery
        from django.utils import timezone

        # Find or create the grammar concept
        concept, _ = await GrammarConcept.objects.aget_or_create(
            name=concept_usage.concept_name,
            language=language_code,
            defaults={
                'description': concept_usage.concept_description,
                'complexity_score': 5.0,  # Default complexity
                'cefr_level': 'A2',  # Default level
            },
        )

        # Get or create concept mastery
        mastery, _ = await ConceptMastery.objects.aget_or_create(
            user=user, concept=concept
        )

        # Determine if this attempt was correct
        is_correct = concept_usage.attempted and concept_usage.correct

        # Calculate difficulty based on concept complexity and user rating
        difficulty = 1.0 - concept_usage.user_rating

        # Update mastery using the existing performance update method
        mastery.update_performance(is_correct, difficulty)
        await mastery.asave()

    async def _create_or_update_error_pattern(self, user, error: GrammarError) -> None:
        """Create or update error pattern based on grammar error."""
        from .models import ErrorPattern

        # Try to find existing error pattern
        existing_pattern = await ErrorPattern.objects.filter(
            user=user,
            error_type=error.error_type,
            error_description__icontains=error.explanation[:50],  # Match similar errors
        ).afirst()

        if existing_pattern:
            # Update existing pattern
            existing_pattern.add_occurrence(error.original_text, error.corrected_text)
            await existing_pattern.asave()
        else:
            # Create new error pattern
            await ErrorPattern.objects.acreate(
                user=user,
                error_type=error.error_type,
                error_description=error.explanation,
                example_errors=[error.original_text],
                correction_suggestions=[error.corrected_text],
            )


class ConceptMasteryUpdate(BaseModel):
    """Data for updating a user's concept mastery based on performance."""

    concept_name: str = Field(..., description="Name of the grammar concept")
    attempted: bool = Field(..., description="Whether this concept was attempted")
    correct: bool = Field(..., description="Whether the usage was correct")
    difficulty: float = Field(
        ..., ge=0.0, le=1.0, description="Difficulty level of this usage"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the assessment"
    )
    examples: List[str] = Field(default=[], description="Examples from the user's text")


class LearningRecommendations(BaseModel):
    """Personalized learning recommendations based on user's performance."""

    priority_concepts: List[str] = Field(
        ..., description="High-priority concepts to practice"
    )
    review_concepts: List[str] = Field(
        ..., description="Previously learned concepts to review"
    )
    target_level: CEFRLevel = Field(
        ..., description="Recommended target level for next practice"
    )
    difficulty_adjustment: float = Field(
        ..., ge=-1.0, le=1.0, description="Suggested difficulty change"
    )

    # Spaced repetition data
    concepts_for_review: List[str] = Field(
        ..., description="Concepts due for spaced repetition"
    )
    new_concepts: List[str] = Field(..., description="New concepts ready to introduce")

    # Personalized content suggestions
    conversation_topics: List[str] = Field(
        ..., description="Suggested conversation topics"
    )
    practice_exercises: List[str] = Field(
        ..., description="Recommended practice activities"
    )

    # Progress tracking
    estimated_time_to_next_level: int = Field(
        ..., ge=0, description="Estimated days to next CEFR level"
    )
    confidence_in_progression: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in timeline estimate"
    )


class AdaptivePrompt(BaseModel):
    """Data structure for generating adaptive conversation prompts."""

    prompt_text: str = Field(..., description="The conversation prompt to present")
    target_concepts: List[str] = Field(
        ..., description="Grammar concepts this prompt targets"
    )
    difficulty_level: CEFRLevel = Field(..., description="CEFR level of this prompt")
    context: str = Field(..., description="Context or situation for the conversation")

    # Learning objectives
    primary_objective: str = Field(
        ..., description="Main learning goal for this prompt"
    )
    secondary_objectives: List[str] = Field(
        ..., description="Additional skills being practiced"
    )

    # Adaptive elements
    scaffolding_hints: List[str] = Field(
        default=[], description="Optional hints if user struggles"
    )
    extension_questions: List[str] = Field(
        default=[], description="Follow-up questions for advanced users"
    )

    # Spaced repetition integration
    review_concepts: List[str] = Field(
        default=[], description="Previously learned concepts being reviewed"
    )
    new_concepts: List[str] = Field(
        default=[], description="New concepts being introduced"
    )
