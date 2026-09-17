from django.contrib import admin

from apps.rbac.admin import SuperuserOnly

from .models import Project


@admin.register(Project)
class ProjectAdmin(SuperuserOnly, admin.ModelAdmin):
    list_display = ["name", "published", "created_at"]
