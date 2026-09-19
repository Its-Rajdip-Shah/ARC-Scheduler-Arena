"""The admin API (FR-15, FR-16).

Everything here is gated on IsAdminAccount, which is the one place in ARC
where a request legitimately reads across users. Note what is still not
exposed: counts and account state, never the contents of anyone's planner.
"""

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.serializers import (
    AdminUserSerializer,
    LockSerializer,
    PlatformStatsSerializer,
)
from canvas_integration.models import CanvasConnection, SyncLog, SyncStatus
from core.permissions import IsAdminAccount
from planning.models import ItemType, PlanningItem

User = get_user_model()

#: An account counts as active if it has signed in within this window.
ACTIVE_WINDOW_DAYS = 7


class AdminUserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                       viewsets.GenericViewSet):
    """FR-16: /api/admin/users/, with lock and unlock actions."""

    permission_classes = [IsAdminAccount]
    serializer_class = AdminUserSerializer
    filter_backends = [SearchFilter]
    search_fields = ['email']

    def get_queryset(self):
        return User.objects.annotate(
            planning_item_count=Count('planningitems', distinct=True),
            last_sync_at=Max(
                'synclogs__completed_at',
                filter=Q(synclogs__status=SyncStatus.SUCCESS),
            ),
        ).order_by('email')

    @extend_schema(request=None, responses=AdminUserSerializer)
    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        return self._set_locked(request, locked=True)

    @extend_schema(request=None, responses=AdminUserSerializer)
    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        return self._set_locked(request, locked=False)

    def _set_locked(self, request, locked):
        account = self.get_object()
        if locked and account.pk == request.user.pk:
            # Locking yourself out of the console leaves nobody able to
            # unlock it again.
            raise PermissionDenied('You cannot lock your own account.')

        if account.is_locked != locked:
            account.is_locked = locked
            account.save(update_fields=['is_locked'])

        # ArcJWTAuthentication re-reads is_locked per request, so a live
        # session ends at the locked user's very next call; no token
        # blacklisting is needed here.
        return Response(self.get_serializer(self.get_object()).data)


class PlatformStatsView(APIView):
    """FR-16: GET /api/admin/stats/"""

    permission_classes = [IsAdminAccount]

    @extend_schema(responses=PlatformStatsSerializer)
    def get(self, request):
        now = timezone.now()
        today = timezone.localdate()

        item_counts = PlanningItem.objects.aggregate(
            total=Count('id'),
            completed=Count('id', filter=Q(is_completed=True)),
            overdue=Count(
                'id',
                filter=Q(
                    is_completed=False,
                    due_date__lt=today,
                    item_type__in=[ItemType.TASK, ItemType.ASSIGNMENT],
                ),
            ),
            without_deadline=Count('id', filter=Q(due_date__isnull=True, is_completed=False)),
        )

        stats = {
            'users': {
                'total': User.objects.count(),
                'locked': User.objects.locked().count(),
                'admins': User.objects.admins().count(),
                'mfa_enrolled': User.objects.mfa_enrolled().count(),
                f'active_last_{ACTIVE_WINDOW_DAYS}_days': User.objects.active_since(
                    ACTIVE_WINDOW_DAYS
                ).count(),
            },
            'planning_items': {
                'total': item_counts['total'],
                'completed': item_counts['completed'],
                'overdue': item_counts['overdue'],
                'without_deadline': item_counts['without_deadline'],
                'by_type': {
                    row['item_type']: row['count']
                    for row in PlanningItem.objects.values('item_type')
                    .annotate(count=Count('id'))
                    .order_by('item_type')
                },
            },
            'canvas': {
                'connections': CanvasConnection.objects.count(),
                'syncs_total': SyncLog.objects.count(),
                'syncs_failed': SyncLog.objects.failed().count(),
                'last_successful_sync': getattr(
                    SyncLog.objects.latest_successful(), 'completed_at', None
                ),
            },
            'generated_at': now,
        }
        return Response(PlatformStatsSerializer(stats).data)
