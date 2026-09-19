"""Routes for the Canvas API, mounted at /api/canvas/."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from canvas_integration import views

router = DefaultRouter()
router.register('sync-logs', views.SyncLogViewSet, basename='sync-log')

urlpatterns = [
    path('connection/', views.CanvasConnectionView.as_view(), name='canvas-connection'),
    path(
        'connection/test/',
        views.CanvasConnectionTestView.as_view(),
        name='canvas-connection-test',
    ),
    path('sync/', views.CanvasSyncView.as_view(), name='canvas-sync'),
    path('', include(router.urls)),
]
