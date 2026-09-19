"""Routes for the admin API, mounted at /api/admin/ (FR-15, FR-16)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from analytics import views

router = DefaultRouter()
router.register('users', views.AdminUserViewSet, basename='admin-user')

urlpatterns = [
    path('stats/', views.PlatformStatsView.as_view(), name='admin-stats'),
    path('', include(router.urls)),
]
