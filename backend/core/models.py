"""Abstract model bases shared across the ARC apps."""

from django.conf import settings
from django.db import models


class TimestampedModel(models.Model):
    """Adds the created_at / updated_at pair used across the ERD."""

    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        abstract = True


class OwnedModel(models.Model):
    """Adds the owning-user foreign key that FR-03 isolation filters on.

    Concrete models may redeclare ``user`` if they need a different
    related_name or on_delete behaviour.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        related_name='%(class)ss',
    )

    class Meta:
        abstract = True
