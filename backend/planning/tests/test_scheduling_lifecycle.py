from datetime import date, timedelta
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from planning.models import ItemType, PlanningHistoryEntry, PlanningItem, SchedulingPreference, SchedulingState
from planning.services import history, priority, scheduling

pytestmark = pytest.mark.django_db
TODAY = date(2026, 9, 14)


@pytest.fixture(autouse=True)
def clock():
    with freeze_time('2026-09-14'):
        yield


def refresh(*items):
    for item in items:
        item.refresh_from_db()


def test_create_edit_and_title_lifecycle(user, api_for, make_item):
    client = api_for(user)
    future = make_item(user, 'Future', scheduled_date=TODAY + timedelta(days=8))
    response = client.post('/api/planning/items/', {'title': 'New', 'item_type': 'TASK'}, format='json')
    assert response.status_code == 201
    item = PlanningItem.objects.get(pk=response.data['id'])
    assert item.scheduled_date == TODAY
    response = client.patch(f'/api/planning/items/{item.pk}/', {'start_date': '2026-09-17'}, format='json')
    assert response.status_code == 200
    refresh(item, future)
    assert item.scheduled_date == date(2026, 9, 17)
    assert future.scheduled_date == TODAY + timedelta(days=8)
    with patch.object(scheduling, 'schedule', wraps=scheduling.schedule) as run:
        assert client.patch(f'/api/planning/items/{item.pk}/', {'title': 'Renamed'}, format='json').status_code == 200
        run.assert_not_called()


@pytest.mark.parametrize('limit,code', [(0, 'capacity_disabled'), (1, 'no_capacity_before_deadline')])
def test_total_scheduling_at_capacity_limit(user, make_item, limit, code):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=limit)
    release = TODAY + timedelta(days=2)
    items = [make_item(user, str(i), start_date=release, due_date=release) for i in range(3)]
    result = scheduling.schedule(user)
    refresh(*items)
    assert all(item.scheduled_date == release for item in items)
    assert any(conflict['code'] == code for conflict in result['conflicts'])
    assert scheduling.schedule(user)['changed_ids'] == []


def test_global_bubbles_minimal_preserves_and_missed_rolls(user, make_item):
    future = make_item(user, 'Future', scheduled_date=TODAY + timedelta(days=7))
    missed = make_item(user, 'Missed', scheduled_date=TODAY - timedelta(days=3))
    legacy = make_item(user, 'Poster Submission', due_date=TODAY + timedelta(days=13))
    scheduling.schedule(user)
    refresh(future, missed, legacy)
    assert future.scheduled_date == TODAY + timedelta(days=7)
    assert missed.scheduled_date == legacy.scheduled_date == TODAY
    scheduling.schedule(user, mode='global')
    refresh(future)
    assert future.scheduled_date == TODAY
    assert scheduling.schedule(user, mode='global')['changed_ids'] == []


@pytest.mark.parametrize('mode', ['minimal', 'global'])
def test_manual_dates_preserved_even_when_invalid(user, make_item, mode):
    past = make_item(user, 'Past fixed', schedule_is_manual=True, scheduled_date=TODAY - timedelta(days=1))
    future = make_item(user, 'Future fixed', schedule_is_manual=True, scheduled_date=TODAY + timedelta(days=10), due_date=TODAY + timedelta(days=5))
    result = scheduling.schedule(user, mode=mode)
    refresh(past, future)
    assert past.scheduled_date == TODAY - timedelta(days=1)
    assert future.scheduled_date == TODAY + timedelta(days=10)
    assert {c['code'] for c in result['conflicts']} >= {'past_date', 'after_deadline'}


def test_overdue_frozen_and_legacy_repaired_and_visible(user, make_item, api_for):
    due = TODAY - timedelta(days=2)
    existing = make_item(user, 'Old', due_date=due, scheduled_date=due - timedelta(days=1))
    legacy = make_item(user, 'Legacy', start_date=due - timedelta(days=3), due_date=due)
    scheduling.schedule(user, mode='global')
    refresh(existing, legacy)
    assert existing.scheduled_date == due - timedelta(days=1)
    assert legacy.scheduled_date == due
    assert scheduling.schedule(user, mode='global')['changed_ids'] == []
    response = api_for(user).get('/api/planning/overdue/')
    assert response.status_code == 200
    overdue_ids = {row['item']['id'] for bucket in ('recent', 'backlog') for row in response.data[bucket]}
    assert {legacy.pk, existing.pk} <= overdue_ids


def test_daily_local_date_once_isolated_and_history_free(user, other_user, make_item, api_for):
    future = make_item(user, 'Future', scheduled_date=TODAY + timedelta(days=8))
    other = make_item(other_user, 'Other', scheduled_date=TODAY + timedelta(days=8))
    client = api_for(user)
    with patch.object(scheduling, 'schedule', wraps=scheduling.schedule) as run:
        assert client.get('/api/planning/timeline/').status_code == 200
        assert run.call_args.kwargs['mode'] == 'global'
        assert client.get('/api/planning/timeline/').status_code == 200
        assert run.call_args.kwargs['mode'] == 'minimal'
        with freeze_time('2026-09-15'):
            assert client.get('/api/planning/timeline/').status_code == 200
            assert run.call_args.kwargs['mode'] == 'global'
    refresh(future, other)
    assert future.scheduled_date == TODAY + timedelta(days=1)
    assert other.scheduled_date == TODAY + timedelta(days=8)
    assert SchedulingState.objects.get(user=user).last_global_date == TODAY + timedelta(days=1)
    assert not SchedulingState.objects.filter(user=other_user).exists()
    assert not PlanningHistoryEntry.objects.filter(user=user).exists()


def test_completion_frees_capacity_without_bubbling(user, make_item, api_for):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    done = make_item(user, 'Done', scheduled_date=TODAY)
    later = make_item(user, 'Later', scheduled_date=TODAY + timedelta(days=1))
    assert api_for(user).post(f'/api/planning/items/{done.pk}/complete/', {'completed': True}, format='json').status_code == 200
    refresh(later)
    assert later.scheduled_date == TODAY + timedelta(days=1)
    scheduling.schedule(user, mode='global')
    refresh(later)
    assert later.scheduled_date == TODAY


def test_reschedule_auth_isolation_history_and_noop(user, other_user, api, api_for, make_item):
    assert api.post('/api/planning/timeline/reschedule/').status_code in (401, 403)
    mine = make_item(user, 'Mine', scheduled_date=TODAY + timedelta(days=7))
    theirs = make_item(other_user, 'Theirs')
    client = api_for(user)
    response = client.post('/api/planning/timeline/reschedule/')
    assert response.status_code == 200
    assert mine.pk in response.data['changed_ids']
    assert response.data['conflicts'] == []
    refresh(mine, theirs)
    assert mine.scheduled_date == TODAY
    assert theirs.scheduled_date is None
    assert client.post('/api/planning/timeline/reschedule/').data['changed_ids'] == []
    assert PlanningHistoryEntry.objects.filter(user=user, action_type='SCHEDULE').count() == 1
    history.undo(user)
    refresh(mine)
    assert mine.scheduled_date == TODAY + timedelta(days=7)
    history.redo(user)
    refresh(mine)
    assert mine.scheduled_date == TODAY


def test_daily_failure_does_not_mark_maintenance_complete(user):
    with patch.object(scheduling, 'schedule', side_effect=RuntimeError('failed')):
        with pytest.raises(RuntimeError):
            scheduling.daily_schedule(user)
    assert not SchedulingState.objects.filter(user=user).exists()


def test_global_empty_capacity_moves_forward_and_release_is_hard(user, make_item):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    fixed = make_item(user, 'Fixed', schedule_is_manual=True, scheduled_date=TODAY)
    first = make_item(user, 'First')
    second = make_item(user, 'Second')
    released = make_item(user, 'Released', start_date=TODAY + timedelta(days=6))
    scheduling.schedule(user, mode='global')
    refresh(fixed, first, second, released)
    assert fixed.scheduled_date == TODAY
    assert first.scheduled_date == TODAY + timedelta(days=1)
    assert second.scheduled_date == TODAY + timedelta(days=2)
    assert released.scheduled_date == released.start_date


# --------------------------------------------------------------------------
# Scheduler eligibility invariant
# --------------------------------------------------------------------------

def test_global_schedule_includes_actionable_parents_with_children(user, make_item):
    """Children affect priority-frontier membership, not schedulability."""
    assignment = make_item(user, 'Parent assignment', ItemType.ASSIGNMENT)
    child = make_item(user, 'Child task', parent=assignment)

    scheduling.schedule(user, mode='global')
    refresh(assignment, child)

    assert assignment.scheduled_date is not None
    assert child.scheduled_date is not None


def test_global_schedule_gives_every_actionable_item_an_execution_date(user, make_item):
    """Global scheduling must never leave active actionable work unscheduled."""
    assignment = make_item(user, 'Assignment', ItemType.ASSIGNMENT)
    task = make_item(user, 'Task')
    nested = make_item(user, 'Nested task', parent=assignment)

    scheduling.schedule(user, mode='global')
    refresh(assignment, task, nested)

    assert assignment.scheduled_date is not None
    assert task.scheduled_date is not None
    assert nested.scheduled_date is not None


def test_goal_remains_outside_scheduler_eligibility(user, make_item):
    """Structural goals do not acquire execution dates."""
    goal = make_item(user, 'Goal', ItemType.GOAL)
    make_item(user, 'Goal child', parent=goal)

    scheduling.schedule(user, mode='global')
    goal.refresh_from_db()

    assert goal.scheduled_date is None


def test_parent_remains_outside_priority_frontier_but_inside_scheduler(user, make_item):
    """Priority eligibility and scheduling eligibility are intentionally distinct."""
    assignment = make_item(user, 'Parent assignment', ItemType.ASSIGNMENT)
    make_item(user, 'Child task', parent=assignment)

    priority.reconcile(user)

    assert not PlanningItem.objects.for_user(user).priority_eligible().filter(
        pk=assignment.pk
    ).exists()

    scheduling.schedule(user, mode='global')
    assignment.refresh_from_db()

    assert assignment.scheduled_date is not None
