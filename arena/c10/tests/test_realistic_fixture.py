from __future__ import annotations

import pytest

from arena.c10.realistic_fixture import (
    C10_TODAY,
    build_realistic_semester_fixture,
    fixture_manifest,
)
from arena.generation.materialize import (
    materialize_blueprint,
)
from arena.scheduling.adapter import (
    problem_from_user,
)


def test_fixture_is_deterministic():
    left = build_realistic_semester_fixture()
    right = build_realistic_semester_fixture()

    assert left == right
    assert fixture_manifest(left) == fixture_manifest(right)


def test_fixture_cardinality_and_semantics():
    fixture = build_realistic_semester_fixture()
    manifest = fixture_manifest(fixture)

    assert manifest["synthetic"] is True
    assert manifest["contains_personal_user_data"] is False

    assert manifest["item_count_total"] == 24
    assert manifest["frontier_item_count"] == 20
    assert manifest["dependency_count"] == 8

    assert manifest["anchored_frontier_count"] == 5
    assert manifest["priority_frontier_count"] == 8
    assert manifest["partially_completed_frontier_count"] == 1

    assert manifest["deadline_frontier_count"] >= 12
    assert manifest["release_frontier_count"] >= 8


@pytest.mark.django_db
def test_fixture_round_trips_through_canonical_arc_adapter():
    fixture = build_realistic_semester_fixture()

    materialized = materialize_blueprint(
        fixture.blueprint,
        email="arena-c10-realistic@local.test",
    )

    problem = problem_from_user(
        materialized.user,
        C10_TODAY,
    )

    visible_keys = {
        key
        for key, row in materialized.by_key.items()
        if row.pk in {
            item.item_id
            for item in problem.items
        }
    }

    expected_frontier = {
        item.key
        for item in fixture.blueprint.frontier
    }

    assert visible_keys == expected_frontier

    assert len(problem.items) == 20
    assert len(problem.dependencies) == 8

    assert all(
        item.item_id in problem.item_by_id
        for item in problem.items
    )

    # Explicit dependencies survive the canonical adapter.
    key_by_pk = {
        row.pk: key
        for key, row
        in materialized.by_key.items()
    }

    actual_edges = {
        (
            key_by_pk[edge.prerequisite_id],
            key_by_pk[edge.dependent_id],
        )
        for edge in problem.dependencies
    }

    expected_edges = {
        (
            edge.prerequisite_key,
            edge.dependent_key,
        )
        for edge
        in fixture.blueprint.dependencies
    }

    assert actual_edges == expected_edges
