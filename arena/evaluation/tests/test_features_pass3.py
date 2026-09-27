"""Interaction semantics and full-feature isolation/regression tripwires."""
from contextlib import ExitStack
from dataclasses import FrozenInstanceError
from datetime import timedelta
import csv
import json
import math
from unittest.mock import patch

import pytest
from django.apps import apps
from django.db import connection
from django.test.utils import CaptureQueriesContext

from planning.models import (
    DurationCategory as D, ItemType, PlanningDependency, PlanningItem,
    ProgressSegment, SchedulerAllocation,
)
from arena.evaluation.features import (
    CORRELATION_NAMES, FeatureEvaluationError, _average_ranks, _dependency_depths,
    canonical_json, characterize_workload, spearman,
)
from arena.evaluation.tests.test_features import TODAY, item, user
from arena.experiments import run_feature_characterization as runner

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("pairs,expected", [
    ([(1, 2), (2, 4), (3, 9)], 1),
    ([(1, 9), (2, 4), (3, 2)], -1),
    ([(1, 1), (1, 2), (3, 3)], math.sqrt(3) / 2),
    ([], None), ([(1, 2)], None),
    ([(1, 2), (1, 3)], None), ([(1, 2), (3, 2)], None),
])
def test_spearman(pairs, expected):
    result = spearman(pairs)
    assert result is None if expected is None else result == pytest.approx(expected)
    assert spearman(pairs) == result
    assert spearman(list(reversed(pairs))) == result


def test_average_tied_ranks():
    assert _average_ranks([4, 1, 4, 2, 2]) == [4.5, 1, 4.5, 2.5, 2.5]


def test_dependency_depth_longest_path_and_cycle():
    assert _dependency_depths({1, 2, 3, 4, 5}, [(1, 2), (2, 3), (1, 3), (3, 4)]) == {1: 0, 2: 1, 3: 2, 4: 3, 5: 0}
    with pytest.raises(FeatureEvaluationError, match="cycle"):
        _dependency_depths({1, 2}, [(1, 2), (2, 1)])


def test_priority_and_urgency_orientation(user, item):
    for category, position, days in ((D.UNDER_20_MINUTES, 100, 5), (D.UNDER_1_HOUR, 10, 0), (D.UNDER_4_HOURS, 1, -5)):
        item(duration_category=category, priority_position=position, due_date=TODAY + timedelta(days=days))
    result = characterize_workload(user, TODAY)
    for name in CORRELATION_NAMES[:3]:
        assert result.to_mapping()[name] == pytest.approx(1)
    assert result.corr_support == dict.fromkeys(CORRELATION_NAMES, 3)
    assert result.to_mapping()["corr_progress_priority"] is None
    # Rank-equivalent priority gaps leave the whole interaction family unchanged.
    PlanningItem.objects.filter(priority_position=100).update(priority_position=50)
    after = characterize_workload(user, TODAY)
    assert {name: result.to_mapping()[name] for name in CORRELATION_NAMES} == {name: after.to_mapping()[name] for name in CORRELATION_NAMES}


def test_hierarchy_interactions(user, item):
    goal = item(item_type=ItemType.GOAL)
    nested = item(item_type=ItemType.GOAL, parent=goal)
    item(duration_category=D.UNDER_20_MINUTES, priority_position=30)
    item(parent=goal, duration_category=D.UNDER_1_HOUR, priority_position=20)
    item(parent=nested, duration_category=D.UNDER_4_HOURS, priority_position=10)
    result = characterize_workload(user, TODAY)
    assert result.to_mapping()["corr_hierarchy_depth_duration"] == pytest.approx(1)
    assert result.to_mapping()["corr_hierarchy_depth_priority"] == pytest.approx(1)
    assert result.corr_support["corr_hierarchy_depth_duration"] == 3


def test_visible_actionable_interactions_and_missing_pairs(user, item):
    completed = item(is_completed=True, due_date=TODAY - timedelta(days=2), priority_position=1)
    partial = item(duration_category=D.UNDER_8_HOURS, percent_completed=50, due_date=TODAY, priority_position=10)
    ProgressSegment.objects.create(item=partial, percentage=50, is_completed=True)
    unstarted = item(due_date=TODAY + timedelta(days=2), priority_position=100)
    # Non-frontier actionable parent still belongs to progress/dependency pairs.
    item(parent=unstarted)
    PlanningDependency.objects.create(prerequisite=completed, dependent=partial)
    PlanningDependency.objects.create(prerequisite=partial, dependent=unstarted)
    item(is_deleted=True, due_date=TODAY, priority_position=200)
    item(item_type=ItemType.GOAL, due_date=TODAY)
    result = characterize_workload(user, TODAY)
    f, support = result.to_mapping(), result.corr_support
    assert f["corr_progress_priority"] == pytest.approx(1)
    assert f["corr_progress_deadline_urgency"] == pytest.approx(1)
    assert f["corr_dependency_depth_deadline_urgency"] == pytest.approx(-1)
    assert support == {
        "corr_priority_deadline_urgency": 1,
        "corr_duration_priority": 1,
        "corr_duration_deadline_urgency": 1,
        "corr_hierarchy_depth_duration": 2,
        "corr_hierarchy_depth_priority": 1,
        "corr_dependency_depth_deadline_urgency": 3,
        "corr_progress_priority": 3,
        "corr_progress_deadline_urgency": 3,
    }
    assert f["corr_priority_deadline_urgency"] is None


@pytest.fixture
def rich(user, item):
    root = item(item_type=ItemType.GOAL)
    parent = item(parent=root, duration_category=D.OVER_16_HOURS)
    finished = item(parent=parent, is_completed=True, due_date=TODAY - timedelta(days=1))
    partial = item(parent=parent, duration_category=D.UNDER_16_HOURS, percent_completed=25, priority_position=2, start_date=TODAY - timedelta(days=3), due_date=TODAY + timedelta(days=4), manual_requested_date=TODAY + timedelta(days=1))
    ProgressSegment.objects.create(item=partial, percentage=25, is_completed=True)
    leaf = item(duration_category=D.UNDER_8_HOURS, priority_position=1, due_date=TODAY, expired_manual_requested_date=TODAY - timedelta(days=1))
    PlanningDependency.objects.create(prerequisite=finished, dependent=partial)
    PlanningDependency.objects.create(prerequisite=partial, dependent=leaf)
    item(is_deleted=True)
    return partial, leaf


def planning_state():
    # Every planning table: canonical facts/history AND disposable proposal state.
    return {model._meta.label: list(model.objects.order_by("pk").values())
            for model in apps.get_app_config("planning").get_models()}


def forbid_schedulers():
    stack = ExitStack()
    for path in (
        "arena.algorithms.arc_baseline.run",
        "arena.algorithms.arc_baseline.reschedule",
        "planning.services.scheduling.schedule",
        "planning.services.scheduling.daily_schedule",
        "planning.services.scheduling.reschedule",
    ):
        stack.enter_context(patch(path, side_effect=AssertionError(f"Forbidden scheduler: {path}")))
    return stack


def assert_schema(features):
    assert len(features) == 89
    forbidden_fragments = (
        "scheduled_date", "execution_rank", "scheduler_allocation", "algorithm", "runtime",
        "scheduled_count", "allocation_count", "schedule_conflict", "projection", "makespan",
    )
    assert not any(fragment in name for name in features for fragment in forbidden_fragments)
    assert "correlation_support" not in features
    assert "priority_coverage_fraction" in features
    assert "priority_tie_fraction" not in features
    assert "priority_normalized_entropy" not in features
    assert "priority_top_quartile_fraction" not in features
    assert "scenario" not in features and "family" not in features and "seed" not in features


def test_purity_determinism_and_schema(user, rich):
    before = planning_state()
    with forbid_schedulers(), CaptureQueriesContext(connection) as queries:
        results = [characterize_workload(user, TODAY) for _ in range(3)]
    assert planning_state() == before
    assert len({result.to_json().encode("utf-8") for result in results}) == 1
    result = results[0]
    assert result.to_json() == canonical_json(result.to_serializable())
    assert set(json.loads(result.to_json())) == {"features", "correlation_support"}
    assert set(result.corr_support) == set(CORRELATION_NAMES)
    assert_schema(result.to_mapping())
    for query in queries:
        sql = query["sql"].lower()
        assert sql.startswith("select")
        assert not any(token in sql for token in ("scheduled_date", "execution_rank", "scheduler_allocation"))
    detached = result.corr_support
    detached.clear()
    assert len(result.corr_support) == 8
    with pytest.raises(FrozenInstanceError):
        result.support = ()


def test_hard_scheduler_output_leakage(user, rich):
    partial, leaf = rich
    before = characterize_workload(user, TODAY).to_json()
    PlanningItem.objects.filter(pk=partial.pk).update(scheduled_date=TODAY + timedelta(days=200), execution_rank=10)
    PlanningItem.objects.filter(pk=leaf.pk).update(scheduled_date=TODAY - timedelta(days=200), execution_rank=20)
    SchedulerAllocation.objects.create(item=partial, percentage=50, scheduled_date=TODAY + timedelta(days=201), execution_rank=11)
    SchedulerAllocation.objects.create(item=leaf, percentage=100, scheduled_date=TODAY, execution_rank=21)
    assert characterize_workload(user, TODAY).to_json() == before
    SchedulerAllocation.objects.all().delete()
    assert characterize_workload(user, TODAY).to_json() == before


def test_empty_support(user):
    result = characterize_workload(user, TODAY)
    assert result.corr_support == dict.fromkeys(CORRELATION_NAMES, 0)
    assert all(result.to_mapping()[name] is None for name in CORRELATION_NAMES)


def test_corpus_no_scheduler_and_reports(tmp_path, rich):
    before = planning_state()
    with forbid_schedulers():
        records = runner.characterize_corpus()
    assert planning_state() == before
    assert len(records) == 49
    assert [r["metadata"]["scenario"] for r in records] == sorted(r["metadata"]["scenario"] for r in records)
    assert len({r["metadata"]["scenario"] for r in records}) == 49
    assert len({tuple(r["features"]) for r in records}) == 1
    assert sum(r["metadata"]["legacy_priority_linearized"] for r in records) == 30
    for record in records:
        metadata = record["metadata"]
        assert metadata["legacy_priority_linearized"] == (metadata["legacy_priority_tie_count"] > 0)
        assert not {"legacy_priority_linearized", "legacy_priority_tie_count"} & record["features"].keys()
    for record in records:
        assert_schema(record["features"])
        assert tuple(record["correlation_support"]) == CORRELATION_NAMES
    runner.write_reports(records, tmp_path)
    first = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    runner.write_reports(records, tmp_path)
    assert first == {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    assert json.loads(first["workload_features.json"]) == records
    with (tmp_path / "workload_features.csv").open(newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == [*runner.METADATA_COLUMNS, *records[0]["features"]]
        rows = list(reader)
    assert len(rows) == 49
    for row, record in zip(rows, records):
        for name, value in record["features"].items():
            assert row[name] == ("" if value is None else str(value))


def test_corpus_count_mismatch_stops(monkeypatch):
    original = runner._rows
    monkeypatch.setattr(runner, "_rows", lambda name: original(name)[:-1] if name == "scenarios.csv" else original(name))
    with pytest.raises(ValueError, match="exactly 49"):
        runner.characterize_corpus()
