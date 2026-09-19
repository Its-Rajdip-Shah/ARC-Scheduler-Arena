"""Payload shapes for the Canvas API (FR-04, FR-05)."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from canvas_integration.models import CanvasConnection, SyncLog


class SyncLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncLog
        fields = ['id', 'started_at', 'completed_at', 'status', 'error_message']
        read_only_fields = fields


class CanvasConnectionSerializer(serializers.ModelSerializer):
    """The connection as the frontend sees it.

    api_token is write-only. The stored token decrypts transparently on read,
    so it would otherwise come straight back out of the API, which defeats the
    point of encrypting it at rest.
    """

    api_token = serializers.CharField(
        write_only=True, source='api_token_encrypted', min_length=20, max_length=500,
        trim_whitespace=True,
    )
    token_hint = serializers.SerializerMethodField()
    last_sync = SyncLogSerializer(read_only=True)

    class Meta:
        model = CanvasConnection
        fields = [
            'id', 'canvas_user_id', 'connected_at', 'last_sync_at',
            'api_token', 'token_hint', 'last_sync',
        ]
        read_only_fields = ['id', 'canvas_user_id', 'connected_at', 'last_sync_at']

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_token_hint(self, connection):
        """Last four characters only, so the user can tell which token is
        stored without the API handing it back."""
        token = connection.api_token_encrypted or ''
        return f'...{token[-4:]}' if len(token) >= 4 else None
