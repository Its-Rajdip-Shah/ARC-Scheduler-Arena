"""Behavioural proof for authority holes exposed by the final source audit."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction, IntegrityError
from planning.models import DurationCategory, PlanningItem, PlanningDependency, ProgressSegment, SchedulerAllocation
from planning.services import domain_commands as commands, dependencies, hierarchy, progress, scheduling, priority, deletion, focus, history

pytestmark = pytest.mark.django_db


def state(user):
    return list(PlanningItem.objects.filter(user=user).order_by('pk').values())


@pytest.mark.parametrize('endpoint', ['patch', 'complete'])
def test_http_dependency_completion_rejection_is_atomic(user, make_item, api_for, endpoint):
    a, b = make_item(user, 'Prerequisite'), make_item(user, 'Dependent')
    dependencies.add(a, b)
    before = state(user)
    client = api_for(user)
    if endpoint == 'patch':
        response = client.patch(f'/api/planning/items/{b.pk}/', {'title': 'Must roll back', 'is_completed': True}, format='json')
    else:
        response = client.post(f'/api/planning/items/{b.pk}/complete/', {'completed': True}, format='json')
    assert response.status_code == 400
    assert state(user) == before
    hierarchy.complete_subtree(a)
    hierarchy.complete_subtree(b)
    before = state(user)
    response = client.patch(f'/api/planning/items/{a.pk}/', {'is_completed': False}, format='json')
    assert response.status_code == 400
    assert state(user) == before
    dependencies.remove(a, b)
    assert client.patch(f'/api/planning/items/{a.pk}/', {'is_completed': False}, format='json').status_code == 200


def test_confirm_reverse_and_duration_round_trip_through_http(user, api_for):
    item = commands.create_item(user, title='Large', item_type='TASK', duration_category='UNDER_8_HOURS')
    first = progress.complete_segment(item.scheduler_allocations.first())
    item.refresh_from_db()
    assert item.percent_completed == first.percentage
    second = progress.complete_segment(item.scheduler_allocations.first())
    item.refresh_from_db()
    assert item.percent_completed == first.percentage + second.percentage
    progress.reopen_segment(first)
    item.refresh_from_db()
    assert item.percent_completed == second.percentage
    assert ProgressSegment.objects.get(pk=second.pk).percentage == second.percentage
    client = api_for(user)
    for category in ['UNDER_4_HOURS', 'UNDER_16_HOURS']:
        assert client.patch(f'/api/planning/items/{item.pk}/', {'duration_category': category}, format='json').status_code == 200
        item.refresh_from_db()
        assert item.percent_completed == 0
    assert not item.progress_segments.exists()


def test_generic_command_cannot_write_owned_state(user, make_item, other_user):
    item = make_item(user, 'Protected')
    before = state(user)
    for changes in [{'user': other_user}, {'is_deleted': True}, {'priority_position': 7}, {'percent_completed': 25}, {'scheduled_date': timezone.localdate()}]:
        with pytest.raises(ValidationError):
            commands.update_item(item, changes)
        assert state(user) == before


def test_http_delete_undo_restores_dependency_and_identity(user, make_item, api_for):
    a, b = make_item(user, 'A'), make_item(user, 'B')
    dependencies.add(a, b)
    client = api_for(user)
    assert client.delete(f'/api/planning/items/{a.pk}/').status_code == 204
    assert not PlanningDependency.objects.exists()
    assert client.post('/api/planning/items/undo/').status_code == 200
    a.refresh_from_db()
    assert not a.is_deleted
    assert PlanningDependency.objects.filter(prerequisite=a, dependent=b).exists()
    assert client.post('/api/planning/items/redo/').status_code == 200
    assert not PlanningDependency.objects.exists()


def test_http_reparent_rejects_deleted_and_foreign_parent(user, other_user, make_item, api_for):
    item = make_item(user, 'Child')
    deleted = make_item(user, 'Deleted', is_deleted=True)
    foreign = make_item(other_user, 'Private')
    before = state(user)
    for parent in [deleted, foreign, item]:
        response = api_for(user).patch(f'/api/planning/items/{item.pk}/', {'parent': parent.pk, 'title': 'Rejected'}, format='json')
        assert response.status_code == 400
        assert state(user) == before


def test_replacement_preserves_priority_and_rolls_back_nonfrontier(user, make_item):
    a, b = make_item(user, 'Unpositioned A'), make_item(user, 'Unpositioned B')
    scheduling.schedule(user)
    scheduling.replace(user, b.pk, a.pk)
    assert list(PlanningItem.objects.filter(user=user).values_list('priority_position', flat=True)) == [None, None]
    child = commands.create_item(user, title='Child', item_type='TASK', parent=a)
    before = state(user)
    with pytest.raises(scheduling.SchedulingConflict):
        scheduling.replace(user, b.pk, a.pk)
    assert state(user) == before


def test_scheduler_replaces_proposal_without_manufacturing_manual_intent(user, make_item):
    today = timezone.localdate()
    item = make_item(user, 'Automatic proposal', scheduled_date=today + timedelta(days=20), percent_completed=100, duration_category='UNDER_8_HOURS')
    before = (item.is_completed, item.percent_completed, item.manual_requested_date, item.priority_position)
    scheduling.schedule(user, mode='global')
    item.refresh_from_db()
    assert (item.is_completed, item.percent_completed, item.manual_requested_date, item.priority_position) == before
    assert item.scheduled_date == today
    assert item.manual_requested_date is None


def test_focus_clears_on_dependency_and_release_without_planning_writes(user, make_item):
    a, b = make_item(user, 'A'), make_item(user, 'B')
    priority.reconcile(user)
    scheduling.schedule(user)
    focus.set_current(user, b)
    dependencies.add(a, b)
    before = state(user)
    assert focus.build(user)['current_item_id'] is None
    assert state(user) == before
    dependencies.remove(a, b)
    commands.update_item(b, {'start_date': timezone.localdate() + timedelta(days=2)})
    assert focus.set_current(user, b) is None


def test_repeated_cross_domain_lifecycle_has_no_drift(user):
    a = commands.create_item(user, title='A', item_type='TASK')
    b = commands.create_item(user, title='B', item_type='TASK')
    original = list(priority.ordered(user).values_list('pk', flat=True))
    for _ in range(4):
        dependencies.add(a, b)
        hierarchy.complete_subtree(a)
        scheduling.set_anchor(b, timezone.localdate())
        deletion.delete_subtree(b)
        deletion.restore_subtree(b)
        scheduling.remove_anchor(b)
        dependencies.remove(a, b)
        hierarchy.reopen(a)
        assert list(priority.ordered(user).values_list('pk', flat=True)) == original
        assert not PlanningDependency.objects.exists()
        assert all(not row.is_completed and not row.is_deleted and row.manual_requested_date is None for row in PlanningItem.objects.filter(user=user))


def test_undo_rejects_later_conflicting_edit_and_preserves_unrelated_edit(user, make_item, api_for):
    item = make_item(user, 'Original')
    client = api_for(user)
    assert client.patch(f'/api/planning/items/{item.pk}/', {'title': 'Checkpoint'}, format='json').status_code == 200
    commands.update_item(item, {'title': 'Later'})
    before = state(user)
    with pytest.raises(ValidationError):
        history.undo(user)
    assert state(user) == before
    commands.update_item(item, {'title': 'Checkpoint', 'description': 'Independent fact'})
    history.undo(user)
    item.refresh_from_db()
    assert item.title == 'Original'
    assert item.description == 'Independent fact'


def test_progress_completion_and_reverse_reconcile_completion_and_priority(user):
    item = commands.create_item(user, title='Large', item_type='TASK', duration_category='UNDER_8_HOURS')
    confirmed = []
    # Complete the currently proposed remaining allocations, without relying
    # on the scheduler's session sizing policy.
    while item.percent_completed < 100:
        allocations = list(item.scheduler_allocations.all())
        allocation = allocations[0]
        # Confirm remaining work as a user-recorded allocation for final session.
        allocation.percentage = 100 - item.percent_completed
        allocation.save(update_fields=['percentage'])
        confirmed.append(progress.complete_segment(allocation))
        item.refresh_from_db()
    assert item.is_completed and item.priority_position is None
    progress.reopen_segment(confirmed[-1])
    item.refresh_from_db()
    assert not item.is_completed and item.percent_completed == 0
    assert item.priority_position is not None
    assert sum(a.percentage for a in item.scheduler_allocations.all()) == 100


def test_scheduler_failure_rolls_back_entire_http_create(user, api_for, monkeypatch):
    # Failure injection tests the enclosing transaction; no domain behaviour is mocked.
    def fail(*args, **kwargs):
        raise RuntimeError('Injected proposal failure')
    monkeypatch.setattr(scheduling, '_reconcile_progress_allocations', fail)
    before = state(user)
    with pytest.raises(RuntimeError):
        api_for(user).post('/api/planning/items/', {'title': 'Rollback', 'item_type': 'TASK'}, format='json')
    assert state(user) == before


def test_anchor_overload_requires_confirmation_and_preserves_exact_prestate(user, make_item, monkeypatch):
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 1)
    a, b = make_item(user, 'A'), make_item(user, 'B')
    scheduling.set_anchor(a, timezone.localdate())
    before = state(user)
    with pytest.raises(ValidationError):
        scheduling.set_anchor(b, timezone.localdate())
    assert state(user) == before
    scheduling.set_anchor(b, timezone.localdate(), allow_overload=True)
    b.refresh_from_db()
    assert b.manual_requested_date == timezone.localdate()


def test_restore_cycle_via_actual_delete_history_rolls_back(user, make_item, api_for):
    a, b, c = [make_item(user, title) for title in ['A', 'B', 'C']]
    dependencies.add(a, b)
    dependencies.add(b, c)
    client = api_for(user)
    assert client.delete(f'/api/planning/items/{b.pk}/').status_code == 204
    dependencies.add(c, a)
    before = state(user)
    assert client.post('/api/planning/items/undo/').status_code == 400
    assert state(user) == before
    assert list(PlanningDependency.objects.values_list('prerequisite_id', 'dependent_id')) == [(c.pk, a.pk)]


def test_expiry_retains_recovery_history_without_scheduler_authority(user, make_item):
    today = timezone.localdate()
    item = make_item(user, 'Missed', manual_requested_date=today - timedelta(days=1))
    scheduling.daily_schedule(user, today)
    item.refresh_from_db()
    assert item.manual_requested_date is None
    assert item.expired_manual_requested_date == today - timedelta(days=1)
    before = item.expired_manual_requested_date
    scheduling.schedule(user, today)
    item.refresh_from_db()
    assert item.expired_manual_requested_date == before
    scheduling.remove_anchor(item)
    item.refresh_from_db()
    assert item.expired_manual_requested_date is None


def test_focus_uses_disposable_execution_rank_not_canonical_priority(user, make_item):
    a = make_item(user, 'Important', priority_position=1, scheduled_date=timezone.localdate(), execution_rank=2)
    b = make_item(user, 'Execute first', priority_position=2, scheduled_date=timezone.localdate(), execution_rank=1)
    before = state(user)
    assert [row.item_id for row in focus.build(user)['candidates']] == [b.pk, a.pk]
    assert state(user) == before


def test_anchor_expiry_and_focus_reprioritisation_roll_back_on_scheduler_failure(user, make_item, monkeypatch):
    a = make_item(user, 'A', manual_requested_date=timezone.localdate() - timedelta(days=1))
    b = make_item(user, 'B')
    priority.reconcile(user)
    before = state(user)
    def fail(*args, **kwargs):
        raise RuntimeError('Injected failure')
    monkeypatch.setattr(scheduling, 'schedule', fail)
    for operation in [lambda: scheduling.reconcile_anchors(user), lambda: focus.reprioritise(user, b, 1)]:
        with pytest.raises(RuntimeError):
            operation()
        assert state(user) == before


def test_completed_large_parent_decomposition_preserves_history_and_exposes_closure(user):
    parent = commands.create_item(user, title='Project', item_type='TASK', duration_category='UNDER_8_HOURS', is_completed=True)
    records = list(parent.progress_segments.values('id', 'percentage'))
    child = commands.create_item(user, title='Extra work', item_type='TASK', parent=parent)
    parent.refresh_from_db()
    assert not parent.is_completed and parent.scheduled_date is None
    assert child.percent_completed == 0
    hierarchy.complete_subtree(child)
    parent.refresh_from_db()
    assert parent.duration_category == 'UNDER_8_HOURS'
    assert parent.scheduled_date is not None
    assert not parent.scheduler_allocations.exists()
    assert list(parent.progress_segments.values('id', 'percentage')) == records
