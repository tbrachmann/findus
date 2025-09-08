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

        # Verify the AI service was called
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'Hello, how are you?'
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

        await analyze_grammar_async(self.message.id, self.message.message)

        # Refresh the message from the database
        await self.message.arefresh_from_db()

        self.assertEqual(
            self.message.grammar_analysis,
            "Found spelling error: error's should be errors",
        )
        mock_ai_service.analyze_grammar.assert_called_once_with(self.message.message)

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

        await analyze_grammar_async(self.message.id, self.message.message)

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
        self.assertEqual(message.grammar_analysis, "Grammar analysis completed successfully.")
        
        # Verify both AI service methods were called
        mock_ai_service.generate_chat_response.assert_called_once()
        mock_ai_service.analyze_grammar.assert_called_once_with(
            'Hello, can you help me with my grammer?'
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

        result = await service.generate_chat_response("Hello")

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
        service.grammar_agent = mock_agent_instance

        result = await service.analyze_grammar("This is a test.")

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
        service.analysis_agent = mock_agent_instance

        messages_data = [
            {'message': 'Hello', 'feedback': 'Good greeting'},
            {'message': 'How are you?', 'feedback': 'Correct grammar'},
        ]

        result = await service.analyze_conversation(messages_data)

        self.assertEqual(result, "Overall analysis complete")
        mock_agent_instance.run.assert_called_once()
        call_args = mock_agent_instance.run.call_args[0][0]
        self.assertIn("Hello", call_args)
        self.assertIn("Good greeting", call_args)


class AIServiceRealIntegrationTest(TransactionTestCase):
    """Test AI service with real Pydantic AI integration to reproduce bugs."""

    async def test_agent_run_result_data_attribute_bug_fixed(self) -> None:
        """
        Test that verifies the bug is fixed - AI service now uses result.output correctly.
        
        This test verifies that the AI service no longer tries to access result.data 
        and instead properly uses result.output from AgentRunResult.
        """
        from chat.ai_service import AIService
        
        service = AIService()
        
        # This should now work without AttributeError
        try:
            response = await service.generate_chat_response("Hello, test message")
            # Should get a string response
            self.assertIsInstance(response, str)
            self.assertTrue(len(response) > 0)
        except AttributeError as e:
            if "'AgentRunResult' object has no attribute 'data'" in str(e):
                self.fail("Bug not fixed: AI service still trying to access result.data")


class ConversationStarterTestCase(TestCase):
    """Test cases for the conversation starter feature."""

    def setUp(self) -> None:
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_conversation_starters_list_exists(self) -> None:
        """Test that CONVERSATION_STARTERS list is defined and not empty."""
        from .views import CONVERSATION_STARTERS
        self.assertIsInstance(CONVERSATION_STARTERS, list)
        self.assertGreater(len(CONVERSATION_STARTERS), 0)

        # Check that all starters are strings
        for starter in CONVERSATION_STARTERS:
            self.assertIsInstance(starter, str)
            self.assertGreater(len(starter.strip()), 0)

    def test_conversation_starters_content(self) -> None:
        """Test that conversation starters contain expected prompts."""
        from .views import CONVERSATION_STARTERS
        expected_starters = [
            "Tell me about your family?",
            "What did you do today?",
            "What do you like doing for fun?",
            "What did you do this weekend?",
        ]

        for expected in expected_starters:
            self.assertIn(expected, CONVERSATION_STARTERS)

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
        # Verify random.choice was called with our starters list
        from .views import CONVERSATION_STARTERS
        mock_choice.assert_called_once_with(CONVERSATION_STARTERS)

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
            for starter in CONVERSATION_STARTERS:
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
        self.assertIn(response.context['conversation_starter'], CONVERSATION_STARTERS)
