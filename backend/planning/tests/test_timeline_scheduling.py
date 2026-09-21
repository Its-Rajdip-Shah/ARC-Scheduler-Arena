from datetime import date, timedelta

import pytest
from freezegun import freeze_time

from planning.models import (AssignmentDetail, DurationCategory, ItemType, PlanningHistoryEntry,
                             PlanningItem, SchedulingOverload)
from planning.services import history, priority, scheduling

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock():
    with freeze_time('2026-09-14'):
        yield
TODAY = date(2026, 9, 14)


def snapshot(user):
    return scheduling._snapshot(user)


@pytest.mark.parametrize('bucket,limit', [(DurationCategory.UNDER_20_MINUTES, 5), (DurationCategory.UNDER_1_HOUR, 4), (DurationCategory.UNDER_4_HOURS, 3), (DurationCategory.UNDER_8_HOURS, 3), (DurationCategory.UNDER_16_HOURS, 3), (DurationCategory.OVER_16_HOURS, 3)])
def test_capacity_is_global_and_priority_ordered(user, make_item, bucket, limit):
    roots = [make_item(user, str(i), ItemType.GOAL) for i in range(2)]
    items = [make_item(user, str(i), parent=roots[i % 2], duration_category=bucket) for i in range(limit + 1)]
    priority.reconcile(user)
    priority.reorder(user, items[-1].pk, 1)
    result = scheduling.schedule(user, TODAY)
    assert result['conflicts'] == []
    for item in items:
        item.refresh_from_db()
    assert items[-1].scheduled_date == TODAY
    assert items[-2].scheduled_date == TODAY + timedelta(days=1)
    assert sum(item.scheduled_date == TODAY for item in items) == limit


def test_release_deadline_assignment_interval_and_overdue(user, make_item):
    task = make_item(user, 'Task', start_date=TODAY + timedelta(days=1), due_date=TODAY + timedelta(days=1))
    assignment = make_item(user, 'Assignment', ItemType.ASSIGNMENT, start_date=TODAY, due_date=TODAY + timedelta(days=9))
    past = make_item(user, 'Overdue', due_date=TODAY - timedelta(days=1))
    result = scheduling.schedule(user, TODAY)
    task.refresh_from_db()
    assignment.refresh_from_db()
    past.refresh_from_db()
    assert task.scheduled_date == task.due_date
    assert assignment.scheduled_date == TODAY
    assert past.scheduled_date >= TODAY
    assert past.due_date == TODAY - timedelta(days=1)
    assert {'item_id': past.pk, 'code': 'overdue'} in result['conflicts']


def test_missed_manual_work_retains_user_dates(user, make_item, monkeypatch):
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 1)
    first = make_item(user, 'First', scheduled_date=TODAY - timedelta(days=3), manual_requested_date=TODAY - timedelta(days=3))
    second = make_item(user, 'Second', scheduled_date=TODAY - timedelta(days=1), manual_requested_date=TODAY - timedelta(days=1))
    scheduling.schedule(user, TODAY)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.scheduled_date >= TODAY
    assert second.scheduled_date >= TODAY
    assert scheduling.schedule(user, TODAY)['changed_ids'] == []


def test_manual_move_overload_and_undo_redo(user, other_user, make_item, monkeypatch):
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 1)
    first = make_item(user, 'First', scheduled_date=TODAY, manual_requested_date=TODAY)
    second = make_item(user, 'Second')
    third = make_item(user, 'Third')
    theirs = make_item(other_user, 'Other', scheduled_date=TODAY - timedelta(days=5))
    before = snapshot(user)
    with pytest.raises(scheduling.SchedulingConflict):
        scheduling.move_to_date(user, second.pk, TODAY)
    assert snapshot(user) == before
    scheduling.move_to_date(user, second.pk, TODAY, allow_overload=True)
    after = snapshot(user)
    assert SchedulingOverload.objects.get(user=user, date=TODAY).allowed
    first.refresh_from_db(); second.refresh_from_db(); third.refresh_from_db(); theirs.refresh_from_db()
    assert first.scheduled_date == second.scheduled_date == TODAY
    assert third.scheduled_date > TODAY  # overload never expands automatic capacity
    assert theirs.scheduled_date == TODAY - timedelta(days=5)
    assert PlanningHistoryEntry.objects.filter(user=user).count() == 1
    history.undo(user)
    assert snapshot(user) == before
    history.redo(user)
    assert snapshot(user) == after


@pytest.mark.parametrize('overload', [False, True])
def test_replacement_execution_intent_and_history(user, make_item, overload, monkeypatch):
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 2)
    a, b, c, d = [make_item(user, title) for title in 'ABCD']
    scheduling.schedule(user, TODAY)
    before = snapshot(user)
    scheduling.replace(user, d.pk, a.pk, allow_overload=overload)
    after = snapshot(user)
    assert history.capture_priority(user, include_unpositioned=True) == before['priority']
    a.refresh_from_db(); b.refresh_from_db(); d.refresh_from_db()
    assert d.scheduled_date == TODAY
    assert b.manual_requested_date is None
    if not overload:
        assert b.scheduled_date == TODAY
    assert a.scheduled_date == (TODAY if overload else TODAY + timedelta(days=1))
    assert PlanningHistoryEntry.objects.filter(user=user).count() == 1
    history.undo(user); assert snapshot(user) == before
    history.redo(user); assert snapshot(user) == after


def test_replacement_deadline_conflict_rolls_back_everything(user, make_item, monkeypatch):
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 1)
    a = make_item(user, 'A', due_date=TODAY)
    d = make_item(user, 'D')
    scheduling.schedule(user, TODAY)
    before = snapshot(user)
    with pytest.raises(scheduling.SchedulingConflict) as exc:
        scheduling.replace(user, d.pk, a.pk)
    assert exc.value.conflicts == [{'item_id': a.pk, 'code': 'no_capacity_before_deadline'}]
    assert snapshot(user) == before
    assert not PlanningHistoryEntry.objects.filter(user=user).exists()


@pytest.mark.parametrize('offset,code', [(-1, 'past_date'), (0, 'before_start'), (4, 'after_deadline')])
def test_exact_move_constraint_conflicts(user, make_item, offset, code):
    item = make_item(user, 'Task', start_date=TODAY + timedelta(days=1), due_date=TODAY + timedelta(days=3))
    before = snapshot(user)
    with pytest.raises(scheduling.SchedulingConflict) as exc:
        scheduling.move_to_date(user, item.pk, TODAY + timedelta(days=offset))
    assert exc.value.conflicts == [{'item_id': item.pk, 'code': code}]
    assert snapshot(user) == before


def test_timeline_api_context_and_tenant_scoped_operations(user, other_user, api_for, make_item):
    client = api_for(user)
    root = make_item(user, 'Root', ItemType.GOAL)
    task = make_item(user, 'Assignment', ItemType.ASSIGNMENT, parent=root, due_date=TODAY + timedelta(days=5))
    AssignmentDetail.objects.create(planning_item=task, submission_url='https://example.com/submit')
    other = make_item(other_user, 'Private')
    response = client.get('/api/planning/timeline/')
    assert response.status_code == 200, response.data
    row = response.data['groups'][0]['items'][0]
    assert row['scheduled_date'] == TODAY.isoformat()
    assert row['due_date'] != row['scheduled_date']
    assert row['submission_url'] == 'https://example.com/submit'
    assert row['hierarchy_path'] == [{'id': root.pk, 'title': root.title}]
    assert row['overdue'] is False
    before = snapshot(user)
    response = client.post('/api/planning/timeline/move/', {'item_id': other.pk, 'date': TODAY.isoformat()}, format='json')
    assert response.status_code == 409
    assert response.data['conflicts'][0]['code'] == 'not_eligible'
    assert snapshot(user) == before


def test_estimate_defaults_and_null_rejected(user, api_for):
    client = api_for(user)
    response = client.post('/api/planning/items/', {'title': 'Default', 'item_type': 'TASK'}, format='json')
    assert response.status_code == 201
    assert response.data['duration_category'] == DurationCategory.UNDER_1_HOUR
    response = client.post('/api/planning/items/', {'title': 'Invalid', 'item_type': 'TASK', 'duration_category': None}, format='json')
    assert response.status_code == 400


def test_baseline_policy_disabled_bucket_and_no_capacity_mutation_api(user, api_for, make_item, monkeypatch):
    client = api_for(user)
    item = make_item(user, 'Task')
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 1)
    assert scheduling.schedule(user)['conflicts'] == []
    assert scheduling.capacities(user)[DurationCategory.UNDER_1_HOUR] == 1
    before = snapshot(user)
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 0)
    result = scheduling.schedule(user)
    assert {'item_id': item.pk, 'code': 'capacity_disabled'} in result['conflicts']
    assert snapshot(user) == before
    assert PlanningItem.objects.get(pk=item.pk).scheduled_date == TODAY
    response = client.patch('/api/planning/timeline/capacity/', {DurationCategory.UNDER_1_HOUR: 1}, format='json')
    assert response.status_code == 404
    assert snapshot(user) == before


def test_manual_endpoints_report_changes_and_overload_is_tenant_owned(user, other_user, api_for, make_item):
    client = api_for(user)
    a, b = [make_item(user, title) for title in 'AB']
    SchedulingOverload.objects.create(user=other_user, date=TODAY, allowed=True)
    response = client.post('/api/planning/timeline/move/', {
        'item_id': a.pk, 'date': TODAY.isoformat(),
    }, format='json')
    assert response.status_code == 200, response.data
    assert a.pk in response.data['changed_ids']
    response = client.post('/api/planning/timeline/replace/', {
        'replacement_id': b.pk, 'displaced_id': a.pk,
    }, format='json')
    assert response.status_code == 200, response.data
    assert b.pk in response.data['changed_ids']
    assert client.get('/api/planning/timeline/').data['overload'] == []
    response = client.post('/api/planning/timeline/overload/', {
        'date': TODAY.isoformat(), 'allowed': True,
    }, format='json')
    assert response.status_code == 200, response.data
    assert len(client.get('/api/planning/timeline/').data['overload']) == 1
    history.undo(user)
    assert not SchedulingOverload.objects.filter(user=user).exists()
    assert SchedulingOverload.objects.filter(user=other_user, allowed=True).exists()
    history.redo(user)
    assert SchedulingOverload.objects.filter(user=user, allowed=True).exists()


def test_timeline_keeps_constraint_span_when_execution_is_outside_window(user, api_for, make_item):
    item = make_item(user, 'Long assignment', ItemType.ASSIGNMENT,
                     start_date=TODAY - timedelta(days=10), due_date=TODAY + timedelta(days=30),
                     scheduled_date=TODAY - timedelta(days=1), is_completed=True)
    response = api_for(user).get('/api/planning/timeline/', {
        'from': TODAY.isoformat(), 'to': (TODAY + timedelta(days=7)).isoformat(),
    })
    assert response.status_code == 200
    row = next(row for group in response.data['groups'] for row in group['items'] if row['id'] == item.pk)
    assert row['scheduled_date'] == (TODAY - timedelta(days=1)).isoformat()
    assert row['due_date'] == (TODAY + timedelta(days=30)).isoformat()


@pytest.mark.parametrize('bucket,limit', [
    (DurationCategory.UNDER_20_MINUTES, 5),
    (DurationCategory.UNDER_1_HOUR, 4),
    (DurationCategory.UNDER_4_HOURS, 3),
])
def test_timeline_load_schedules_unscheduled_work_globally_without_history(user, other_user, api_for, make_item, bucket, limit):
    roots = [make_item(user, title, ItemType.GOAL) for title in ('A', 'B')]
    items = [make_item(user, str(i), parent=roots[i % 2], duration_category=bucket)
             for i in range(limit + 1)]
    other = make_item(other_user, 'Private', duration_category=bucket)
    priority.reconcile(user)
    # Include an existing redo branch: reads must preserve history, not just its count.
    history.record_checkpoint(user, 'PRIORITY', {'priority': []}, {'priority': history.capture_priority(user)})
    PlanningHistoryEntry.objects.filter(user=user).update(is_undone=True)
    history_before = list(PlanningHistoryEntry.objects.filter(user=user).values())
    response = api_for(user).get('/api/planning/timeline/')
    assert response.status_code == 200
    rows = {row['id']: row for group in response.data['groups'] for row in group['items']}
    assert [rows[item.pk]['scheduled_date'] for item in items] == [
        TODAY.isoformat()
    ] * limit + [(TODAY + timedelta(days=1)).isoformat()]
    assert response.data['conflicts'] == []
    assert api_for(user).get('/api/planning/timeline/').data == response.data
    assert list(PlanningHistoryEntry.objects.filter(user=user).values()) == history_before
    other.refresh_from_db()
    assert other.scheduled_date is None
    assert other.priority_position is None


def test_timeline_read_respects_policy_manual_overload_and_constraints(user, api_for, make_item, monkeypatch):
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 1)
    SchedulingOverload.objects.create(user=user, date=TODAY, allowed=True)
    manual = [make_item(user, title, scheduled_date=TODAY, manual_requested_date=TODAY)
              for title in ('Manual A', 'Manual B')]
    missed = make_item(user, 'Missed', scheduled_date=TODAY - timedelta(days=2))
    assignment = make_item(user, 'Assignment', ItemType.ASSIGNMENT,
                           start_date=TODAY + timedelta(days=2), due_date=TODAY + timedelta(days=2))
    overdue = make_item(user, 'Overdue', due_date=TODAY - timedelta(days=1))
    response = api_for(user).get('/api/planning/timeline/')
    assert response.status_code == 200
    for item in [*manual, missed, assignment, overdue]:
        item.refresh_from_db()
    assert all(item.scheduled_date == TODAY and item.manual_requested_date == item.scheduled_date for item in manual)
    assert missed.scheduled_date == TODAY + timedelta(days=1)
    assert assignment.scheduled_date == assignment.start_date == assignment.due_date
    assert overdue.due_date == TODAY - timedelta(days=1)
    assert overdue.scheduled_date >= TODAY
    assert {'item_id': overdue.pk, 'code': 'overdue'} in response.data['conflicts']
    assert not PlanningHistoryEntry.objects.filter(user=user).exists()
