import re

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.projects.models import Project

from .models import AuditLog, Role


class RoleSerializer(serializers.ModelSerializer):
    permission_ids = serializers.PrimaryKeyRelatedField(
        source="permissions", many=True, read_only=True
    )

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "code",
            "description",
            "is_active",
            "is_system",
            "permission_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["is_system", "created_at", "updated_at"]

    def validate(self, attrs):
        if "is_system" in self.initial_data:
            raise serializers.ValidationError(
                {"is_system": "System roles require a reviewed data migration."}
            )
        for field in ["name", "code"]:
            if field in attrs:
                query = Role.objects.filter(**{f"{field}__iexact": attrs[field]})
                if self.instance:
                    query = query.exclude(pk=self.instance.pk)
                if query.exists():
                    raise serializers.ValidationError({field: "Already exists (case insensitive)."})
        return attrs


class PermissionSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True)

    class Meta:
        model = Permission
        fields = ["id", "name", "codename", "content_type", "code"]
        read_only_fields = ["content_type"]
        validators = []

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result["code"] = f"{instance.content_type.app_label}.{instance.codename}"
        return result

    def validate(self, attrs):
        if "content_type" in self.initial_data:
            raise serializers.ValidationError("Content type is controlled by the server.")
        if self.instance and "codename" in attrs and attrs["codename"] != self.instance.codename:
            raise serializers.ValidationError("Permission identifiers cannot be renamed.")
        code = attrs.get("codename", getattr(self.instance, "codename", ""))
        if not re.fullmatch(r"custom_[a-z][a-z0-9_]{0,80}", code):
            raise serializers.ValidationError(
                "Use custom_<lowercase_name> for runtime permissions."
            )
        content_type = ContentType.objects.get_for_model(Project)
        query = Permission.objects.filter(content_type=content_type, codename=code)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("Permission already exists.")
        attrs["content_type"] = content_type
        return attrs


class PermissionMappingSerializer(serializers.Serializer):
    permission_id = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.select_related("content_type")
    )


class RoleMappingSerializer(serializers.Serializer):
    role_id = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all())


class AuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = "__all__"


class PermissionLinkSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    permission_id = serializers.IntegerField()


class RoleLinkSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    role_id = serializers.IntegerField()


class EffectiveRoleSerializer(serializers.Serializer):
    role_id = serializers.IntegerField()
    role__code = serializers.CharField()
    role__is_active = serializers.BooleanField()


class EffectiveGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class EffectiveAccessSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    is_active = serializers.BooleanField()
    roles = EffectiveRoleSerializer(many=True)
    groups = EffectiveGroupSerializer(many=True)
    permissions = serializers.ListField(child=serializers.CharField())


class PaginatedRolesSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = RoleSerializer(many=True)
