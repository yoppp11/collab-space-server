"""
Custom Exception Handler for DRF
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.http import Http404
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error responses.
    """
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        custom_response_data = {
            'success': False,
            'error': {
                'code': response.status_code,
                'message': get_error_message(response.data),
                'details': response.data if isinstance(response.data, dict) else {'detail': response.data}
            }
        }
        response.data = custom_response_data
        return response

    # Handle Django's ValidationError
    if isinstance(exc, ValidationError):
        return Response(
            {
                'success': False,
                'error': {
                    'code': status.HTTP_400_BAD_REQUEST,
                    'message': 'Validation Error',
                    'details': exc.message_dict if hasattr(exc, 'message_dict') else {'detail': str(exc)}
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Handle 404 errors
    if isinstance(exc, Http404):
        return Response(
            {
                'success': False,
                'error': {
                    'code': status.HTTP_404_NOT_FOUND,
                    'message': 'Resource not found',
                    'details': {'detail': str(exc)}
                }
            },
            status=status.HTTP_404_NOT_FOUND
        )

    # Log unexpected exceptions
    logger.exception(f"Unhandled exception: {exc}")
    
    return Response(
        {
            'success': False,
            'error': {
                'code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'message': 'An unexpected error occurred',
                'details': {}
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def get_error_message(data):
    """Extract a human-readable error message from DRF error data."""
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        if 'non_field_errors' in data:
            return str(data['non_field_errors'][0])
        # Return first error message found
        for key, value in data.items():
            if isinstance(value, list) and value:
                return f"{key}: {value[0]}"
            return f"{key}: {value}"
    if isinstance(data, list) and data:
        return str(data[0])
    return str(data)


class CollaborationException(Exception):
    """Base exception for collaboration-related errors."""
    pass


class ConflictError(CollaborationException):
    """Raised when there's a conflict during concurrent editing."""
    pass


class PermissionDeniedError(CollaborationException):
    """Raised when user doesn't have required permissions."""
    pass


class RateLimitExceeded(CollaborationException):
    """Raised when rate limit is exceeded."""
    pass


class WebSocketError(CollaborationException):
    """Raised for WebSocket-related errors."""
    pass
