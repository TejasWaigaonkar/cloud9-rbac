from contextlib import contextmanager
from contextvars import ContextVar

current_actor = ContextVar("audit_actor", default=None)


@contextmanager
def actor_context(actor):
    token = current_actor.set(actor if actor and actor.is_authenticated else None)
    try:
        yield
    finally:
        current_actor.reset(token)


class ActorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in {"/health/", "/ready/"}:
            with actor_context(None):
                return self.get_response(request)
        with actor_context(request.user):
            return self.get_response(request)


def record(action, entity, entity_id, before=None, after=None):
    from .models import AuditLog

    AuditLog.objects.create(
        actor=current_actor.get(),
        action=action,
        entity=entity,
        entity_id=str(entity_id),
        before=before or {},
        after=after or {},
    )
