import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.rbac.backends import RBACBackend
from apps.rbac.models import Role, RolePermission, UserRole

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("field,value", [("name", "editor"), ("code", "EDITOR")])
def test_case_insensitive_role_uniqueness(role, field, value):
    data = {"name": "Other", "code": "other", field: value}
    with pytest.raises(ValidationError):
        Role.objects.create(**data)


def test_unique_mappings(role, user, permission):
    with pytest.raises(IntegrityError), transaction.atomic():
        RolePermission.objects.create(role=role, permission=permission)
    UserRole.objects.create(user=user, role=role)
    with pytest.raises(IntegrityError), transaction.atomic():
        UserRole.objects.create(user=user, role=role)


def test_three_sources_and_immediate_revocation(role, user, permission, django_assert_num_queries):
    UserRole.objects.create(user=user, role=role)
    group = Group.objects.create(name="Readers")
    group.permissions.add(permission)
    user.groups.add(group)
    user.user_permissions.add(permission)
    with django_assert_num_queries(1):
        assert user.get_all_permissions() == {"projects.view_project"}
    UserRole.objects.filter(user=user).delete()
    assert user.has_perm("projects.view_project")
    user.groups.remove(group)
    assert user.has_perm("projects.view_project")
    user.user_permissions.remove(permission)
    assert not user.has_perm("projects.view_project")


def test_inactive_role_and_user(role, user, permission):
    link = UserRole.objects.create(user=user, role=role)
    role.is_active = False
    role.save()
    assert not user.has_perm("projects.view_project")
    with pytest.raises(ValidationError):
        link.full_clean()
    user.user_permissions.add(permission)
    user.is_active = False
    user.save()
    assert not user.get_all_permissions()


def test_multiple_roles_preserve_grant(role, user, permission):
    other = Role.objects.create(name="Second", code="second")
    RolePermission.objects.create(role=other, permission=permission)
    UserRole.objects.create(user=user, role=role)
    UserRole.objects.create(user=user, role=other)
    role.delete()
    assert user.has_perm("projects.view_project")


def test_system_role_model_protection():
    role = Role.objects.create(name="System", code="system", is_system=True)
    role.is_active = False
    with pytest.raises(ValidationError):
        role.save()
    with pytest.raises(ValidationError):
        Role.objects.filter(pk=role.pk).delete()


def test_backend_native_interfaces(user, permission):
    backend = RBACBackend()
    assert backend.get_all_permissions(AnonymousUser()) == set()
    assert backend.get_all_permissions(user, obj=object()) == set()
    user.user_permissions.add(permission)
    assert backend.get_user_permissions(user) == {"projects.view_project"}
    assert user.has_module_perms("projects")
    assert not user.has_perm("projects.view_project", obj=object())


def test_permission_protected_when_mapped(role, permission):
    from django.db.models.deletion import ProtectedError

    with pytest.raises(ProtectedError):
        permission.delete()


def test_superuser_and_inactive_superuser(admin_user):
    assert admin_user.has_perm("projects.view_project")
    admin_user.is_active = False
    admin_user.save()
    assert not admin_user.has_perm("projects.view_project")
    assert not admin_user.get_all_permissions()
