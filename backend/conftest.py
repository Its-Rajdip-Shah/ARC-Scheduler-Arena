"""Fixtures available to every app's tests."""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from planning.models import ItemType, PlanningItem


@pytest.fixture(autouse=True)
def clear_cache():
    """Two features keep state in the cache: the TOTP replay guard and the
    once-a-day adaptive sweep. Neither should survive into the next test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api():
    """An unauthenticated client, for tests that drive the login flow."""
    return APIClient()


@pytest.fixture
def api_for():
    """An APIClient already authenticated as the given user.

    force_authenticate skips ArcJWTAuthentication on purpose. The scope and
    is_locked checks that class performs are covered directly in
    accounts/tests/test_auth.py, and repeating the two-step MFA login in every
    planning test would only slow the suite down.
    """

    def factory(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return factory


@pytest.fixture
def make_item(db):
    """Create a planning item. Defaults to an active task with no dates.

    Lives here rather than in planning/tests/ because the Canvas and admin
    tests need planning data too.
    """

    def factory(user, title, item_type=ItemType.TASK, parent=None, **fields):
        return PlanningItem.objects.create(
            user=user, title=title, item_type=item_type, parent=parent, **fields
        )

    return factory
