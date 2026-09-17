from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission
from django.db.models import Q


class RBACBackend(ModelBackend):
    """No permission cache: revocations are visible on an existing User instance."""

    def get_all_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()
        permissions = Permission.objects.all()
        if not user_obj.is_superuser:
            permissions = permissions.filter(
                Q(user=user_obj)
                | Q(group__user=user_obj)
                | Q(rbac_roles__user_links__user=user_obj, rbac_roles__is_active=True)
            )
        return {
            f"{app}.{code}"
            for app, code in permissions.values_list(
                "content_type__app_label", "codename"
            ).distinct()
        }

    def get_user_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()
        return {
            f"{app}.{code}"
            for app, code in user_obj.user_permissions.values_list(
                "content_type__app_label", "codename"
            )
        }

    def get_group_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()
        return {
            f"{app}.{code}"
            for app, code in Permission.objects.filter(group__user=user_obj)
            .values_list("content_type__app_label", "codename")
            .distinct()
        }
