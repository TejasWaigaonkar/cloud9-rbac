from django.contrib.auth.models import Permission, User
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .audit import actor_context
from .models import AuditLog, Role, RolePermission, UserRole
from .permissions import IsRBACAdministrator
from .serializers import (
    AuditSerializer,
    EffectiveAccessSerializer,
    PaginatedRolesSerializer,
    PermissionLinkSerializer,
    PermissionMappingSerializer,
    PermissionSerializer,
    RoleLinkSerializer,
    RoleMappingSerializer,
    RoleSerializer,
)
from .services import (
    assignment_target,
    editable_permission,
    editable_role,
    lock_administration,
    require_grant_authority,
)


class AuditedViewSet(viewsets.GenericViewSet):
    def dispatch(self, request, *args, **kwargs):
        # JWT authentication happens in DRF initial(), after Django middleware.
        with actor_context(None), transaction.atomic():
            return super().dispatch(request, *args, **kwargs)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            lock_administration()
            # Recheck after acquiring the lock: another writer may have revoked access.
            self.check_permissions(request)
        from .audit import current_actor

        current_actor.set(request.user)


class RoleViewSet(AuditedViewSet, viewsets.ModelViewSet):
    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    permission_classes = [IsRBACAdministrator]
    filterset_fields = ["is_active", "is_system", "code"]
    search_fields = ["name", "code"]
    ordering_fields = ["id", "name", "created_at"]

    def perform_update(self, serializer):
        editable_role(self.request.user, serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        editable_role(self.request.user, instance)
        instance.delete()

    @extend_schema(responses={201: PermissionLinkSerializer})
    @action(
        detail=True,
        methods=["post"],
        url_path="permissions",
        serializer_class=PermissionMappingSerializer,
    )
    def map_permission(self, request, pk=None):
        role = self.get_object()
        editable_role(request.user, role)
        if not role.is_active:
            raise ValidationError("Inactive roles cannot receive permissions.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission = serializer.validated_data["permission_id"]
        require_grant_authority(request.user, [permission])
        link, created = RolePermission.objects.get_or_create(role=role, permission=permission)
        if not created:
            raise ValidationError("Permission is already mapped.")
        return Response(
            {"id": link.pk, "permission_id": permission.pk}, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["delete"], url_path=r"permissions/(?P<permission_id>[0-9]+)")
    def unmap_permission(self, request, pk=None, permission_id=None):
        role = self.get_object()
        editable_role(request.user, role)
        get_object_or_404(RolePermission, role=role, permission_id=permission_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PermissionViewSet(AuditedViewSet, viewsets.ModelViewSet):
    queryset = Permission.objects.select_related("content_type").order_by("id")
    serializer_class = PermissionSerializer
    permission_classes = [IsRBACAdministrator]
    search_fields = ["name", "codename"]
    filterset_fields = ["content_type__app_label", "content_type__model", "codename"]
    ordering_fields = ["id", "codename", "name"]

    def get_object(self):
        instance = super().get_object()
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            self.require_superuser()
            editable_permission(instance)
        return instance

    def require_superuser(self):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only superusers may change the permission catalog.")

    def perform_create(self, serializer):
        self.require_superuser()
        serializer.save()

    def perform_update(self, serializer):
        self.require_superuser()
        editable_permission(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self.require_superuser()
        editable_permission(instance)
        if (
            instance.role_links.exists()
            or instance.group_set.exists()
            or instance.user_set.exists()
        ):
            raise ValidationError(
                "Revoke all role, group and direct grants before deleting a permission."
            )
        instance.delete()


class UserAccessViewSet(AuditedViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = RoleMappingSerializer

    def target(self, request, pk, write=False):
        target = get_object_or_404(User, pk=pk)
        if write or request.user.pk != target.pk:
            if not request.user.has_perm("rbac.manage_rbac"):
                raise PermissionDenied("RBAC administration permission required.")
        if write:
            assignment_target(request.user, target)
        return target

    @extend_schema(methods=["GET"], responses=PaginatedRolesSerializer)
    @extend_schema(
        methods=["POST"], request=RoleMappingSerializer, responses={201: RoleLinkSerializer}
    )
    @action(detail=True, methods=["get", "post"])
    def roles(self, request, pk=None):
        target = self.target(request, pk, request.method == "POST")
        if request.method == "GET":
            roles = Role.objects.filter(user_links__user=target).prefetch_related("permissions")
            page = self.paginate_queryset(roles)
            return self.get_paginated_response(RoleSerializer(page, many=True).data)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data["role_id"]
        if not role.is_active:
            raise ValidationError("Cannot assign an inactive role.")
        if role.is_system and not request.user.is_superuser:
            raise PermissionDenied("Only superusers may assign system roles.")
        require_grant_authority(request.user, role.permissions.select_related("content_type").all())
        link, created = UserRole.objects.get_or_create(
            user=target, role=role, defaults={"assigned_by": request.user}
        )
        if not created:
            raise ValidationError("Role is already assigned.")
        return Response({"id": link.pk, "role_id": role.pk}, status=201)

    @action(detail=True, methods=["delete"], url_path=r"roles/(?P<role_id>[0-9]+)")
    def revoke(self, request, pk=None, role_id=None):
        target = self.target(request, pk, True)
        link = get_object_or_404(
            UserRole.objects.select_related("role"), user=target, role_id=role_id
        )
        if link.role.is_system and not request.user.is_superuser:
            raise PermissionDenied("Only superusers may revoke system roles.")
        require_grant_authority(
            request.user, link.role.permissions.select_related("content_type").all()
        )
        link.delete()
        return Response(status=204)

    @extend_schema(responses=EffectiveAccessSerializer)
    @action(detail=True, methods=["get"])
    def permissions(self, request, pk=None):
        target = self.target(request, pk)
        return Response(
            {
                "user_id": target.pk,
                "is_active": target.is_active,
                "roles": list(target.role_links.values("role_id", "role__code", "role__is_active")),
                "groups": list(target.groups.values("id", "name")),
                "permissions": sorted(target.get_all_permissions()),
            }
        )


class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor").all()
    serializer_class = AuditSerializer
    permission_classes = [IsRBACAdministrator]
    filterset_fields = ["actor", "action", "entity", "entity_id"]
    ordering_fields = ["id", "created_at"]
