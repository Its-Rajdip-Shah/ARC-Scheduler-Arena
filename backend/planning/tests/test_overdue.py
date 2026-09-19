"""Recent and Backlog classification (FR-12)."""

from datetime import date, timedelta

import pytest
from freezegun import freeze_time

from planning.models import ItemType
from planning.services import overdue

pytestmark = pytest.mark.django_db

FROZEN = '2026-09-14'
TODAY = date(2026, 9, 14)


def days(offset):
    return TODAY + timedelta(days=offset)


def bucket_titles(result, bucket):
    return [entry['item'].title for entry in result[bucket]]


@pytest.fixture
def root(user, make_item):
    return make_item(user, 'ELEC3609', ItemType.GOAL)


# --------------------------------------------------------------------------
# The Recent / Backlog boundary
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    'days_past, expected',
    [
        (1, 'recent'),
        (3, 'recent'),
        (6, 'recent'),
        (7, 'recent'),   # "seven days or less" is Recent
        (8, 'backlog'),  # "more than seven days" is Backlog
        (30, 'backlog'),
    ],
)
@freeze_time(FROZEN)
def test_the_seven_day_boundary(user, make_item, root, days_past, expected):
    make_item(user, 'task', parent=root, due_date=days(-days_past))

    result = overdue.classify(user, TODAY)

    assert bucket_titles(result, expected) == ['task']
    other = 'backlog' if expected == 'recent' else 'recent'
    assert bucket_titles(result, other) == []


@freeze_time(FROZEN)
def test_work_due_today_is_not_yet_overdue(user, make_item, root):
    make_item(user, 'task', parent=root, due_date=TODAY)

    result = overdue.classify(user, TODAY)

    assert result == {'recent': [], 'backlog': []}


@freeze_time(FROZEN)
def test_future_work_is_not_overdue(user, make_item, root):
    make_item(user, 'task', parent=root, due_date=days(5))
    assert overdue.classify(user, TODAY) == {'recent': [], 'backlog': []}


# --------------------------------------------------------------------------
# What can and cannot be overdue
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_an_adaptive_task_is_never_overdue(user, make_item, root):
    """The structural point: no due_date means FR-11 reschedules it instead."""
    make_item(user, 'adaptive', parent=root, scheduled_date=days(-20))

    assert overdue.classify(user, TODAY) == {'recent': [], 'backlog': []}


@freeze_time(FROZEN)
def test_a_completed_task_is_never_overdue(user, make_item, root):
    make_item(user, 'done', parent=root, due_date=days(-10), is_completed=True)
    assert overdue.classify(user, TODAY) == {'recent': [], 'backlog': []}


@freeze_time(FROZEN)
def test_a_goal_is_never_overdue(user, make_item, root):
    """Goals are containers; only tasks and assignments are actionable."""
    make_item(user, 'goal', ItemType.GOAL, parent=root, due_date=days(-10))
    assert overdue.classify(user, TODAY) == {'recent': [], 'backlog': []}


@freeze_time(FROZEN)
def test_an_overdue_assignment_is_included(user, make_item, root):
    make_item(user, 'report', ItemType.ASSIGNMENT, parent=root, due_date=days(-2))
    assert bucket_titles(overdue.classify(user, TODAY), 'recent') == ['report']


# --------------------------------------------------------------------------
# Presentation details the wireframe needs
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_entries_carry_the_hierarchy_path(user, make_item, root):
    mid = make_item(user, 'Assignment 2', ItemType.GOAL, parent=root)
    make_item(user, 'Draft the ERD', parent=mid, due_date=days(-2))

    entry = overdue.classify(user, TODAY)['recent'][0]

    assert entry['hierarchy_path'] == ['ELEC3609', 'Assignment 2', 'Draft the ERD']


@freeze_time(FROZEN)
def test_a_root_level_task_has_a_single_element_path(user, make_item):
    make_item(user, 'lonely', due_date=days(-1))
    entry = overdue.classify(user, TODAY)['recent'][0]
    assert entry['hierarchy_path'] == ['lonely']


@freeze_time(FROZEN)
def test_entries_report_how_late_they_are(user, make_item, root):
    make_item(user, 'task', parent=root, due_date=days(-4))
    assert overdue.classify(user, TODAY)['recent'][0]['days_overdue'] == 4


@freeze_time(FROZEN)
def test_the_oldest_work_is_listed_first_in_each_bucket(user, make_item, root):
    make_item(user, 'newer', parent=root, due_date=days(-2))
    make_item(user, 'older', parent=root, due_date=days(-5))
    make_item(user, 'ancient', parent=root, due_date=days(-40))
    make_item(user, 'old', parent=root, due_date=days(-12))

    result = overdue.classify(user, TODAY)

    assert bucket_titles(result, 'recent') == ['older', 'newer']
    assert bucket_titles(result, 'backlog') == ['ancient', 'old']


# --------------------------------------------------------------------------
# Isolation and helpers
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_only_the_requested_users_work_is_returned(user, other_user, make_item):
    make_item(user, 'mine', due_date=days(-2))
    make_item(other_user, 'theirs', due_date=days(-2))

    assert bucket_titles(overdue.classify(user, TODAY), 'recent') == ['mine']
    assert bucket_titles(overdue.classify(other_user, TODAY), 'recent') == ['theirs']


@freeze_time(FROZEN)
def test_is_overdue_matches_the_queryset(user, make_item, root):
    late = make_item(user, 'late', parent=root, due_date=days(-1))
    adaptive = make_item(user, 'adaptive', parent=root, scheduled_date=days(-1))
    goal = make_item(user, 'goal', ItemType.GOAL, parent=root, due_date=days(-1))

    assert overdue.is_overdue(late, TODAY) is True
    assert overdue.is_overdue(adaptive, TODAY) is False
    assert overdue.is_overdue(goal, TODAY) is False
