from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.projects.models import Project
from apps.rbac.models import Role, RolePermission, UserRole


class Command(BaseCommand):
    help = "Idempotent development demo; users have unusable passwords until setpassword."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo seeding is disabled outside development.")
        role, _ = Role.objects.get_or_create(
            code="project-editor", defaults={"name": "Project Editor"}
        )
        for code in ["view_project", "add_project", "change_project"]:
            permission = Permission.objects.get(content_type__app_label="projects", codename=code)
            RolePermission.objects.get_or_create(role=role, permission=permission)
        group, _ = Group.objects.get_or_create(name="Project Readers")
        group.permissions.add(
            Permission.objects.get(content_type__app_label="projects", codename="view_project")
        )
        for name in ["demo_editor", "demo_reader"]:
            user, created = User.objects.get_or_create(username=name)
            if created:
                user.set_unusable_password()
                user.save()
            if name == "demo_editor":
                UserRole.objects.get_or_create(user=user, role=role)
            else:
                user.groups.add(group)
        Project.objects.get_or_create(
            name="Cloud9 demo", defaults={"description": "Protected sample project"}
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Demo ready. Run changepassword for each demo account to enable login."
            )
        )
