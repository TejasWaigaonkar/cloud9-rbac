import pytest
from django.contrib.auth.models import Group, Permission, User
from django.core.management import CommandError, call_command
from rest_framework.test import APIClient

from apps.rbac.models import AuditLog, Role, RolePermission, UserRole

pytestmark = pytest.mark.django_db


def test_seed_idempotent_and_no_default_password(settings):
    settings.DEBUG = True
    call_command("seed_demo")
    counts = (
        Role.objects.count(),
        User.objects.count(),
        Group.objects.count(),
        UserRole.objects.count(),
    )
    call_command("seed_demo")
    assert counts == (
        Role.objects.count(),
        User.objects.count(),
        Group.objects.count(),
        UserRole.objects.count(),
    )
    assert not User.objects.get(username="demo_editor").has_usable_password()
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_demo")


def test_admin_assignment_and_revocation_audit(admin_user, user, role):
    client = APIClient()
    client.force_login(admin_user)
    response = client.post(
        "/admin/rbac/userrole/add/", {"user": user.pk, "role": role.pk, "_save": "Save"}
    )
    assert response.status_code == 302
    link = UserRole.objects.get(user=user, role=role)
    assert link.assigned_by == admin_user
    assert AuditLog.objects.filter(
        actor=admin_user, entity="rbac.userrole", action="create"
    ).exists()
    assert (
        client.post(f"/admin/rbac/userrole/{link.pk}/delete/", {"post": "yes"}).status_code == 302
    )
    assert not user.has_perm("projects.view_project")
    assert AuditLog.objects.filter(
        actor=admin_user, entity="rbac.userrole", action="delete"
    ).exists()


def test_admin_self_assignment_is_form_error(admin_user, role):
    client = APIClient()
    client.force_login(admin_user)
    response = client.post(
        "/admin/rbac/userrole/add/", {"user": admin_user.pk, "role": role.pk, "_save": "Save"}
    )
    assert response.status_code == 200
    assert b"Self-assignment" in response.content
    assert not UserRole.objects.filter(user=admin_user).exists()


def test_admin_system_mapping_is_form_error(admin_user, permission):
    client = APIClient()
    client.force_login(admin_user)
    role = Role.objects.create(name="System", code="system", is_system=True)
    response = client.post(
        "/admin/rbac/rolepermission/add/",
        {"role": role.pk, "permission": permission.pk, "_save": "Save"},
    )
    assert response.status_code == 200
    assert not RolePermission.objects.filter(role=role).exists()


def test_admin_inactive_mapping_is_form_error(admin_user, role):
    client = APIClient()
    client.force_login(admin_user)
    role.is_active = False
    role.save()
    permission = Permission.objects.get(codename="delete_project")
    response = client.post(
        "/admin/rbac/rolepermission/add/",
        {"role": role.pk, "permission": permission.pk, "_save": "Save"},
    )
    assert response.status_code == 200
    assert not RolePermission.objects.filter(role=role, permission=permission).exists()


def test_admin_mapping_and_role_changes_audited(admin_user, role):
    client = APIClient()
    client.force_login(admin_user)
    permission = Permission.objects.get(codename="delete_project")
    assert (
        client.post(
            "/admin/rbac/rolepermission/add/",
            {"role": role.pk, "permission": permission.pk, "_save": "Save"},
        ).status_code
        == 302
    )
    assert AuditLog.objects.filter(
        actor=admin_user, entity="rbac.rolepermission", action="create"
    ).exists()
    assert (
        client.post(
            f"/admin/rbac/role/{role.pk}/change/",
            {"name": role.name, "code": role.code, "description": "Updated", "_save": "Save"},
        ).status_code
        == 302
    )
    role.refresh_from_db()
    assert not role.is_active
    assert AuditLog.objects.filter(
        actor=admin_user, entity="rbac.role", after__is_active=False
    ).exists()


def test_admin_native_membership_audit(admin_user, user, permission):
    group = Group.objects.create(name="Readers")
    client = APIClient()
    client.force_login(admin_user)
    response = client.post(
        f"/admin/auth/user/{user.pk}/change/",
        {
            "username": user.username,
            "is_active": "on",
            "groups": [group.pk],
            "user_permissions": [permission.pk],
            "date_joined_0": "2026-09-16",
            "date_joined_1": "12:00:00",
            "_save": "Save",
        },
    )
    assert response.status_code == 302
    assert user.groups.filter(pk=group.pk).exists()
    assert (
        AuditLog.objects.filter(
            actor=admin_user, entity="auth.user", entity_id=str(user.pk), action="post_add"
        ).count()
        == 2
    )
