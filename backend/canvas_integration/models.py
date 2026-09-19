"""Canvas connection state and synchronisation history (FR-04, FR-05)."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.fields import EncryptedCharField
from core.models import OwnedModel


class CanvasConnection(models.Model):
    """One user's Canvas credentials.

    The ERD's UNIQUE on user_id is what limits a user to a single connection;
    a OneToOneField expresses exactly that.
    """

    id = models.BigAutoField(primary_key=True, db_column='canvas_connection_id')
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='canvas_connection',
    )
    api_token_encrypted = EncryptedCharField(max_length=500)
    canvas_user_id = models.CharField(max_length=100, null=True, blank=True)
    connected_at = models.DateTimeField(default=timezone.now)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'canvas_connections'

    def __str__(self):
        return f'Canvas connection for {self.user_id}'


class SyncStatus(models.TextChoices):
    SUCCESS = 'SUCCESS', 'Success'
    FAILED = 'FAILED', 'Failed'


class SyncLogQuerySet(models.QuerySet):
    def successful(self):
        return self.filter(status=SyncStatus.SUCCESS)

    def failed(self):
        return self.filter(status=SyncStatus.FAILED)

    def latest_successful(self):
        """Backs FR-04's 'time of the most recent successful synchronisation'."""
        return self.successful().order_by('-completed_at').first()


class SyncLog(OwnedModel):
    """One Canvas synchronisation attempt, successful or not (FR-04, FR-05)."""

    id = models.BigAutoField(primary_key=True, db_column='sync_log_id')
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=7, choices=SyncStatus.choices)
    error_message = models.TextField(null=True, blank=True)

    objects = SyncLogQuerySet.as_manager()

    class Meta:
        db_table = 'sync_logs'
        ordering = ['-started_at']
        constraints = [
            # Django emits a check constraint rather than the report's native
            # sync_status enum, but the guarantee is the same.
            models.CheckConstraint(
                condition=models.Q(status__in=SyncStatus.values),
                name='sync_log_status_valid',
            ),
        ]

    def __str__(self):
        return f'{self.status} sync at {self.started_at:%Y-%m-%d %H:%M}'
