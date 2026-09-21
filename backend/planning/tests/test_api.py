"""Smoke tests for the planning API.

The rules themselves are tested against the services in the sibling modules.
These tests check the HTTP layer on top: status codes, payload shapes, the
custom actions, and above all that no endpoint will serve or accept another
user's rows (FR-03).
"""

import pyotp
import pytest
from freezegun import freeze_time

from accounts.tests.conftest import login_through_mfa, make_user
from planning.models import (
    AssignmentDetail,
    DurationCategory,
    ItemType,
    PlanningItem,
    Tag,
    Timezone,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def client(api_for, user):
    return api_for(user)


@pytest.fixture
def other_client(api_for, other_user):
    return api_for(other_user)


# --- Items: create, read, update, delete -----------------------------------

def test_creating_a_task_places_it_in_the_priority_order(client):
    response = client.post(
        '/api/planning/items/',
        {'item_type': ItemType.TASK, 'title': 'Read chapter 4'},
        format='json',
    )
    assert response.status_code == 201, response.data
    assert response.data['priority_position'] == 1
    assert response.data['has_deadline'] is False


def test_creating_a_goal_stays_out_of_the_priority_order(client):
    response = client.post(
        '/api/planning/items/',
        {'item_type': ItemType.GOAL, 'title': 'ELEC3609'},
        format='json',
    )
    assert response.status_code == 201, response.data
    assert response.data['priority_position'] is None


def test_a_new_item_is_numbered_after_its_siblings(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    make_item(user, 'first', parent=root)

    response = client.post(
        '/api/planning/items/',
        {'item_type': ItemType.TASK, 'title': 'second', 'parent': root.pk},
        format='json',
    )
    assert response.data['sibling_order'] == 2


def test_creating_an_assignment_with_nested_detail(client):
    response = client.post(
        '/api/planning/items/',
        {
            'item_type': ItemType.ASSIGNMENT,
            'title': 'Assignment 1',
            'due_date': '2026-10-01',
            'assignment_detail': {'weight_percent': '25.00', 'submission_url': 'https://x.test/a'},
        },
        format='json',
    )
    assert response.status_code == 201, response.data
    assert response.data['assignment_detail']['weight_percent'] == '25.00'
    assert response.data['assignment_detail']['mark_achieved'] is None


def test_assignment_detail_is_refused_on_a_plain_task(client):
    response = client.post(
        '/api/planning/items/',
        {
            'item_type': ItemType.TASK,
            'title': 'Not an assignment',
            'assignment_detail': {'weight_percent': '10.00'},
        },
        format='json',
    )
    assert response.status_code == 400


def test_a_due_date_before_the_start_date_is_refused(client):
    response = client.post(
        '/api/planning/items/',
        {
            'item_type': ItemType.TASK,
            'title': 'Backwards',
            'start_date': '2026-10-10',
            'due_date': '2026-10-01',
        },
        format='json',
    )
    assert response.status_code == 400


def test_tags_attach_and_detach_through_tag_ids(client, user, make_item):
    item = make_item(user, 'Tagged')
    reading = Tag.objects.create(user=user, name='reading')
    lab = Tag.objects.create(user=user, name='lab')

    response = client.patch(
        f'/api/planning/items/{item.pk}/',
        {'tag_ids': [reading.pk, lab.pk]},
        format='json',
    )
    assert response.status_code == 200, response.data
    assert {tag['name'] for tag in response.data['tags']} == {'lab', 'reading'}

    response = client.patch(
        f'/api/planning/items/{item.pk}/', {'tag_ids': []}, format='json'
    )
    assert response.data['tags'] == []


def test_priority_position_cannot_be_set_directly(client, user, make_item):
    make_item(user, 'first', priority_position=1)
    item = make_item(user, 'second', priority_position=2)

    response = client.patch(
        f'/api/planning/items/{item.pk}/', {'priority_position': 1}, format='json'
    )
    # Read-only on the serializer: the write is dropped rather than honoured,
    # because reordering has to go through /priority/reorder/ (FR-09).
    assert response.status_code == 200
    assert response.data['priority_position'] == 2


def test_deleting_an_item_keeps_the_order_dense(client, user, make_item):
    first = make_item(user, 'first', priority_position=1)
    make_item(user, 'second', priority_position=2)
    make_item(user, 'third', priority_position=3)

    assert client.delete(f'/api/planning/items/{first.pk}/').status_code == 204
    assert list(
        PlanningItem.objects.for_user(user)
        .exclude(priority_position=None)
        .order_by('priority_position')
        .values_list('priority_position', 'title')
    ) == [(1, 'second'), (2, 'third')]


# --- Items: filtering -------------------------------------------------------

def test_the_list_filters_by_type_and_completion(client, user, make_item):
    make_item(user, 'goal', ItemType.GOAL)
    make_item(user, 'open task')
    make_item(user, 'done task', is_completed=True)

    titles = lambda response: {row['title'] for row in response.data['results']}

    assert titles(client.get('/api/planning/items/?type=goal')) == {'goal'}
    assert titles(client.get('/api/planning/items/?completed=false')) == {'goal', 'open task'}
    assert titles(client.get('/api/planning/items/?completed=true')) == {'done task'}


def test_the_list_filters_to_one_root_subtree(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    child = make_item(user, 'week 1', parent=root)
    make_item(user, 'grandchild', parent=child)
    make_item(user, 'unrelated', ItemType.GOAL)

    response = client.get(f'/api/planning/items/?root={root.pk}')
    assert {row['title'] for row in response.data['results']} == {
        'ELEC3609', 'week 1', 'grandchild'
    }


def test_search_matches_title_and_tag_name(client, user, make_item):
    tagged = make_item(user, 'Unremarkable title')
    tagged.tags.add(Tag.objects.create(user=user, name='thermodynamics'))
    make_item(user, 'Thermodynamics reading')

    response = client.get('/api/planning/items/?search=thermo')
    assert len(response.data['results']) == 2


def test_a_search_hit_is_not_duplicated_by_its_tags(client, user, make_item):
    """Joining tags to search their names can fan a row out; distinct() is
    what keeps one item one result."""
    item = make_item(user, 'Reading week')
    for name in ('reading', 'reading-group'):
        item.tags.add(Tag.objects.create(user=user, name=name))

    response = client.get('/api/planning/items/?search=reading')
    assert len(response.data['results']) == 1


def test_a_bad_root_parameter_is_a_400_not_a_500(client):
    assert client.get('/api/planning/items/?root=abc').status_code == 400


# --- Items: tree ------------------------------------------------------------

def test_the_tree_nests_children_under_their_parent(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    week = make_item(user, 'Week 1', ItemType.GOAL, parent=root)
    make_item(user, 'Watch lecture', parent=week)

    response = client.get('/api/planning/items/tree/')
    assert response.status_code == 200

    assert len(response.data) == 1
    top = response.data[0]
    assert (top['title'], top['depth']) == ('ELEC3609', 0)
    assert (top['children'][0]['title'], top['children'][0]['depth']) == ('Week 1', 1)
    assert top['children'][0]['children'][0]['title'] == 'Watch lecture'


def test_the_tree_orders_siblings_by_sibling_order(client, user, make_item):
    root = make_item(user, 'root', ItemType.GOAL)
    make_item(user, 'third', parent=root, sibling_order=3)
    make_item(user, 'first', parent=root, sibling_order=1)
    make_item(user, 'second', parent=root, sibling_order=2)

    children = client.get('/api/planning/items/tree/').data[0]['children']
    assert [child['title'] for child in children] == ['first', 'second', 'third']


def test_the_tree_is_empty_for_a_new_account(client):
    response = client.get('/api/planning/items/tree/')
    assert response.status_code == 200
    assert response.data == []


def test_the_tree_never_includes_another_users_items(client, other_user, make_item):
    make_item(other_user, 'Their course', ItemType.GOAL)
    assert client.get('/api/planning/items/tree/').data == []


# --- Items: move ------------------------------------------------------------

def test_move_reparents_an_item(client, user, make_item):
    root = make_item(user, 'root', ItemType.GOAL)
    item = make_item(user, 'floating')

    response = client.post(
        f'/api/planning/items/{item.pk}/move/', {'parent_id': root.pk}, format='json'
    )
    assert response.status_code == 200, response.data
    assert response.data['parent'] == root.pk


def test_move_to_the_top_level_is_allowed(client, chain):
    _, _, c = chain
    response = client.post(
        f'/api/planning/items/{c.pk}/move/', {'parent_id': None}, format='json'
    )
    assert response.status_code == 200
    assert response.data['parent'] is None


def test_move_refuses_a_cycle(client, chain):
    """FR-06: a -> b -> c, so moving a under c would close the loop."""
    a, _, c = chain
    response = client.post(
        f'/api/planning/items/{a.pk}/move/', {'parent_id': c.pk}, format='json'
    )
    assert response.status_code == 400, response.data
    a.refresh_from_db()
    assert a.parent_id is None


def test_move_refuses_an_item_under_itself(client, user, make_item):
    item = make_item(user, 'lonely', ItemType.GOAL)
    response = client.post(
        f'/api/planning/items/{item.pk}/move/', {'parent_id': item.pk}, format='json'
    )
    assert response.status_code == 400


def test_move_refuses_another_users_parent(client, user, other_user, make_item):
    """FR-03: theirs is invisible, so naming it reads as a bad id, not as
    confirmation that it exists."""
    mine = make_item(user, 'mine')
    theirs = make_item(other_user, 'theirs', ItemType.GOAL)

    response = client.post(
        f'/api/planning/items/{mine.pk}/move/', {'parent_id': theirs.pk}, format='json'
    )
    assert response.status_code == 400
    mine.refresh_from_db()
    assert mine.parent_id is None


# --- Items: complete --------------------------------------------------------

def test_complete_cascades_to_the_whole_subtree(client, user, make_item):
    """FR-08."""
    root = make_item(user, 'root', ItemType.GOAL)
    child = make_item(user, 'child', parent=root)
    grandchild = make_item(user, 'grandchild', parent=child)

    response = client.post(f'/api/planning/items/{root.pk}/complete/', {}, format='json')
    assert response.status_code == 200, response.data
    assert set(response.data['affected_ids']) == {root.pk, child.pk, grandchild.pk}
    assert all(
        item.is_completed
        for item in PlanningItem.objects.filter(pk__in=[root.pk, child.pk, grandchild.pk])
    )


def test_completing_a_task_gives_up_its_priority_position(client, user, make_item):
    first = make_item(user, 'first', priority_position=1)
    make_item(user, 'second', priority_position=2)

    client.post(f'/api/planning/items/{first.pk}/complete/', {}, format='json')

    first.refresh_from_db()
    assert first.priority_position is None
    assert PlanningItem.objects.get(title='second').priority_position == 1


def test_reopening_does_not_cascade(client, user, make_item):
    root = make_item(user, 'root', ItemType.GOAL, is_completed=True)
    child = make_item(user, 'child', parent=root, is_completed=True)

    response = client.post(
        f'/api/planning/items/{root.pk}/complete/', {'completed': False}, format='json'
    )
    assert response.data['affected_ids'] == [root.pk]
    child.refresh_from_db()
    assert child.is_completed is True


def test_reopening_a_task_returns_it_to_the_priority_order(client, user, make_item):
    make_item(user, 'active', priority_position=1)
    done = make_item(user, 'done', is_completed=True)

    client.post(f'/api/planning/items/{done.pk}/complete/', {'completed': False},
                format='json')
    done.refresh_from_db()
    assert done.priority_position == 2


# --- Priority ---------------------------------------------------------------

def test_priority_lists_active_tasks_in_order_with_their_root(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    make_item(user, 'second', parent=root, priority_position=2,
              duration_category=DurationCategory.UNDER_4_HOURS)
    make_item(user, 'first', parent=root, priority_position=1)

    response = client.get('/api/planning/priority/')
    assert response.status_code == 200
    assert [(row['position'], row['title']) for row in response.data] == [
        (1, 'first'), (2, 'second')
    ]
    assert response.data[0]['root']['title'] == 'ELEC3609'


def test_priority_excludes_goals_and_completed_tasks(client, user, make_item):
    make_item(user, 'goal', ItemType.GOAL)
    make_item(user, 'done', is_completed=True)
    make_item(user, 'active', priority_position=1)

    response = client.get('/api/planning/priority/')
    assert [row['title'] for row in response.data] == ['active']


def test_reorder_moves_a_task_and_returns_the_whole_order(client, user, make_item):
    """FR-09."""
    for position, title in enumerate(['a', 'b', 'c', 'd'], start=1):
        make_item(user, title, priority_position=position)

    target = PlanningItem.objects.get(title='d')
    response = client.post(
        '/api/planning/priority/reorder/',
        {'item_id': target.pk, 'new_position': 1},
        format='json',
    )
    assert response.status_code == 200, response.data
    assert [row['title'] for row in response.data] == ['d', 'a', 'b', 'c']
    assert [row['position'] for row in response.data] == [1, 2, 3, 4]


def test_reorder_clamps_a_position_past_the_end(client, user, make_item):
    for position, title in enumerate(['a', 'b'], start=1):
        make_item(user, title, priority_position=position)

    target = PlanningItem.objects.get(title='a')
    response = client.post(
        '/api/planning/priority/reorder/',
        {'item_id': target.pk, 'new_position': 999},
        format='json',
    )
    assert [row['title'] for row in response.data] == ['b', 'a']


def test_reorder_refuses_an_unpositioned_item(client, user, make_item):
    goal = make_item(user, 'goal', ItemType.GOAL)
    response = client.post(
        '/api/planning/priority/reorder/',
        {'item_id': goal.pk, 'new_position': 1},
        format='json',
    )
    assert response.status_code == 400


def test_reorder_refuses_another_users_task(client, other_user, make_item):
    """FR-03: their order must be untouchable even by id."""
    theirs = make_item(other_user, 'theirs', priority_position=1)
    response = client.post(
        '/api/planning/priority/reorder/',
        {'item_id': theirs.pk, 'new_position': 1},
        format='json',
    )
    assert response.status_code == 400
    theirs.refresh_from_db()
    assert theirs.priority_position == 1


# --- Timeline ---------------------------------------------------------------

@freeze_time('2026-09-14')
def test_the_timeline_groups_dated_items_under_their_root(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    make_item(user, 'Quiz', parent=root, due_date='2026-09-16')
    make_item(user, 'Lab', parent=root, due_date='2026-09-15')

    response = client.get('/api/planning/timeline/')
    assert response.status_code == 200
    assert response.data['range']['from'] == '2026-09-07'
    assert response.data['range']['to'] == '2026-10-12'

    assert len(response.data['groups']) == 1
    group = response.data['groups'][0]
    assert group['root']['title'] == 'ELEC3609'
    assert [item['title'] for item in group['items']] == ['Quiz', 'Lab']


@freeze_time('2026-09-14')
def test_the_timeline_separates_execution_dates_and_deadlines(client, user, make_item):
    """FR-11: the client has to be able to tell a real deadline from an ARC
    suggestion."""
    make_item(user, 'Fixed', ItemType.GOAL)  # a root to group under
    make_item(user, 'Deadline', due_date='2026-09-20')
    make_item(user, 'Whenever', scheduled_date='2026-09-20')

    items = {
        item['title']: item
        for group in client.get('/api/planning/timeline/').data['groups']
        for item in group['items']
    }
    assert items['Deadline']['due_date'] == '2026-09-20'
    assert items['Deadline']['scheduled_date'] == '2026-09-14'
    assert items['Whenever']['due_date'] is None
    assert items['Whenever']['scheduled_date'] == '2026-09-14'  # daily global optimisation


@freeze_time('2026-09-14')
def test_the_timeline_honours_an_explicit_range(client, user, make_item):
    make_item(user, 'Inside', due_date='2026-09-20')
    make_item(user, 'Outside', due_date='2026-11-01')

    response = client.get('/api/planning/timeline/?from=2026-09-15&to=2026-09-30')
    titles = [item['title'] for group in response.data['groups'] for item in group['items']]
    assert titles == ['Inside']


def test_the_timeline_refuses_a_backwards_range(client):
    response = client.get('/api/planning/timeline/?from=2026-09-30&to=2026-09-01')
    assert response.status_code == 400


def test_the_timeline_refuses_an_unparseable_date(client):
    assert client.get('/api/planning/timeline/?from=soon&to=2026-09-30').status_code == 400


@freeze_time('2026-09-14')
def test_the_timeline_includes_overlapping_timezones(client, user):
    """FR-13."""
    Timezone.objects.create(
        user=user, title='Semester 2', start_date='2026-07-27', end_date='2026-11-01'
    )
    Timezone.objects.create(
        user=user, title='Summer break', start_date='2026-12-01', end_date='2027-02-01'
    )

    response = client.get('/api/planning/timeline/')
    assert [zone['title'] for zone in response.data['timezones']] == ['Semester 2']


@freeze_time('2026-09-14')
def test_reading_the_timeline_rolls_neglected_adaptive_tasks_forward(client, user, make_item):
    """FR-11: a task ARC scheduled for last week should not still sit in the
    past the next time the user looks."""
    stale = make_item(user, 'Neglected', scheduled_date='2026-09-01', priority_position=1)

    client.get('/api/planning/timeline/')

    stale.refresh_from_db()
    assert stale.scheduled_date.isoformat() == '2026-09-14'
    assert stale.due_date is None


@freeze_time('2026-09-14')
def test_the_timeline_never_includes_another_users_items(client, other_user, make_item):
    make_item(other_user, 'Their quiz', due_date='2026-09-15')
    assert client.get('/api/planning/timeline/').data['groups'] == []


# --- Overdue ----------------------------------------------------------------

@freeze_time('2026-09-14')
def test_overdue_splits_recent_from_backlog(client, user, make_item):
    """FR-12: the boundary is seven days."""
    make_item(user, 'Yesterday', due_date='2026-09-13')
    make_item(user, 'A week ago', due_date='2026-09-07')
    make_item(user, 'Ancient', due_date='2026-08-01')

    response = client.get('/api/planning/overdue/')
    assert response.status_code == 200
    assert [row['item']['title'] for row in response.data['recent']] == [
        'A week ago', 'Yesterday'
    ]
    assert [row['item']['title'] for row in response.data['backlog']] == ['Ancient']
    assert response.data['recent'][1]['days_overdue'] == 1


@freeze_time('2026-09-14')
def test_overdue_reports_the_hierarchy_path(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    week = make_item(user, 'Week 5', ItemType.GOAL, parent=root)
    make_item(user, 'Quiz', parent=week, due_date='2026-09-13')

    row = client.get('/api/planning/overdue/').data['recent'][0]
    assert row['hierarchy_path'] == ['ELEC3609', 'Week 5', 'Quiz']


@freeze_time('2026-09-14')
def test_adaptive_and_completed_items_are_never_overdue(client, user, make_item):
    """FR-11 and FR-12: an adaptive task has no deadline to miss."""
    make_item(user, 'Adaptive', scheduled_date='2026-09-01')
    make_item(user, 'Done', due_date='2026-09-01', is_completed=True)
    make_item(user, 'Goal', ItemType.GOAL, due_date='2026-09-01')

    response = client.get('/api/planning/overdue/')
    assert response.data == {'recent': [], 'backlog': []}


@freeze_time('2026-09-14')
def test_overdue_never_includes_another_users_items(client, other_user, make_item):
    make_item(other_user, 'Their missed quiz', due_date='2026-09-01')
    assert client.get('/api/planning/overdue/').data == {'recent': [], 'backlog': []}


# --- Marks ------------------------------------------------------------------

def test_marks_group_by_subject_and_total_only_what_is_marked(client, user, make_item):
    """FR-14: an unmarked assessment is unmarked, not zero."""
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    marked = make_item(user, 'Assignment 1', ItemType.ASSIGNMENT, parent=root)
    unmarked = make_item(user, 'Assignment 2', ItemType.ASSIGNMENT, parent=root)
    AssignmentDetail.objects.create(
        planning_item=marked, weight_percent='25.00', mark_achieved='18.50'
    )
    AssignmentDetail.objects.create(planning_item=unmarked, weight_percent='30.00')

    response = client.get('/api/planning/marks/')
    assert response.status_code == 200

    group = response.data[0]
    assert group['root']['title'] == 'ELEC3609'
    assert group['total_weight'] == '55.00'
    assert group['total_marks'] == '18.50'
    assert group['unmarked_count'] == 1
    assert group['assessments'][1]['mark_achieved'] is None


def test_marks_separate_one_subject_from_another(client, user, make_item):
    for title in ('ELEC3609', 'COMP2123'):
        root = make_item(user, title, ItemType.GOAL)
        make_item(user, f'{title} quiz', ItemType.ASSIGNMENT, parent=root)

    response = client.get('/api/planning/marks/')
    assert [group['root']['title'] for group in response.data] == ['COMP2123', 'ELEC3609']


def test_an_assignment_without_detail_still_appears(client, user, make_item):
    """Canvas gives ARC assignments with no weighting, and those must not
    vanish from the Marks View."""
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    make_item(user, 'Imported quiz', ItemType.ASSIGNMENT, parent=root)

    group = client.get('/api/planning/marks/').data[0]
    assert group['assessments'][0]['title'] == 'Imported quiz'
    assert group['assessments'][0]['weight_percent'] is None
    assert group['unmarked_count'] == 1


def test_marks_are_empty_without_assignments(client, user, make_item):
    make_item(user, 'Just a task')
    assert client.get('/api/planning/marks/').data == []


def test_marks_reorder_renumbers_the_group(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    details = []
    for title in ('a', 'b', 'c'):
        item = make_item(user, title, ItemType.ASSIGNMENT, parent=root)
        details.append(AssignmentDetail.objects.create(planning_item=item))

    ordered_ids = [details[2].pk, details[0].pk, details[1].pk]
    response = client.post(
        '/api/planning/marks/reorder/', {'ordered_ids': ordered_ids}, format='json'
    )
    assert response.status_code == 200, response.data
    assert response.data == {'reordered': 3}

    group = client.get('/api/planning/marks/').data[0]
    assert [row['title'] for row in group['assessments']] == ['c', 'a', 'b']


def test_marks_reorder_refuses_another_users_assessment(client, other_user, make_item):
    """FR-03."""
    theirs = make_item(other_user, 'theirs', ItemType.ASSIGNMENT)
    detail = AssignmentDetail.objects.create(planning_item=theirs, marks_position=1)

    response = client.post(
        '/api/planning/marks/reorder/', {'ordered_ids': [detail.pk]}, format='json'
    )
    assert response.status_code == 400
    detail.refresh_from_db()
    assert detail.marks_position == 1


def test_a_mark_can_be_recorded_through_the_detail_endpoint(client, user, make_item):
    item = make_item(user, 'Assignment 1', ItemType.ASSIGNMENT)
    AssignmentDetail.objects.create(planning_item=item, weight_percent='25.00')

    response = client.patch(
        f'/api/planning/assignment-details/{item.pk}/',
        {'mark_achieved': '21.00'},
        format='json',
    )
    assert response.status_code == 200, response.data
    assert response.data['mark_achieved'] == '21.00'


def test_another_users_assignment_detail_is_a_404(other_client, user, make_item):
    """FR-03: 404 rather than 403, so the API does not confirm it exists."""
    item = make_item(user, 'Assignment 1', ItemType.ASSIGNMENT)
    AssignmentDetail.objects.create(planning_item=item)

    response = other_client.patch(
        f'/api/planning/assignment-details/{item.pk}/',
        {'mark_achieved': '100.00'},
        format='json',
    )
    assert response.status_code == 404


# --- Tags and timezones -----------------------------------------------------

def test_a_duplicate_tag_name_is_a_400_not_a_500(client, user):
    Tag.objects.create(user=user, name='reading')
    response = client.post('/api/planning/tags/', {'name': 'Reading'}, format='json')
    assert response.status_code == 400


def test_two_users_may_hold_the_same_tag_name(client, other_user):
    Tag.objects.create(user=other_user, name='reading')
    response = client.post('/api/planning/tags/', {'name': 'reading'}, format='json')
    assert response.status_code == 201


def test_a_tag_id_from_another_user_is_refused(client, other_user, make_item, user):
    theirs = Tag.objects.create(user=other_user, name='theirs')
    response = client.post(
        '/api/planning/items/',
        {'item_type': ItemType.TASK, 'title': 'Mine', 'tag_ids': [theirs.pk]},
        format='json',
    )
    assert response.status_code == 400


def test_a_timezone_cannot_end_before_it_starts(client):
    response = client.post(
        '/api/planning/timezones/',
        {'title': 'Backwards', 'start_date': '2026-10-01', 'end_date': '2026-09-01'},
        format='json',
    )
    assert response.status_code == 400


def test_overlapping_timezones_are_allowed(client):
    """FR-13: a teaching week sits inside a semester, so overlap is normal."""
    payload = {'start_date': '2026-07-27', 'end_date': '2026-11-01'}
    assert client.post(
        '/api/planning/timezones/', {'title': 'Semester 2', **payload}, format='json'
    ).status_code == 201
    assert client.post(
        '/api/planning/timezones/',
        {'title': 'Week 5', 'start_date': '2026-08-24', 'end_date': '2026-08-30'},
        format='json',
    ).status_code == 201


# --- Isolation and authentication ------------------------------------------

def test_every_planning_endpoint_refuses_an_anonymous_request(db, api):
    for path in (
        '/api/planning/items/',
        '/api/planning/items/tree/',
        '/api/planning/tags/',
        '/api/planning/timezones/',
        '/api/planning/priority/',
        '/api/planning/timeline/',
        '/api/planning/overdue/',
        '/api/planning/marks/',
    ):
        assert api.get(path).status_code == 401, path


def test_the_item_list_shows_only_your_own_items(client, user, other_user, make_item):
    """FR-03: identically titled rows for two users is exactly the case a
    naive queryset would leak."""
    mine = make_item(user, 'Read chapter 4')
    make_item(other_user, 'Read chapter 4')

    response = client.get('/api/planning/items/')
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == mine.pk


def test_another_users_item_is_a_404(client, other_user, make_item):
    theirs = make_item(other_user, 'theirs')
    assert client.get(f'/api/planning/items/{theirs.pk}/').status_code == 404
    assert client.delete(f'/api/planning/items/{theirs.pk}/').status_code == 404
    assert client.patch(
        f'/api/planning/items/{theirs.pk}/', {'title': 'hijacked'}, format='json'
    ).status_code == 404
    theirs.refresh_from_db()
    assert theirs.title == 'theirs'


def test_a_real_bearer_token_reaches_the_planning_api(api, db, make_item):
    """The rest of this module force-authenticates; this one proves the
    ArcJWTAuthentication wiring works end to end."""
    secret = pyotp.random_base32()
    user = make_user('token@example.com', secret)
    make_item(user, 'Read chapter 4')

    tokens = login_through_mfa(api, user, secret)
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

    response = api.get('/api/planning/items/')
    assert response.status_code == 200
    assert response.data['results'][0]['title'] == 'Read chapter 4'
