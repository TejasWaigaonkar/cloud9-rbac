import pytest
from django.contrib.auth.models import Group, Permission
from rest_framework.test import APIClient

from apps.rbac.models import AuditLog, Role

pytestmark = pytest.mark.django_db


def test_role_lifecycle(client):
    response = client.post("/api/roles/", {"name": "New", "code": "new"}, format="json")
    assert response.status_code == 201
    pk = response.data["id"]
    assert (
        client.patch(f"/api/roles/{pk}/", {"description": "Updated"}, format="json").status_code
        == 200
    )
    assert client.patch(f"/api/roles/{pk}/", {"is_active": False}, format="json").status_code == 200
    assert client.delete(f"/api/roles/{pk}/").status_code == 204


def test_role_validation_and_filters(client, role):
    assert client.post("/api/roles/", {"name": "editor", "code": "other"}).status_code == 400
    assert client.post("/api/roles/", {"name": "New", "code": "bad code"}).status_code == 400
    assert (
        client.post("/api/roles/", {"name": "New", "code": "new", "is_system": True}).status_code
        == 400
    )
    data = client.get("/api/roles/?search=Editor&is_active=true").data
    assert data["count"] == 1
    assert {"count", "next", "previous", "results"} <= data.keys()


def test_mapping_lifecycle(client, role, permission):
    endpoint = f"/api/roles/{role.pk}/permissions/"
    assert client.post(endpoint, {"permission_id": permission.pk}).status_code == 400
    assert client.delete(endpoint + f"{permission.pk}/").status_code == 204
    assert client.post(endpoint, {"permission_id": permission.pk}).status_code == 201
    assert client.post(endpoint, {"permission_id": 999999}).status_code == 400


def test_assignment_lifecycle(client, role, user):
    endpoint = f"/api/users/{user.pk}/roles/"
    assert client.post(endpoint, {"role_id": role.pk}).status_code == 201
    assert client.post(endpoint, {"role_id": role.pk}).status_code == 400
    assert client.get(endpoint).data["count"] == 1
    result = client.get(f"/api/users/{user.pk}/permissions/").data
    assert result["permissions"] == ["projects.view_project"]
    assert client.delete(endpoint + f"{role.pk}/").status_code == 204
    assert not user.has_perm("projects.view_project")


def test_inactive_assignment_rejected(client, role, user):
    role.is_active = False
    role.save()
    assert client.post(f"/api/users/{user.pk}/roles/", {"role_id": role.pk}).status_code == 400
    role.is_active = True
    role.save()
    user.is_active = False
    user.save()
    assert client.post(f"/api/users/{user.pk}/roles/", {"role_id": role.pk}).status_code == 400


def test_custom_permission_lifecycle(client):
    response = client.post("/api/permissions/", {"name": "Export", "codename": "custom_export"})
    assert response.status_code == 201
    pk = response.data["id"]
    assert response.data["code"] == "projects.custom_export"
    assert client.patch(f"/api/permissions/{pk}/", {"name": "Export projects"}).status_code == 200
    assert client.patch(f"/api/permissions/{pk}/", {"codename": "custom_other"}).status_code == 400
    assert client.delete(f"/api/permissions/{pk}/").status_code == 204


def test_permission_protection(client, permission):
    assert client.patch(f"/api/permissions/{permission.pk}/", {"name": "Oops"}).status_code == 403
    assert client.delete(f"/api/permissions/{permission.pk}/").status_code == 403
    assert (
        client.post("/api/permissions/", {"name": "Oops", "codename": "view_project"}).status_code
        == 400
    )
    assert (
        client.post(
            "/api/permissions/",
            {"name": "Oops", "codename": "custom_ok", "content_type": permission.content_type_id},
        ).status_code
        == 400
    )


@pytest.mark.parametrize("source", ["role", "group", "direct"])
def test_in_use_custom_permission_cannot_be_deleted(client, role, user, source):
    from apps.rbac.models import RolePermission

    response = client.post("/api/permissions/", {"name": "Export", "codename": "custom_export"})
    permission = Permission.objects.get(pk=response.data["id"])
    if source == "role":
        RolePermission.objects.create(role=role, permission=permission)
    elif source == "group":
        Group.objects.create(name="Exports").permissions.add(permission)
    else:
        user.user_permissions.add(permission)
    assert client.delete(f"/api/permissions/{permission.pk}/").status_code == 400


def test_audit_actor_and_readonly(client, admin_user):
    response = client.post("/api/roles/", {"name": "Audited", "code": "audited"})
    log = AuditLog.objects.get(
        entity="rbac.role", entity_id=str(response.data["id"]), action="create"
    )
    assert log.actor == admin_user
    assert log.after["name"] == "Audited"
    assert log.before == {}
    assert client.post("/api/audit-logs/", {}).status_code == 405


def test_self_access_and_other_privacy(user, admin_user):
    client = APIClient()
    client.force_authenticate(user)
    assert client.get(f"/api/users/{user.pk}/permissions/").status_code == 200
    assert client.get(f"/api/users/{admin_user.pk}/permissions/").status_code == 403


def test_role_list_query_bound(client, permission, django_assert_num_queries):
    from apps.rbac.models import RolePermission

    for index in range(15):
        role = Role.objects.create(name=f"Role {index}", code=f"role-{index}")
        RolePermission.objects.create(role=role, permission=permission)
    # Two nested transaction savepoint pairs + count + role query + permission prefetch.
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as queries:
        response = client.get("/api/roles/")
    assert response.status_code == 200
    selects = [q for q in queries if q["sql"].lstrip().upper().startswith("SELECT")]
    assert len(selects) <= 4


def test_missing_objects(client):
    assert client.get("/api/roles/999999/").status_code == 404
    assert client.post("/api/users/999999/roles/", {"role_id": 1}).status_code == 404
