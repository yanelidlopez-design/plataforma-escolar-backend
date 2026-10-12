import os
import hmac
from functools import wraps
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status


def validate_webhook_signature(view_func):
    """
    Decorator to validate webhook signature via X-Webhook-Token header.
    Uses constant-time comparison to prevent timing attacks.
    Returns 403 Forbidden if token is missing or invalid.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Get expected token from environment variable
        token_esperado = getattr(settings, 'WEBHOOK_SECRET_TOKEN', '') or ''

        # If no token is configured in environment, reject all requests
        if not token_esperado:
            return Response(
                {'error': 'Webhook not configured: No secret token set in environment'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get token from request header
        token_recibido = request.headers.get('X-Webhook-Token', '')

        # Use constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(
            token_recibido.encode('utf-8'),
            token_esperado.encode('utf-8')
        ):
            return Response(
                {'error': 'Invalid webhook signature: Token does not match'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Token is valid, proceed to the view
        return view_func(request, *args, **kwargs)

    return _wrapped_view
