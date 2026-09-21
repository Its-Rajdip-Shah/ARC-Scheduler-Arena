"""Global capacity roll-forward.

The clock is frozen throughout so that "yesterday" and "today" mean something
stable, and so the idempotency tests can run the sweep twice inside one day.
"""

from datetime import date, timedelta

import pytest
from freezegun import freeze_time

from planning.models import DurationCategory, ItemType, PlanningItem
from planning.services import priority, scheduling

pytestmark = pytest.mark.django_db

FROZEN = '2026-09-14'
TODAY = date(2026, 9, 14)


def days(offset):
    return TODAY + timedelta(days=offset)


def schedule_of(user):
    return dict(
        PlanningItem.objects.for_user(user)
        .exclude(scheduled_date=None)
        .values_list('title', 'scheduled_date')
    )


@pytest.fixture
def root(user, make_item):
    return make_item(user, 'course', ItemType.GOAL)


# --------------------------------------------------------------------------
# Initial placement
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_an_adaptive_task_with_no_date_gets_one(user, make_item, root):
    task = make_item(user, 'task', parent=root)
    assert task.scheduled_date is None

    scheduling.roll_forward_adaptive(user, TODAY)

    task.refresh_from_db()
    assert task.scheduled_date == TODAY


@freeze_time(FROZEN)
def test_a_future_date_is_left_alone(user, make_item, root):
    task = make_item(user, 'task', parent=root, scheduled_date=days(5))

    scheduling.roll_forward_adaptive(user, TODAY)

    task.refresh_from_db()
    assert task.scheduled_date == days(5)


@freeze_time(FROZEN)
def test_a_task_with_an_expired_deadline_recovers_without_changing_deadline(user, make_item, root):
    fixed = make_item(user, 'fixed', parent=root, due_date=days(-5))

    scheduling.roll_forward_adaptive(user, TODAY)

    fixed.refresh_from_db()
    assert fixed.scheduled_date >= TODAY
    assert fixed.due_date == days(-5)


@freeze_time(FROZEN)
def test_goals_are_not_scheduled(user, make_item, root):
    sub_goal = make_item(user, 'sub-goal', ItemType.GOAL, parent=root)

    scheduling.roll_forward_adaptive(user, TODAY)

    sub_goal.refresh_from_db()
    assert sub_goal.scheduled_date is None


@freeze_time(FROZEN)
def test_completed_tasks_are_not_scheduled(user, make_item, root):
    done = make_item(user, 'done', parent=root, scheduled_date=days(-3), is_completed=True)

    scheduling.roll_forward_adaptive(user, TODAY)

    done.refresh_from_db()
    assert done.scheduled_date == days(-3)


# --------------------------------------------------------------------------
# Roll-forward
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_yesterdays_unfinished_task_moves_to_today(user, make_item, root):
    task = make_item(user, 'task', parent=root, scheduled_date=days(-1))

    scheduling.roll_forward_adaptive(user, TODAY)

    task.refresh_from_db()
    assert task.scheduled_date == TODAY


@freeze_time(FROZEN)
def test_a_long_neglected_task_lands_on_today_not_one_day_later(user, make_item, root):
    """Moving strictly one day per run would leave a task abandoned for a
    month still sitting in the past."""
    task = make_item(user, 'task', parent=root, scheduled_date=days(-30))

    scheduling.roll_forward_adaptive(user, TODAY)

    task.refresh_from_db()
    assert task.scheduled_date == TODAY


@freeze_time(FROZEN)
def test_an_overdue_task_is_rescheduled_rather_than_marked_overdue(user, make_item, root):
    """The FR-11 / FR-12 split: no due_date means no overdue state."""
    task = make_item(user, 'task', parent=root, scheduled_date=days(-4))

    scheduling.roll_forward_adaptive(user, TODAY)

    task.refresh_from_db()
    assert task.scheduled_date == TODAY
    assert not PlanningItem.objects.for_user(user).overdue(TODAY).exists()


# --------------------------------------------------------------------------
# Collision cascade
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_a_collision_pushes_the_lower_priority_task_along(user, make_item, root, monkeypatch):
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 1)
    first = make_item(user, 'first', parent=root, scheduled_date=days(-1))
    second = make_item(user, 'second', parent=root, scheduled_date=TODAY)
    priority.assign_initial_position(first)
    priority.assign_initial_position(second)

    scheduling.roll_forward_adaptive(user, TODAY)

    assert schedule_of(user) == {'first': TODAY, 'second': days(1)}


@freeze_time(FROZEN)
def test_a_collision_cascades_down_a_whole_run(user, make_item, root, monkeypatch):
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 1)
    made = []
    for index, offset in enumerate([-1, 0, 1, 2]):
        item = make_item(user, f'task-{index}', parent=root, scheduled_date=days(offset))
        priority.assign_initial_position(item)
        made.append(item)

    scheduling.roll_forward_adaptive(user, TODAY)

    assert schedule_of(user) == {
        'task-0': TODAY,
        'task-1': days(1),
        'task-2': days(2),
        'task-3': days(3),
    }


@freeze_time(FROZEN)
def test_priority_order_decides_who_moves(user, make_item, root, monkeypatch):
    """Both tasks want today; the one lower down the Priority View yields."""
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 1)
    low = make_item(user, 'low', parent=root, scheduled_date=TODAY)
    high = make_item(user, 'high', parent=root, scheduled_date=TODAY)
    priority.assign_initial_position(low)
    priority.assign_initial_position(high)
    priority.reorder(user, high.pk, 1)

    scheduling.roll_forward_adaptive(user, TODAY)

    assert schedule_of(user) == {'high': TODAY, 'low': days(1)}


@freeze_time(FROZEN)
def test_collisions_are_resolved_globally_across_roots(user, make_item, monkeypatch):
    """Different roots share the same user capacity."""
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 1)
    first_root = make_item(user, 'course-a', ItemType.GOAL)
    second_root = make_item(user, 'course-b', ItemType.GOAL)
    a = make_item(user, 'a-task', parent=first_root, scheduled_date=TODAY)
    b = make_item(user, 'b-task', parent=second_root, scheduled_date=TODAY)
    priority.assign_initial_position(a)
    priority.assign_initial_position(b)

    scheduling.roll_forward_adaptive(user, TODAY)

    assert schedule_of(user) == {'a-task': TODAY, 'b-task': days(1)}


@freeze_time(FROZEN)
def test_a_deeply_nested_task_groups_by_its_root(user, make_item, root, monkeypatch):
    monkeypatch.setitem(scheduling.BASELINE_SCHEDULER_CAPACITY, DurationCategory.UNDER_1_HOUR, 1)
    mid = make_item(user, 'mid', ItemType.GOAL, parent=root)
    deep = make_item(user, 'deep', parent=mid, scheduled_date=TODAY)
    shallow = make_item(user, 'shallow', parent=root, scheduled_date=TODAY)
    priority.assign_initial_position(shallow)
    priority.assign_initial_position(deep)

    scheduling.roll_forward_adaptive(user, TODAY)

    # Same root despite different depths, so one of them must move.
    assert sorted(schedule_of(user).values()) == [TODAY, days(1)]


# --------------------------------------------------------------------------
# Guarantees
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_due_dates_are_never_modified(user, make_item, root):
    """The central promise of FR-11: ARC reschedules its own suggestions and
    leaves real deadlines alone."""
    fixed = make_item(user, 'fixed', parent=root, due_date=days(-10), start_date=days(-20))
    adaptive = make_item(user, 'adaptive', parent=root, scheduled_date=days(-10))
    before = dict(
        PlanningItem.objects.for_user(user).values_list('id', 'due_date')
    )

    scheduling.roll_forward_adaptive(user, TODAY)

    after = dict(PlanningItem.objects.for_user(user).values_list('id', 'due_date'))
    assert after == before
    fixed.refresh_from_db()
    assert fixed.start_date == days(-20)
    adaptive.refresh_from_db()
    assert adaptive.scheduled_date == TODAY


@freeze_time(FROZEN)
def test_running_twice_in_one_day_changes_nothing_the_second_time(user, make_item, root):
    for index, offset in enumerate([-5, -3, 0, 1]):
        item = make_item(user, f'task-{index}', parent=root, scheduled_date=days(offset))
        priority.assign_initial_position(item)

    scheduling.roll_forward_adaptive(user, TODAY)
    after_first = schedule_of(user)

    changed = scheduling.roll_forward_adaptive(user, TODAY)

    assert changed == []
    assert schedule_of(user) == after_first


@freeze_time(FROZEN)
def test_no_adaptive_task_is_left_in_the_past(user, make_item, root):
    for index, offset in enumerate([-9, -4, -1, 0]):
        item = make_item(user, f'task-{index}', parent=root, scheduled_date=days(offset))
        priority.assign_initial_position(item)

    scheduling.roll_forward_adaptive(user, TODAY)

    assert all(value >= TODAY for value in schedule_of(user).values())


@freeze_time(FROZEN)
def test_another_users_schedule_is_untouched(user, other_user, make_item):
    mine_root = make_item(user, 'course', ItemType.GOAL)
    theirs_root = make_item(other_user, 'course', ItemType.GOAL)
    make_item(user, 'mine', parent=mine_root, scheduled_date=days(-3))
    theirs = make_item(other_user, 'theirs', parent=theirs_root, scheduled_date=days(-3))

    scheduling.roll_forward_adaptive(user, TODAY)

    theirs.refresh_from_db()
    assert theirs.scheduled_date == days(-3)


@freeze_time(FROZEN)
def test_a_user_with_nothing_to_schedule_is_a_no_op(user):
    assert scheduling.roll_forward_adaptive(user, TODAY) == []


def test_scheduler_does_not_schedule_parent_with_unfinished_child(user):
    """Decomposed parents are not execution-schedulable."""
    from planning.models import PlanningItem
    from planning.services.scheduling import schedule

    parent = PlanningItem.objects.create(
        user=user,
        title="Assignment 2",
        item_type="ASSIGNMENT",
    )
    child = PlanningItem.objects.create(
        user=user,
        title="Implement scheduler",
        item_type="TASK",
        parent=parent,
    )

    schedule(user)

    parent.refresh_from_db()
    child.refresh_from_db()

    assert parent.scheduled_date is None
    assert child.scheduled_date is not None


def test_parent_becomes_schedulable_when_children_complete(user):
    """Completing the frontier exposes its parent as the new frontier."""
    from planning.models import PlanningItem
    from planning.services.scheduling import schedule

    parent = PlanningItem.objects.create(
        user=user,
        title="Assignment 2",
        item_type="ASSIGNMENT",
    )
    child = PlanningItem.objects.create(
        user=user,
        title="Implement scheduler",
        item_type="TASK",
        parent=parent,
        is_completed=True,
    )

    schedule(user)

    parent.refresh_from_db()

    assert parent.scheduled_date is not None
