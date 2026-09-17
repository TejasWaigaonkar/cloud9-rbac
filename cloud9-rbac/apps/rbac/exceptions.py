from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler as drf_handler


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(getattr(exc, "message_dict", None) or exc.messages)
    elif isinstance(exc, ProtectedError):
        exc = ValidationError("Object is still referenced; remove its mappings first.")
    elif isinstance(exc, IntegrityError):
        exc = ValidationError("This operation conflicts with an existing record.")
    response = drf_handler(exc, context)
    if response is not None:
        response.data = {"error": {"status": response.status_code, "details": response.data}}
    return response
