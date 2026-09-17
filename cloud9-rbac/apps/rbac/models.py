from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, max_length=2000)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    permissions = models.ManyToManyField(
        Permission, through="RolePermission", related_name="rbac_roles"
    )

    class Meta:
        ordering = ["id"]
        permissions = [("manage_rbac", "Manage delegated RBAC administration")]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="role_name_ci_unique"),
            models.UniqueConstraint(Lower("code"), name="role_code_ci_unique"),
        ]

    def clean(self):
        if self.pk:
            old = Role.objects.filter(pk=self.pk).first()
            if old and old.is_system:
                fields = ["name", "code", "description", "is_active", "is_system"]
                if any(getattr(old, f) != getattr(self, f) for f in fields):
                    raise ValidationError(
                        "System roles are immutable; use a reviewed data migration."
                    )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.is_system:
            raise ValidationError("System roles cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permission_links")
    permission = models.ForeignKey(Permission, on_delete=models.PROTECT, related_name="role_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="unique_role_permission")
        ]


class UserRole(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="role_links"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_links")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="unique_user_role")]

    def clean(self):
        if not self.role.is_active or not self.user.is_active:
            raise ValidationError("Both user and role must be active.")


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    action = models.CharField(max_length=80)
    entity = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["entity", "entity_id"], name="audit_entity_idx")]
