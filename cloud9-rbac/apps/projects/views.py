from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.rbac.permissions import StrictModelPermissions

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "description", "published", "created_at"]
        read_only_fields = ["published", "created_at"]


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [StrictModelPermissions]
    action_permissions = {"publish": "projects.publish_project"}
    search_fields = ["name"]
    filterset_fields = ["published"]
    ordering_fields = ["id", "name", "created_at"]

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        project = self.get_object()
        project.published = True
        project.save(update_fields=["published"])
        return Response(self.get_serializer(project).data)
