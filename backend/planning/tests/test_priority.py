"""The single global priority order (FR-09)."""

import random

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

from planning.models import ItemType, PlanningItem
from planning.services import priority

from .conftest import positions

pytestmark = pytest.mark.django_db


@pytest.fixture
def tasks(user, make_item):
    """Five positioned tasks, named for their starting position."""
    created = [make_item(user, f't{i}') for i in range(1, 6)]
    for task in created:
        priority.assign_initial_position(task)
    return created


def titles(user):
    return [title for _, title in positions(user)]


# --------------------------------------------------------------------------
# Initial placement
# --------------------------------------------------------------------------

def test_positions_start_at_one_and_increment(user, tasks):
    assert positions(user) == [(1, 't1'), (2, 't2'), (3, 't3'), (4, 't4'), (5, 't5')]


def test_goals_never_take_a_position(user, make_item):
    goal = make_item(user, 'goal', ItemType.GOAL)
    assert priority.assign_initial_position(goal) is None
    goal.refresh_from_db()
    assert goal.priority_position is None


def test_completed_tasks_never_take_a_position(user, make_item):
    done = make_item(user, 'done', is_completed=True)
    assert priority.assign_initial_position(done) is None


def test_assigning_twice_is_a_no_op(user, make_item):
    task = make_item(user, 'task')
    first = priority.assign_initial_position(task)
    assert priority.assign_initial_position(task) == first


def test_each_user_has_an_independent_order(user, other_user, make_item, tasks):
    theirs = make_item(other_user, 'theirs')
    priority.assign_initial_position(theirs)
    # Position 1 is already taken by alice; bob still starts at 1.
    assert theirs.priority_position == 1


# --------------------------------------------------------------------------
# Reordering
# --------------------------------------------------------------------------

def test_moving_a_task_up_shifts_the_others_down(user, tasks):
    priority.reorder(user, tasks[3].pk, 1)
    assert titles(user) == ['t4', 't1', 't2', 't3', 't5']


def test_moving_a_task_down_shifts_the_others_up(user, tasks):
    priority.reorder(user, tasks[0].pk, 4)
    assert titles(user) == ['t2', 't3', 't4', 't1', 't5']


def test_moving_a_task_to_its_current_row_changes_nothing(user, tasks):
    before = titles(user)
    priority.reorder(user, tasks[2].pk, 3)
    assert titles(user) == before


def test_a_position_past_the_end_clamps_to_the_end(user, tasks):
    priority.reorder(user, tasks[0].pk, 999)
    assert titles(user) == ['t2', 't3', 't4', 't5', 't1']


def test_a_position_below_one_clamps_to_the_top(user, tasks):
    priority.reorder(user, tasks[4].pk, -5)
    assert titles(user) == ['t5', 't1', 't2', 't3', 't4']


def test_reordering_an_unpositioned_task_is_refused(user, tasks, make_item):
    goal = make_item(user, 'goal', ItemType.GOAL)
    with pytest.raises(ValidationError):
        priority.reorder(user, goal.pk, 1)


def test_reordering_cannot_reach_another_users_task(user, other_user, make_item, tasks):
    theirs = make_item(other_user, 'theirs')
    priority.assign_initial_position(theirs)
    with pytest.raises(ValidationError):
        priority.reorder(user, theirs.pk, 1)


def test_a_swap_needs_no_temporary_offset(user, tasks):
    """Proves the deferred constraint is doing its job: this reorder writes a
    duplicate position mid-transaction and only the committed state is
    checked."""
    priority.reorder(user, tasks[0].pk, 2)
    assert titles(user) == ['t2', 't1', 't3', 't4', 't5']


@pytest.mark.parametrize('seed', range(10))
def test_randomised_reordering_keeps_the_order_dense_and_unique(user, tasks, seed):
    rng = random.Random(seed)
    ids = [task.pk for task in tasks]

    for _ in range(20):
        priority.reorder(user, rng.choice(ids), rng.randint(1, len(ids)))

        current = positions(user)
        numbers = [number for number, _ in current]
        assert numbers == list(range(1, len(ids) + 1)), f'not dense: {numbers}'
        assert len(set(numbers)) == len(numbers), f'duplicates: {numbers}'
        assert len({title for _, title in current}) == len(ids), 'lost a task'


# --------------------------------------------------------------------------
# Leaving and rejoining the order
# --------------------------------------------------------------------------

def test_releasing_a_position_closes_the_gap(user, tasks):
    priority.release_position(tasks[1])
    assert titles(user) == ['t1', 't3', 't4', 't5']
    assert [number for number, _ in positions(user)] == [1, 2, 3, 4]


def test_releasing_twice_is_harmless(user, tasks):
    priority.release_position(tasks[1])
    priority.release_position(tasks[1])
    assert len(positions(user)) == 4


def test_restoring_returns_to_the_previous_relative_position(user, tasks):
    priority.release_position(tasks[0])
    tasks[0].refresh_from_db()

    priority.restore_position(tasks[0])

    assert titles(user) == ['t1', 't2', 't3', 't4', 't5']


def test_releasing_many_positions_at_once_renumbers_the_rest(user, tasks):
    priority.release_positions(user, [tasks[0].pk, tasks[2].pk, tasks[4].pk])
    assert positions(user) == [(1, 't2'), (2, 't4')]


def test_renumber_repairs_a_sparse_order(user, tasks):
    PlanningItem.objects.filter(pk=tasks[0].pk).update(priority_position=40)
    PlanningItem.objects.filter(pk=tasks[1].pk).update(priority_position=70)

    priority.renumber(user)

    numbers = [number for number, _ in positions(user)]
    assert numbers == [1, 2, 3, 4, 5]
    # 40 and 70 sorted after the untouched 3, 4, 5.
    assert titles(user) == ['t3', 't4', 't5', 't1', 't2']


# --------------------------------------------------------------------------
# The database backstop
# --------------------------------------------------------------------------

def test_the_database_refuses_a_duplicate_position(user, tasks):
    """Duplicate active positions fail on both supported database engines."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PlanningItem.objects.filter(pk=tasks[0].pk).update(
                priority_position=tasks[1].priority_position
            )


def test_the_database_allows_many_null_positions(user, make_item):
    for index in range(10):
        make_item(user, f'goal-{index}', ItemType.GOAL)
    assert PlanningItem.objects.for_user(user).filter(priority_position=None).count() == 10
