"""Tests for the admin API (FR-15, FR-16).

Two things matter here. First, that an ordinary account cannot reach any of
it. Second, that what an administrator can reach is account state and counts
and nothing else: FR-15 gives admins user management, not a window into
anyone's planner.
"""

from datetime import timedelta

import pyotp
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.tests.conftest import PASSWORD, login_through_mfa, make_user
from canvas_integration.models import CanvasConnection, SyncLog, SyncStatus
from planning.models import ItemType, PlanningItem

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def admin(db):
    return User.objects.create_user('admin@example.com', PASSWORD, is_admin=True)


@pytest.fixture
def member(db):
    return User.objects.create_user('alice@example.com', PASSWORD)


@pytest.fixture
def client(api_for, admin):
    return api_for(admin)


# --- Access control (FR-15) -------------------------------------------------

@pytest.mark.parametrize('path', ['/api/admin/stats/', '/api/admin/users/'])
def test_an_ordinary_account_is_refused(api_for, member, path):
    assert api_for(member).get(path).status_code == 403


def test_an_ordinary_account_cannot_lock_anyone(api_for, member, admin):
    response = api_for(member).post(f'/api/admin/users/{admin.pk}/lock/')
    assert response.status_code == 403
    admin.refresh_from_db()
    assert admin.is_locked is False


@pytest.mark.parametrize('path', ['/api/admin/stats/', '/api/admin/users/'])
def test_an_anonymous_request_is_refused(db, api, path):
    assert api.get(path).status_code == 401


def test_an_administrator_is_allowed(client):
    assert client.get('/api/admin/stats/').status_code == 200


# --- Users (FR-16) ----------------------------------------------------------

def test_the_user_list_reports_account_state_and_counts(client, member, make_item):
    make_item(member, 'Read chapter 4')
    make_item(member, 'ELEC3609', ItemType.GOAL)

    rows = {row['email']: row for row in client.get('/api/admin/users/').data['results']}
    assert rows['alice@example.com']['planning_item_count'] == 2
    assert rows['alice@example.com']['is_locked'] is False
    assert rows['admin@example.com']['is_admin'] is True


def test_the_user_list_exposes_no_credentials(client, member):
    """A secret an administrator never needs is a secret the API should not
    serve."""
    member.totp_secret_encrypted = pyotp.random_base32()
    member.save(update_fields=['totp_secret_encrypted'])

    row = next(
        row for row in client.get('/api/admin/users/').data['results']
        if row['email'] == 'alice@example.com'
    )
    assert set(row) == {
        'id', 'email', 'is_admin', 'is_locked', 'mfa_enabled',
        'created_at', 'last_login', 'planning_item_count', 'last_sync_at',
    }
    assert row['mfa_enabled'] is True


def test_the_user_list_exposes_no_planning_titles(client, member, make_item):
    """FR-15 is user management, not a window into anyone's planner."""
    make_item(member, 'A deeply private goal', ItemType.GOAL)
    assert 'deeply private' not in str(client.get('/api/admin/users/').data)


def test_the_user_list_can_be_searched_by_email(client, member):
    results = client.get('/api/admin/users/?search=alice').data['results']
    assert [row['email'] for row in results] == ['alice@example.com']


def test_the_user_list_reports_the_last_successful_sync(client, member):
    connection = CanvasConnection.objects.create(user=member, api_token_encrypted='x' * 30)
    SyncLog.objects.create(
        user=member, status=SyncStatus.FAILED, completed_at=timezone.now()
    )
    success = SyncLog.objects.create(
        user=member, status=SyncStatus.SUCCESS, completed_at=timezone.now()
    )

    row = next(
        row for row in client.get('/api/admin/users/').data['results']
        if row['email'] == member.email
    )
    assert row['last_sync_at'] is not None
    assert connection.pk and success.pk


def test_the_user_list_is_read_only(client, member):
    assert client.delete(f'/api/admin/users/{member.pk}/').status_code == 405
    assert client.post('/api/admin/users/', {'email': 'x@y.test'}, format='json'
                       ).status_code == 405


# --- Lock and unlock (FR-16) ------------------------------------------------

def test_lock_and_unlock_flip_the_flag(client, member):
    response = client.post(f'/api/admin/users/{member.pk}/lock/')
    assert response.status_code == 200, response.data
    assert response.data['is_locked'] is True
    member.refresh_from_db()
    assert member.is_locked is True

    response = client.post(f'/api/admin/users/{member.pk}/unlock/')
    assert response.data['is_locked'] is False
    member.refresh_from_db()
    assert member.is_locked is False


def test_locking_twice_is_harmless(client, member):
    client.post(f'/api/admin/users/{member.pk}/lock/')
    assert client.post(f'/api/admin/users/{member.pk}/lock/').status_code == 200
    member.refresh_from_db()
    assert member.is_locked is True


def test_an_administrator_cannot_lock_themselves_out(client, admin):
    """Nobody would be left able to unlock the console."""
    response = client.post(f'/api/admin/users/{admin.pk}/lock/')
    assert response.status_code == 403
    admin.refresh_from_db()
    assert admin.is_locked is False


def test_locking_ends_the_users_live_session(client, api, db, make_item):
    """The point of FR-16. ArcJWTAuthentication re-reads is_locked per
    request, so an already-issued token stops working without any
    blacklisting."""
    secret = pyotp.random_base32()
    victim = make_user('victim@example.com', secret)
    make_item(victim, 'Read chapter 4')

    tokens = login_through_mfa(api, victim, secret)
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
    assert api.get('/api/planning/items/').status_code == 200

    client.post(f'/api/admin/users/{victim.pk}/lock/')

    assert api.get('/api/planning/items/').status_code == 401


def test_locking_leaves_the_users_data_intact(client, member, make_item):
    """A lock suspends access; it is not a deletion."""
    make_item(member, 'Read chapter 4')
    client.post(f'/api/admin/users/{member.pk}/lock/')
    assert PlanningItem.objects.filter(user=member).count() == 1


# --- Stats (FR-16) ----------------------------------------------------------

def test_stats_count_users_by_state(client, member):
    locked = User.objects.create_user('locked@example.com', PASSWORD, is_locked=True)
    member.totp_secret_encrypted = pyotp.random_base32()
    member.save(update_fields=['totp_secret_encrypted'])

    users = client.get('/api/admin/stats/').data['users']
    assert users['total'] == 3
    assert users['locked'] == 1
    assert users['admins'] == 1
    assert users['mfa_enrolled'] == 1
    assert locked.pk


def test_stats_count_planning_items_across_all_users(client, member, admin, make_item):
    make_item(member, 'ELEC3609', ItemType.GOAL)
    make_item(member, 'Done', is_completed=True)
    make_item(admin, 'Adaptive')

    items = client.get('/api/admin/stats/').data['planning_items']
    assert items['total'] == 3
    assert items['completed'] == 1
    assert items['without_deadline'] == 2  # the goal has no due date either
    assert items['by_type'] == {ItemType.GOAL: 1, ItemType.TASK: 2}


def test_stats_count_overdue_work(client, member, make_item):
    today = timezone.localdate()
    make_item(member, 'Missed', due_date=today - timedelta(days=3))
    make_item(member, 'Upcoming', due_date=today + timedelta(days=3))

    assert client.get('/api/admin/stats/').data['planning_items']['overdue'] == 1


def test_stats_report_canvas_health(client, member):
    CanvasConnection.objects.create(user=member, api_token_encrypted='x' * 30)
    SyncLog.objects.create(user=member, status=SyncStatus.FAILED, completed_at=timezone.now())
    SyncLog.objects.create(user=member, status=SyncStatus.SUCCESS, completed_at=timezone.now())

    canvas = client.get('/api/admin/stats/').data['canvas']
    assert canvas['connections'] == 1
    assert canvas['syncs_total'] == 2
    assert canvas['syncs_failed'] == 1
    assert canvas['last_successful_sync'] is not None


def test_stats_hold_up_on_an_empty_deployment(client):
    stats = client.get('/api/admin/stats/').data
    assert stats['planning_items']['total'] == 0
    assert stats['planning_items']['by_type'] == {}
    assert stats['canvas']['last_successful_sync'] is None
