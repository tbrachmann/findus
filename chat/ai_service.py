"""
AI service module using Pydantic AI with Logfire integration.

This module provides LLM interactions using Pydantic AI instead of direct
Gemini API calls, with automatic logging to Logfire for observability.
"""

import asyncio

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models.google import GoogleModel


class AIService:
    """Service class for LLM interactions with Pydantic AI and Logfire."""

    def __init__(self) -> None:
        """Initialize the AI service with Google Gemini model."""
        self.model = GoogleModel(
            'gemini-2.5-flash-lite',
        )

        # Agent for general chat responses
        self.chat_agent = Agent(
            model=self.model,
            system_prompt="You are a helpful AI assistant. Provide clear, concise responses.",
        )

        # Agent for grammar analysis
        self.grammar_agent = Agent(
            model=self.model,
            system_prompt=(
                "You are an English teacher analyzing text for grammatical errors "
                "and spelling mistakes. Provide brief, helpful feedback. If there "
                "are no issues, respond with 'No issues found.'"
            ),
        )

        # Agent for conversation analysis
        self.analysis_agent = Agent(
            model=self.model,
            system_prompt=(
                "You are an experienced English teacher creating a short "
                "after-action report for your student. Identify recurring "
                "grammar/spelling issues, highlight strengths, and provide "
                "3-5 concrete exercises or recommendations to improve. "
                "Respond in concise bullet-points."
            ),
        )

    async def generate_chat_response(self, user_message: str) -> str:
        """
        Generate a chat response using Pydantic AI with Logfire tracking.

        Args:
            user_message: The user's input message

        Returns:
            AI response text

        Raises:
            AgentRunError: If the AI model fails to respond
        """
        result = await self.chat_agent.run(user_message)

        return str(result.data)

    async def analyze_grammar(self, text: str) -> str:
        """
        Analyze text for grammar and spelling issues.

        Args:
            text: The text to analyze

        Returns:
            Grammar analysis feedback
        """
        try:
            result = await self.grammar_agent.run(f'Text: """\n{text}\n"""')
            return str(result.data)
        except AgentRunError as e:
            return f"Analysis failed: {e}"

    async def analyze_conversation(self, messages_data: list[dict]) -> str:
        """
        Generate an after-action report for a conversation.

        Args:
            messages_data: List of dicts with 'message' and 'feedback' keys

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

            result = await self.analysis_agent.run(prompt)
            return str(result.data)

        except AgentRunError as e:
            return f"⚠️ Failed to generate analysis: {e}"

    def generate_chat_response_sync(self, user_message: str) -> str:
        """Generate chat response synchronously."""
        return asyncio.run(self.generate_chat_response(user_message))

    def analyze_grammar_sync(self, text: str) -> str:
        """Analyze grammar synchronously."""
        return asyncio.run(self.analyze_grammar(text))

    def analyze_conversation_sync(self, messages_data: list[dict]) -> str:
        """Analyze conversation synchronously."""
        return asyncio.run(self.analyze_conversation(messages_data))


# Global AI service instance
ai_service = AIService()
