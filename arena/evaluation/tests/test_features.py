import csv
from dataclasses import FrozenInstanceError
from datetime import date
import json
import math
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from accounts.models import User
from planning.models import DurationCategory as D, ItemType, PlanningDependency, PlanningItem
from arena.datasets.importer import RAW_DIR, load_scenario, map_legacy_duration
from arena.evaluation.features import characterize_workload

pytestmark = pytest.mark.django_db
TODAY = date(2026, 9, 20)


@pytest.fixture
def user():
    return User.objects.create_user(email="features@test.local", password="test")


@pytest.fixture
def item(user):
    def create(**kwargs):
        return PlanningItem.objects.create(user=user, title="Example", item_type=kwargs.pop("item_type", ItemType.TASK), **kwargs)
    return create


def features(user):
    return characterize_workload(user, TODAY).to_mapping()


def test_empty(user):
    f = features(user)
    assert len(f) == 89
    assert all(value == 0 for name, value in f.items() if name.startswith("item_count"))
    assert f["temporal_span_days"] is None
    for name in ("hierarchy_mean_depth", "hierarchy_depth_std", "hierarchy_mean_branching", "duration_entropy"):
        assert f[name] is None
    for name, value in f.items():
        if (name.startswith(("hierarchy_", "duration_")) and name.endswith("fraction")) or name in ("hierarchy_max_depth", "hierarchy_max_branching"):
            assert value == 0


def test_minimal_and_serialization(user, item):
    item(start_date=TODAY)
    result = characterize_workload(user, TODAY)
    f = result.to_mapping()
    assert f["item_count_executable"] == 1
    assert f["hierarchy_root_fraction"] == f["hierarchy_frontier_fraction"] == 1
    assert f["hierarchy_mean_depth"] == f["hierarchy_depth_std"] == 0
    assert f["temporal_span_days"] == 0
    assert f["duration_under_1h_fraction"] == 1
    assert f["duration_entropy"] == 0
    assert result.to_json() == characterize_workload(user, TODAY).to_json()
    assert json.loads(result.to_json())["features"] == f
    f.clear()
    assert result.to_mapping()
    with pytest.raises(FrozenInstanceError):
        result.raw = ()


def test_populations_and_dependencies(user, item):
    goal = item(item_type=ItemType.GOAL)
    parent = item(parent=goal)
    prerequisite = item(parent=parent, item_type=ItemType.ASSIGNMENT)
    dependent = item()
    completed = item(is_completed=True)
    deleted = item(is_deleted=True)
    PlanningDependency.objects.create(prerequisite=prerequisite, dependent=dependent)
    PlanningDependency.objects.create(prerequisite=completed, dependent=prerequisite)
    PlanningDependency.objects.create(prerequisite=deleted, dependent=prerequisite)
    other = User.objects.create_user(email="other@test.local", password="test")
    PlanningItem.objects.create(user=other, title="Other", item_type=ItemType.TASK)
    f = features(user)
    assert [f[f"item_count_{n}"] for n in ("total", "visible", "active", "actionable", "frontier", "executable", "blocked")] == [6, 5, 4, 3, 2, 1, 1]
    assert f["hierarchy_frontier_fraction"] == pytest.approx(2 / 3)
    assert f["duration_under_1h_fraction"] == 1


def test_dates_canonical_actionable_only(user, item):
    task = item(start_date=date(2026, 9, 1), due_date=date(2026, 9, 5), manual_requested_date=date(2026, 9, 9), scheduled_date=date(2040, 1, 1))
    item(item_type=ItemType.GOAL, start_date=date(2000, 1, 1))
    item(is_deleted=True, due_date=date(2050, 1, 1))
    item(is_completed=True, due_date=date(2060, 1, 1))
    assert features(user)["temporal_span_days"] == 8
    before = features(user)
    PlanningItem.objects.filter(pk=task.pk).update(scheduled_date=date(2080, 1, 1), execution_rank=42)
    assert features(user) == before


@pytest.mark.parametrize("shape,depth,branching,root_fraction,parent_fraction,mean_depth,std", [
    ("flat", 0, 0, 1, 0, 0, 0),
    ("deep", 3, 1, .25, .75, 1.5, math.sqrt(1.25)),
    ("wide", 1, 3, .25, .25, .75, math.sqrt(.1875)),
])
def test_hierarchy(user, item, shape, depth, branching, root_fraction, parent_fraction, mean_depth, std):
    root = previous = item()
    for _ in range(3):
        previous = item(parent=previous if shape == "deep" else root if shape == "wide" else None)
    f = features(user)
    assert f["hierarchy_max_depth"] == depth
    assert f["hierarchy_max_branching"] == branching
    assert f["hierarchy_mean_branching"] == (branching or None)
    assert f["hierarchy_root_fraction"] == root_fraction
    assert f["hierarchy_parent_fraction"] == parent_fraction
    assert f["hierarchy_mean_depth"] == mean_depth
    assert f["hierarchy_depth_std"] == pytest.approx(std)


def test_visible_parent_deleted_and_completed_children(user, item):
    parent = item()
    item(parent=parent, is_deleted=True)
    item(parent=parent, is_completed=True)
    deleted_parent = item(is_deleted=True)
    item(parent=deleted_parent)
    f = features(user)
    assert f["item_count_frontier"] == 2
    assert f["hierarchy_root_fraction"] == pytest.approx(2 / 3)
    assert f["hierarchy_max_branching"] == 1
    assert f["hierarchy_max_depth"] == 1


def test_active_goal_child_prevents_frontier(user, item):
    parent = item()
    item(parent=parent, item_type=ItemType.GOAL)
    assert features(user)["item_count_frontier"] == 0


def test_six_categories_and_structural_parent(user, item):
    parent = item(duration_category=D.OVER_16_HOURS)
    for category in D:
        item(parent=parent, duration_category=category)
    f = features(user)
    fractions = [value for name, value in f.items() if name.startswith("duration_under_") or name == "duration_over_16h_fraction"]
    assert fractions == pytest.approx([1 / 6] * 6)
    assert sum(fractions) == pytest.approx(1)
    assert f["duration_entropy"] == pytest.approx(1)
    assert f["duration_long_fraction"] == .5
    assert f["item_count_frontier"] == 6


def test_mixed_and_homogeneous_entropy(user, item):
    item(duration_category=D.UNDER_8_HOURS)
    item(duration_category=D.UNDER_8_HOURS)
    assert features(user)["duration_entropy"] == 0
    assert features(user)["duration_long_fraction"] == 1
    item(duration_category=D.UNDER_20_MINUTES)
    assert features(user)["duration_entropy"] == pytest.approx(-(2 / 3 * math.log(2 / 3) + 1 / 3 * math.log(1 / 3)) / math.log(6))


def test_read_only_and_no_projection_reads(user, item):
    item()
    before = list(PlanningItem.objects.values())
    with patch("planning.services.scheduling.schedule", side_effect=AssertionError("scheduling forbidden")), CaptureQueriesContext(connection) as queries:
        characterize_workload(user, TODAY)
    assert list(PlanningItem.objects.values()) == before
    for query in queries:
        sql = query["sql"].lower()
        assert sql.startswith("select")
        assert not any(name in sql for name in ("scheduled_date", "execution_rank", "scheduler_allocation", "conflict"))


@pytest.mark.parametrize("raw,expected", [
    ("UNDER_20_MIN", D.UNDER_20_MINUTES), ("MIN_20_TO_60", D.UNDER_1_HOUR),
    ("OVER_60_MIN", D.UNDER_4_HOURS), ("HOURS_1_TO_4", D.UNDER_4_HOURS),
    ("HOURS_4_TO_12", D.UNDER_16_HOURS), ("OVER_12_HOURS", D.OVER_16_HOURS),
])
def test_legacy_mapping(raw, expected):
    assert map_legacy_duration(raw) == expected


def test_unknown_legacy_and_corpus():
    with pytest.raises(ValueError, match="Unknown legacy raw duration class: 'UNKNOWN'"):
        map_legacy_duration("UNKNOWN")
    with (RAW_DIR / "items.csv").open() as source:
        for row in csv.DictReader(source):
            assert map_legacy_duration(row["duration_class"]) in D.values


def test_fixture_import():
    load_scenario("micro_release_only")
    assert set(PlanningItem.objects.values_list("duration_category", flat=True)) <= set(D.values)
