from __future__ import annotations

from decimal import Decimal

import pytest

from arena.evaluation.features import characterize_workload
from arena.generation.blueprint import GENERATOR_TODAY, build_blueprint
from arena.generation.materialize import materialize_blueprint
from arena.generation.spec import (
    ActionableParentCoverage,
    AnchorRelation,
    DependencyLoad,
    DependencyTopology,
    GenerationSpec,
    ExpiredAnchorHistory,
    Heterogeneity,
    HierarchyBranching,
    HierarchyDepth,
    LifecycleProfile,
    PriorityAlignment,
    TemporalPressure,
    TemporalShape,
)
from planning.models import (
    ItemType,
    PlanningDependency,
    PlanningItem,
    ProgressSegment,
    SchedulerAllocation,
)


def rich_spec(seed=3609):
    return GenerationSpec(
        seed=seed,
        size=128,
        dependency_load=DependencyLoad.HEAVY,
        dependency_topology=DependencyTopology.LAYERED,
        priority_coverage=1.0,
        priority_alignment=PriorityAlignment.URGENCY_ALIGNED,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.OVERDUE_MIXED,
        anchor_coverage=1.0,
        anchor_relation=AnchorRelation.MIXED,
        lifecycle=LifecycleProfile.MIXED,
        heterogeneity=Heterogeneity.MIXED,
    )


@pytest.mark.django_db
def test_materialization_round_trips_blueprint_state():
    blueprint = build_blueprint(rich_spec())
    result = materialize_blueprint(blueprint)

    rows = {
        row.title: row
        for row in PlanningItem.objects.filter(user=result.user)
    }

    assert set(rows) == {item.key for item in blueprint.items}

    parent_keys = {
        item.parent_key
        for item in blueprint.items
        if item.parent_key is not None
    }

    for item in blueprint.items:
        row = rows[item.key]

        assert (
            row.parent.title if row.parent_id is not None else None
        ) == item.parent_key

        assert row.item_type == (
            ItemType.GOAL
            if item.key in parent_keys
            else ItemType.TASK
        )

        assert row.duration_category == item.duration_category
        assert row.start_date == item.start_date
        assert row.due_date == item.due_date
        assert row.manual_requested_date == item.manual_requested_date
        assert (
            row.expired_manual_requested_date
            == item.expired_manual_requested_date
        )
        assert row.priority_position == item.priority_position
        assert Decimal(row.percent_completed) == Decimal(
            str(item.percent_completed)
        )
        assert row.is_completed == item.is_completed

        assert row.scheduled_date is None
        assert row.execution_rank is None


@pytest.mark.django_db
def test_materialization_round_trips_dependencies():
    blueprint = build_blueprint(rich_spec())
    result = materialize_blueprint(blueprint)

    db_edges = {
        (
            edge.prerequisite.title,
            edge.dependent.title,
        )
        for edge in PlanningDependency.objects.filter(
            prerequisite__user=result.user
        ).select_related("prerequisite", "dependent")
    }

    blueprint_edges = {
        (edge.prerequisite_key, edge.dependent_key)
        for edge in blueprint.dependencies
    }

    assert db_edges == blueprint_edges


@pytest.mark.django_db
def test_materialization_creates_no_scheduler_state():
    blueprint = build_blueprint(rich_spec())
    result = materialize_blueprint(blueprint)

    assert not SchedulerAllocation.objects.filter(
        item__user=result.user
    ).exists()

    assert not PlanningItem.objects.filter(
        user=result.user,
        scheduled_date__isnull=False,
    ).exists()

    assert not PlanningItem.objects.filter(
        user=result.user,
        execution_rank__isnull=False,
    ).exists()


@pytest.mark.django_db
def test_materialized_priorities_match_canonical_queryset():
    blueprint = build_blueprint(rich_spec())
    result = materialize_blueprint(blueprint)

    positioned = {
        row.title
        for row in PlanningItem.objects.filter(
            user=result.user,
            priority_position__isnull=False,
        )
    }

    eligible = {
        row.title
        for row in PlanningItem.objects.for_user(result.user)
        .priority_eligible()
    }

    assert positioned <= eligible

    expected = {
        item.key
        for item in blueprint.items
        if item.priority_position is not None
    }

    assert positioned == expected


@pytest.mark.django_db
def test_materialized_progress_has_canonical_history():
    blueprint = build_blueprint(rich_spec())
    result = materialize_blueprint(blueprint)

    expected = {
        item.key: Decimal(str(item.percent_completed))
        for item in blueprint.items
        if item.percent_completed > 0
        and item.duration_category
        in {
            "UNDER_8_HOURS",
            "UNDER_16_HOURS",
            "OVER_16_HOURS",
        }
    }

    actual = {}

    for segment in ProgressSegment.objects.filter(
        item__user=result.user
    ).select_related("item"):
        assert segment.is_completed is True
        actual.setdefault(segment.item.title, Decimal("0"))
        actual[segment.item.title] += segment.percentage

    assert actual == expected


@pytest.mark.django_db
def test_materialized_workload_is_characterizable_by_phi89():
    blueprint = build_blueprint(rich_spec())
    result = materialize_blueprint(blueprint)

    characterized = characterize_workload(
        result.user,
        GENERATOR_TODAY,
    )

    assert len(characterized.raw) == 89

    feature_names = {
        name
        for name, _value in characterized.raw
    }

    assert "priority_coverage_fraction" in feature_names

    assert "priority_tie_fraction" not in feature_names
    assert "priority_normalized_entropy" not in feature_names
    assert "priority_top_quartile_fraction" not in feature_names


@pytest.mark.django_db
def test_materialization_is_deterministic_at_semantic_state_level():
    blueprint = build_blueprint(rich_spec(seed=99173))

    first = materialize_blueprint(blueprint)

    def snapshot(user):
        items = tuple(
            PlanningItem.objects.filter(user=user)
            .order_by("title")
            .values_list(
                "title",
                "parent__title",
                "item_type",
                "duration_category",
                "start_date",
                "due_date",
                "manual_requested_date",
                "expired_manual_requested_date",
                "priority_position",
                "percent_completed",
                "is_completed",
                "scheduled_date",
                "execution_rank",
            )
        )

        edges = tuple(
            PlanningDependency.objects.filter(
                prerequisite__user=user
            )
            .order_by(
                "prerequisite__title",
                "dependent__title",
            )
            .values_list(
                "prerequisite__title",
                "dependent__title",
            )
        )

        segments = tuple(
            ProgressSegment.objects.filter(item__user=user)
            .order_by("item__title")
            .values_list(
                "item__title",
                "percentage",
                "is_completed",
            )
        )

        return items, edges, segments

    first_state = snapshot(first.user)

    second = materialize_blueprint(blueprint)
    second_state = snapshot(second.user)

    assert first_state == second_state


@pytest.mark.django_db
def test_phase2b_hole_states_survive_materialization_and_phi89():
    spec = GenerationSpec(
        seed=85001,
        size=128,
        hierarchy_depth=HierarchyDepth.MEDIUM,
        hierarchy_branching=HierarchyBranching.BALANCED,
        dependency_load=DependencyLoad.MODERATE,
        dependency_topology=DependencyTopology.LAYERED,
        priority_coverage=0.5,
        priority_alignment=PriorityAlignment.RANDOM,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.MIXED,
        temporal_shape=TemporalShape.RELEASE_ONLY,
        anchor_coverage=0.5,
        anchor_relation=AnchorRelation.MIXED,
        expired_anchor_history=ExpiredAnchorHistory.DENSE,
        actionable_parent_coverage=ActionableParentCoverage.MANY,
        lifecycle=LifecycleProfile.MIXED,
        heterogeneity=Heterogeneity.MIXED,
    )

    blueprint = build_blueprint(spec)
    result = materialize_blueprint(blueprint)

    rows = {
        row.title: row
        for row in PlanningItem.objects.filter(user=result.user)
    }

    for item in blueprint.items:
        assert rows[item.key].item_type == item.item_type

    measured = characterize_workload(
        result.user,
        GENERATOR_TODAY,
    ).to_mapping()

    assert (
        measured["temporal_release_fraction"]
        > measured["temporal_both_fraction"]
    )
    assert measured["temporal_both_fraction"] == 0
    assert measured["expired_anchor_history_fraction"] > 0
    assert measured["lifecycle_decomposed_parent_fraction"] > 0
