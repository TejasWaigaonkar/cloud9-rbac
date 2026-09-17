from rest_framework.permissions import BasePermission, DjangoModelPermissions


class IsRBACAdministrator(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and request.user.is_active
            and request.user.has_perm("rbac.manage_rbac")
        )


class StrictModelPermissions(DjangoModelPermissions):
    perms_map = {
        **DjangoModelPermissions.perms_map,
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
    }

    def has_permission(self, request, view):
        permission = getattr(view, "action_permissions", {}).get(getattr(view, "action", None))
        if permission:
            return request.user.is_authenticated and request.user.has_perm(permission)
        return super().has_permission(request, view)
