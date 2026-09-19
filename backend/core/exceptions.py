"""A single error envelope for every ARC API response.

DRF's default error body changes shape depending on what was raised: a string
for one thing, a list for another, a field-keyed dict for a third. The
frontend interceptor should not have to branch on that, so every handled
error leaves here as::

    {"error": {"code": "invalid", "message": "...", "fields": {...}}}
"""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.serializers import as_serializer_error
from rest_framework.views import exception_handler as drf_exception_handler

GENERIC_MESSAGES = {
    400: 'The submitted data is invalid.',
    401: 'Authentication credentials were not provided or are no longer valid.',
    403: 'You do not have permission to perform this action.',
    404: 'The requested resource was not found.',
    405: 'That method is not allowed on this endpoint.',
    429: 'Too many requests. Please slow down.',
}


def _stringify(detail):
    """Recursively convert DRF's ErrorDetail tree into plain strings."""
    if isinstance(detail, dict):
        return {key: _stringify(value) for key, value in detail.items()}
    if isinstance(detail, (list, tuple)):
        return [_stringify(item) for item in detail]
    return str(detail)


def _code_for(exc, status_code):
    if isinstance(exc, Http404):
        return 'not_found'
    if isinstance(exc, DjangoPermissionDenied):
        return 'permission_denied'
    codes = getattr(exc, 'get_codes', None)
    if callable(codes):
        resolved = codes()
        if isinstance(resolved, str):
            return resolved
    return getattr(exc, 'default_code', None) or f'http_{status_code}'


def arc_exception_handler(exc, context):
    # Model.clean() and the planning services raise Django's ValidationError,
    # which DRF would otherwise let escape as a 500.
    if isinstance(exc, DjangoValidationError):
        exc = DRFValidationError(detail=as_serializer_error(exc))

    response = drf_exception_handler(exc, context)
    if response is None:
        # Genuinely unexpected; let Django's 500 handling and logging run.
        return None

    fields = {}
    if isinstance(exc, DRFValidationError):
        detail = _stringify(exc.detail)
        fields = detail if isinstance(detail, dict) else {'non_field_errors': detail}
        message = GENERIC_MESSAGES[400]
    else:
        detail = getattr(exc, 'detail', None)
        message = (
            str(detail)
            if isinstance(detail, str) or detail.__class__.__name__ == 'ErrorDetail'
            else GENERIC_MESSAGES.get(response.status_code, 'Request failed.')
        )

    response.data = {
        'error': {
            'code': _code_for(exc, response.status_code),
            'message': message,
            'fields': fields,
        }
    }
    return response
