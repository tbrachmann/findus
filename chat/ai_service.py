"""
AI service module using Pydantic AI with Logfire integration.

This module provides LLM interactions using Pydantic AI instead of direct
Gemini API calls, with automatic logging to Logfire for observability.
"""

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models.google import GoogleModel


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


# Default global AI service instance for backwards compatibility
ai_service = AIService()
