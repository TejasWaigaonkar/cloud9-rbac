import logging

from django.db import DatabaseError, connection, transaction
from django.http import JsonResponse


@transaction.non_atomic_requests
def health(request):
    return JsonResponse({"status": "ok"})


@transaction.non_atomic_requests
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        logging.getLogger(__name__).warning("Database readiness check failed")
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready"})
