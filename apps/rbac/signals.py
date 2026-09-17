from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from .audit import record
from .models import Role, RolePermission, UserRole

TRACKED = {
    Role: ["name", "code", "description", "is_active", "is_system"],
    RolePermission: ["role_id", "permission_id"],
    UserRole: ["user_id", "role_id", "assigned_by_id"],
    Group: ["name"],
    Permission: ["name", "codename", "content_type_id"],
    User: ["username", "is_active", "is_staff", "is_superuser"],
}


def snapshot(instance):
    return {field: getattr(instance, field) for field in TRACKED[type(instance)]}


@receiver(pre_save)
def capture_before(sender, instance, **kwargs):
    if sender in TRACKED:
        old = sender.objects.filter(pk=instance.pk).first() if instance.pk else None
        instance._audit_before = snapshot(old) if old else {}


@receiver(post_save)
def log_save(sender, instance, created, raw=False, **kwargs):
    if sender in TRACKED and not raw:
        before = getattr(instance, "_audit_before", {})
        after = snapshot(instance)
        if before != after:
            record(
                "create" if created else "update",
                sender._meta.label_lower,
                instance.pk,
                before,
                after,
            )


@receiver(pre_delete, sender=Role)
def protect_system_delete(sender, instance, **kwargs):
    if instance.is_system:
        raise ValidationError("System roles cannot be deleted.")


@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if sender in TRACKED:
        record("delete", sender._meta.label_lower, instance.pk, snapshot(instance), {})


@receiver(m2m_changed)
def log_native_mapping(sender, instance, action, reverse, model, pk_set, **kwargs):
    fields = {
        User.groups.through: "groups",
        User.user_permissions.through: "user_permissions",
        Group.permissions.through: "permissions",
    }
    if sender not in fields:
        return
    # Capture exact IDs for clear(), including reverse manager operations.
    if action == "pre_clear":
        if reverse:
            relation = "user_set" if sender != Group.permissions.through else "group_set"
        else:
            relation = fields[sender]
        instance._audit_cleared = list(getattr(instance, relation).values_list("pk", flat=True))
    if action.startswith("post_"):
        ids = sorted(pk_set) if pk_set is not None else getattr(instance, "_audit_cleared", [])
        record(
            action,
            instance._meta.label_lower,
            instance.pk,
            {"ids": ids} if action in ["post_remove", "post_clear"] else {},
            {"relation": fields[sender], "reverse": reverse, "ids": ids},
        )
