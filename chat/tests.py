from typing import Any

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch

from .models import Conversation, ChatMessage
from .views import CONVERSATION_STARTERS


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
        self.assertIsInstance(CONVERSATION_STARTERS, list)
        self.assertGreater(len(CONVERSATION_STARTERS), 0)

        # Check that all starters are strings
        for starter in CONVERSATION_STARTERS:
            self.assertIsInstance(starter, str)
            self.assertGreater(len(starter.strip()), 0)

    def test_conversation_starters_content(self) -> None:
        """Test that conversation starters contain expected prompts."""
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
        self.assertIn(response.context['conversation_starter'], CONVERSATION_STARTERS)
