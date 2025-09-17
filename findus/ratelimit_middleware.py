"""Middleware to handle rate limiting exceptions at the Django level."""

from typing import Callable, Optional

from django.http import HttpRequest, HttpResponse, JsonResponse
from django_ratelimit.exceptions import Ratelimited


class RateLimitMiddleware:
    """Middleware to catch and handle rate limit exceptions."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Initialize middleware with get_response callable."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process request through middleware."""
        response = self.get_response(request)
        return response

    def process_exception(
        self, request: HttpRequest, exception: Exception
    ) -> Optional[JsonResponse]:
        """Handle rate limit exceptions."""
        if isinstance(exception, Ratelimited):
            return JsonResponse(
                {
                    'error': 'Rate limit exceeded. Please wait before sending another message.'
                },
                status=429,
            )
        return None
