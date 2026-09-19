"""Tests for the Canvas connection and sync endpoints (FR-04, FR-05).

Canvas itself is replaced by a stub client. The point is not to test Canvas
but to pin down what ARC does with what Canvas returns, including the cases
that matter most: a token that stops working, and the sparse payloads Canvas
gives for assignments with no due date or weighting.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from canvas_integration import sync, views
from canvas_integration.client import CanvasError
from canvas_integration.models import CanvasConnection, SyncLog, SyncStatus
from planning.models import AssignmentDetail, CanvasObjectType, ItemType, PlanningItem

pytestmark = pytest.mark.django_db

User = get_user_model()

TOKEN = 'canvas-token-that-is-long-enough'


class StubCanvas:
    """Stands in for CanvasClient. Records calls so tests can assert on them."""

    def __init__(self, courses=None, assignments=None, profile=None, fail_on=None):
        self._courses = courses or []
        self._assignments = assignments or {}
        self._profile = profile or {'id': 4242, 'name': 'Alice Example'}
        self._fail_on = fail_on
        self.assignment_calls = []

    def _maybe_fail(self, stage):
        if self._fail_on == stage:
            raise CanvasError(f'Canvas rejected the API token at {stage}.', status=401)

    def whoami(self):
        self._maybe_fail('whoami')
        return self._profile

    def courses(self):
        self._maybe_fail('courses')
        return self._courses

    def assignments(self, course_id):
        self._maybe_fail('assignments')
        self.assignment_calls.append(course_id)
        return self._assignments.get(course_id, [])


@pytest.fixture
def user(db):
    return User.objects.create_user('alice@example.com', 'corr3ct-horse-battery')


@pytest.fixture
def other_user(db):
    return User.objects.create_user('bob@example.com', 'corr3ct-horse-battery')


@pytest.fixture
def client(api_for, user):
    return api_for(user)


@pytest.fixture
def connection(user):
    return CanvasConnection.objects.create(user=user, api_token_encrypted=TOKEN)


# --- Connection as a singleton ---------------------------------------------

def test_the_connection_is_a_404_before_it_is_created(client):
    assert client.get('/api/canvas/connection/').status_code == 404


def test_put_creates_the_connection(client, user):
    response = client.put(
        '/api/canvas/connection/', {'api_token': TOKEN}, format='json'
    )
    assert response.status_code == 201, response.data
    assert CanvasConnection.objects.filter(user=user).count() == 1


def test_put_again_replaces_rather_than_duplicates(client, user, connection):
    """FR-04: one connection per user, so re-pasting a token is a replacement."""
    response = client.put(
        '/api/canvas/connection/', {'api_token': 'a-brand-new-canvas-token'}, format='json'
    )
    assert response.status_code == 200, response.data
    assert CanvasConnection.objects.filter(user=user).count() == 1
    connection.refresh_from_db()
    assert connection.api_token_encrypted == 'a-brand-new-canvas-token'


def test_the_api_token_never_comes_back_out(client, connection):
    """Encrypting the token at rest is pointless if the API returns it."""
    body = client.get('/api/canvas/connection/').data
    assert 'api_token' not in body
    assert 'api_token_encrypted' not in body
    assert TOKEN not in str(body)
    assert body['token_hint'] == f'...{TOKEN[-4:]}'


def test_the_stored_token_is_encrypted_in_the_database(client, connection):
    from django.db import connection as db

    with db.cursor() as cursor:
        cursor.execute(
            'SELECT api_token_encrypted FROM canvas_connections WHERE canvas_connection_id = %s',
            [connection.pk],
        )
        stored = cursor.fetchone()[0]
    assert stored != TOKEN


def test_an_implausibly_short_token_is_refused(client):
    response = client.put('/api/canvas/connection/', {'api_token': 'nope'}, format='json')
    assert response.status_code == 400


def test_delete_disconnects_but_keeps_the_imported_items(client, user, connection):
    """The imported items may carry the user's own tags and marks by now."""
    PlanningItem.objects.create(
        user=user, title='Imported', item_type=ItemType.GOAL,
        canvas_object_type=CanvasObjectType.COURSE, canvas_object_id='1',
    )
    assert client.delete('/api/canvas/connection/').status_code == 204
    assert not CanvasConnection.objects.filter(user=user).exists()
    assert PlanningItem.objects.filter(user=user).count() == 1


def test_one_users_connection_is_invisible_to_another(api_for, other_user, connection):
    """FR-03."""
    assert api_for(other_user).get('/api/canvas/connection/').status_code == 404


def test_the_canvas_endpoints_refuse_an_anonymous_request(db, api):
    assert api.get('/api/canvas/connection/').status_code == 401
    assert api.post('/api/canvas/sync/').status_code == 401
    assert api.get('/api/canvas/sync-logs/').status_code == 401


# --- Sync -------------------------------------------------------------------

def test_sync_imports_courses_as_roots_and_assignments_as_children(connection, user):
    """FR-05."""
    stub = StubCanvas(
        courses=[{'id': 11, 'course_code': 'ELEC3609', 'name': 'Internet Software'}],
        assignments={
            11: [
                {
                    'id': 501,
                    'name': 'Assignment 1',
                    'due_at': '2026-10-01T13:00:00Z',
                    'html_url': 'https://canvas.test/courses/11/assignments/501',
                }
            ]
        },
    )

    log = sync.run_sync(connection, client=stub)
    assert log.status == SyncStatus.SUCCESS

    root = PlanningItem.objects.get(user=user, canvas_object_type=CanvasObjectType.COURSE)
    assert (root.title, root.item_type, root.parent_id) == ('ELEC3609', ItemType.GOAL, None)

    assignment = PlanningItem.objects.get(
        user=user, canvas_object_type=CanvasObjectType.ASSIGNMENT
    )
    assert assignment.parent_id == root.pk
    assert assignment.due_date.isoformat() == '2026-10-01'
    assert assignment.priority_position == 1


def test_resyncing_updates_instead_of_duplicating(connection, user):
    """FR-05: the uniqueness of (user, canvas_object_type, canvas_object_id) is
    what makes a re-sync idempotent."""
    first = StubCanvas(
        courses=[{'id': 11, 'course_code': 'ELEC3609'}],
        assignments={11: [{'id': 501, 'name': 'Assignment 1', 'due_at': None}]},
    )
    sync.run_sync(connection, client=first)

    renamed = StubCanvas(
        courses=[{'id': 11, 'course_code': 'ELEC3609'}],
        assignments={11: [{'id': 501, 'name': 'Assignment 1 (revised)', 'due_at': None}]},
    )
    log = sync.run_sync(connection, client=renamed)

    assert log.status == SyncStatus.SUCCESS
    assert PlanningItem.objects.filter(user=user).count() == 2
    assert PlanningItem.objects.get(canvas_object_id='501').title == 'Assignment 1 (revised)'


def test_a_resync_leaves_the_users_own_edits_alone(connection, user):
    """Canvas owns the title and the deadline. Everything the user decided for
    themselves has to survive the next sync."""
    payload = {
        'courses': [{'id': 11, 'course_code': 'ELEC3609'}],
        'assignments': {11: [{'id': 501, 'name': 'Assignment 1', 'due_at': None}]},
    }
    sync.run_sync(connection, client=StubCanvas(**payload))

    item = PlanningItem.objects.get(canvas_object_id='501')
    item.is_completed = True
    item.save(update_fields=['is_completed'])
    AssignmentDetail.objects.filter(planning_item=item).update(
        weight_percent='25.00', mark_achieved='20.00'
    )

    sync.run_sync(connection, client=StubCanvas(**payload))

    item.refresh_from_db()
    detail = AssignmentDetail.objects.get(planning_item=item)
    assert item.is_completed is True
    assert (detail.weight_percent, detail.mark_achieved) == (
        Decimal('25.00'), Decimal('20.00')
    )


def test_an_assignment_with_no_due_date_preserves_missing_deadline(connection, user):
    """AGENTS.md: never invent missing Canvas data. No due_at means no
    deadline; execution scheduling must not invent one."""
    stub = StubCanvas(
        courses=[{'id': 11, 'course_code': 'ELEC3609'}],
        assignments={11: [{'id': 501, 'name': 'Ungraded survey', 'due_at': None}]},
    )
    sync.run_sync(connection, client=stub)

    item = PlanningItem.objects.get(canvas_object_id='501')
    assert item.due_date is None
    assert item.has_deadline is False


def test_missing_canvas_fields_do_not_break_the_import(connection, user):
    """A course with no course_code and an assignment with no name at all."""
    stub = StubCanvas(
        courses=[{'id': 11, 'name': 'Internet Software Platforms'}, {'id': None}],
        assignments={11: [{'id': 502}, {'id': None, 'name': 'skipped'}]},
    )
    log = sync.run_sync(connection, client=stub)

    assert log.status == SyncStatus.SUCCESS
    assert PlanningItem.objects.get(canvas_object_id='11').title == 'Internet Software Platforms'
    assert PlanningItem.objects.get(canvas_object_id='502').title == (
        'Untitled Canvas assignment'
    )
    assert PlanningItem.objects.filter(user=user).count() == 2


def test_canvas_gives_no_weighting_so_none_is_recorded(connection):
    """points_possible is not a percentage of the unit, so FR-14's
    weight_percent stays for the user to fill in."""
    stub = StubCanvas(
        courses=[{'id': 11, 'course_code': 'ELEC3609'}],
        assignments={11: [{'id': 501, 'name': 'Quiz', 'points_possible': 40}]},
    )
    sync.run_sync(connection, client=stub)

    detail = AssignmentDetail.objects.get(planning_item__canvas_object_id='501')
    assert detail.weight_percent is None
    assert detail.mark_achieved is None


def test_sync_records_a_success_log(connection, user):
    """FR-04."""
    log = sync.run_sync(connection, client=StubCanvas())

    assert SyncLog.objects.filter(user=user).count() == 1
    assert log.status == SyncStatus.SUCCESS
    assert log.completed_at is not None
    assert log.error_message is None

    connection.refresh_from_db()
    assert connection.last_sync_at == log.completed_at
    assert connection.canvas_user_id == '4242'


def test_a_rejected_token_records_a_failure_log(connection, user):
    """FR-04: the attempt is recorded either way, which is what lets the
    Connection screen explain itself."""
    log = sync.run_sync(connection, client=StubCanvas(fail_on='whoami'))

    assert log.status == SyncStatus.FAILED
    assert 'rejected the API token' in log.error_message
    assert log.completed_at is not None

    connection.refresh_from_db()
    assert connection.last_sync_at is None


def test_a_failure_partway_through_still_logs(connection, user):
    log = sync.run_sync(
        connection,
        client=StubCanvas(courses=[{'id': 11, 'course_code': 'X'}], fail_on='assignments'),
    )
    assert log.status == SyncStatus.FAILED


@pytest.fixture
def canvas_returns(monkeypatch):
    """Make the view's own CanvasClient construction hand back a stub.

    Patching the client rather than run_sync means the endpoint tests still
    exercise the real sync and logging path.
    """

    def install(stub):
        monkeypatch.setattr(sync, 'CanvasClient', lambda *args, **kwargs: stub)
        monkeypatch.setattr(views, 'CanvasClient', lambda *args, **kwargs: stub)
        return stub

    return install


def test_the_sync_endpoint_returns_the_log_and_counts(client, connection, canvas_returns):
    canvas_returns(StubCanvas(
        courses=[{'id': 11, 'course_code': 'ELEC3609'}],
        assignments={11: [{'id': 501, 'name': 'Assignment 1'}]},
    ))

    response = client.post('/api/canvas/sync/')
    assert response.status_code == 200, response.data
    assert response.data['status'] == SyncStatus.SUCCESS
    assert response.data['counts'] == {
        'courses_created': 1, 'courses_updated': 0,
        'assignments_created': 1, 'assignments_updated': 0,
    }


def test_the_sync_endpoint_reports_a_canvas_failure_as_502(client, connection,
                                                           canvas_returns):
    canvas_returns(StubCanvas(fail_on='whoami'))

    response = client.post('/api/canvas/sync/')
    assert response.status_code == 502
    assert response.data['status'] == SyncStatus.FAILED
    assert 'rejected the API token' in response.data['error_message']


def test_the_sync_endpoint_needs_a_connection_first(client):
    assert client.post('/api/canvas/sync/').status_code == 404


def test_the_connection_test_endpoint_confirms_a_working_token(client, connection,
                                                                canvas_returns):
    """FR-04."""
    canvas_returns(StubCanvas())

    response = client.post('/api/canvas/connection/test/')
    assert response.status_code == 200, response.data
    assert response.data == {'ok': True, 'canvas_user_id': '4242', 'name': 'Alice Example'}


def test_the_connection_test_endpoint_reports_a_dead_token(client, connection,
                                                            canvas_returns):
    canvas_returns(StubCanvas(fail_on='whoami'))

    response = client.post('/api/canvas/connection/test/')
    assert response.status_code == 502
    assert response.data['ok'] is False
    assert response.data['status'] == 401


def test_testing_the_connection_writes_no_sync_log(client, connection, canvas_returns):
    """It checks the token; it is not a synchronisation attempt."""
    canvas_returns(StubCanvas())
    client.post('/api/canvas/connection/test/')
    assert SyncLog.objects.count() == 0


# --- Sync history -----------------------------------------------------------

def test_sync_logs_are_listed_newest_first(client, user, connection):
    sync.run_sync(connection, client=StubCanvas(fail_on='whoami'))
    sync.run_sync(connection, client=StubCanvas())

    results = client.get('/api/canvas/sync-logs/').data['results']
    assert [row['status'] for row in results] == [SyncStatus.SUCCESS, SyncStatus.FAILED]


def test_sync_logs_are_read_only(client, connection):
    assert client.post('/api/canvas/sync-logs/', {}, format='json').status_code == 405


def test_another_users_sync_logs_are_invisible(api_for, other_user, connection):
    """FR-03."""
    sync.run_sync(connection, client=StubCanvas())
    assert api_for(other_user).get('/api/canvas/sync-logs/').data['count'] == 0


def test_existing_assignment_regains_eligible_priority_with_deadline(connection, user):
    from planning.services import priority

    stub = StubCanvas(
        courses=[{'id': 11, 'course_code': 'ELEC3609'}],
        assignments={11: [{'id': 501, 'name': 'Quiz', 'due_at': '2026-10-01T12:00:00Z'}]},
    )
    sync.run_sync(connection, client=stub)
    item = PlanningItem.objects.get(user=user, canvas_object_id='501')
    PlanningItem.objects.filter(pk=item.pk).update(priority_position=None)
    sync.run_sync(connection, client=stub)
    item.refresh_from_db()
    assert item.has_deadline is True
    assert item.pk in priority.ordered(user).values_list('pk', flat=True)


def test_sync_schedules_each_course_batch_once(connection, user):
    from unittest.mock import patch
    from planning.services import scheduling

    client = StubCanvas(courses=[{'id': 1}], assignments={1: [
        {'id': 100, 'name': 'One'}, {'id': 101, 'name': 'Two'},
    ]})
    with patch.object(scheduling, 'schedule', wraps=scheduling.schedule) as run:
        log = sync.run_sync(connection, client)
        assert log.status == SyncStatus.SUCCESS
        assert run.call_count == 1
        assert run.call_args.kwargs.get('mode', 'minimal') == 'minimal'
    items = PlanningItem.objects.for_user(user).priority_eligible()
    assert items.count() == 2
    assert not items.filter(scheduled_date=None).exists()
