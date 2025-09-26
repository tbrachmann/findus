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
