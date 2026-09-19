"""Cross-tenant isolation matrix (FR-03).

The planning DefaultRouter is the source of truth: every registered viewset
that owns a detail lookup is asked, as user B, to GET, PATCH and DELETE user
A's primary keys. A new viewset cannot ship without being included in this
sweep, which is the point of iterating ``router.registry`` rather than a
hand-maintained URL list.

Write-path cases sit beside the sweep. Queryset scoping only hides rows on
read; a payload that names a foreign ``parent``, ``tag_ids`` or priority
``item_id`` has to be rejected by UserScopedPrimaryKeyRelatedField / the
priority service, or user B could still attach themselves to user A's tree.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.mixins import (
    DestroyModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)

from canvas_integration.models import SyncLog, SyncStatus
from canvas_integration.urls import router as canvas_router
from core.mixins import UserScopedMixin
from planning.models import (
    AssignmentDetail,
    ItemType,
    PlanningItem,
    PlanningItemTag,
    Tag,
    Timezone,
)
from planning.urls import router as planning_router

pytestmark = pytest.mark.django_db

User = get_user_model()

#: 404 is the intended response (the row falls out of the scoped queryset).
#: 403 is accepted if an object-level permission fires first. Either way the
#: API must not confirm that the foreign object exists by returning it.
HIDDEN = {403, 404}

OWNED_ROUTERS = (
    ('/api/planning/', planning_router),
    ('/api/canvas/', canvas_router),
)

PATCH_BODIES = {
    'planning-item': {'title': 'hijacked'},
    'tag': {'name': 'hijacked'},
    'timezone': {'title': 'hijacked'},
    'assignment-detail': {'mark_achieved': '99.00'},
    'sync-log': {'error_message': 'hijacked'},
}


def _owned_viewsets():
    """(base_url, prefix, viewset, basename) for every user-scoped registration."""
    rows = []
    for base, router in OWNED_ROUTERS:
        for prefix, viewset, basename in router.registry:
            if issubclass(viewset, UserScopedMixin):
                rows.append((base, prefix, viewset, basename))
    return rows


def _http_allowed(viewset, method):
    return method.lower() in set(viewset.http_method_names)


def _detail_attempts(base, prefix, viewset):
    """GET / PATCH / DELETE on the canonical detail URL, plus every @action
    that takes a lookup (move, complete, …)."""
    pk_url = f'{base}{prefix}/{{pk}}/'
    attempts = []

    if issubclass(viewset, RetrieveModelMixin) and _http_allowed(viewset, 'get'):
        attempts.append(('GET', pk_url, None))
    if issubclass(viewset, UpdateModelMixin) and _http_allowed(viewset, 'patch'):
        attempts.append(('PATCH', pk_url, None))
    if issubclass(viewset, UpdateModelMixin) and _http_allowed(viewset, 'put'):
        attempts.append(('PUT', pk_url, None))
    if issubclass(viewset, DestroyModelMixin) and _http_allowed(viewset, 'delete'):
        attempts.append(('DELETE', pk_url, None))

    for action in viewset.get_extra_actions():
        if not action.detail:
            continue
        action_url = f'{base}{prefix}/{{pk}}/{action.url_path}/'
        for method in action.mapping:
            if _http_allowed(viewset, method):
                attempts.append((method.upper(), action_url, action.url_path))
    return attempts


def _detail_matrix():
    cases = []
    for base, prefix, viewset, basename in _owned_viewsets():
        for method, url_template, action in _detail_attempts(base, prefix, viewset):
            label = f'{method} {prefix}' + (f'/{action}' if action else '')
            cases.append((label, basename, method, url_template))
    return cases


DETAIL_CASES = _detail_matrix()


@pytest.fixture
def user_a(db):
    return User.objects.create_user('alice@example.com', 'corr3ct-horse-battery')


@pytest.fixture
def user_b(db):
    return User.objects.create_user('bob@example.com', 'corr3ct-horse-battery')


@pytest.fixture
def client_b(api_for, user_b):
    return api_for(user_b)


@pytest.fixture
def alice_rows(user_a, make_item):
    """One row of each owned type, identical in shape to what user B will get
    so a leaked title would be distinguishable only by id (FR-03)."""
    root = make_item(user_a, 'Shared-looking course', ItemType.GOAL)
    task = make_item(
        user_a, 'Shared-looking task', parent=root, priority_position=1,
    )
    assignment = make_item(
        user_a, 'Shared-looking assignment', ItemType.ASSIGNMENT,
        parent=root, due_date='2026-10-01', priority_position=2,
    )
    detail = AssignmentDetail.objects.create(
        planning_item=assignment, weight_percent='25.00', mark_achieved='12.00',
    )
    tag = Tag.objects.create(user=user_a, name='shared-looking')
    PlanningItemTag.objects.create(planning_item=task, tag=tag)
    timezone = Timezone.objects.create(
        user=user_a, title='Semester 2',
        start_date='2026-07-27', end_date='2026-11-01',
    )
    sync_log = SyncLog.objects.create(user=user_a, status=SyncStatus.SUCCESS)

    return {
        'planning-item': task,
        'tag': tag,
        'timezone': timezone,
        'assignment-detail': detail,
        'sync-log': sync_log,
        'root': root,
        'assignment': assignment,
    }


def _pk_for(basename, rows):
    obj = rows[basename]
    return obj.pk


def _snapshot(user_a):
    """Enough of Alice's state to prove a write did not sneak through."""
    return {
        'item_titles': list(
            PlanningItem.objects.filter(user=user_a).order_by('id').values_list('title', flat=True)
        ),
        'tag_names': list(
            Tag.objects.filter(user=user_a).order_by('id').values_list('name', flat=True)
        ),
        'timezone_titles': list(
            Timezone.objects.filter(user=user_a).order_by('id').values_list('title', flat=True)
        ),
        'marks': list(
            AssignmentDetail.objects.filter(planning_item__user=user_a)
            .order_by('planning_item_id')
            .values_list('mark_achieved', flat=True)
        ),
        'positions': list(
            PlanningItem.objects.filter(user=user_a)
            .exclude(priority_position=None)
            .order_by('priority_position')
            .values_list('priority_position', 'title')
        ),
        'item_count': PlanningItem.objects.filter(user=user_a).count(),
    }


@pytest.mark.parametrize(
    'label, basename, method, url_template',
    DETAIL_CASES,
    ids=[case[0] for case in DETAIL_CASES],
)
def test_detail_route_hides_foreign_objects(
    label, basename, method, url_template, client_b, alice_rows, user_a,
):
    """FR-03: user B cannot read, mutate or delete user A's rows by id."""
    before = _snapshot(user_a)
    pk = _pk_for(basename, alice_rows)
    url = url_template.format(pk=pk)
    body = PATCH_BODIES.get(basename, {})
    response = client_b.generic(method, url, data=body, format='json')

    assert response.status_code in HIDDEN, (
        f'{label} against Alice\'s #{pk} returned {response.status_code} '
        f'({getattr(response, "data", None)!r}); expected {sorted(HIDDEN)}'
    )
    # A 200 would have leaked or mutated. A 400 that echoes the foreign title
    # would also confirm the row exists, so only 403/404 are allowed here.
    assert _snapshot(user_a) == before


def test_the_router_matrix_covers_every_owned_viewset():
    """Guard the sweep itself: if a UserScoped viewset is registered without a
    retrieve/update/destroy mixin, the parametrize list would silently skip it."""
    covered = {basename for _, basename, _, _ in DETAIL_CASES}
    registered = {basename for _, _, _, basename in _owned_viewsets()}
    assert registered <= covered, (
        f'These user-scoped viewsets have no detail attempts: {registered - covered}'
    )
    assert {'planning-item', 'tag', 'timezone', 'assignment-detail'} <= registered


def test_list_routes_never_include_foreign_ids(client_b, alice_rows, user_b, make_item):
    """User B's own rows may appear; Alice's primary keys must not."""
    make_item(user_b, 'Bob\'s own task')
    alice_ids = {
        'planning-item': {alice_rows['planning-item'].pk, alice_rows['root'].pk,
                          alice_rows['assignment'].pk},
        'tag': {alice_rows['tag'].pk},
        'timezone': {alice_rows['timezone'].pk},
        'assignment-detail': {alice_rows['assignment-detail'].pk},
        'sync-log': {alice_rows['sync-log'].pk},
    }

    for base, prefix, viewset, basename in _owned_viewsets():
        if not hasattr(viewset, 'list') or not _http_allowed(viewset, 'get'):
            continue
        response = client_b.get(f'{base}{prefix}/')
        assert response.status_code == 200, f'GET {base}{prefix}/ -> {response.status_code}'
        payload = response.data
        rows = payload.get('results', payload) if isinstance(payload, dict) else payload
        seen = {row['id'] for row in rows}
        leaked = seen & alice_ids[basename]
        assert not leaked, f'GET {base}{prefix}/ leaked Alice ids {leaked}'


# --- Write-path: naming a foreign key in a payload --------------------------

def test_create_rejects_a_foreign_parent(client_b, alice_rows, user_a, user_b):
    before = _snapshot(user_a)
    response = client_b.post(
        '/api/planning/items/',
        {
            'item_type': ItemType.TASK,
            'title': 'Bob hanging off Alice',
            'parent': alice_rows['root'].pk,
        },
        format='json',
    )
    assert response.status_code in {400, 403, 404}, response.data
    assert PlanningItem.objects.filter(user=user_b).count() == 0
    assert _snapshot(user_a) == before


def test_create_rejects_a_foreign_tag(client_b, alice_rows, user_a, user_b):
    before = _snapshot(user_a)
    response = client_b.post(
        '/api/planning/items/',
        {
            'item_type': ItemType.TASK,
            'title': 'Bob wearing Alice\'s tag',
            'tag_ids': [alice_rows['tag'].pk],
        },
        format='json',
    )
    assert response.status_code in {400, 403, 404}, response.data
    assert PlanningItem.objects.filter(user=user_b).count() == 0
    assert not PlanningItemTag.objects.filter(tag=alice_rows['tag'], planning_item__user=user_b).exists()
    assert _snapshot(user_a) == before


def test_move_rejects_a_foreign_parent(client_b, alice_rows, user_a, user_b, make_item):
    bob_item = make_item(user_b, 'Bob\'s task')
    before = _snapshot(user_a)
    response = client_b.post(
        f'/api/planning/items/{bob_item.pk}/move/',
        {'parent_id': alice_rows['root'].pk},
        format='json',
    )
    assert response.status_code in {400, 403, 404}, response.data
    bob_item.refresh_from_db()
    assert bob_item.parent_id is None
    assert _snapshot(user_a) == before


def test_reorder_rejects_a_foreign_priority_item(client_b, alice_rows, user_a, user_b, make_item):
    make_item(user_b, 'Bob\'s task', priority_position=1)
    before = _snapshot(user_a)
    response = client_b.post(
        '/api/planning/priority/reorder/',
        {'item_id': alice_rows['planning-item'].pk, 'new_position': 1},
        format='json',
    )
    assert response.status_code in {400, 403, 404}, response.data
    assert _snapshot(user_a) == before


def test_marks_reorder_rejects_a_foreign_assessment(client_b, alice_rows, user_a):
    before = _snapshot(user_a)
    response = client_b.post(
        '/api/planning/marks/reorder/',
        {'ordered_ids': [alice_rows['assignment-detail'].pk]},
        format='json',
    )
    assert response.status_code in {400, 403, 404}, response.data
    assert _snapshot(user_a) == before
