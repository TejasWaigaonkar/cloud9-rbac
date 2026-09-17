import pytest
from django.contrib.auth.models import Group, Permission, User
from rest_framework.test import APIClient

from apps.rbac.models import AuditLog, Role, UserRole

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("url", ["/api/roles/", "/api/permissions/", "/api/audit-logs/"])
def test_normal_user_denied_admin_endpoints(user, url):
    client = APIClient()
    client.force_authenticate(user)
    assert client.get(url).status_code == 403
    assert client.post(url, {"name": "Admin", "code": "admin"}).status_code == 403


def test_anonymous_denied():
    assert APIClient().get("/api/projects/").status_code == 401
    assert APIClient().post("/api/roles/", {}).status_code == 401


def test_self_assignment_blocked_even_for_superuser(client, role, admin_user):
    assert (
        client.post(f"/api/users/{admin_user.pk}/roles/", {"role_id": role.pk}).status_code == 403
    )
    assert not UserRole.objects.filter(user=admin_user).exists()


def test_cannot_edit_own_role(client, admin_user, role, permission):
    UserRole.objects.create(user=admin_user, role=role)
    assert client.patch(f"/api/roles/{role.pk}/", {"name": "Escalated"}).status_code == 403
    assert client.delete(f"/api/roles/{role.pk}/").status_code == 403
    assert client.delete(f"/api/roles/{role.pk}/permissions/{permission.pk}/").status_code == 403


def test_system_role_api_protection(client, permission):
    role = Role.objects.create(name="System", code="system", is_system=True)
    assert client.patch(f"/api/roles/{role.pk}/", {"is_active": False}).status_code == 403
    assert client.delete(f"/api/roles/{role.pk}/").status_code == 403
    assert (
        client.post(
            f"/api/roles/{role.pk}/permissions/", {"permission_id": permission.pk}
        ).status_code
        == 403
    )


def test_delegated_admin_limits(user, role, permission):
    user.user_permissions.add(Permission.objects.get(codename="manage_rbac"), permission)
    client = APIClient()
    client.force_authenticate(user)
    target = User.objects.create_user(username="target")
    assert client.post(f"/api/users/{target.pk}/roles/", {"role_id": role.pk}).status_code == 201
    deletion = Permission.objects.get(content_type__app_label="projects", codename="delete_project")
    assert (
        client.post(
            f"/api/roles/{role.pk}/permissions/", {"permission_id": deletion.pk}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/roles/{role.pk}/permissions/",
            {"permission_id": Permission.objects.get(codename="manage_rbac").pk},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/permissions/", {"name": "Export", "codename": "custom_export"}
        ).status_code
        == 403
    )
    assert client.post(f"/api/users/{user.pk}/roles/", {"role_id": role.pk}).status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "auth/user",
        "auth/group",
        "rbac/role",
        "rbac/userrole",
        "rbac/rolepermission",
        "auth/permission",
    ],
)
def test_manipulated_admin_post_blocked_for_staff(user, role, permission, path):
    user.is_staff = True
    user.save()
    # Even native model permissions do not unlock the hardened auth/RBAC admin.
    user.user_permissions.add(*Permission.objects.all())
    client = APIClient()
    client.force_login(user)
    response = client.post(
        f"/admin/{path}/add/",
        {
            "user": user.pk,
            "role": role.pk,
            "permission": permission.pk,
            "is_superuser": "on",
            "name": "Escalated",
        },
    )
    assert response.status_code == 403
    user.refresh_from_db()
    assert not user.is_superuser
    assert not UserRole.objects.filter(user=user).exists()


def test_nonstaff_cannot_access_admin(user):
    client = APIClient()
    client.force_login(user)
    assert (
        client.post(f"/admin/auth/user/{user.pk}/change/", {"is_superuser": "on"}).status_code
        == 302
    )


def test_session_csrf_enforced(admin_user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(admin_user)
    assert client.post("/api/roles/", {"name": "CSRF", "code": "csrf"}).status_code == 403


def test_admin_native_group_audit(admin_user, permission):
    client = APIClient()
    client.force_login(admin_user)
    response = client.post(
        "/admin/auth/group/add/",
        {"name": "Audited group", "permissions": [permission.pk], "_save": "Save"},
    )
    assert response.status_code == 302
    group = Group.objects.get(name="Audited group")
    assert AuditLog.objects.filter(
        actor=admin_user, entity="auth.group", entity_id=str(group.pk), action="post_add"
    ).exists()


def test_native_membership_clear_and_password_not_logged(user, permission):
    from apps.rbac.audit import actor_context

    with actor_context(user):
        group = Group.objects.create(name="Readers")
        user.groups.add(group)
        user.groups.clear()
        user.user_permissions.add(permission)
        user.set_password("never-record-this")
        user.save()
    log = AuditLog.objects.filter(
        action="post_clear", entity="auth.user", entity_id=str(user.pk)
    ).latest("id")
    assert log.before["ids"] == [group.pk]
    assert "password" not in str(list(AuditLog.objects.values("before", "after")))


def test_failed_write_does_not_create_audit(client, role, permission):
    before = AuditLog.objects.count()
    assert (
        client.post(
            f"/api/roles/{role.pk}/permissions/", {"permission_id": permission.pk}
        ).status_code
        == 400
    )
    assert AuditLog.objects.count() == before
