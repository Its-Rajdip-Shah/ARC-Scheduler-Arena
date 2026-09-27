"""Pass-2 feature definitions, canonical boundaries and purity."""
from datetime import timedelta
import json
import math
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from accounts.models import User
from planning.models import DurationCategory as D, ItemType, PlanningDependency, PlanningItem, ProgressSegment, SchedulerAllocation
from arena.evaluation.features import (
    DURATION_WEIGHTS, FeatureEvaluationError, _dependency_features,
    _priority_features, characterize_workload,
)
from arena.evaluation.tests.test_features import TODAY, features, item, user

pytestmark = pytest.mark.django_db


def day(offset):
    return TODAY + timedelta(days=offset)


def edge(a, b):
    PlanningDependency.objects.create(prerequisite=a, dependent=b)


def test_empty_pass2(user):
    f = features(user)
    none = {
        "temporal_window_mean_days", "temporal_window_median_days",
        "temporal_window_std_days", "deadline_slack_mean_days", "deadline_slack_median_days",
        "deadline_slack_min_days", "anchor_before_deadline_fraction", "anchor_after_deadline_fraction",
        "anchor_deadline_same_day_fraction", "dependency_mean_indegree", "dependency_mean_outdegree",
        "lifecycle_mean_progress", "lifecycle_progress_std",
    }
    new = list(f)[24:81]
    assert len(new) == 57
    for name in new:
        assert f[name] is None if name in none else f[name] == 0, name


def test_priority_coverage_empty_frontier(user):
    f = features(user)
    assert f["priority_count"] == 0
    assert f["priority_coverage_fraction"] == 0.0


def test_priority_coverage_none_prioritized(user, item):
    item()
    item()
    f = features(user)
    assert f["priority_count"] == 0
    assert f["priority_coverage_fraction"] == 0.0


def test_priority_coverage_all_prioritized(user, item):
    item(priority_position=10)
    item(priority_position=20)
    f = features(user)
    assert f["priority_count"] == 2
    assert f["priority_coverage_fraction"] == 1.0


def test_priority_coverage_partial(user, item):
    item(priority_position=10)
    item()
    item(priority_position=30)
    item()
    f = features(user)
    assert f["priority_count"] == 2
    assert f["priority_coverage_fraction"] == pytest.approx(0.5)


def test_priority_coverage_excludes_structural_non_frontier(user, item):
    parent = item(priority_position=10)
    item(parent=parent, priority_position=20)
    item(priority_position=30)

    f = features(user)

    assert f["item_count_frontier"] == 2
    assert f["priority_count"] == 2
    assert f["priority_coverage_fraction"] == 1.0


def test_priority_coverage_excludes_deleted_and_completed_non_frontier(user, item):
    item(priority_position=10)
    item()
    item(is_deleted=True, priority_position=20)
    item(is_completed=True, priority_position=30)

    f = features(user)

    assert f["item_count_frontier"] == 2
    assert f["priority_count"] == 1
    assert f["priority_coverage_fraction"] == pytest.approx(0.5)


def test_priority_helper_uses_explicit_frontier_denominator():
    assert _priority_features([], frontier_count=0)["priority_coverage_fraction"] == 0.0
    assert _priority_features([], frontier_count=3)["priority_coverage_fraction"] == 0.0
    assert _priority_features([1, 9], frontier_count=4)["priority_coverage_fraction"] == pytest.approx(0.5)
    assert _priority_features([10, 20], frontier_count=2)["priority_coverage_fraction"] == 1.0

def test_temporal_windows_slack_and_collisions(user, item):
    item(start_date=day(-2), due_date=day(2))
    item(start_date=day(1), due_date=day(3))
    item(start_date=day(1))
    item(due_date=day(3))
    item()
    f = features(user)
    assert f["temporal_release_fraction"] == .6
    assert f["temporal_deadline_fraction"] == .6
    assert f["temporal_both_fraction"] == .4
    assert f["temporal_unconstrained_fraction"] == .2
    assert f["temporal_window_mean_days"] == f["temporal_window_median_days"] == 3
    assert f["temporal_window_std_days"] == 1
    assert f["deadline_slack_mean_days"] == pytest.approx(7 / 3)
    assert f["deadline_slack_median_days"] == f["deadline_slack_min_days"] == 2
    assert f["deadline_collision_index"] == pytest.approx(1 / 3)
    assert f["release_collision_index"] == pytest.approx(1 / 3)


def test_deadline_boundaries(user, item):
    for offset in (-1, 0, 1, 2, 3, 4, 7, 8):
        item(due_date=day(offset))
    item()
    f = features(user)
    assert f["deadline_within_1d_fraction"] == 2 / 8
    assert f["deadline_within_3d_fraction"] == 4 / 8
    assert f["deadline_within_7d_fraction"] == 6 / 8
    assert f["overdue_fraction"] == 1 / 8
    assert f["deadline_slack_min_days"] == -1


def test_anchor_relationships(user, item):
    item(manual_requested_date=day(0), due_date=day(1))
    item(manual_requested_date=day(0), due_date=day(-1))
    item(manual_requested_date=day(1), due_date=day(1))
    item(manual_requested_date=day(2))
    item(expired_manual_requested_date=day(-5))
    f = features(user)
    assert f["anchor_count"] == 4
    assert f["anchor_fraction"] == .8
    assert f["anchor_collision_index"] == .25
    assert f["anchor_with_deadline_fraction"] == .75
    for name in ("before_deadline", "after_deadline", "deadline_same_day"):
        assert f[f"anchor_{name}_fraction"] == pytest.approx(1 / 3)
    assert f["expired_anchor_history_fraction"] == .2


def test_anchor_without_deadline(user, item):
    item(manual_requested_date=TODAY)
    f = features(user)
    assert f["anchor_with_deadline_fraction"] == 0
    assert f["anchor_before_deadline_fraction"] is None
    assert f["anchor_collision_index"] == 0


def test_isolated_graph(user, item):
    item()
    item(is_completed=True)
    item(item_type=ItemType.GOAL)
    f = features(user)
    assert f["dependency_root_fraction"] == f["dependency_sink_fraction"] == 1
    assert f["dependency_mean_indegree"] == f["dependency_mean_outdegree"] == 0
    assert f["dependency_longest_chain"] == 0


@pytest.mark.parametrize("pairs,longest,max_in,max_out,roots,sinks", [
    ([(0, 1), (1, 2)], 2, 1, 1, 2, 2),
    ([(0, 1), (0, 2)], 1, 1, 2, 2, 3),
    ([(0, 2), (1, 2)], 1, 2, 1, 3, 2),
])
def test_graph_shapes(user, item, pairs, longest, max_in, max_out, roots, sinks):
    nodes = [item() for _ in range(4)]
    for a, b in pairs:
        edge(nodes[a], nodes[b])
    f = features(user)
    assert f["dependency_edge_count"] == 2
    assert f["dependency_density"] == pytest.approx(1 / 6)
    assert f["dependency_mean_indegree"] == f["dependency_mean_outdegree"] == .5
    assert f["dependency_max_indegree"] == max_in
    assert f["dependency_max_outdegree"] == max_out
    assert f["dependency_longest_chain"] == longest
    assert f["dependency_root_fraction"] == roots / 4
    assert f["dependency_sink_fraction"] == sinks / 4
    assert f["dependency_blocked_fraction"] == len({b for _, b in pairs}) / 4
    assert f["lifecycle_blocked_fraction"] == f["dependency_blocked_fraction"]


def test_graph_filters(user, item):
    completed = item(is_completed=True)
    current = item()
    deleted = item(is_deleted=True)
    goal = item(item_type=ItemType.GOAL)
    edge(completed, current)
    edge(deleted, current)
    edge(goal, current)
    other = User.objects.create_user(email="elsewhere@test.local", password="test")
    foreign = PlanningItem.objects.create(user=other, title="Other", item_type=ItemType.TASK)
    assert foreign.user_id != current.user_id
    f = features(user)
    assert f["dependency_edge_count"] == 1
    assert f["dependency_mean_indegree"] == .5
    assert f["dependency_density"] == .5


def test_cycle_helper():
    with pytest.raises(FeatureEvaluationError, match="Dependency graph contains a cycle"):
        _dependency_features({1, 2, 3}, [(1, 2), (2, 1)], 0, 0)


def test_lifecycle_progress_and_confirmed_segments(user, item):
    item()
    partial = item(duration_category=D.UNDER_8_HOURS, percent_completed=50)
    item(is_completed=True)  # atomic storage percentage remains zero
    ProgressSegment.objects.create(item=partial, percentage=50, is_completed=True)
    hidden = item(is_deleted=True, duration_category=D.UNDER_8_HOURS, percent_completed=20)
    ProgressSegment.objects.create(item=hidden, percentage=20, is_completed=True)
    item(item_type=ItemType.GOAL)
    f = features(user)
    for name in ("completed", "commenced", "unstarted"):
        assert f[f"lifecycle_{name}_fraction"] == pytest.approx(1 / 3)
    assert f["lifecycle_mean_progress"] == .5
    assert f["lifecycle_progress_std"] == pytest.approx(math.sqrt(1 / 6))
    assert f["confirmed_progress_segment_count"] == 1
    assert f["confirmed_progress_segment_density"] == pytest.approx(1 / 3)
    # Frozen model's DB constraint prohibits unconfirmed ProgressSegment rows.
    assert "progress_segment_must_be_confirmed" in {c.name for c in ProgressSegment._meta.constraints}


def test_residual_transitions(user, item):
    parent = item()
    child = item(parent=parent)
    assert features(user)["lifecycle_decomposed_parent_fraction"] == .5
    assert features(user)["lifecycle_residual_fraction"] == 0
    PlanningItem.objects.filter(pk=child.pk).update(is_completed=True)
    assert features(user)["lifecycle_residual_fraction"] == .5
    prerequisite = item()
    edge(prerequisite, parent)
    assert features(user)["lifecycle_residual_fraction"] == pytest.approx(1 / 3)
    PlanningItem.objects.filter(pk=parent.pk).update(is_completed=True)
    assert features(user)["lifecycle_residual_fraction"] == 0
    PlanningItem.objects.filter(pk=parent.pk).update(is_completed=False)
    PlanningItem.objects.filter(pk=child.pk).update(is_deleted=True)
    assert features(user)["lifecycle_residual_fraction"] == 0
    assert features(user)["lifecycle_decomposed_parent_fraction"] == 0


@pytest.mark.parametrize("category,weight", [(D.UNDER_20_MINUTES, 1), (D.UNDER_1_HOUR, 2), (D.UNDER_4_HOURS, 4), (D.UNDER_8_HOURS, 8), (D.UNDER_16_HOURS, 16), (D.OVER_16_HOURS, 24)])
def test_characterization_weights(user, item, category, weight):
    item(duration_category=category)
    assert DURATION_WEIGHTS[category] == weight
    assert features(user)["workload_mass_total"] == weight


def test_remaining_mass_and_structure(user, item):
    parent = item(duration_category=D.OVER_16_HOURS)
    partial = item(parent=parent, duration_category=D.UNDER_16_HOURS, percent_completed=25)
    ProgressSegment.objects.create(item=partial, percentage=25, is_completed=True)
    item(is_completed=True, duration_category=D.UNDER_8_HOURS, percent_completed=100)
    item(item_type=ItemType.GOAL)
    item(duration_category=D.UNDER_1_HOUR)
    f = features(user)
    assert f["workload_mass_total"] == 14  # 16 * .75 + 2 characterization units
    assert f["pressure_frontier_count"] == 2


def test_pressure_horizons(user, item):
    for offset in (-2, 1, 2, 3, 4, 7, 8, 14, 15):
        item(due_date=day(offset), duration_category=D.UNDER_20_MINUTES)
    item(due_date=day(7), duration_category=D.UNDER_8_HOURS)
    item(manual_requested_date=day(-2))
    item(manual_requested_date=day(7))
    item(manual_requested_date=day(8))
    item(expired_manual_requested_date=day(-1))
    f = features(user)
    assert [f[f"pressure_due_{n}d_count"] for n in (1, 3, 7, 14)] == [2, 4, 7, 9]
    assert [f[f"workload_mass_due_{n}d"] for n in (3, 7, 14)] == [4, 14, 16]
    assert f["pressure_long_due_7d_fraction"] == pytest.approx(1 / 7)
    assert f["pressure_anchored_7d_fraction"] == pytest.approx(2 / 14)


def test_all_features_pure_deterministic_and_output_independent(user, item):
    task = item(duration_category=D.UNDER_8_HOURS, percent_completed=25, start_date=day(-2), due_date=day(3), manual_requested_date=day(1), priority_position=1)
    ProgressSegment.objects.create(item=task, percentage=25, is_completed=True)
    before = list(PlanningItem.objects.values())
    segments = list(ProgressSegment.objects.values())
    with patch("planning.services.scheduling.schedule", side_effect=AssertionError("must not schedule")), CaptureQueriesContext(connection) as queries:
        first = characterize_workload(user, TODAY)
        second = characterize_workload(user, TODAY)
    assert first.to_json() == second.to_json()
    assert len(json.loads(first.to_json())["features"]) == 89
    assert list(PlanningItem.objects.values()) == before
    assert list(ProgressSegment.objects.values()) == segments
    for query in queries:
        sql = query["sql"].lower()
        assert sql.startswith("select")
        assert not any(token in sql for token in ("scheduled_date", "execution_rank", "scheduler_allocation", "conflict"))
    PlanningItem.objects.filter(pk=task.pk).update(scheduled_date=day(500), execution_rank=900)
    SchedulerAllocation.objects.create(item=task, percentage=75, scheduled_date=day(600))
    assert characterize_workload(user, TODAY).to_json() == first.to_json()


def test_nonempty_without_priority_or_dates(user, item):
    item()
    f = features(user)
    assert f["priority_count"] == 0
    assert f["priority_coverage_fraction"] == 0.0
    assert f["temporal_unconstrained_fraction"] == 1
    assert f["deadline_slack_mean_days"] is None
    assert f["anchor_count"] == 0
    assert f["anchor_before_deadline_fraction"] is None
    assert f["lifecycle_unstarted_fraction"] == 1
    assert f["lifecycle_mean_progress"] == f["lifecycle_progress_std"] == 0


def test_frontier_families_include_blocked_exclude_other_rows(user, item):
    parent = item(priority_position=1, due_date=TODAY, manual_requested_date=TODAY)
    child = item(parent=parent, priority_position=2, due_date=day(3), manual_requested_date=day(2))
    prerequisite = item()
    edge(prerequisite, child)
    item(is_completed=True, priority_position=3, due_date=TODAY, manual_requested_date=TODAY)
    item(is_deleted=True, priority_position=4, due_date=TODAY, manual_requested_date=TODAY)
    item(item_type=ItemType.GOAL, due_date=TODAY, manual_requested_date=TODAY)
    f = features(user)
    assert f["item_count_frontier"] == 2
    assert f["item_count_blocked"] == 1
    assert f["priority_count"] == f["anchor_count"] == 1
    assert f["temporal_deadline_fraction"] == f["anchor_fraction"] == .5
    assert f["deadline_within_1d_fraction"] == 0
    assert f["workload_mass_total"] == 4
    assert f["workload_mass_due_3d"] == 2
    assert f["pressure_due_1d_count"] == 0
    assert f["pressure_anchored_7d_fraction"] == .5
