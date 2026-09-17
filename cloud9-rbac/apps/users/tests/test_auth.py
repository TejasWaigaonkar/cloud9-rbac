import pytest
from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_jwt_login_refresh_logout_and_audit():
    from apps.rbac.models import AuditLog

    cache.clear()
    user = User.objects.create_superuser(username="root", password="Strong-test-password-123")
    client = APIClient()
    response = client.post(
        "/api/auth/token/", {"username": "root", "password": "Strong-test-password-123"}
    )
    assert response.status_code == 200
    client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access"])
    role = client.post("/api/roles/", {"name": "JWT role", "code": "jwt-role"})
    assert role.status_code == 201
    assert AuditLog.objects.filter(
        actor=user, entity="rbac.role", entity_id=str(role.data["id"])
    ).exists()
    refreshed = client.post("/api/auth/refresh/", {"refresh": response.data["refresh"]})
    assert refreshed.status_code == 200
    assert (
        client.post("/api/auth/refresh/", {"refresh": response.data["refresh"]}).status_code == 401
    )
    assert (
        client.post("/api/auth/logout/", {"refresh": refreshed.data["refresh"]}).status_code == 200
    )
    assert (
        client.post("/api/auth/refresh/", {"refresh": refreshed.data["refresh"]}).status_code == 401
    )


def test_inactive_and_invalid_login():
    cache.clear()
    User.objects.create_user(username="inactive", password="Some-password-123", is_active=False)
    client = APIClient()
    assert (
        client.post(
            "/api/auth/token/", {"username": "inactive", "password": "Some-password-123"}
        ).status_code
        == 401
    )
    assert client.get("/api/projects/", HTTP_AUTHORIZATION="Bearer invalid").status_code == 401


def test_jwt_does_not_embed_stale_grants():
    cache.clear()
    user = User.objects.create_user(username="reader", password="Some-password-123")
    permission = Permission.objects.get(codename="view_project")
    user.user_permissions.add(permission)
    client = APIClient()
    token = client.post(
        "/api/auth/token/", {"username": "reader", "password": "Some-password-123"}
    ).data["access"]
    client.credentials(HTTP_AUTHORIZATION="Bearer " + token)
    assert client.get("/api/projects/").status_code == 200
    user.user_permissions.clear()
    assert client.get("/api/projects/").status_code == 403
