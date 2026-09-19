"""Routes for the planning API, mounted at /api/planning/.

The literal paths come before the router so that /priority/ and /marks/ are
not shadowed by a router-generated detail route.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from planning import views

router = DefaultRouter()
router.register('items', views.PlanningItemViewSet, basename='planning-item')
router.register('tags', views.TagViewSet, basename='tag')
router.register('timezones', views.TimezoneViewSet, basename='timezone')
router.register(
    'assignment-details', views.AssignmentDetailViewSet, basename='assignment-detail'
)

urlpatterns = [
    path('priority/', views.PriorityView.as_view(), name='priority'),
    path('priority/reorder/', views.PriorityReorderView.as_view(), name='priority-reorder'),
    path('timeline/reschedule/', views.ScheduleRescheduleView.as_view(), name='schedule-reschedule'),
    path('timeline/move/', views.ScheduleMoveView.as_view(), name='schedule-move'),
    path('timeline/replace/', views.ScheduleReplaceView.as_view(), name='schedule-replace'),
    path('timeline/capacity/', views.ScheduleCapacityView.as_view(), name='schedule-capacity'),
    path('timeline/overload/', views.ScheduleOverloadView.as_view(), name='schedule-overload'),
    path('timeline/', views.TimelineView.as_view(), name='timeline'),
    path('overdue/', views.OverdueView.as_view(), name='overdue'),
    path('marks/', views.MarksView.as_view(), name='marks'),
    path('marks/reorder/', views.MarksReorderView.as_view(), name='marks-reorder'),
    path('', include(router.urls)),
]
