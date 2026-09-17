from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.exceptions import APIException

from .models import AuditLog, Role, RolePermission, UserRole
from .services import assignment_target, editable_role, lock_administration, require_grant_authority


class SuperuserOnly:
    """Native auth editing is intentionally restricted to trusted superusers."""

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def get_actions(self, request):
        return {}  # No bulk deletion bypassing object policy.

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        with transaction.atomic():
            if request.method == "POST" and request.user.is_superuser:
                lock_administration()
            return super().changeform_view(request, object_id, form_url, extra_context)

    def delete_view(self, request, object_id, extra_context=None):
        with transaction.atomic():
            if request.method == "POST" and request.user.is_superuser:
                lock_administration()
            return super().delete_view(request, object_id, extra_context)

    def get_form(self, request, obj=None, **kwargs):
        base_form = super().get_form(request, obj, **kwargs)

        class PolicyForm(base_form):
            def clean(self):
                data = super().clean()
                try:
                    if self._meta.model is UserRole and data.get("user") and data.get("role"):
                        assignment_target(request.user, data["user"])
                    elif self._meta.model is RolePermission and data.get("role"):
                        editable_role(request.user, data["role"])
                        if not data["role"].is_active:
                            raise ValidationError("Inactive roles cannot receive permissions.")
                except APIException as exc:
                    raise ValidationError(str(exc.detail)) from exc
                return data

        return PolicyForm


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class SecureUserAdmin(SuperuserOnly, UserAdmin):
    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (
            obj is None or obj.pk != request.user.pk
        )

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (
            obj is None or obj.pk != request.user.pk
        )


@admin.register(Group)
class SecureGroupAdmin(SuperuserOnly, GroupAdmin):
    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (
            obj is None or not request.user.groups.filter(pk=obj.pk).exists()
        )

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(Role)
class RoleAdmin(SuperuserOnly, admin.ModelAdmin):
    list_display = ["name", "code", "is_active", "is_system"]
    list_filter = ["is_active", "is_system"]
    search_fields = ["name", "code"]
    readonly_fields = ["is_system", "created_at", "updated_at"]

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (
            obj is None
            or (not obj.is_system and not obj.user_links.filter(user=request.user).exists())
        )

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(RolePermission)
class RolePermissionAdmin(SuperuserOnly, admin.ModelAdmin):
    list_display = ["role", "permission", "created_at"]
    list_select_related = ["role", "permission"]
    autocomplete_fields = ["role"]

    def has_change_permission(self, request, obj=None):
        return obj is None and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (
            obj is None
            or (
                not obj.role.is_system
                and not obj.role.user_links.filter(user=request.user).exists()
            )
        )

    def save_model(self, request, obj, form, change):
        editable_role(request.user, obj.role)
        if not obj.role.is_active:
            raise ValidationError("Inactive roles cannot receive permissions.")
        require_grant_authority(request.user, [obj.permission])
        super().save_model(request, obj, form, change)


@admin.register(UserRole)
class UserRoleAdmin(SuperuserOnly, admin.ModelAdmin):
    list_display = ["user", "role", "assigned_by", "created_at"]
    list_select_related = ["user", "role", "assigned_by"]
    readonly_fields = ["assigned_by", "created_at"]
    autocomplete_fields = ["user", "role"]

    def has_change_permission(self, request, obj=None):
        return obj is None and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (
            obj is None or obj.user_id != request.user.pk
        )

    def save_model(self, request, obj, form, change):
        assignment_target(request.user, obj.user)
        obj.full_clean()
        obj.assigned_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Permission)
class PermissionAdmin(SuperuserOnly, admin.ModelAdmin):
    list_display = ["name", "codename", "content_type"]
    search_fields = ["name", "codename"]
    list_select_related = ["content_type"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(PermissionAdmin):
    list_display = ["created_at", "actor", "action", "entity", "entity_id"]
    list_select_related = ["actor"]
    search_fields = ["entity", "entity_id", "action"]
    list_filter = ["action", "entity"]
