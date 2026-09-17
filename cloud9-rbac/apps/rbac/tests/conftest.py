import pytest
from django.contrib.auth.models import Permission, User
from rest_framework.test import APIClient

from apps.rbac.models import Role, RolePermission


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(username="root", password="Root-test-password-123")


@pytest.fixture
def user(db):
    return User.objects.create_user(username="normal", password="Normal-test-password-123")


@pytest.fixture
def client(admin_user):
    client = APIClient()
    client.force_authenticate(admin_user)
    return client


@pytest.fixture
def permission(db):
    return Permission.objects.get(content_type__app_label="projects", codename="view_project")


@pytest.fixture
def role(permission):
    role = Role.objects.create(name="Editor", code="editor")
    RolePermission.objects.create(role=role, permission=permission)
    return role
