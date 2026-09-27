from datetime import date

import pytest

from arena.generation.blueprint import build_blueprint
from arena.generation.materialize import materialize_blueprint
from arena.generation.spec import (
    DependencyLoad,
    DependencyTopology,
    GenerationSpec,
    HierarchyBranching,
    HierarchyDepth,
)
from arena.scheduling.adapter import problem_from_user
from planning.models import (
    ItemType,
    PlanningDependency,
    PlanningItem,
)


@pytest.mark.django_db
def test_adapter_preserves_explicit_dependency_edges_only():
    spec = GenerationSpec(
        seed=99001,
        size=64,
        hierarchy_depth=HierarchyDepth.MEDIUM,
        hierarchy_branching=HierarchyBranching.BALANCED,
        dependency_load=DependencyLoad.HEAVY,
        dependency_topology=DependencyTopology.CHAIN,
    )

    blueprint = build_blueprint(spec)
    materialized = materialize_blueprint(
        blueprint,
        email="arena-c0-adapter@local.test",
    )

    problem = problem_from_user(
        materialized.user,
        date(2026, 1, 15),
    )

    visible_ids = {
        item.item_id
        for item in problem.items
    }

    expected = {
        (
            materialized.by_key[edge.prerequisite_key].pk,
            materialized.by_key[edge.dependent_key].pk,
        )
        for edge in blueprint.dependencies
        if (
            materialized.by_key[edge.prerequisite_key].pk
            in visible_ids
            and
            materialized.by_key[edge.dependent_key].pk
            in visible_ids
        )
    }

    actual = {
        (
            edge.prerequisite_id,
            edge.dependent_id,
        )
        for edge in problem.dependencies
    }

    assert actual == expected


@pytest.mark.django_db
def test_future_problem_preserves_dependency_blocked_chain():
    """A -> B -> C must all be visible to a future-planning algorithm."""

    from django.contrib.auth import get_user_model
    from planning.models import (
        ItemType,
        PlanningDependency,
        PlanningItem,
    )
    from planning.services.scheduling import _scheduler_eligible

    User = get_user_model()

    user = User.objects.create_user(
        email="arena-c0-future-chain@local.test",
        password="x",
    )

    common = dict(
        user=user,
        item_type=ItemType.TASK,
        duration_category="UNDER_1_HOUR",
    )

    a = PlanningItem.objects.create(
        **common,
        title="A",
    )
    b = PlanningItem.objects.create(
        **common,
        title="B",
    )
    c = PlanningItem.objects.create(
        **common,
        title="C",
    )

    PlanningDependency.objects.create(
        prerequisite=a,
        dependent=b,
    )
    PlanningDependency.objects.create(
        prerequisite=b,
        dependent=c,
    )

    # Production correctly answers "what can execute NOW?"
    assert set(
        _scheduler_eligible(user).values_list(
            "pk",
            flat=True,
        )
    ) == {a.pk}

    # Laboratory instead answers "what can become executable over
    # the future schedule?"
    problem = problem_from_user(
        user,
        date(2026, 1, 15),
    )

    assert {
        item.item_id
        for item in problem.items
    } == {
        a.pk,
        b.pk,
        c.pk,
    }

    # Preserve ONLY explicit canonical edges.
    assert {
        (
            edge.prerequisite_id,
            edge.dependent_id,
        )
        for edge in problem.dependencies
    } == {
        (a.pk, b.pk),
        (b.pk, c.pk),
    }

    # No invented A -> C edge...
    assert (
        a.pk,
        c.pk,
    ) not in {
        (
            edge.prerequisite_id,
            edge.dependent_id,
        )
        for edge in problem.dependencies
    }

    # ...but reachability derives the transitive relationship.
    assert problem.transitive_prerequisites(
        c.pk
    ) == frozenset({
        a.pk,
        b.pk,
    })


@pytest.mark.django_db
def test_future_problem_still_excludes_structural_parent():
    """Dependency expansion must not weaken ARC hierarchy semantics."""

    from django.contrib.auth import get_user_model
    from planning.models import (
        ItemType,
        PlanningItem,
    )

    User = get_user_model()

    user = User.objects.create_user(
        email="arena-c0-structural-parent@local.test",
        password="x",
    )

    parent = PlanningItem.objects.create(
        user=user,
        item_type=ItemType.TASK,
        title="Parent",
        duration_category="UNDER_1_HOUR",
    )

    child = PlanningItem.objects.create(
        user=user,
        parent=parent,
        item_type=ItemType.TASK,
        title="Child",
        duration_category="UNDER_1_HOUR",
    )

    problem = problem_from_user(
        user,
        date(2026, 1, 15),
    )

    ids = {
        item.item_id
        for item in problem.items
    }

    assert child.pk in ids
    assert parent.pk not in ids


@pytest.mark.django_db
def test_existing_schedule_snapshot_is_exact_independent_and_read_only():
    from django.contrib.auth import get_user_model
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    user = get_user_model().objects.create_user(
        email='arena-c13-snapshot@local.test', password='x')
    common = dict(user=user, item_type=ItemType.TASK,
                  duration_category='UNDER_1_HOUR')
    scheduled = PlanningItem.objects.create(**common, title='Scheduled')
    unscheduled = PlanningItem.objects.create(**common, title='Unscheduled')
    old_date = date(2026, 1, 10)  # Preserve even past proposal dates exactly.
    anchor = date(2026, 1, 20)
    PlanningItem.objects.filter(pk=scheduled.pk).update(
        scheduled_date=old_date, manual_requested_date=anchor)
    PlanningItem.objects.filter(pk=unscheduled.pk).update(scheduled_date=None)
    before = list(PlanningItem.objects.filter(user=user).order_by('pk').values())
    with CaptureQueriesContext(connection) as queries:
        first = problem_from_user(user, date(2026, 1, 15))
    assert all(q['sql'].lstrip().upper().startswith('SELECT') for q in queries)
    assert list(PlanningItem.objects.filter(user=user).order_by('pk').values()) == before
    assert first.item_by_id[scheduled.pk].existing_scheduled_date == old_date
    assert first.item_by_id[scheduled.pk].anchor_date == anchor
    assert first.item_by_id[unscheduled.pk].existing_scheduled_date is None
    new_date = date(2026, 1, 22)
    PlanningItem.objects.filter(pk=scheduled.pk).update(scheduled_date=new_date)
    second = problem_from_user(user, date(2026, 1, 15))
    assert second.item_by_id[scheduled.pk].existing_scheduled_date == new_date
    assert first.item_by_id[scheduled.pk].existing_scheduled_date == old_date
    assert second.item_by_id[scheduled.pk].anchor_date == anchor
