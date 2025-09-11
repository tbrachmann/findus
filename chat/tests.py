"""
Comprehensive tests for the chat application with async views.

These tests cover all async views and use mocked Agent methods to avoid
external API calls during testing.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, patch, MagicMock
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from asgiref.sync import sync_to_async
from django.test.client import AsyncClient

from .models import ChatMessage, Conversation, AfterActionReport
from .ai_service import ai_service


class AsyncChatViewsTest(TransactionTestCase):
    """Test async chat views with mocked AI service."""

    def setUp(self) -> None:
        """Set up test data."""
        self.client = AsyncClient()

    async def asetUp(self) -> None:
        """Set up async test data."""
        self.user = await User.objects.acreate_user(
            username='testuser', password='testpass123', email='test@example.com'
        )

        self.conversation = await Conversation.objects.acreate(
            user=self.user, title='Test Conversation'
        )

    async def test_new_conversation_authenticated(self) -> None:
        """Test creating a new conversation when authenticated."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        response = await self.client.get(reverse('new_conversation'))

        self.assertEqual(response.status_code, 302)
        # Should redirect to a chat view with the new conversation ID
        self.assertIn('/conversation/', response.url)

    async def test_new_conversation_redirects_unauthenticated(self) -> None:
        """Test new conversation redirects to login when not authenticated."""
        await self.asetUp()
        response = await self.client.get(reverse('new_conversation'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    async def test_chat_view_authenticated(self) -> None:
        """Test chat view loads correctly for authenticated user."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        response = await self.client.get(
            reverse('chat', kwargs={'conversation_id': self.conversation.id})
        )

        self.assertEqual(response.status_code, 200)
        # Check that the response contains the conversation ID in a URL or form field
        self.assertContains(response, str(self.conversation.id))

    async def test_chat_view_wrong_user(self) -> None:
        """Test chat view returns 404 for wrong user."""
        await self.asetUp()
        other_user = await User.objects.acreate_user(
            username='otheruser', password='testpass123'
        )
        await sync_to_async(self.client.force_login)(other_user)

        response = await self.client.get(
            reverse('chat', kwargs={'conversation_id': self.conversation.id})
        )

        self.assertEqual(response.status_code, 404)

    @patch('chat.views.ai_service')
    async def test_send_message_success(self, mock_ai_service: MagicMock) -> None:
        """Test sending a message successfully with mocked AI service."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Mock the AI service methods
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="This is a test response from AI"
        )
        mock_ai_service.analyze_grammar = AsyncMock(
            return_value="No grammar issues found."
        )

        response = await self.client.post(
            reverse('send_message'),
            {
                'message': 'Hello, how are you?',
                'conversation_id': str(self.conversation.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertEqual(response_data['message'], 'Hello, how are you?')
        self.assertEqual(response_data['response'], 'This is a test response from AI')
        self.assertIn('timestamp', response_data)
        self.assertIn('message_id', response_data)

        # Verify the AI service was called with conversation language and history
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'Hello, how are you?',
            'en',
            [],  # default language, empty history for first message
        )

        # Verify the message was saved
        message_count = await ChatMessage.objects.filter(
            conversation=self.conversation
        ).acount()
        self.assertEqual(message_count, 1)

    async def test_send_message_empty_message(self) -> None:
        """Test sending an empty message returns error."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        response = await self.client.post(
            reverse('send_message'),
            {'message': '', 'conversation_id': str(self.conversation.id)},
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)
        self.assertEqual(response_data['error'], 'Message cannot be empty')

    async def test_send_message_missing_conversation_id(self) -> None:
        """Test sending a message without conversation ID returns error."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        response = await self.client.post(reverse('send_message'), {'message': 'Hello'})

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)
        self.assertEqual(response_data['error'], 'Conversation ID is required')

    async def test_send_message_get_request(self) -> None:
        """Test GET request to send_message returns method not allowed."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        response = await self.client.get(reverse('send_message'))

        self.assertEqual(response.status_code, 405)
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)

    @patch('chat.views.ai_service')
    async def test_send_message_ai_error(self, mock_ai_service: MagicMock) -> None:
        """Test handling AI service errors during message sending."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Mock AI service to raise an exception
        mock_ai_service.generate_chat_response = AsyncMock(
            side_effect=Exception("AI service error")
        )

        response = await self.client.post(
            reverse('send_message'),
            {
                'message': 'Hello, how are you?',
                'conversation_id': str(self.conversation.id),
            },
        )

        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)
        self.assertIn('AI service error', response_data['error'])

    async def test_check_grammar_status_no_analysis(self) -> None:
        """Test checking grammar status when no analysis exists yet."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        message = await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="Test message",
            response="Test response",
        )

        response = await self.client.get(
            reverse('check_grammar_status', kwargs={'message_id': message.id})
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['grammar_analysis'], '')

    async def test_check_grammar_status_with_analysis(self) -> None:
        """Test checking grammar status when analysis exists."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        message = await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="Test message",
            response="Test response",
            grammar_analysis="No issues found.",
        )

        response = await self.client.get(
            reverse('check_grammar_status', kwargs={'message_id': message.id})
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['grammar_analysis'], 'No issues found.')

    async def test_check_grammar_status_post_request(self) -> None:
        """Test POST request to check_grammar_status returns method not allowed."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        message = await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="Test message",
            response="Test response",
        )

        response = await self.client.post(
            reverse('check_grammar_status', kwargs={'message_id': message.id})
        )

        self.assertEqual(response.status_code, 405)

    async def test_conversation_analysis_no_messages(self) -> None:
        """Test conversation analysis redirects when no messages exist."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        response = await self.client.get(
            reverse(
                'conversation_analysis',
                kwargs={'conversation_id': self.conversation.id},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/conversation/', response.url)

    @patch('chat.views.ai_service')
    async def test_conversation_analysis_success(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test successful conversation analysis with mocked AI service."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Create some test messages
        await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="Hello, how are you?",
            response="I'm doing well, thank you!",
            grammar_analysis="No issues found.",
        )
        await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="Can you help me with my English?",
            response="Of course! I'd be happy to help.",
            grammar_analysis="Good grammar and spelling.",
        )

        # Mock the AI service
        mock_analysis = (
            "• Strengths: Clear communication, polite tone\n"
            "• Areas for improvement: None identified\n"
            "• Recommendations: Continue practicing daily conversations"
        )
        mock_ai_service.analyze_conversation = AsyncMock(return_value=mock_analysis)

        response = await self.client.get(
            reverse(
                'conversation_analysis',
                kwargs={'conversation_id': self.conversation.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clear communication")
        self.assertContains(response, "Continue practicing")

        # Verify the AI service was called
        mock_ai_service.analyze_conversation.assert_called_once()

        # Verify the report was saved
        report_count = await AfterActionReport.objects.filter(
            conversation=self.conversation
        ).acount()
        self.assertEqual(report_count, 1)

    async def test_conversation_analysis_existing_report(self) -> None:
        """Test conversation analysis reuses existing report."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Create a test message
        await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="Test message",
            response="Test response",
        )

        # Create an existing report
        existing_analysis = "Existing analysis content"
        await AfterActionReport.objects.acreate(
            conversation=self.conversation, analysis_content=existing_analysis
        )

        response = await self.client.get(
            reverse(
                'conversation_analysis',
                kwargs={'conversation_id': self.conversation.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, existing_analysis)

    @patch('chat.views.ai_service')
    async def test_conversation_analysis_ai_error(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test conversation analysis handles AI service errors."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Create a test message
        await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="Test message",
            response="Test response",
        )

        # Mock AI service to raise an exception
        mock_ai_service.analyze_conversation = AsyncMock(
            return_value="⚠️ Failed to generate analysis: AI service error"
        )

        response = await self.client.get(
            reverse(
                'conversation_analysis',
                kwargs={'conversation_id': self.conversation.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Failed to generate analysis")

    async def test_conversation_analysis_wrong_user(self) -> None:
        """Test conversation analysis returns 404 for wrong user."""
        await self.asetUp()
        other_user = await User.objects.acreate_user(
            username='otheruser', password='testpass123'
        )
        await sync_to_async(self.client.force_login)(other_user)

        # Create a test message for the original user's conversation
        await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="Test message",
            response="Test response",
        )

        response = await self.client.get(
            reverse(
                'conversation_analysis',
                kwargs={'conversation_id': self.conversation.id},
            )
        )

        self.assertEqual(response.status_code, 404)


class AsyncGrammarAnalysisTest(TransactionTestCase):
    """Test async grammar analysis functionality."""

    def setUp(self) -> None:
        """Set up test data."""
        pass

    async def asetUp(self) -> None:
        """Set up async test data."""
        self.user = await User.objects.acreate_user(
            username='testuser', password='testpass123'
        )
        self.conversation = await Conversation.objects.acreate(user=self.user)
        self.message = await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="Test message with error's",
            response="Test response",
        )

    @patch('chat.views.ai_service')
    async def test_analyze_grammar_async_success(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test successful async grammar analysis."""
        await self.asetUp()
        from chat.views import analyze_grammar_async

        mock_ai_service.analyze_grammar = AsyncMock(
            return_value="Found spelling error: error's should be errors"
        )

        await analyze_grammar_async(self.message.id, self.message.message, 'en')

        # Refresh the message from the database
        await self.message.arefresh_from_db()

        self.assertEqual(
            self.message.grammar_analysis,
            "Found spelling error: error's should be errors",
        )
        mock_ai_service.analyze_grammar.assert_called_once_with(
            self.message.message, 'en'
        )

    @patch('chat.views.ai_service')
    async def test_analyze_grammar_async_error(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test grammar analysis handles errors gracefully."""
        await self.asetUp()
        from chat.views import analyze_grammar_async

        mock_ai_service.analyze_grammar = AsyncMock(
            side_effect=Exception("AI service unavailable")
        )

        await analyze_grammar_async(self.message.id, self.message.message, 'en')

        # Refresh the message from the database
        await self.message.arefresh_from_db()

        self.assertIn("Analysis failed", self.message.grammar_analysis)
        self.assertIn("AI service unavailable", self.message.grammar_analysis)

    @patch('chat.views.ai_service')
    async def test_send_message_with_grammar_analysis_completion(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test that grammar analysis completes when sending a message via asyncio.gather."""
        from django.test.client import AsyncClient

        await self.asetUp()
        client = AsyncClient()
        await sync_to_async(client.force_login)(self.user)
        # Mock the AI service methods
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="This is a test response from AI"
        )
        mock_ai_service.analyze_grammar = AsyncMock(
            return_value="Grammar analysis completed successfully."
        )

        # Send a message
        response = await client.post(
            reverse('send_message'),
            {
                'message': 'Hello, can you help me with my grammer?',
                'conversation_id': str(self.conversation.id),
            },
        )

        # Verify the response is successful
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        message_id = response_data['message_id']

        # Verify that the message was created
        message = await ChatMessage.objects.aget(id=message_id)

        # Verify that grammar analysis was completed (not None)
        self.assertIsNotNone(message.grammar_analysis)
        self.assertEqual(
            message.grammar_analysis, "Grammar analysis completed successfully."
        )
        # Verify both AI service methods were called
        mock_ai_service.generate_chat_response.assert_called_once()
        mock_ai_service.analyze_grammar.assert_called_once_with(
            'Hello, can you help me with my grammer?', 'en'  # default language
        )


class AIServiceTest(TransactionTestCase):
    """Test AI service functionality with mocked agents."""

    def setUp(self) -> None:
        """Set up test data."""
        pass

    @patch('chat.ai_service.Agent')
    async def test_generate_chat_response(self, MockAgent: MagicMock) -> None:
        """Test chat response generation with mocked agent."""
        mock_agent_instance = AsyncMock()
        mock_result = AsyncMock()
        mock_result.output = "Mocked AI response"
        mock_agent_instance.run.return_value = mock_result
        MockAgent.return_value = mock_agent_instance

        # Create a fresh AI service instance for testing
        from chat.ai_service import AIService

        service = AIService()
        service.chat_agent = mock_agent_instance

        result = await service.generate_chat_response("Hello", "en")

        self.assertEqual(result, "Mocked AI response")
        mock_agent_instance.run.assert_called_once_with("Hello")

    @patch('chat.ai_service.Agent')
    async def test_analyze_grammar(self, MockAgent: MagicMock) -> None:
        """Test grammar analysis with mocked agent."""
        mock_agent_instance = AsyncMock()
        mock_result = AsyncMock()
        mock_result.output = "Grammar looks good!"
        mock_agent_instance.run.return_value = mock_result
        MockAgent.return_value = mock_agent_instance

        # Create a fresh AI service instance for testing
        from chat.ai_service import AIService

        service = AIService()

        result = await service.analyze_grammar("This is a test.", "en")

        self.assertEqual(result, "Grammar looks good!")
        mock_agent_instance.run.assert_called_once_with(
            'Text: """\nThis is a test.\n"""'
        )

    @patch('chat.ai_service.Agent')
    async def test_analyze_conversation(self, MockAgent: MagicMock) -> None:
        """Test conversation analysis with mocked agent."""
        mock_agent_instance = AsyncMock()
        mock_result = AsyncMock()
        mock_result.output = "Overall analysis complete"
        mock_agent_instance.run.return_value = mock_result
        MockAgent.return_value = mock_agent_instance

        # Create a fresh AI service instance for testing
        from chat.ai_service import AIService

        service = AIService()

        messages_data = [
            {'message': 'Hello', 'feedback': 'Good greeting'},
            {'message': 'How are you?', 'feedback': 'Correct grammar'},
        ]

        result = await service.analyze_conversation(messages_data, "en")

        self.assertEqual(result, "Overall analysis complete")
        mock_agent_instance.run.assert_called_once()
        call_args = mock_agent_instance.run.call_args[0][0]
        self.assertIn("Hello", call_args)
        self.assertIn("Good greeting", call_args)


class ConversationStarterTestCase(TestCase):
    """Test cases for the conversation starter feature."""

    def setUp(self) -> None:
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_conversation_starters_dict_exists(self) -> None:
        """Test that CONVERSATION_STARTERS dict is defined and not empty."""
        from .views import CONVERSATION_STARTERS

        self.assertIsInstance(CONVERSATION_STARTERS, dict)
        self.assertGreater(len(CONVERSATION_STARTERS), 0)

        # Check that all languages have lists of starters
        expected_languages = ['en', 'es', 'de']
        for lang in expected_languages:
            self.assertIn(lang, CONVERSATION_STARTERS)
            self.assertIsInstance(CONVERSATION_STARTERS[lang], list)
            self.assertGreater(len(CONVERSATION_STARTERS[lang]), 0)

            # Check that all starters are strings
            for starter in CONVERSATION_STARTERS[lang]:
                self.assertIsInstance(starter, str)
                self.assertGreater(len(starter.strip()), 0)

    def test_conversation_starters_content(self) -> None:
        """Test that conversation starters contain expected prompts."""
        from .views import CONVERSATION_STARTERS

        # Test English starters
        expected_en_starters = [
            "Tell me about your family?",
            "What did you do today?",
            "What do you like doing for fun?",
            "What did you do this weekend?",
        ]
        for expected in expected_en_starters:
            self.assertIn(expected, CONVERSATION_STARTERS['en'])

        # Test Spanish starters
        expected_es_starters = [
            "Háblame de tu familia?",
            "¿Qué hiciste hoy?",
        ]
        for expected in expected_es_starters:
            self.assertIn(expected, CONVERSATION_STARTERS['es'])

        # Test German starters
        expected_de_starters = [
            "Erzähl mir von deiner Familie?",
            "Was hast du heute gemacht?",
        ]
        for expected in expected_de_starters:
            self.assertIn(expected, CONVERSATION_STARTERS['de'])

    @patch('chat.views.random.choice')
    def test_chat_view_with_no_messages_shows_conversation_starter(
        self, mock_choice: Any
    ) -> None:
        """Test that a conversation with no messages shows a random conversation starter."""
        mock_choice.return_value = "What's your favorite food?"

        conversation = Conversation.objects.create(user=self.user)
        url = reverse('chat', args=[conversation.id])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Check that the conversation starter appears in the template context
        self.assertEqual(
            response.context['conversation_starter'], "What's your favorite food?"
        )
        # Check that the Gemini greeting appears (indicates conversation starter section is rendering)
        self.assertContains(response, "Hello! I'm Gemini.")
        # Verify random.choice was called with our starters list for English
        from .views import CONVERSATION_STARTERS

        mock_choice.assert_called_once_with(CONVERSATION_STARTERS['en'])

    @patch('chat.views.random.choice')
    def test_chat_view_with_messages_doesnt_show_conversation_starter(
        self, mock_choice: Any
    ) -> None:
        """Test that a conversation with existing messages doesn't show conversation starter in template."""
        mock_choice.return_value = "What's your favorite food?"

        conversation = Conversation.objects.create(user=self.user)
        ChatMessage.objects.create(
            conversation=conversation, message="Hello", response="Hi there!"
        )

        url = reverse('chat', args=[conversation.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Should still have conversation_starter in context, but it won't be rendered
        self.assertEqual(
            response.context['conversation_starter'], "What's your favorite food?"
        )
        # Should not contain the starter message since we have existing messages
        self.assertNotContains(response, "What's your favorite food?")
        # Should contain our actual messages
        self.assertContains(response, "Hello")
        self.assertContains(response, "Hi there!")

    def test_chat_view_conversation_starter_randomness(self) -> None:
        """Test that different conversations get different starters (with high probability)."""
        from .views import CONVERSATION_STARTERS

        starters_seen = set()

        # Create multiple conversations and check their starters
        for i in range(10):
            conversation = Conversation.objects.create(user=self.user)
            url = reverse('chat', args=[conversation.id])

            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

            # Extract the conversation starter from the response
            content = response.content.decode()
            # Check all English starters since conversation has default language 'en'
            for starter in CONVERSATION_STARTERS['en']:
                if starter in content:
                    starters_seen.add(starter)
                    break

        # We should see some variety (at least 2 different starters in 10 tries)
        # This test has a small chance of failing due to randomness, but it's very unlikely
        self.assertGreaterEqual(len(starters_seen), 2)

    def test_chat_view_requires_login(self) -> None:
        """Test that the chat view requires user authentication."""
        self.client.logout()
        conversation = Conversation.objects.create(user=self.user)
        url = reverse('chat', args=[conversation.id])

        response = self.client.get(url)

        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_chat_view_user_can_only_access_own_conversations(self) -> None:
        """Test that users can only access their own conversations."""
        # Create another user and their conversation
        other_user = User.objects.create_user(
            username='otheruser', email='other@example.com', password='otherpass123'
        )
        other_conversation = Conversation.objects.create(user=other_user)

        # Try to access other user's conversation
        url = reverse('chat', args=[other_conversation.id])
        response = self.client.get(url)

        # Should get 404 (not found) since user doesn't have access
        self.assertEqual(response.status_code, 404)

    def test_new_conversation_creation(self) -> None:
        """Test that new_conversation creates a conversation and redirects to it."""
        url = reverse('new_conversation')
        response = self.client.get(url)

        # Should redirect to the newly created conversation
        self.assertEqual(response.status_code, 302)

        # Check that a conversation was created
        conversation = Conversation.objects.filter(user=self.user).first()
        self.assertIsNotNone(conversation)

        # Check that redirect goes to the correct chat URL
        expected_url = reverse('chat', args=[conversation.id])
        self.assertEqual(response.url, expected_url)

    def test_conversation_starter_template_context(self) -> None:
        """Test that conversation_starter is properly passed to template context."""
        conversation = Conversation.objects.create(user=self.user)
        url = reverse('chat', args=[conversation.id])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('conversation_starter', response.context)
        from .views import CONVERSATION_STARTERS

        self.assertIn(
            response.context['conversation_starter'], CONVERSATION_STARTERS['en']
        )


class LanguageSelectionTest(TransactionTestCase):
    """Test cases for language selection functionality."""

    def setUp(self) -> None:
        """Set up test data."""
        self.client = AsyncClient()

    async def asetUp(self) -> None:
        """Set up async test data."""
        self.user = await User.objects.acreate_user(
            username='testuser', email='test@example.com', password='testpass123'
        )

    async def test_language_selection_view_requires_login(self) -> None:
        """Test that language selection view requires authentication."""
        await self.asetUp()
        response = await self.client.get(reverse('language_selection'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    async def test_language_selection_view_authenticated(self) -> None:
        """Test language selection view for authenticated user."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)
        response = await self.client.get(reverse('language_selection'))
        self.assertEqual(response.status_code, 200)
        # Template contains the expected text
        content = response.content.decode()
        self.assertIn("Choose Your Language", content)
        self.assertIn("English", content)
        self.assertIn("Spanish", content)
        self.assertIn("German", content)

    async def test_new_conversation_with_language_selection(self) -> None:
        """Test creating new conversation with language selection."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Test creating Spanish conversation
        response = await self.client.post(
            reverse('new_conversation'), {'language': 'es'}
        )
        self.assertEqual(response.status_code, 302)

        # Get the created conversation
        conversation = await Conversation.objects.filter(user=self.user).afirst()
        self.assertIsNotNone(conversation)
        self.assertEqual(conversation.language, 'es')

    async def test_new_conversation_with_invalid_language(self) -> None:
        """Test creating conversation with invalid language defaults to English."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        response = await self.client.post(
            reverse('new_conversation'), {'language': 'invalid'}
        )
        self.assertEqual(response.status_code, 302)

        conversation = await Conversation.objects.filter(user=self.user).afirst()
        self.assertIsNotNone(conversation)
        self.assertEqual(conversation.language, 'en')  # Should default to English

    async def test_new_conversation_without_language(self) -> None:
        """Test creating conversation without language parameter defaults to English."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        response = await self.client.get(reverse('new_conversation'))
        self.assertEqual(response.status_code, 302)

        conversation = await Conversation.objects.filter(user=self.user).afirst()
        self.assertIsNotNone(conversation)
        self.assertEqual(conversation.language, 'en')  # Should default to English

    async def test_new_conversation_with_analysis_language(self) -> None:
        """Test creating conversation with both language and analysis_language."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Test German conversation with English analysis
        response = await self.client.post(
            reverse('new_conversation'), {'language': 'de', 'analysis_language': 'en'}
        )
        self.assertEqual(response.status_code, 302)

        conversation = await Conversation.objects.filter(user=self.user).afirst()
        self.assertIsNotNone(conversation)
        self.assertEqual(conversation.language, 'de')  # German conversation
        self.assertEqual(conversation.analysis_language, 'en')  # English analysis

    async def test_new_conversation_with_invalid_analysis_language(self) -> None:
        """Test creating conversation with invalid analysis_language defaults to English."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        response = await self.client.post(
            reverse('new_conversation'),
            {'language': 'es', 'analysis_language': 'invalid'},
        )
        self.assertEqual(response.status_code, 302)

        conversation = await Conversation.objects.filter(user=self.user).afirst()
        self.assertIsNotNone(conversation)
        self.assertEqual(conversation.language, 'es')  # Spanish conversation
        self.assertEqual(
            conversation.analysis_language, 'en'
        )  # Should default to English


class LanguageSpecificConversationTest(TestCase):
    """Test language-specific conversation functionality."""

    def setUp(self) -> None:
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_spanish_conversation_starter(self) -> None:
        """Test that Spanish conversations show Spanish starters."""
        conversation = Conversation.objects.create(user=self.user, language='es')
        url = reverse('chat', args=[conversation.id])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Should contain a Spanish greeting
        content = response.content.decode()
        from .views import CONVERSATION_STARTERS

        # Check if any Spanish starter appears in the content
        spanish_starter_found = False
        for starter in CONVERSATION_STARTERS['es']:
            if starter in content:
                spanish_starter_found = True
                break
        self.assertTrue(spanish_starter_found, "No Spanish conversation starter found")

    def test_german_conversation_starter(self) -> None:
        """Test that German conversations show German starters."""
        conversation = Conversation.objects.create(user=self.user, language='de')
        url = reverse('chat', args=[conversation.id])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Should contain a German greeting
        content = response.content.decode()
        from .views import CONVERSATION_STARTERS

        # Check if any German starter appears in the content
        german_starter_found = False
        for starter in CONVERSATION_STARTERS['de']:
            if starter in content:
                german_starter_found = True
                break
        self.assertTrue(german_starter_found, "No German conversation starter found")

    @patch('chat.views.random.choice')
    def test_language_specific_starter_selection(self, mock_choice: Any) -> None:
        """Test that conversation starters are selected from correct language."""
        mock_choice.return_value = "¿Qué hiciste hoy?"

        conversation = Conversation.objects.create(user=self.user, language='es')
        url = reverse('chat', args=[conversation.id])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Verify random.choice was called with Spanish starters
        from .views import CONVERSATION_STARTERS

        mock_choice.assert_called_once_with(CONVERSATION_STARTERS['es'])


class AsyncLanguageSpecificAIServiceTest(TransactionTestCase):
    """Test language-specific AI service functionality."""

    def setUp(self) -> None:
        """Set up test data."""
        self.client = AsyncClient()

    async def asetUp(self) -> None:
        """Set up async test data."""
        self.user = await User.objects.acreate_user(
            username='testuser', password='testpass123', email='test@example.com'
        )

    @patch('chat.views.ai_service')
    async def test_send_message_spanish_conversation(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test sending message in Spanish conversation calls AI with Spanish language."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Create Spanish conversation
        spanish_conversation = await Conversation.objects.acreate(
            user=self.user, language='es'
        )

        # Mock AI service
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Respuesta en español"
        )
        mock_ai_service.analyze_grammar = AsyncMock(
            return_value="Sin problemas gramaticales."
        )

        response = await self.client.post(
            reverse('send_message'),
            {
                'message': 'Hola, ¿cómo estás?',
                'conversation_id': str(spanish_conversation.id),
            },
        )

        self.assertEqual(response.status_code, 200)

        # Verify AI service was called with Spanish language and empty history
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'Hola, ¿cómo estás?', 'es', []
        )

    @patch('chat.views.ai_service')
    async def test_grammar_analysis_german_conversation(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test grammar analysis in German conversation uses analysis language (default English)."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Create German conversation (analysis_language defaults to 'en')
        german_conversation = await Conversation.objects.acreate(
            user=self.user, language='de'
        )

        # Mock AI service
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Deutsche Antwort"
        )
        mock_ai_service.analyze_grammar = AsyncMock(return_value="Grammar error found.")

        response = await self.client.post(
            reverse('send_message'),
            {
                'message': 'Wie geht es dir?',
                'conversation_id': str(german_conversation.id),
            },
        )

        self.assertEqual(response.status_code, 200)

        # Verify grammar analysis was called with analysis language (English by default)
        mock_ai_service.analyze_grammar.assert_called_once_with(
            'Wie geht es dir?', 'en'  # analysis_language defaults to English
        )

    @patch('chat.views.ai_service')
    async def test_grammar_analysis_different_from_conversation_language(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test grammar analysis uses analysis_language when different from conversation language."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Create German conversation with English analysis
        german_conversation = await Conversation.objects.acreate(
            user=self.user, language='de', analysis_language='en'
        )

        # Mock AI service
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Deutsche Antwort"
        )
        mock_ai_service.analyze_grammar = AsyncMock(
            return_value="Grammar error found in English feedback."
        )

        response = await self.client.post(
            reverse('send_message'),
            {
                'message': 'Wie geht es dir?',
                'conversation_id': str(german_conversation.id),
            },
        )

        self.assertEqual(response.status_code, 200)

        # Verify chat response was called with German (conversation language) and empty history
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'Wie geht es dir?', 'de', []
        )

        # Verify grammar analysis was called with English (analysis language)
        mock_ai_service.analyze_grammar.assert_called_once_with(
            'Wie geht es dir?', 'en'  # Analysis language, not conversation language
        )

    @patch('chat.views.ai_service')
    async def test_conversation_analysis_uses_analysis_language(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test conversation analysis uses the conversation's analysis language."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Create Spanish conversation with English analysis (analysis_language defaults to 'en')
        spanish_conversation = await Conversation.objects.acreate(
            user=self.user, language='es'  # analysis_language defaults to 'en'
        )
        await ChatMessage.objects.acreate(
            conversation=spanish_conversation,
            message="Hola",
            response="¡Hola! ¿Cómo estás?",
            grammar_analysis="Perfect.",
        )

        # Mock AI service
        mock_ai_service.analyze_conversation = AsyncMock(
            return_value="• Strengths: Appropriate greeting\n• Recommendations: Continue practicing"
        )

        response = await self.client.get(
            reverse(
                'conversation_analysis',
                kwargs={'conversation_id': spanish_conversation.id},
            )
        )

        self.assertEqual(response.status_code, 200)

        # Verify conversation analysis was called with analysis language (English by default)
        mock_ai_service.analyze_conversation.assert_called_once()
        call_args = mock_ai_service.analyze_conversation.call_args
        # Check the keyword arguments or positional arguments
        if len(call_args) > 1 and len(call_args[0]) > 1:
            # Positional argument
            self.assertEqual(
                call_args[0][1], 'en'
            )  # Second positional argument should be analysis language
        else:
            # Keyword argument
            self.assertEqual(call_args[1].get('language_code'), 'en')


class ConversationMemoryTest(TransactionTestCase):
    """Test conversation memory functionality using Pydantic AI conversation history."""

    def setUp(self) -> None:
        """Set up test data."""
        self.client = AsyncClient()

    async def asetUp(self) -> None:
        """Set up async test data."""
        self.user = await User.objects.acreate_user(
            username='testuser', password='testpass123', email='test@example.com'
        )
        self.conversation = await Conversation.objects.acreate(
            user=self.user, title='Test Conversation'
        )

    @patch('chat.views.ai_service')
    async def test_first_message_no_history(self, mock_ai_service: MagicMock) -> None:
        """Test that first message in conversation has no history."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Hello! Nice to meet you."
        )
        mock_ai_service.analyze_grammar = AsyncMock(return_value="No issues found.")

        response = await self.client.post(
            reverse('send_message'),
            {
                'message': 'Hi there!',
                'conversation_id': str(self.conversation.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        # Verify AI service was called with empty conversation history
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'Hi there!', 'en', []  # Empty history for first message
        )

    @patch('chat.views.ai_service')
    async def test_second_message_includes_history(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test that second message includes conversation history."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Create first message in conversation
        first_message = await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="Hi there!",
            response="Hello! Nice to meet you.",
        )

        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="My name is Claude."
        )
        mock_ai_service.analyze_grammar = AsyncMock(return_value="No issues found.")

        response = await self.client.post(
            reverse('send_message'),
            {
                'message': 'What is your name?',
                'conversation_id': str(self.conversation.id),
            },
        )

        self.assertEqual(response.status_code, 200)

        # Verify AI service was called with conversation history
        expected_history = [
            {'role': 'user', 'content': 'Hi there!'},
            {'role': 'assistant', 'content': 'Hello! Nice to meet you.'},
        ]
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'What is your name?', 'en', expected_history
        )

    @patch('chat.views.ai_service')
    async def test_multiple_messages_build_history(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test that multiple messages build up conversation history."""
        await self.asetUp()
        await sync_to_async(self.client.force_login)(self.user)

        # Create multiple messages in conversation
        await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="Hi there!",
            response="Hello! Nice to meet you.",
        )
        await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="What is your name?",
            response="My name is Claude.",
        )
        await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="Do you have any hobbies?",
            response="I enjoy helping with various tasks.",
        )

        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Yes, I remember you asked about my name earlier."
        )
        mock_ai_service.analyze_grammar = AsyncMock(return_value="No issues found.")

        response = await self.client.post(
            reverse('send_message'),
            {
                'message': 'Do you remember our conversation?',
                'conversation_id': str(self.conversation.id),
            },
        )

        self.assertEqual(response.status_code, 200)

        # Verify AI service was called with full conversation history
        expected_history = [
            {'role': 'user', 'content': 'Hi there!'},
            {'role': 'assistant', 'content': 'Hello! Nice to meet you.'},
            {'role': 'user', 'content': 'What is your name?'},
            {'role': 'assistant', 'content': 'My name is Claude.'},
            {'role': 'user', 'content': 'Do you have any hobbies?'},
            {'role': 'assistant', 'content': 'I enjoy helping with various tasks.'},
        ]
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'Do you remember our conversation?', 'en', expected_history
        )

    @patch('chat.ai_service.Agent')
    async def test_ai_service_conversation_memory_pydantic_messages(
        self, MockAgent: MagicMock
    ) -> None:
        """Test that AI service correctly builds Pydantic AI message objects for conversation history."""
        await self.asetUp()

        mock_agent_instance = AsyncMock()
        mock_result = AsyncMock()
        mock_result.output = "I remember you asked about my name."
        mock_agent_instance.run.return_value = mock_result
        MockAgent.return_value = mock_agent_instance

        from chat.ai_service import AIService

        service = AIService()

        conversation_history = [
            {'role': 'user', 'content': 'Hi there!'},
            {'role': 'assistant', 'content': 'Hello! Nice to meet you.'},
            {'role': 'user', 'content': 'What is your name?'},
            {'role': 'assistant', 'content': 'My name is Claude.'},
        ]

        result = await service.generate_chat_response(
            "Do you remember our conversation?", "en", conversation_history
        )

        self.assertEqual(result, "I remember you asked about my name.")

        # Verify agent.run was called with message_history parameter
        mock_agent_instance.run.assert_called_once()

        # Check the call arguments
        call_args, call_kwargs = mock_agent_instance.run.call_args
        self.assertEqual(
            call_args[0], "Do you remember our conversation?"
        )  # user_message
        self.assertIn('message_history', call_kwargs)

        message_history = call_kwargs['message_history']
        self.assertIsInstance(message_history, list)
        self.assertEqual(len(message_history), 4)  # 4 history messages

        # Check that the message types and content are correct
        from pydantic_ai.messages import ModelRequest, ModelResponse

        self.assertIsInstance(message_history[0], ModelRequest)
        self.assertEqual(message_history[0].parts[0].content, 'Hi there!')
        self.assertIsInstance(message_history[1], ModelResponse)
        self.assertEqual(
            message_history[1].parts[0].content, 'Hello! Nice to meet you.'
        )
        self.assertIsInstance(message_history[2], ModelRequest)
        self.assertEqual(message_history[2].parts[0].content, 'What is your name?')
        self.assertIsInstance(message_history[3], ModelResponse)
        self.assertEqual(message_history[3].parts[0].content, 'My name is Claude.')

    async def test_conversation_memory_isolated_between_conversations(self) -> None:
        """Test that conversation memory is isolated between different conversations."""
        await self.asetUp()

        # Create a second conversation
        second_conversation = await Conversation.objects.acreate(
            user=self.user, title='Second Conversation'
        )

        # Add messages to first conversation
        await ChatMessage.objects.acreate(
            conversation=self.conversation,
            message="My dog's name is Toby",
            response="That's a nice name for a dog!",
        )

        # Add different messages to second conversation
        await ChatMessage.objects.acreate(
            conversation=second_conversation,
            message="My cat's name is Whiskers",
            response="That's a great name for a cat!",
        )

        # Test that first conversation only sees its own history
        with patch('chat.views.ai_service') as mock_ai_service:
            mock_ai_service.generate_chat_response = AsyncMock(
                return_value="Yes, your dog's name is Toby."
            )
            mock_ai_service.analyze_grammar = AsyncMock(return_value="No issues found.")

            await sync_to_async(self.client.force_login)(self.user)
            response = await self.client.post(
                reverse('send_message'),
                {
                    'message': 'What is my pet\'s name?',
                    'conversation_id': str(self.conversation.id),
                },
            )

            self.assertEqual(response.status_code, 200)

            # Verify only first conversation's history was passed
            expected_history = [
                {'role': 'user', 'content': "My dog's name is Toby"},
                {'role': 'assistant', 'content': "That's a nice name for a dog!"},
            ]
            mock_ai_service.generate_chat_response.assert_called_once_with(
                'What is my pet\'s name?', 'en', expected_history
            )


class DemoModeConversationMemoryTest(TransactionTestCase):
    """Test conversation memory functionality in demo mode using session storage."""

    def setUp(self) -> None:
        """Set up test data."""
        self.client = AsyncClient()

    @patch('chat.views.ai_service')
    async def test_demo_first_message_no_history(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test that first message in demo mode has no history."""
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Hello! Nice to meet you."
        )
        mock_ai_service.analyze_grammar = AsyncMock(return_value="No issues found.")

        response = await self.client.post(
            reverse('demo_send_message'),
            {
                'message': 'Hi there!',
                'language': 'en',
                'analysis_language': 'en',
            },
        )

        self.assertEqual(response.status_code, 200)
        # Verify AI service was called with empty conversation history
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'Hi there!', 'en', []  # Empty history for first message
        )

    @patch('chat.views.ai_service')
    async def test_demo_second_message_includes_history(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test that second message in demo mode includes conversation history from session."""
        # First send a message to populate the session
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Hello! Nice to meet you."
        )
        mock_ai_service.analyze_grammar = AsyncMock(return_value="No issues found.")

        await self.client.post(
            reverse('demo_send_message'),
            {
                'message': 'Hi there!',
                'language': 'en',
                'analysis_language': 'en',
            },
        )

        # Reset mock for second call
        mock_ai_service.reset_mock()
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="My name is Claude."
        )
        mock_ai_service.analyze_grammar = AsyncMock(return_value="No issues found.")

        # Send second message
        response = await self.client.post(
            reverse('demo_send_message'),
            {
                'message': 'What is your name?',
                'language': 'en',
                'analysis_language': 'en',
            },
        )

        self.assertEqual(response.status_code, 200)

        # Verify AI service was called with conversation history
        expected_history = [
            {'role': 'user', 'content': 'Hi there!'},
            {'role': 'assistant', 'content': 'Hello! Nice to meet you.'},
        ]
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'What is your name?', 'en', expected_history
        )

    @patch('chat.views.ai_service')
    async def test_demo_session_gets_updated_with_new_messages(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test that session gets updated with new messages after AI response."""
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Hello! Nice to meet you."
        )
        mock_ai_service.analyze_grammar = AsyncMock(return_value="No issues found.")

        # Make first request
        response1 = await self.client.post(
            reverse('demo_send_message'),
            {
                'message': 'Hi there!',
                'language': 'en',
                'analysis_language': 'en',
            },
        )
        self.assertEqual(response1.status_code, 200)

        # Verify second request includes history from first
        mock_ai_service.reset_mock()
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="My name is Claude."
        )

        response2 = await self.client.post(
            reverse('demo_send_message'),
            {
                'message': 'What is your name?',
                'language': 'en',
                'analysis_language': 'en',
            },
        )

        self.assertEqual(response2.status_code, 200)

        # Verify history was passed correctly
        expected_history = [
            {'role': 'user', 'content': 'Hi there!'},
            {'role': 'assistant', 'content': 'Hello! Nice to meet you.'},
        ]
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'What is your name?', 'en', expected_history
        )

    @patch('chat.views.ai_service')
    async def test_demo_multiple_messages_build_history(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test that multiple messages build up conversation history in session storage."""
        # Send first message
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Hello! Nice to meet you."
        )
        mock_ai_service.analyze_grammar = AsyncMock(return_value="No issues found.")

        await self.client.post(
            reverse('demo_send_message'),
            {
                'message': 'Hi there!',
                'language': 'en',
                'analysis_language': 'en',
            },
        )

        # Send second message
        mock_ai_service.reset_mock()
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="My name is Claude."
        )

        await self.client.post(
            reverse('demo_send_message'),
            {
                'message': 'What is your name?',
                'language': 'en',
                'analysis_language': 'en',
            },
        )

        # Send third message and verify full history
        mock_ai_service.reset_mock()
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Yes, I remember you asked about my name earlier."
        )

        response = await self.client.post(
            reverse('demo_send_message'),
            {
                'message': 'Do you remember our conversation?',
                'language': 'en',
                'analysis_language': 'en',
            },
        )

        self.assertEqual(response.status_code, 200)

        # Verify AI service was called with full conversation history
        expected_history = [
            {'role': 'user', 'content': 'Hi there!'},
            {'role': 'assistant', 'content': 'Hello! Nice to meet you.'},
            {'role': 'user', 'content': 'What is your name?'},
            {'role': 'assistant', 'content': 'My name is Claude.'},
        ]
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'Do you remember our conversation?', 'en', expected_history
        )

    @patch('chat.views.ai_service')
    async def test_demo_conversation_memory_with_different_languages(
        self, mock_ai_service: MagicMock
    ) -> None:
        """Test that demo conversation memory works with different languages."""
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Hola! ¿Cómo estás?"
        )
        mock_ai_service.analyze_grammar = AsyncMock(
            return_value="Sin problemas gramaticales."
        )

        response = await self.client.post(
            reverse('demo_send_message'),
            {
                'message': '¡Hola! Soy nuevo aquí.',
                'language': 'es',
                'analysis_language': 'es',
            },
        )

        self.assertEqual(response.status_code, 200)

        # Verify Spanish conversation was handled correctly
        mock_ai_service.generate_chat_response.assert_called_once_with(
            '¡Hola! Soy nuevo aquí.', 'es', []
        )

    async def test_demo_clear_conversation_history(self) -> None:
        """Test that demo conversation history can be cleared."""
        # Send a message first to populate history
        with patch('chat.views.ai_service') as mock_ai_service:
            mock_ai_service.generate_chat_response = AsyncMock(return_value="Hello!")
            mock_ai_service.analyze_grammar = AsyncMock(return_value="No issues found.")

            await self.client.post(
                reverse('demo_send_message'),
                {
                    'message': 'Hi there!',
                    'language': 'en',
                    'analysis_language': 'en',
                },
            )

        # Clear the conversation
        response = await self.client.post(reverse('demo_clear_conversation'))

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')

        # Verify next message has no history
        with patch('chat.views.ai_service') as mock_ai_service:
            mock_ai_service.generate_chat_response = AsyncMock(
                return_value="Hello again!"
            )
            mock_ai_service.analyze_grammar = AsyncMock(return_value="No issues found.")

            await self.client.post(
                reverse('demo_send_message'),
                {
                    'message': 'Hi again!',
                    'language': 'en',
                    'analysis_language': 'en',
                },
            )

            # Should be called with empty history after clear
            mock_ai_service.generate_chat_response.assert_called_once_with(
                'Hi again!', 'en', []
            )

    async def test_demo_clear_conversation_only_post(self) -> None:
        """Test that demo clear conversation only accepts POST requests."""
        response = await self.client.get(reverse('demo_clear_conversation'))
        self.assertEqual(response.status_code, 405)

    @patch('chat.views.ai_service')
    async def test_demo_isolated_sessions(self, mock_ai_service: MagicMock) -> None:
        """Test that different browser sessions have isolated conversation histories."""
        mock_ai_service.generate_chat_response = AsyncMock(return_value="Hello!")
        mock_ai_service.analyze_grammar = AsyncMock(return_value="No issues found.")

        # First client/session
        client1 = AsyncClient()
        await client1.post(
            reverse('demo_send_message'),
            {
                'message': 'Hi from session 1!',
                'language': 'en',
                'analysis_language': 'en',
            },
        )

        # Second client/session - this should have empty history
        client2 = AsyncClient()
        mock_ai_service.reset_mock()

        response2 = await client2.post(
            reverse('demo_send_message'),
            {
                'message': 'Hi from session 2!',
                'language': 'en',
                'analysis_language': 'en',
            },
        )

        self.assertEqual(response2.status_code, 200)

        # Session 2 should start with empty history (isolated from session 1)
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'Hi from session 2!', 'en', []
        )


class ConversationModelTest(TestCase):
    """Test Conversation model with language field."""

    def setUp(self) -> None:
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )

    def test_conversation_default_language(self) -> None:
        """Test that conversations default to English."""
        conversation = Conversation.objects.create(user=self.user)
        self.assertEqual(conversation.language, 'en')

    def test_conversation_language_choices(self) -> None:
        """Test that all supported languages can be set."""
        # Test English
        en_conversation = Conversation.objects.create(user=self.user, language='en')
        self.assertEqual(en_conversation.language, 'en')

        # Test Spanish
        es_conversation = Conversation.objects.create(user=self.user, language='es')
        self.assertEqual(es_conversation.language, 'es')

        # Test German
        de_conversation = Conversation.objects.create(user=self.user, language='de')
        self.assertEqual(de_conversation.language, 'de')

    def test_conversation_language_choices_validation(self) -> None:
        """Test that language choices are properly defined."""
        from .models import Conversation

        expected_choices = [
            ('en', 'English'),
            ('es', 'Spanish'),
            ('de', 'German'),
        ]

        self.assertEqual(Conversation.LANGUAGE_CHOICES, expected_choices)

    def test_conversation_analysis_language_field(self) -> None:
        """Test that conversations have analysis_language field."""
        conversation = Conversation.objects.create(
            user=self.user,
            language='de',  # German conversation
            analysis_language='en',  # English analysis
        )
        self.assertEqual(conversation.language, 'de')
        self.assertEqual(conversation.analysis_language, 'en')

    def test_conversation_analysis_language_default(self) -> None:
        """Test that analysis_language defaults to English."""
        conversation = Conversation.objects.create(user=self.user, language='es')
        self.assertEqual(conversation.analysis_language, 'en')
