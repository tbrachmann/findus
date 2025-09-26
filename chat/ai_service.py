"""
AI service module using Pydantic AI with Logfire integration.

This module provides LLM interactions using Pydantic AI instead of direct
Gemini API calls, with automatic logging to Logfire for observability.
"""

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models.google import GoogleModel
from typing import Dict, List, Optional, Any
from django.contrib.auth.models import User

from .analysis_models import (
    StructuredGrammarAnalysis,
    AdaptivePrompt,
    CEFRLevel,
    ErrorSeverity,
)
from .models import GrammarConcept, LanguageProfile, ConceptMastery, ErrorPattern


class AIService:
    """Service class for LLM interactions with Pydantic AI and Logfire."""

    def __init__(self) -> None:
        """Initialize the AI service with Google Gemini model."""
        self.model = GoogleModel('gemini-2.5-flash-lite')

        # Agent for general chat responses
        self.chat_agent = Agent(
            model=self.model,
            system_prompt="You are a helpful AI assistant. Provide clear, concise responses.",
        )

    def _get_language_name(self, language_code: str) -> str:
        """Convert language code to language name."""
        language_map = {'en': 'English', 'es': 'Spanish', 'de': 'German'}
        return language_map.get(language_code, 'English')

    def _create_grammar_agent(
        self, language_code: str, grammar_analysis_language_code: str
    ) -> Agent:
        """Create a grammar analysis agent for the specified language."""
        language_name = self._get_language_name(language_code)
        grammar_analysis_language_name = self._get_language_name(
            grammar_analysis_language_code
        )

        system_prompt = (
            f"You are a {language_name} teacher analyzing text for grammatical errors "
            f"and spelling mistakes. Provide brief, helpful feedback in "
            f"{grammar_analysis_language_name}. If there are no issues, respond with "
            f"'No issues found' in {grammar_analysis_language_name}."
        )

        return Agent(model=self.model, system_prompt=system_prompt)

    def _create_analysis_agent(
        self, analysis_language_code: str, target_language_code: str
    ) -> Agent:
        """Create a conversation analysis agent for the specified languages."""
        analysis_language_name = self._get_language_name(analysis_language_code)
        target_language_name = self._get_language_name(target_language_code)

        system_prompt = (
            f"You are an experienced {target_language_name} teacher creating a short "
            f"after-action report for your student. Identify recurring "
            f"grammar/spelling issues, highlight strengths, and provide "
            f"3-5 concrete exercises or recommendations to improve. "
            f"Respond using markdown bullet-points (with * or -) in {analysis_language_name}."
        )

        return Agent(model=self.model, system_prompt=system_prompt)

    async def generate_chat_response(
        self,
        user_message: str,
        language_code: str = 'en',
        conversation_history: list[dict] | None = None,
    ) -> str:
        """
        Generate a chat response using Pydantic AI with conversation memory.

        Args:
            user_message: The user's input message
            language_code: Language code for the conversation (en, es, de)
            conversation_history: Previous messages in format
                [{'role': 'user', 'content': '...'}, ...]

        Returns:
            AI response text

        Raises:
            AgentRunError: If the AI model fails to respond
        """
        language_name = self._get_language_name(language_code)

        # Create a language-specific chat agent
        chat_agent = Agent(
            model=self.model,
            system_prompt=(
                f"You are a helpful AI assistant. Respond in {language_name}. "
                "Provide clear, concise responses."
            ),
        )

        # If we have conversation history, run with context
        if conversation_history:
            # Build message sequence for Pydantic AI
            from pydantic_ai.messages import (
                ModelRequest,
                ModelResponse,
                UserPromptPart,
                TextPart,
            )

            messages = []
            for msg in conversation_history:
                if msg['role'] == 'user':
                    messages.append(
                        ModelRequest(parts=[UserPromptPart(content=msg['content'])])
                    )
                elif msg['role'] == 'assistant':
                    messages.append(
                        ModelResponse(parts=[TextPart(content=msg['content'])])
                    )

            # Run with conversation history and current message
            result = await chat_agent.run(user_message, message_history=messages)
        else:
            # First message in conversation - no history
            result = await chat_agent.run(user_message)

        return str(result.output)

    async def analyze_grammar(
        self,
        text: str,
        grammar_analysis_language_code: str = 'en',
        language_code: str = 'en',
    ) -> str:
        """
        Analyze text for grammar and spelling issues.

        Args:
            text: The text to analyze
            language_code: Language code for the analysis (en, es, de)

        Returns:
            Grammar analysis feedback
        """
        try:
            grammar_agent = self._create_grammar_agent(
                language_code, grammar_analysis_language_code
            )
            result = await grammar_agent.run(f'Text: """\n{text}\n"""')
            return str(result.output)
        except AgentRunError as e:
            return f"Analysis failed: {e}"

    async def analyze_conversation(
        self,
        messages_data: list[dict],
        analysis_language_code: str = 'en',
        target_language_code: str = 'en',
    ) -> str:
        """
        Generate an after-action report for a conversation.

        Args:
            messages_data: List of dicts with 'message' and 'feedback' keys
            analysis_language_code: Language code for the analysis feedback (en, es, de)
            target_language_code: Language code of the conversation being analyzed (en, es, de)

        Returns:
            Conversation analysis text
        """
        try:
            # Build the analysis prompt
            prompt_parts = [
                "Below is the full conversation in pairs of user text followed by "
                "the grammar feedback they already received:\n\n"
            ]

            for msg_data in messages_data:
                feedback = msg_data.get('feedback') or "No feedback available."
                prompt_parts.append(
                    f"User: {msg_data['message']}\nFeedback: {feedback}\n---\n"
                )

            prompt = "".join(prompt_parts)

            analysis_agent = self._create_analysis_agent(
                analysis_language_code, target_language_code
            )
            result = await analysis_agent.run(prompt)
            return str(result.output)

        except AgentRunError as e:
            return f"⚠️ Failed to generate analysis: {e}"

    async def analyze_grammar_structured(
        self,
        text: str,
        user: User,
        language_code: str = 'en',
        analysis_language_code: str = 'en',
    ) -> StructuredGrammarAnalysis:
        """
        Perform structured grammar analysis with concept extraction and scoring.

        Args:
            text: The text to analyze
            user: The user whose proficiency we're assessing
            language_code: Target language being learned
            analysis_language_code: Language for feedback

        Returns:
            Structured analysis with concept scores, errors, and recommendations
        """
        # Get user's language profile for context
        language_profile = await LanguageProfile.objects.filter(
            user=user, target_language=language_code
        ).afirst()

        current_level = language_profile.current_level if language_profile else 'A1'

        # Create structured analysis agent
        analysis_agent = Agent(
            model=self.model,
            result_type=StructuredGrammarAnalysis,
            system_prompt=self._create_structured_analysis_prompt(
                language_code, analysis_language_code, current_level
            ),
        )

        # Run structured analysis
        result = await analysis_agent.run(
            f"Analyze this {self._get_language_name(language_code)} text: \"{text}\"\n\n"
            f"User's current level: {current_level}\n"
        )

        return result.output

    async def generate_adaptive_prompt(
        self,
        user: User,
        language_code: str,
        session_context: Optional[Dict[str, Any]] = None,
    ) -> AdaptivePrompt:
        """
        Generate an adaptive conversation prompt based on user's proficiency and needs.

        Args:
            user: The user to generate content for
            language_code: Target language
            session_context: Optional context from current conversation

        Returns:
            Adaptive prompt with targeted practice opportunities
        """
        # Get user's language profile and recent performance
        language_profile = await LanguageProfile.objects.filter(
            user=user, target_language=language_code
        ).afirst()

        if not language_profile:
            # Create basic profile for new users
            language_profile = LanguageProfile(
                user=user, target_language=language_code, current_level='A1'
            )

        # Get concepts that need review (spaced repetition)
        concepts_for_review = await self._get_concepts_for_review(user, language_code)

        # Get new concepts to introduce
        new_concepts = await self._get_new_concepts(
            user, language_code, language_profile.current_level
        )

        # Create adaptive prompt agent
        prompt_agent = Agent(
            model=self.model,
            result_type=AdaptivePrompt,
            system_prompt=self._create_adaptive_prompt_system_prompt(
                language_code, language_profile.current_level
            ),
        )

        # Build context for prompt generation
        context = {
            'current_level': language_profile.current_level,
            'weak_areas': language_profile.weak_areas,
            'strong_areas': language_profile.strong_areas,
            'learning_goals': language_profile.learning_goals,
            'review_concepts': [c.concept.name for c in concepts_for_review],
            'new_concepts': [c.name for c in new_concepts],
            'session_context': session_context or {},
        }

        result = await prompt_agent.run(
            f"Generate an adaptive conversation prompt for a {language_profile.current_level} "
            f"{self._get_language_name(language_code)} learner.\n\n"
            f"Review concepts: {', '.join(context['review_concepts'][:5])}\n"
            f"New concepts: {', '.join(context['new_concepts'][:3])}\n"
            f"Weak areas: {', '.join(context['weak_areas'])}\n"
            f"Learning goals: {', '.join(context['learning_goals'])}"
        )

        return result.output

    async def update_user_proficiency(
        self, analysis: StructuredGrammarAnalysis, user: User, language_code: str
    ) -> None:
        """
        Update user's proficiency metrics and concept masteries based on analysis.

        Args:
            analysis: Structured analysis results
            user: User to update
            language_code: Target language
        """
        # Get or create language profile
        language_profile, created = await LanguageProfile.objects.aget_or_create(
            user=user,
            target_language=language_code,
            defaults={
                'current_level': analysis.proficiency.estimated_level.value,
                'proficiency_score': analysis.accuracy_score,
                'grammar_accuracy': analysis.accuracy_score,
                'fluency_score': analysis.proficiency.fluency_score,
            },
        )

        if not created:
            # Update existing profile with weighted average
            language_profile.grammar_accuracy = (
                language_profile.grammar_accuracy * 0.8 + analysis.accuracy_score * 0.2
            )
            language_profile.fluency_score = (
                language_profile.fluency_score * 0.8
                + analysis.proficiency.fluency_score * 0.2
            )

            # Update proficiency score
            language_profile.proficiency_score = (
                language_profile.grammar_accuracy * 0.6
                + language_profile.fluency_score * 0.4
            )

            # Update weak/strong areas
            language_profile.weak_areas = list(
                set(language_profile.weak_areas + analysis.weaknesses)
            )[
                :10
            ]  # Keep only top 10

            language_profile.strong_areas = list(
                set(language_profile.strong_areas + analysis.strengths)
            )[
                :10
            ]  # Keep only top 10

            await language_profile.asave()

        # Update concept masteries
        for concept_usage in analysis.concepts_used:
            await self._update_concept_mastery(user, concept_usage, language_code)

        # Create error patterns for persistent errors
        for error in analysis.errors:
            if error.severity in [ErrorSeverity.MODERATE, ErrorSeverity.SEVERE]:
                await self._create_or_update_error_pattern(user, error, language_code)

    def _create_structured_analysis_prompt(
        self,
        language_code: str,
        analysis_language_code: str,
        current_level: str,
    ) -> str:
        """Create system prompt for structured grammar analysis with organic concept discovery."""
        language_name = self._get_language_name(language_code)
        feedback_language = self._get_language_name(analysis_language_code)

        return (
            f"You are an expert {language_name} teacher providing detailed "
            f"analysis for a {current_level} level student.\n\n"
            f"Analyze the student's {language_name} text and identify what grammar concepts "
            f"are actually present in their writing. Focus on:\n\n"
            "1. **Grammar concepts observed**: What specific grammar concepts do you see? "
            f"(e.g., verb tenses, word order, articles, prepositions, sentence structure, etc.)\n"
            "2. **Concept usage accuracy**: How well did they use each concept?\n"
            "3. **Specific errors with corrections**: Point out mistakes and provide corrections\n"
            "4. **Overall proficiency assessment**: Based on what you observe\n"
            "5. **Learning recommendations**: What should they focus on next?\n\n"
            f"Discover the grammar organically from their actual text - don't assume concepts "
            f"that aren't clearly demonstrated. Provide feedback in {feedback_language}.\n"
            "Rate confidence levels based on how clear the evidence is in the text.\n"
            "Estimate CEFR levels conservatively - only suggest higher levels "
            "with strong evidence."
        )

    def _create_adaptive_prompt_system_prompt(
        self, language_code: str, current_level: str
    ) -> str:
        """Create system prompt for adaptive prompt generation."""
        language_name = self._get_language_name(language_code)

        return (
            f"You are an expert {language_name} teacher creating personalized "
            "conversation prompts.\n\n"
            "Create engaging, level-appropriate prompts that:\n"
            "1. Target specific grammar concepts for practice\n"
            "2. Incorporate spaced repetition of previous concepts\n"
            "3. Gradually introduce new concepts\n"
            "4. Provide natural conversation contexts\n\n"
            f"Current student level: {current_level}\n"
            "Make the prompt interesting and relevant to adult learners.\n"
            "Include scaffolding for support and extensions for challenge."
        )

    async def _get_relevant_concepts(
        self, language_code: str, current_level: str
    ) -> List[GrammarConcept]:
        """Get grammar concepts relevant to user's current level and below."""
        level_order = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        try:
            current_index = level_order.index(current_level)
            relevant_levels = level_order[: current_index + 2]  # Current + one above
        except ValueError:
            relevant_levels = ['A1', 'A2']

        concepts = []
        async for concept in GrammarConcept.objects.filter(
            language=language_code, cefr_level__in=relevant_levels
        ).order_by('complexity_score'):
            concepts.append(concept)

        return concepts

    async def _get_concepts_for_review(
        self, user: User, language_code: str
    ) -> List[ConceptMastery]:
        """Get concepts that need spaced repetition review."""
        concepts = []
        async for mastery in ConceptMastery.objects.filter(
            user=user, concept__language=language_code
        ).select_related('concept'):
            if mastery.needs_review():
                concepts.append(mastery)

        return concepts[:10]  # Limit to top 10 for review

    async def _get_new_concepts(
        self, user: User, language_code: str, current_level: str
    ) -> List[GrammarConcept]:
        """Get new concepts ready to introduce to the user."""
        # Get concepts user hasn't practiced yet at their level
        practiced_concept_ids = []
        async for mastery in ConceptMastery.objects.filter(
            user=user, concept__language=language_code
        ).values_list('concept_id', flat=True):
            practiced_concept_ids.append(mastery)

        new_concepts = []
        async for concept in GrammarConcept.objects.filter(
            language=language_code, cefr_level=current_level
        ).exclude(id__in=practiced_concept_ids)[:5]:
            new_concepts.append(concept)

        return new_concepts

    async def _update_concept_mastery(
        self,
        user: User,
        concept_usage: Any,  # ConceptUsage from analysis
        language_code: str,
    ) -> None:
        """Update or create concept mastery based on usage analysis."""
        # Find the grammar concept
        concept = await GrammarConcept.objects.filter(
            name=concept_usage.concept_name, language=language_code
        ).afirst()

        if not concept:
            return  # Skip if concept not found

        # Get or create mastery record
        mastery, _ = await ConceptMastery.objects.aget_or_create(
            user=user,
            concept=concept,
            defaults={
                'mastery_score': 0.5 if concept_usage.correct else 0.1,
                'confidence_level': concept_usage.confidence,
            },
        )

        # Update performance
        difficulty = (
            0.5  # Default difficulty, could be calculated based on level difference
        )
        mastery.update_performance(concept_usage.correct, difficulty)
        await mastery.asave()

    async def _create_or_update_error_pattern(
        self, user: User, error: Any, _language_code: str  # GrammarError from analysis
    ) -> None:
        """Create or update error pattern for persistent tracking."""
        # Try to find existing error pattern
        error_pattern = await ErrorPattern.objects.filter(
            user=user,
            error_type=error.error_type,
            error_description__icontains=error.original_text,
        ).afirst()

        if error_pattern:
            # Update existing pattern
            error_pattern.add_occurrence(error.original_text, error.corrected_text)
            await error_pattern.asave()
        else:
            # Create new error pattern
            await ErrorPattern.objects.acreate(
                user=user,
                error_type=error.error_type,
                error_description=error.explanation,
                example_errors=[error.original_text],
                correction_suggestions=[error.corrected_text],
            )

    async def _create_fallback_analysis(
        self, text: str, language_code: str, analysis_language_code: str
    ) -> StructuredGrammarAnalysis:
        """Create a basic fallback analysis if structured analysis fails."""
        from .analysis_models import (
            StructuredGrammarAnalysis,
            ProficiencyAssessment,
        )

        return StructuredGrammarAnalysis(
            proficiency=ProficiencyAssessment(
                estimated_level=CEFRLevel.A2,
                confidence=0.3,
                vocabulary_level=CEFRLevel.A2,
                grammar_level=CEFRLevel.A2,
                fluency_score=0.5,
                coherence_score=0.5,
            ),
            concepts_used=[],
            errors=[],
            total_errors=0,
            error_rate=0.0,
            accuracy_score=0.8,
            strengths=["Text submitted for analysis"],
            weaknesses=["Analysis could not be completed"],
            next_concepts=["Basic grammar review"],
            practice_suggestions=["Continue practicing with short texts"],
            analysis_language=analysis_language_code,
            target_language=language_code,
            text_length=len(text),
            word_count=len(text.split()),
        )

    async def _create_fallback_prompt(
        self, language_code: str, level: str
    ) -> AdaptivePrompt:
        """Create a basic fallback prompt if generation fails."""
        basic_prompts = {
            'en': "Tell me about your day. What did you do today?",
            'es': "Háblame de tu día. ¿Qué hiciste hoy?",
            'de': "Erzähl mir von deinem Tag. Was hast du heute gemacht?",
        }

        return AdaptivePrompt(
            prompt_text=basic_prompts.get(language_code, basic_prompts['en']),
            target_concepts=["basic conversation", "past tense"],
            difficulty_level=CEFRLevel(level),
            context="Daily routine conversation",
            primary_objective="Practice basic conversation skills",
            secondary_objectives=["Past tense usage", "Vocabulary building"],
            scaffolding_hints=["Think about activities you did today"],
            extension_questions=["What was the most interesting part of your day?"],
        )


# Default global AI service instance for backwards compatibility
ai_service = AIService()
