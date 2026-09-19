"""The Canvas API: one connection per user, plus sync history (FR-04, FR-05)."""

from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from canvas_integration import sync
from canvas_integration.client import CanvasClient, CanvasError
from canvas_integration.models import CanvasConnection, SyncLog, SyncStatus
from canvas_integration.serializers import CanvasConnectionSerializer, SyncLogSerializer
from core.mixins import UserScopedMixin


def _connection_or_404(user):
    connection = CanvasConnection.objects.filter(user=user).first()
    if connection is None:
        raise NotFound('You have not connected a Canvas account.')
    return connection


class CanvasConnectionView(GenericAPIView):
    """A singleton resource at /api/canvas/connection/.

    The connection is one per user, so it has no id in the URL: PUT creates or
    replaces it, GET reads it, DELETE disconnects.
    """

    serializer_class = CanvasConnectionSerializer

    def get(self, request):
        connection = _connection_or_404(request.user)
        connection.last_sync = SyncLog.objects.filter(user=request.user).first()
        return Response(self.get_serializer(connection).data)

    @extend_schema(request=CanvasConnectionSerializer, responses=CanvasConnectionSerializer)
    def put(self, request):
        existing = CanvasConnection.objects.filter(user=request.user).first()
        serializer = self.get_serializer(existing, data=request.data)
        serializer.is_valid(raise_exception=True)
        connection = serializer.save(user=request.user)
        return Response(
            self.get_serializer(connection).data,
            status=status.HTTP_200_OK if existing else status.HTTP_201_CREATED,
        )

    @extend_schema(responses={204: None})
    def delete(self, request):
        """Disconnect. The imported planning items stay: they may carry the
        user's own tags, marks and priority decisions by now."""
        _connection_or_404(request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CanvasConnectionTestView(APIView):
    """FR-04: POST /api/canvas/connection/test/, validate the stored token."""

    @extend_schema(
        request=None,
        responses=inline_serializer(
            'CanvasConnectionTestResponse',
            {
                'ok': serializers.BooleanField(),
                'canvas_user_id': serializers.CharField(allow_null=True, required=False),
                'name': serializers.CharField(allow_null=True, required=False),
                'detail': serializers.CharField(required=False),
                'status': serializers.IntegerField(allow_null=True, required=False),
            },
        ),
    )
    def post(self, request):
        connection = _connection_or_404(request.user)
        client = CanvasClient(settings.CANVAS_BASE_URL, connection.api_token_encrypted)
        try:
            profile = client.whoami()
        except CanvasError as exc:
            return Response(
                {'ok': False, 'detail': str(exc), 'status': exc.status},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({
            'ok': True,
            'canvas_user_id': str(profile.get('id') or '') or None,
            'name': profile.get('name'),
        })


class CanvasSyncView(APIView):
    """FR-05: POST /api/canvas/sync/, pull courses and assignments."""

    @extend_schema(request=None, responses=SyncLogSerializer)
    def post(self, request):
        connection = _connection_or_404(request.user)
        log = sync.run_sync(connection)

        body = SyncLogSerializer(log).data
        body['counts'] = getattr(log, 'counts', None)
        if log.status == SyncStatus.FAILED:
            # The attempt is recorded either way, so the client can show the
            # error without a second request.
            return Response(body, status=status.HTTP_502_BAD_GATEWAY)
        return Response(body)


class SyncLogViewSet(UserScopedMixin, mixins.ListModelMixin,
                     mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """FR-04: read-only sync history at /api/canvas/sync-logs/."""

    serializer_class = SyncLogSerializer
    queryset = SyncLog.objects.all()
