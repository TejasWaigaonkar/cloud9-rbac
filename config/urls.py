from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import IsAuthenticated
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from apps.projects.views import ProjectViewSet
from apps.rbac.views import AuditViewSet, PermissionViewSet, RoleViewSet, UserAccessViewSet
from apps.users.views import LoginView

from .health import health, ready

router = DefaultRouter()
router.register("roles", RoleViewSet)
router.register("permissions", PermissionViewSet)
router.register("users", UserAccessViewSet)
router.register("audit-logs", AuditViewSet)
router.register("projects", ProjectViewSet)
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/auth/token/", LoginView.as_view()),
    path("api/auth/refresh/", TokenRefreshView.as_view()),
    path("api/auth/logout/", TokenBlacklistView.as_view()),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[IsAuthenticated]),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[IsAuthenticated]),
    ),
    path("health/", health),
    path("ready/", ready),
]
