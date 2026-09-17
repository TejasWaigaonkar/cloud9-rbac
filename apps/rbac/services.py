from django.contrib.auth.models import Permission
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import UserRole

# Only this namespace is editable at runtime. Model/declared permissions stay immutable.
CUSTOM_PREFIX = "custom_"


def permission_code(permission):
    return f"{permission.content_type.app_label}.{permission.codename}"


def require_grant_authority(actor, permissions):
    permissions = list(permissions)
    if actor.is_superuser:
        return
    owned = actor.get_all_permissions()
    for permission in permissions:
        code = permission_code(permission)
        if permission.content_type.app_label in {
            "auth",
            "admin",
            "contenttypes",
            "sessions",
            "rbac",
        }:
            raise PermissionDenied("Only a superuser can delegate administrative permissions.")
        if code not in owned:
            raise PermissionDenied("You may only delegate permissions you currently hold.")


def editable_role(actor, role):
    if role.is_system:
        raise PermissionDenied("System roles are immutable; use a reviewed data migration.")
    if UserRole.objects.filter(user=actor, role=role).exists():
        raise PermissionDenied("You cannot modify a role assigned to yourself.")
    require_grant_authority(actor, role.permissions.select_related("content_type").all())


def assignment_target(actor, target):
    if actor.pk == target.pk:
        raise PermissionDenied("Self-assignment and self-revocation are forbidden.")
    if not target.is_active:
        raise ValidationError("Target user is inactive.")
    if (target.is_staff or target.is_superuser) and not actor.is_superuser:
        raise PermissionDenied("Only superusers may change staff or superuser assignments.")


def editable_permission(permission):
    if permission.content_type.app_label != "projects" or not permission.codename.startswith(
        CUSTOM_PREFIX
    ):
        raise PermissionDenied("Generated and application-declared permissions are protected.")


def lock_administration():
    # Serialize all API RBAC writes, including privilege checks, across workers.
    # This stable, migration-created permission is never runtime-editable.
    return Permission.objects.select_for_update().get(
        content_type__app_label="rbac", content_type__model="role", codename="manage_rbac"
    )
