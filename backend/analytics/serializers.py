"""Payload shapes for the admin API (FR-15, FR-16)."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class AdminUserSerializer(serializers.ModelSerializer):
    """An account as the admin console lists it.

    Deliberately no password or TOTP secret: an administrator manages access
    under FR-16, which needs neither.
    """

    mfa_enabled = serializers.BooleanField(read_only=True)
    planning_item_count = serializers.IntegerField(read_only=True)
    last_sync_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'is_admin', 'is_locked', 'mfa_enabled',
            'created_at', 'last_login', 'planning_item_count', 'last_sync_at',
        ]
        read_only_fields = fields


class LockSerializer(serializers.Serializer):
    locked = serializers.BooleanField()


class PlatformStatsSerializer(serializers.Serializer):
    """FR-16: the numbers the admin dashboard reports."""

    users = serializers.DictField()
    planning_items = serializers.DictField()
    canvas = serializers.DictField()
    generated_at = serializers.DateTimeField()
