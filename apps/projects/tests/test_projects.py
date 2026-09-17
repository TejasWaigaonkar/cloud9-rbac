import pytest
from django.contrib.auth.models import Permission, User
from rest_framework.test import APIClient

from apps.projects.models import Project

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "method,code,status", [("get", "view_project", 200), ("post", "add_project", 201)]
)
def test_collection_permissions(method, code, status):
    user = User.objects.create_user(username="member")
    client = APIClient()
    client.force_authenticate(user)
    assert getattr(client, method)("/api/projects/", {"name": "Example"}).status_code == 403
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="projects", codename=code)
    )
    assert getattr(client, method)("/api/projects/", {"name": "Example"}).status_code == status


@pytest.mark.parametrize(
    "method,code,status", [("patch", "change_project", 200), ("delete", "delete_project", 204)]
)
def test_detail_permissions(method, code, status):
    user = User.objects.create_user(username="member")
    project = Project.objects.create(name="Example")
    client = APIClient()
    client.force_authenticate(user)
    endpoint = f"/api/projects/{project.pk}/"
    assert getattr(client, method)(endpoint, {"name": "Edited"}).status_code == 403
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="projects", codename=code)
    )
    assert getattr(client, method)(endpoint, {"name": "Edited"}).status_code == status


def test_publish_requires_separate_permission():
    user = User.objects.create_user(username="member")
    user.user_permissions.add(Permission.objects.get(codename="change_project"))
    project = Project.objects.create(name="Example")
    client = APIClient()
    client.force_authenticate(user)
    assert client.patch(f"/api/projects/{project.pk}/", {"published": True}).status_code == 200
    project.refresh_from_db()
    assert not project.published
    endpoint = f"/api/projects/{project.pk}/publish/"
    assert client.post(endpoint).status_code == 403
    user.user_permissions.add(Permission.objects.get(codename="publish_project"))
    assert client.post(endpoint).status_code == 200
    project.refresh_from_db()
    assert project.published


def test_health_and_readiness():
    from unittest.mock import patch

    from django.db import OperationalError

    client = APIClient()
    assert client.get("/health/").status_code == 200
    assert client.get("/ready/").status_code == 200
    with patch(
        "config.health.connection.cursor", side_effect=OperationalError("private connection info")
    ):
        response = client.get("/ready/")
    assert response.status_code == 503
    assert b"private" not in response.content
