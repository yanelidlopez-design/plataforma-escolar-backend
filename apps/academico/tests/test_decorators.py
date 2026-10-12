"""
Tests for webhook security decorator.
"""
import pytest
from django.test import RequestFactory
from rest_framework.test import APIRequestFactory
from apps.academico.decorators import validate_webhook_signature
from django.conf import settings
from rest_framework.response import Response


@pytest.mark.django_db
class TestWebhookDecorator:
    """Test suite for webhook signature validation decorator."""

    def test_valid_token_accepts_request(self):
        """Test that requests with valid token are accepted."""
        # Mock the settings to have a token
        original_token = getattr(settings, 'WEBHOOK_SECRET_TOKEN', '')
        settings.WEBHOOK_SECRET_TOKEN = 'test_secret_token_123'

        factory = APIRequestFactory()
        request = factory.post(
            '/api/academico/webhook-google-forms/',
            {'test': 'data'},
            HTTP_X_WEBHOOK_TOKEN='test_secret_token_123'
        )

        # Create a dummy view function
        @validate_webhook_signature
        def dummy_view(request):
            return Response({'success': True})

        response = dummy_view(request)
        assert response.status_code == 200
        assert response.data == {'success': True}

        # Restore original token
        settings.WEBHOOK_SECRET_TOKEN = original_token

    def test_missing_token_rejects_request(self):
        """Test that requests without token are rejected with 403."""
        original_token = getattr(settings, 'WEBHOOK_SECRET_TOKEN', '')
        settings.WEBHOOK_SECRET_TOKEN = 'test_secret_token_123'

        factory = APIRequestFactory()
        request = factory.post(
            '/api/academico/webhook-google-forms/',
            {'test': 'data'}
        )

        @validate_webhook_signature
        def dummy_view(request):
            return Response({'success': True})

        response = dummy_view(request)
        assert response.status_code == 403
        assert 'error' in response.data

        settings.WEBHOOK_SECRET_TOKEN = original_token

    def test_invalid_token_rejects_request(self):
        """Test that requests with invalid token are rejected with 403."""
        original_token = getattr(settings, 'WEBHOOK_SECRET_TOKEN', '')
        settings.WEBHOOK_SECRET_TOKEN = 'test_secret_token_123'

        factory = APIRequestFactory()
        request = factory.post(
            '/api/academico/webhook-google-forms/',
            {'test': 'data'},
            HTTP_X_WEBHOOK_TOKEN='wrong_token'
        )

        @validate_webhook_signature
        def dummy_view(request):
            return Response({'success': True})

        response = dummy_view(request)
        assert response.status_code == 403
        assert 'error' in response.data

        settings.WEBHOOK_SECRET_TOKEN = original_token

    def test_no_token_configured_rejects_all(self):
        """Test that when no token is configured, all requests are rejected."""
        original_token = getattr(settings, 'WEBHOOK_SECRET_TOKEN', '')
        settings.WEBHOOK_SECRET_TOKEN = ''

        factory = APIRequestFactory()
        request = factory.post(
            '/api/academico/webhook-google-forms/',
            {'test': 'data'},
            HTTP_X_WEBHOOK_TOKEN='any_token'
        )

        @validate_webhook_signature
        def dummy_view(request):
            return Response({'success': True})

        response = dummy_view(request)
        assert response.status_code == 403
        assert 'Webhook not configured' in response.data['error']

        settings.WEBHOOK_SECRET_TOKEN = original_token
