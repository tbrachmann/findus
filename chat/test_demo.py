"""Tests for demo mode functionality."""

from typing import Any
from unittest.mock import patch, AsyncMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User


class DemoModeTestCase(TestCase):
    """Test cases for demo mode functionality."""

    def setUp(self) -> None:
        """Set up test client."""
        self.client = Client()

    def test_demo_chat_view_accessible_without_login(self) -> None:
        """Test that demo chat view is accessible without authentication with language parameter."""
        response = self.client.get(reverse('demo_chat') + '?language=en')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'findus Demo Chat')
        self.assertContains(response, 'DEMO MODE')
        self.assertContains(response, 'Demo Mode:')

    def test_demo_chat_view_contains_conversation_starter(self) -> None:
        """Test that demo chat view contains a conversation starter."""
        response = self.client.get(reverse('demo_chat') + '?language=en')
        self.assertEqual(response.status_code, 200)
        # Should contain one of the conversation starters
        self.assertContains(response, 'Hello! I\'m an AI assistant')

    def test_demo_chat_view_template_and_context(self) -> None:
        """Test that demo chat view uses correct template and context."""
        response = self.client.get(reverse('demo_chat') + '?language=en')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'chat/demo_chat.html')
        self.assertIn('conversation_starter', response.context)
        self.assertIn('language', response.context)
        self.assertIsInstance(response.context['conversation_starter'], str)
        self.assertEqual(response.context['language'], 'en')

    def test_demo_send_message_post_only(self) -> None:
        """Test that demo send message only accepts POST requests."""
        # GET request should return 405
        response = self.client.get(reverse('demo_send_message'))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()['error'], 'Only POST requests are allowed')

        # HEAD request should return 405
        response = self.client.head(reverse('demo_send_message'))
        self.assertEqual(response.status_code, 405)

    def test_demo_send_message_requires_message(self) -> None:
        """Test that demo send message requires a message parameter."""
        # Empty message should return 400
        response = self.client.post(reverse('demo_send_message'), {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Message cannot be empty')

        # Whitespace-only message should return 400
        response = self.client.post(reverse('demo_send_message'), {'message': '   '})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Message cannot be empty')

    @patch('chat.views.ai_service')
    def test_demo_send_message_success(self, mock_ai_service: Any) -> None:
        """Test successful demo message sending."""
        # Mock AI service responses for async methods
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Hello! How can I help you?"
        )
        mock_ai_service.analyze_grammar = AsyncMock(return_value="Good grammar!")

        # Get CSRF token first
        response = self.client.get(reverse('demo_chat') + '?language=en')
        csrf_token = response.cookies['csrftoken'].value

        response = self.client.post(
            reverse('demo_send_message'),
            {'message': 'Hello, how are you?', 'csrfmiddlewaretoken': csrf_token},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check response structure
        self.assertIn('message', data)
        self.assertIn('response', data)
        self.assertIn('grammar_analysis', data)
        self.assertIn('timestamp', data)

        # Check response content
        self.assertEqual(data['message'], 'Hello, how are you?')
        self.assertEqual(data['response'], 'Hello! How can I help you?')
        self.assertEqual(data['grammar_analysis'], 'Good grammar!')

        # Verify AI service was called
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'Hello, how are you?', 'en', []
        )
        mock_ai_service.analyze_grammar.assert_called_once_with(
            'Hello, how are you?', 'en'
        )

    @patch('chat.views.ai_service')
    def test_demo_send_message_ai_error_handling(self, mock_ai_service: Any) -> None:
        """Test error handling when AI service fails."""
        # Mock AI service to raise an exception
        mock_ai_service.generate_chat_response = AsyncMock(
            side_effect=Exception("API Error")
        )
        mock_ai_service.analyze_grammar = AsyncMock(side_effect=Exception("API Error"))

        # Get CSRF token first
        response = self.client.get(reverse('demo_chat') + '?language=en')
        csrf_token = response.cookies['csrftoken'].value

        response = self.client.post(
            reverse('demo_send_message'),
            {'message': 'Hello, how are you?', 'csrfmiddlewaretoken': csrf_token},
        )

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Error communicating with AI', data['error'])
        self.assertIn('API Error', data['error'])

    @patch('chat.views.ai_service')
    def test_demo_send_message_no_database_interaction(
        self, mock_ai_service: Any
    ) -> None:
        """Test that demo mode doesn't interact with database."""
        # Mock AI service responses
        mock_ai_service.generate_chat_response = AsyncMock(return_value="Test response")
        mock_ai_service.analyze_grammar = AsyncMock(return_value="Good grammar!")

        # Verify no ChatMessage or Conversation objects exist before
        from chat.models import ChatMessage, Conversation

        self.assertEqual(ChatMessage.objects.count(), 0)
        self.assertEqual(Conversation.objects.count(), 0)

        # Get CSRF token first
        response = self.client.get(reverse('demo_chat') + '?language=en')
        csrf_token = response.cookies['csrftoken'].value

        response = self.client.post(
            reverse('demo_send_message'),
            {'message': 'Hello, this is a test!', 'csrfmiddlewaretoken': csrf_token},
        )

        self.assertEqual(response.status_code, 200)

        # Verify no ChatMessage or Conversation objects were created
        self.assertEqual(ChatMessage.objects.count(), 0)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_demo_urls_accessible(self) -> None:
        """Test that demo URLs are properly configured."""
        # Test demo chat URL redirects to language selection when no language provided
        response = self.client.get('/demo/')
        self.assertEqual(response.status_code, 302)  # Redirect to language selection

        # Test demo chat with language parameter
        response = self.client.get('/demo/?language=en')
        self.assertEqual(response.status_code, 200)

        # Test demo language selection URL
        response = self.client.get('/demo/language/')
        self.assertEqual(response.status_code, 200)

        # Test demo send message URL structure (will fail due to method but URL should resolve)
        response = self.client.get('/demo/send/')
        self.assertEqual(
            response.status_code, 405
        )  # Method not allowed, but URL exists

    def test_demo_chat_view_no_authentication_required(self) -> None:
        """Test that demo mode doesn't require authentication while regular chat does."""
        # Demo should work without login when language is provided
        response = self.client.get(reverse('demo_chat') + '?language=en')
        self.assertEqual(response.status_code, 200)

        # Regular chat should redirect to login (if no conversation_id)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_demo_mode_template_elements(self) -> None:
        """Test that demo mode template contains expected UI elements."""
        response = self.client.get(reverse('demo_chat') + '?language=en')
        self.assertEqual(response.status_code, 200)

        # Check for demo-specific elements
        self.assertContains(response, 'DEMO MODE')
        self.assertContains(response, 'demo-notice')
        self.assertContains(
            response, 'sessionStorage.removeItem'
        )  # JS for clearing storage
        self.assertContains(response, 'Login for Full Version')
        self.assertContains(response, '/register/')
        self.assertContains(response, '/login/')
        self.assertContains(response, 'New Chat')  # New button for language selection

    def test_demo_chat_redirects_to_language_selection(self) -> None:
        """Test that demo chat redirects to language selection when no language provided."""
        response = self.client.get(reverse('demo_chat'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('demo_language_selection'))

    def test_demo_chat_redirects_on_invalid_language(self) -> None:
        """Test that demo chat redirects to language selection for invalid language."""
        response = self.client.get(reverse('demo_chat') + '?language=invalid')
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('demo_language_selection'))

    def test_demo_language_selection_accessible(self) -> None:
        """Test that demo language selection is accessible without authentication."""
        response = self.client.get(reverse('demo_language_selection'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose Language - Demo')
        self.assertContains(response, 'DEMO MODE')
        self.assertContains(response, 'Start Demo Conversation')

    def test_demo_language_selection_contains_languages(self) -> None:
        """Test that demo language selection contains expected language options."""
        response = self.client.get(reverse('demo_language_selection'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'English')
        self.assertContains(response, 'Spanish')
        self.assertContains(response, 'German')
        self.assertContains(response, 'Español')
        self.assertContains(response, 'Deutsch')
        # Check for grammar analysis section
        self.assertContains(response, 'Grammar Analysis Language')

    def test_demo_chat_with_different_languages(self) -> None:
        """Test demo chat works with different language combinations."""
        # Test Spanish conversation with English grammar analysis
        response = self.client.get(
            reverse('demo_chat') + '?language=es&analysis_language=en'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['language'], 'es')
        self.assertEqual(response.context['analysis_language'], 'en')

        # Test German conversation with German grammar analysis
        response = self.client.get(
            reverse('demo_chat') + '?language=de&analysis_language=de'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['language'], 'de')
        self.assertEqual(response.context['analysis_language'], 'de')

    def test_demo_chat_defaults_analysis_language(self) -> None:
        """Test that demo chat defaults analysis language to English if not provided."""
        response = self.client.get(reverse('demo_chat') + '?language=es')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['language'], 'es')
        self.assertEqual(response.context['analysis_language'], 'en')

    def test_demo_mode_javascript_functionality(self) -> None:
        """Test that demo mode template includes expected JavaScript functionality."""
        response = self.client.get(reverse('demo_chat') + '?language=en')
        self.assertEqual(response.status_code, 200)

        # Check for session storage JavaScript
        self.assertContains(response, 'sessionStorage.removeItem')
        self.assertContains(response, 'demo-messages')
        self.assertContains(response, '/demo/send/')
        self.assertContains(response, 'saveMessage')
        self.assertContains(response, 'loadSavedMessages')

    @patch('chat.views.ai_service')
    def test_demo_send_message_json_response_format(self, mock_ai_service: Any) -> None:
        """Test that demo send message returns properly formatted JSON."""
        # Mock AI service responses for async methods
        mock_ai_service.generate_chat_response = AsyncMock(
            return_value="Test AI response"
        )
        mock_ai_service.analyze_grammar = AsyncMock(return_value="Good grammar!")

        # Get CSRF token first
        response = self.client.get(reverse('demo_chat') + '?language=en')
        csrf_token = response.cookies['csrftoken'].value

        response = self.client.post(
            reverse('demo_send_message'),
            {'message': 'Test message', 'csrfmiddlewaretoken': csrf_token},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        data = response.json()

        # Verify all expected fields are present
        expected_fields = ['message', 'response', 'grammar_analysis', 'timestamp']
        for field in expected_fields:
            self.assertIn(field, data, f"Field '{field}' missing from response")

        # Verify field types and values
        self.assertIsInstance(data['message'], str)
        self.assertIsInstance(data['response'], str)
        self.assertIsInstance(data['grammar_analysis'], str)
        self.assertIsInstance(data['timestamp'], str)

        self.assertEqual(data['message'], 'Test message')
        self.assertEqual(data['response'], 'Test AI response')
        self.assertEqual(data['grammar_analysis'], 'Good grammar!')

        # Verify async methods were called
        mock_ai_service.generate_chat_response.assert_called_once_with(
            'Test message', 'en', []
        )
        mock_ai_service.analyze_grammar.assert_called_once_with('Test message', 'en')

    def test_demo_mode_csrf_protection(self) -> None:
        """Test that demo mode still uses CSRF protection."""
        # POST without CSRF token should fail
        # Use a client that enforces CSRF checks
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse('demo_send_message'), {'message': 'Test message'}
        )

        # Should get CSRF error (403) or 500 if there's an exception
        self.assertIn(response.status_code, [403, 500])


class DemoModeIntegrationTestCase(TestCase):
    """Integration tests for demo mode."""

    def setUp(self) -> None:
        """Set up test client."""
        self.client = Client()

    def test_demo_mode_workflow(self) -> None:
        """Test complete demo mode workflow."""
        # 1. Access demo page with language
        response = self.client.get(reverse('demo_chat') + '?language=en')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DEMO MODE')

        # 2. Try to send message without CSRF token (should fail)
        # Use a fresh client to avoid automatic CSRF token handling
        fresh_client = Client(enforce_csrf_checks=True)
        response = fresh_client.post(
            reverse('demo_send_message'), {'message': 'Hello!'}
        )
        self.assertIn(response.status_code, [403, 500])  # CSRF failure expected

        # 3. Get CSRF token and send message with proper token
        response = self.client.get(reverse('demo_chat') + '?language=en')
        csrf_token = response.cookies['csrftoken'].value

        with patch('chat.views.ai_service') as mock_ai_service:
            mock_ai_service.generate_chat_response = AsyncMock(
                return_value="Demo response"
            )
            mock_ai_service.analyze_grammar = AsyncMock(return_value="Good grammar!")

            response = self.client.post(
                reverse('demo_send_message'),
                {'message': 'Hello demo!', 'csrfmiddlewaretoken': csrf_token},
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['message'], 'Hello demo!')
            self.assertEqual(data['response'], 'Demo response')

    def test_demo_mode_vs_regular_mode_isolation(self) -> None:
        """Test that demo mode is isolated from regular chat functionality."""
        # Create a user and conversation for regular mode
        user = User.objects.create_user(username='testuser', password='testpass')
        from chat.models import Conversation, ChatMessage

        conversation = Conversation.objects.create(user=user, title='Test Conversation')
        ChatMessage.objects.create(
            conversation=conversation,
            message='Regular chat message',
            response='Regular chat response',
        )

        # Verify regular data exists
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(ChatMessage.objects.count(), 1)

        # Use demo mode
        response = self.client.get(reverse('demo_chat') + '?language=en')
        self.assertEqual(response.status_code, 200)

        # Demo mode shouldn't affect regular chat data
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(ChatMessage.objects.count(), 1)

        # Send demo message
        with patch('chat.views.ai_service') as mock_ai_service:
            mock_ai_service.generate_chat_response = AsyncMock(
                return_value="Demo response"
            )
            mock_ai_service.analyze_grammar = AsyncMock(return_value="Good grammar!")

            csrf_token = response.cookies['csrftoken'].value
            response = self.client.post(
                reverse('demo_send_message'),
                {'message': 'Demo message', 'csrfmiddlewaretoken': csrf_token},
            )
            self.assertEqual(response.status_code, 200)

        # Regular data should remain unchanged
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(ChatMessage.objects.count(), 1)

        # Verify the existing message is still there
        msg = ChatMessage.objects.first()
        self.assertEqual(msg.message, 'Regular chat message')
        self.assertEqual(msg.response, 'Regular chat response')
