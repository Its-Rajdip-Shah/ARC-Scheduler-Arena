from dataclasses import FrozenInstanceError, asdict, replace
from datetime import date, timedelta
from decimal import Decimal
import os
import subprocess
import sys

import pytest

from arena.evaluation import PerformanceVector, evaluate_plan
from arena.scheduling.domain import Allocation, DependencyEdge, ScheduleItem, SchedulePlan, ScheduleProblem
from arena.scheduling.validation import PlanViolation, ValidationResult, validate_plan
from arena.algorithms.earliest_feasible import EarliestFeasible
from arena.algorithms.tests import test_earliest_feasible as baseline_cases

TODAY = date(2026, 1, 15)


def day(offset):
    return TODAY + timedelta(days=offset)


def item(i, **kwargs):
    return replace(ScheduleItem(i, 'UNDER_8_HOURS', None, None, None, None,
                                Decimal(0), Decimal(1)), **kwargs)


def row(i, offset=0, percentage=100, rank=1):
    return Allocation(i, day(offset), Decimal(percentage), rank)


def problem(items=(), edges=(), capacity=None, allowed=()):
    return ScheduleProblem(TODAY, tuple(items), tuple(DependencyEdge(*e) for e in edges),
                           {'UNDER_8_HOURS': 2} if capacity is None else capacity,
                           frozenset(allowed))


def evaluate(p, rows=(), validation=None):
    plan = SchedulePlan(tuple(rows))
    return evaluate_plan(p, plan, validate_plan(p, plan) if validation is None else validation)


def test_empty_and_exact_schema():
    result = evaluate(problem())
    counts = '''hard_violation_count canonical_infeasibility_count soft_violation_count
    deadline_item_count deadline_miss_count priority_item_count priority_comparison_count
    priority_inversion_count overloaded_bucket_day_count excess_session_count
    unapproved_overloaded_bucket_day_count unapproved_excess_session_count split_item_count
    fragmented_item_count dependency_edge_count previously_scheduled_item_count
    moved_item_count total_movement_days moved_earlier_item_count moved_later_item_count
    unchanged_item_count deadline_slack_item_count schedulable_window_item_count
    front_loaded_item_count active_day_count'''.split()
    undefined = '''deadline_miss_rate mean_lateness_days max_lateness_days priority_inversion_rate
    peak_capacity_ratio mean_start_delay_days max_start_delay_days zero_wait_rate makespan_days
    fragmented_item_rate mean_session_gap_days max_session_gap_days mean_dependency_wait_days
    max_dependency_wait_days immediate_dependency_transition_rate moved_item_rate
    mean_movement_days max_movement_days mean_completion_slack_days min_completion_slack_days
    mean_relative_window_position front_loaded_item_rate mean_sessions_per_active_day
    max_sessions_on_day daily_session_load_variance'''.split()
    assert asdict(result) == {**dict.fromkeys(counts, 0), **dict.fromkeys(undefined, None)}
    assert list(asdict(result)) == """hard_violation_count canonical_infeasibility_count soft_violation_count
    deadline_item_count deadline_miss_count deadline_miss_rate
    mean_lateness_days max_lateness_days priority_item_count
    priority_comparison_count priority_inversion_count priority_inversion_rate
    peak_capacity_ratio overloaded_bucket_day_count excess_session_count
    unapproved_overloaded_bucket_day_count unapproved_excess_session_count mean_start_delay_days
    max_start_delay_days zero_wait_rate makespan_days
    split_item_count fragmented_item_count fragmented_item_rate
    mean_session_gap_days max_session_gap_days dependency_edge_count
    mean_dependency_wait_days max_dependency_wait_days immediate_dependency_transition_rate
    previously_scheduled_item_count moved_item_count moved_item_rate
    total_movement_days mean_movement_days max_movement_days
    moved_earlier_item_count moved_later_item_count unchanged_item_count
    deadline_slack_item_count mean_completion_slack_days min_completion_slack_days
    schedulable_window_item_count mean_relative_window_position front_loaded_item_count
    front_loaded_item_rate active_day_count mean_sessions_per_active_day
    max_sessions_on_day daily_session_load_variance""".split()
    with pytest.raises(FrozenInstanceError):
        result.makespan_days = 1


def test_validation_is_authoritative():
    v = ValidationResult((PlanViolation('x'), PlanViolation('y')),
                         (PlanViolation('z'),), (PlanViolation('a'),) * 3)
    f = evaluate(problem(), validation=v)
    assert (f.hard_violation_count, f.canonical_infeasibility_count, f.soft_violation_count) == (2, 1, 3)


@pytest.mark.parametrize('finish,miss,mean,maximum', [(1, 0, 0, 0), (4, 1, 1.5, 3)])
def test_deadline_final_completion_and_zero_in_mean(finish, miss, mean, maximum):
    p = problem([item(1, due_date=day(1)), item(2, due_date=day(2)), item(3)])
    f = evaluate(p, [row(1, 0, 50), row(1, finish, 50), row(2, 1), row(3, 9)])
    assert f.deadline_item_count == 2
    assert f.deadline_miss_count == miss
    assert f.deadline_miss_rate == miss / 2
    assert f.mean_lateness_days == mean
    assert f.max_lateness_days == maximum


@pytest.mark.parametrize('high_start,low_start,release,edges,expected', [
    (2, 0, None, (), (1, 1)), (0, 2, None, (), (1, 0)),
    (2, 0, day(2), (), (0, 0)), (2, 0, None, ((3, 1),), (0, 0)),
    (2, 1, None, ((3, 1),), (1, 1)), (0, 0, None, (), (1, 0)),
])
def test_priority(high_start, low_start, release, edges, expected):
    p = problem([item(1, priority_position=1, release_date=release),
                 item(2, priority_position=2), item(3)], edges)
    f = evaluate(p, [row(1, high_start, 50, 2), row(1, high_start + 1, 50),
                     row(2, low_start), row(3)])
    assert f.priority_item_count == 2
    assert (f.priority_comparison_count, f.priority_inversion_count) == expected
    assert f.priority_inversion_rate == (expected[1] / expected[0] if expected[0] else None)


@pytest.mark.parametrize('limit,count,allowed', [(3, 2, False), (2, 2, False),
                                                 (1, 3, False), (1, 3, True), (0, 2, False), (0, 2, True)])
def test_capacity(limit, count, allowed):
    p = problem([item(i) for i in range(count)], capacity={'UNDER_8_HOURS': limit},
                allowed=[TODAY] if allowed else [])
    f = evaluate(p, [row(i, rank=i + 1) for i in range(count)])
    excess = max(0, count - limit)
    assert f.peak_capacity_ratio == (count / limit if limit else None)
    assert f.overloaded_bucket_day_count == int(excess > 0)
    assert f.excess_session_count == excess
    assert f.unapproved_overloaded_bucket_day_count == (0 if allowed else int(excess > 0))
    assert f.unapproved_excess_session_count == (0 if allowed else excess)
    assert f.soft_violation_count == f.unapproved_overloaded_bucket_day_count


def test_residual_and_missing_capacity():
    p = problem([item(1, is_residual=True), item(2)], capacity={'UNDER_20_MINUTES': 1})
    f = evaluate(p, [row(1), row(2)])
    assert f.peak_capacity_ratio == 1
    assert f.excess_session_count == 0
    assert evaluate(problem([item(1)], capacity={}), [row(1)]).peak_capacity_ratio is None


@pytest.mark.parametrize('start,release,anchor,expected', [
    (0, None, None, 0), (3, day(3), None, 0), (5, day(2), None, 3),
    (4, None, day(4), 4), (-1, None, None, None), (1, day(2), None, None),
])
def test_temporal(start, release, anchor, expected):
    f = evaluate(problem([item(1, release_date=release, anchor_date=anchor)]), [row(1, start)])
    assert f.mean_start_delay_days == f.max_start_delay_days == expected
    assert f.zero_wait_rate == (None if expected is None else float(expected == 0))


@pytest.mark.parametrize('offsets,span', [([0], 1), ([0, 1], 2), ([0, 4], 5)])
def test_makespan(offsets, span):
    f = evaluate(problem([item(1)]), [row(1, d, 100 // len(offsets)) for d in offsets])
    assert f.makespan_days == span


@pytest.mark.parametrize('offset,gap', [(1, 0), (2, 1), (4, 3)])
def test_continuity(offset, gap):
    f = evaluate(problem([item(1)]), [row(1, offset, 50), row(1, 0, 50)])
    assert f.split_item_count == 1
    assert f.fragmented_item_count == int(gap > 0)
    assert f.fragmented_item_rate == float(gap > 0)
    assert f.mean_session_gap_days == f.max_session_gap_days == gap


def test_continuity_pair_weighted_mean():
    f = evaluate(problem([item(1), item(2), item(3)]),
                 [row(1, 0, 25), row(1, 1, 25), row(1, 4, 50),
                  row(2, 0, 50, 2), row(2, 1, 50, 2), row(3, 8)])
    assert (f.split_item_count, f.fragmented_item_count, f.fragmented_item_rate) == (2, 1, .5)
    assert f.mean_session_gap_days == pytest.approx(2 / 3)
    assert f.max_session_gap_days == 2


@pytest.mark.parametrize('dependent,wait', [(1, 0), (3, 2), (0, None), (-1, None)])
def test_dependency_flow_and_readiness(dependent, wait):
    f = evaluate(problem([item(1), item(2)], [(1, 2)]), [row(1), row(2, dependent, rank=2)])
    assert f.dependency_edge_count == 1
    assert f.mean_dependency_wait_days == f.max_dependency_wait_days == wait
    assert f.immediate_dependency_transition_rate == (None if wait is None else float(wait == 0))
    assert f.mean_start_delay_days == (0 if wait is None else wait / 2)


def test_fan_in_and_explicit_chain():
    f = evaluate(problem([item(i) for i in range(1, 5)], [(1, 3), (2, 3), (3, 4)]),
                 [row(1), row(2, 2), row(3, 3), row(4, 4)])
    assert f.dependency_edge_count == 3
    assert f.mean_dependency_wait_days == pytest.approx(2 / 3)
    assert f.max_dependency_wait_days == 2
    assert f.immediate_dependency_transition_rate == pytest.approx(2 / 3)
    assert f.mean_start_delay_days == .5


def test_missing_partial_and_unknown_do_not_manufacture_completion():
    p = problem([item(1, due_date=TODAY), item(2, priority_position=1),
                 item(3, priority_position=2)], [(1, 2)])
    f = evaluate(p, [row(1, 0, 50), row(2, 3), row(3), row(999, 100)])
    assert f.deadline_item_count == 1
    assert f.deadline_miss_rate is f.mean_lateness_days is f.max_lateness_days is None
    assert f.priority_comparison_count == 0
    assert f.mean_dependency_wait_days is None
    assert f.makespan_days == 4
    missing = evaluate(p)
    assert missing.makespan_days is None
    assert missing.mean_start_delay_days is None
    assert missing.hard_violation_count == 3


def test_duplicates_remain_observable_and_deterministic_without_mutation():
    p = problem([item(1, due_date=TODAY)])
    plan = SchedulePlan((row(1), row(1)))
    before = (p.items, p.dependencies, dict(p.capacity_by_duration), p.overload_dates, asdict(plan))
    validation = validate_plan(p, plan)
    f = evaluate_plan(p, plan, validation)
    assert f == evaluate_plan(p, plan, validation)
    assert f.hard_violation_count == 2
    assert f.deadline_miss_rate is None
    assert f.split_item_count == 1
    assert f.mean_session_gap_days == 0
    assert f.peak_capacity_ratio == 1
    assert before == (p.items, p.dependencies, dict(p.capacity_by_duration), p.overload_dates, asdict(plan))


def test_invalid_date_is_excluded():
    p = problem([item(1)])
    plan = SchedulePlan((replace(row(1), scheduled_date=None),))
    f = evaluate_plan(p, plan, ValidationResult((PlanViolation('malformed'),)))
    assert f.makespan_days is f.mean_start_delay_days is None


def test_public_api_without_django():
    env = dict(os.environ)
    env.pop('DJANGO_SETTINGS_MODULE', None)
    subprocess.run([sys.executable, '-c',
                    "from arena.evaluation import evaluate_plan, PerformanceVector; "
                    "import sys; assert 'django' not in sys.modules"], env=env, check=True)


@pytest.mark.parametrize('allowed', [False, True])
def test_earliest_feasible_cross_check(allowed):
    p = problem([item(1, due_date=TODAY), item(2, due_date=TODAY),
                 item(3, release_date=day(4)), item(4, is_residual=True)], [(1, 3), (2, 3)],
                capacity={'UNDER_8_HOURS': 1, 'UNDER_20_MINUTES': 1},
                allowed=[TODAY, day(1)] if allowed else [])
    before = (p.items, p.dependencies, dict(p.capacity_by_duration), p.overload_dates)
    plan = EarliestFeasible().solve(p)
    validation = validate_plan(p, plan)
    assert validation.is_valid
    f = evaluate_plan(p, plan, validation)
    assert f == evaluate_plan(p, EarliestFeasible().solve(p), validation)
    assert f.mean_start_delay_days >= 0
    assert f.mean_dependency_wait_days >= 0
    assert f.deadline_miss_count == 2
    assert f.mean_lateness_days >= 1
    assert f.overloaded_bucket_day_count > 0
    capacity_dates = {v.scheduled_date for v in validation.soft_violations if v.code == 'capacity_exceeded'}
    assert f.unapproved_overloaded_bucket_day_count == len(capacity_dates)
    if allowed:
        assert f.unapproved_excess_session_count == 0
    assert before == (p.items, p.dependencies, dict(p.capacity_by_duration), p.overload_dates)


@pytest.mark.parametrize('case', [getattr(baseline_cases, name) for name in sorted(dir(baseline_cases))
                                  if name.startswith('test_')], ids=lambda case: case.__name__)
def test_existing_earliest_feasible_cases(case, monkeypatch):
    original = EarliestFeasible.solve

    def checked_solve(self, p):
        plan = original(self, p)
        validation = validate_plan(p, plan)
        before = (p.items, dict(p.capacity_by_duration), asdict(plan))
        f = evaluate_plan(p, plan, validation)
        assert f == evaluate_plan(p, original(self, p), validation)
        assert f.mean_start_delay_days is None or f.mean_start_delay_days >= 0
        assert f.mean_dependency_wait_days is None or f.mean_dependency_wait_days >= 0
        assert before == (p.items, dict(p.capacity_by_duration), asdict(plan))
        return plan

    monkeypatch.setattr(EarliestFeasible, 'solve', checked_solve)
    case()


@pytest.mark.django_db
def test_frozen_benchmark_evaluation_has_no_database_access():
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    from arena.benchmarks.reconstruct import load_v1_scenarios, reconstruct_scenario

    p = reconstruct_scenario(load_v1_scenarios()[0], email='performance@local.test').problem
    plan = EarliestFeasible().solve(p)
    validation = validate_plan(p, plan)
    with CaptureQueriesContext(connection) as queries:
        f = evaluate_plan(p, plan, validation)
        assert f == evaluate_plan(p, plan, validation)
    assert len(queries) == 0
    assert f.dependency_edge_count == len(p.dependencies)
    assert f.deadline_item_count == sum(i.due_date is not None for i in p.items)


@pytest.mark.parametrize('percentages,ranks', [((50, 50), (1, 1)), ((40, 60), (1, 1)),
                                             ((40, 40), (1, 2)), ((60, 60), (1, 2))])
def test_malformed_work_cannot_supply_completion_or_readiness(percentages, ranks):
    p = problem([item(1, due_date=TODAY), item(2, priority_position=1),
                 item(3, priority_position=2)], [(1, 2)], capacity={'UNDER_8_HOURS': 1})
    f = evaluate(p, [row(1, 0, percentages[0], ranks[0]), row(1, 0, percentages[1], ranks[1]),
                     row(2, 2), row(3, 1)])
    assert f.hard_violation_count > 0
    assert f.deadline_item_count == 1
    assert f.deadline_miss_rate is f.mean_lateness_days is f.max_lateness_days is None
    assert f.priority_comparison_count == 0
    assert f.mean_dependency_wait_days is None
    assert f.makespan_days == 2  # Only the two complete items, not invented completion.
    assert f.peak_capacity_ratio == 2
    assert f.excess_session_count == 1


def test_distinct_same_day_sessions_can_complete_proposed_work():
    f = evaluate(problem([item(1, due_date=TODAY)]), [row(1, 0, 50, 1), row(1, 0, 50, 2)])
    assert f.hard_violation_count == 0
    assert f.deadline_miss_rate == 0
    assert f.makespan_days == 1


def test_uncomputable_split_is_not_classified_as_unfragmented():
    p = problem([item(1), item(2)])
    plan = SchedulePlan((row(1, 0, 50), row(1, 2, 50), row(2, 0, 50, 2),
                         replace(row(2, 1, 50), scheduled_date=None)))
    f = evaluate_plan(p, plan, ValidationResult((PlanViolation('malformed'),)))
    assert f.split_item_count == 2
    assert f.fragmented_item_count == 1
    assert f.fragmented_item_rate is None
    assert f.mean_session_gap_days == f.max_session_gap_days == 1


def test_omission_improves_conditional_diagnostics_but_is_hard_invalid():
    p = problem([item(1, due_date=TODAY, priority_position=1),
                 item(2, due_date=TODAY, priority_position=2)])
    complete = evaluate(p, [row(1, 3), row(2)])
    omitted = evaluate(p, [row(2)])
    assert complete.hard_violation_count == 0
    assert complete.deadline_miss_rate == .5
    assert complete.priority_inversion_rate == 1
    assert omitted.hard_violation_count == 1  # Excludes this plan from quality comparison.
    assert omitted.deadline_item_count == omitted.priority_item_count == 2
    assert omitted.deadline_miss_rate == 0  # Conditional diagnostic, not a fabricated miss.
    assert omitted.priority_comparison_count == 0
    assert omitted.priority_inversion_rate is None
    assert omitted.makespan_days == 1


def test_negative_wait_exclusion_is_diagnostic_not_success():
    p = problem([item(1, release_date=day(3)), item(2)])
    f = evaluate(p, [row(1), row(2, rank=2)])
    assert f.hard_violation_count == 1
    assert f.mean_start_delay_days == 0
    assert f.zero_wait_rate == 1  # Only the legal observation, not permission to compare.


def test_edge_flow_wait_is_distinct_from_latest_item_readiness():
    p = problem([item(1), item(2), item(3, release_date=day(5))], [(1, 3), (2, 3)])
    f = evaluate(p, [row(1), row(2, 3), row(3, 5)])
    assert f.hard_violation_count == 0
    assert f.mean_dependency_wait_days == 2.5  # Individual edges wait 4 and 1 days.
    assert f.max_dependency_wait_days == 4
    assert f.mean_start_delay_days == 1  # Item waits 0, 3, 0 from their own readiness.


def test_no_existing_schedules_has_no_movement_population():
    f = evaluate(problem([item(1)]), [row(1)])
    assert (f.previously_scheduled_item_count, f.moved_item_count, f.total_movement_days,
            f.moved_earlier_item_count, f.moved_later_item_count, f.unchanged_item_count) == (0,) * 6
    assert f.moved_item_rate is f.mean_movement_days is f.max_movement_days is None


@pytest.mark.parametrize('start,earlier,later,unchanged', [(2, 0, 0, 1), (0, 1, 0, 0), (5, 0, 1, 0)])
def test_movement_directions(start, earlier, later, unchanged):
    f = evaluate(problem([item(1, existing_scheduled_date=day(2))]), [row(1, start)])
    assert f.hard_violation_count == 0  # Existing schedule imposes no constraint.
    assert f.previously_scheduled_item_count == 1
    assert (f.moved_earlier_item_count, f.moved_later_item_count, f.unchanged_item_count) == (earlier, later, unchanged)
    assert f.moved_item_count == f.moved_item_rate == earlier + later
    assert f.total_movement_days == f.mean_movement_days == f.max_movement_days == abs(start - 2)


def test_mixed_movement_split_first_date_and_purity():
    p = problem([item(i, existing_scheduled_date=day(3)) for i in range(1, 4)])
    # First calendar session has a higher rank; later split sessions add no movement.
    plan = SchedulePlan((row(1, 3), row(2, 8, 50, 1), row(2, 1, 50, 9), row(3, 7), row(999, 100)))
    before = (p.items, p.dependencies, dict(p.capacity_by_duration), p.overload_dates, asdict(plan))
    validation = validate_plan(p, plan)
    f = evaluate_plan(p, plan, validation)
    assert f.previously_scheduled_item_count == 3
    assert f.moved_item_count == 2
    assert f.moved_item_rate == pytest.approx(2 / 3)
    assert (f.total_movement_days, f.mean_movement_days, f.max_movement_days) == (6, 2, 4)
    assert (f.moved_earlier_item_count, f.moved_later_item_count, f.unchanged_item_count) == (1, 1, 1)
    assert f == evaluate_plan(p, plan, validation)
    assert before == (p.items, p.dependencies, dict(p.capacity_by_duration), p.overload_dates, asdict(plan))


def test_uncomputable_movement_excluded_but_partial_start_observable():
    p = problem([item(i, existing_scheduled_date=TODAY) for i in range(1, 4)])
    f = evaluate(p, [row(1, 2, 50), replace(row(1, 3, 50), scheduled_date=None),
                     row(2, 4, 50), row(999)], ValidationResult((PlanViolation('malformed'),)))
    assert f.previously_scheduled_item_count == f.moved_item_count == 1
    assert f.total_movement_days == f.mean_movement_days == f.max_movement_days == 4
    assert f.unchanged_item_count == 0


def test_anchor_movement_is_observable_and_hard_invalid():
    p = problem([item(1, anchor_date=TODAY, existing_scheduled_date=TODAY)])
    plan = SchedulePlan((row(1, 2),))
    validation = validate_plan(p, plan)
    assert not validation.is_valid
    f = evaluate_plan(p, plan, validation)
    assert f.hard_violation_count == len(validation.violations) > 0
    assert f.moved_item_count == 1
    assert f.total_movement_days == 2


@pytest.mark.parametrize('finish,slack', [(1, 3), (4, 0), (6, -2)])
def test_signed_completion_slack(finish, slack):
    f = evaluate(problem([item(1, due_date=day(4))]), [row(1, 0, 50), row(1, finish, 50)])
    assert f.deadline_slack_item_count == 1
    assert f.mean_completion_slack_days == f.min_completion_slack_days == slack


def test_slack_population_and_signed_mean():
    p = problem([item(i, due_date=day(4)) for i in range(1, 6)])
    f = evaluate(p, [row(1, 1), row(2, 4), row(3, 6), row(4, 2, 50)])
    assert f.deadline_slack_item_count == 3
    assert f.mean_completion_slack_days == pytest.approx(1 / 3)
    assert f.min_completion_slack_days == -2
    empty = evaluate(p, [row(4, 2, 50)])
    assert empty.deadline_slack_item_count == 0
    assert empty.mean_completion_slack_days is empty.min_completion_slack_days is None


@pytest.mark.parametrize('start,position,front', [(2, 0, 1), (6, 1, 0), (4, .5, 0),
                                                 (3, .25, 1), (0, -.5, 1), (8, 1.5, 0)])
def test_relative_window_position_unclamped(start, position, front):
    f = evaluate(problem([item(1, release_date=day(2), due_date=day(6))]), [row(1, start)])
    assert f.schedulable_window_item_count == 1
    assert f.mean_relative_window_position == position
    assert f.front_loaded_item_count == f.front_loaded_item_rate == front


@pytest.mark.parametrize('start,expected', [(2, 0.0), (1, None), (3, None)])
def test_zero_width_window(start, expected):
    f = evaluate(problem([item(1, release_date=day(2), due_date=day(2))]), [row(1, start)])
    assert f.mean_relative_window_position == expected
    assert f.schedulable_window_item_count == int(expected is not None)
    assert f.front_loaded_item_rate == (None if expected is None else 1)


def test_window_prerequisites_and_missing_observations():
    p = problem([item(1), item(2, due_date=day(5)), item(3),
                 item(4, release_date=day(4), due_date=day(3)),
                 item(5, due_date=day(5)), item(6, due_date=day(5))], [(1, 2)])
    f = evaluate(p, [row(1, 0, 50), row(2, 3), row(3), row(4, 4),
                     replace(row(5), scheduled_date=None)], ValidationResult(()))
    assert f.schedulable_window_item_count == f.front_loaded_item_count == 0
    assert f.mean_relative_window_position is f.front_loaded_item_rate is None
    # Own completion is not needed, but prerequisite completion sets readiness.
    f = evaluate(p, [row(1, 2), row(2, 4, 50)])
    assert f.schedulable_window_item_count == 1
    assert f.mean_relative_window_position == .5


def test_window_population_mean_and_front_loaded_rate():
    f = evaluate(problem([item(i, due_date=day(4)) for i in range(1, 4)]),
                 [row(1), row(2, 1), row(3, 4)])
    assert f.schedulable_window_item_count == 3
    assert f.mean_relative_window_position == pytest.approx(5 / 12)
    assert f.front_loaded_item_count == 2
    assert f.front_loaded_item_rate == pytest.approx(2 / 3)


@pytest.mark.parametrize('offsets,mean,maximum,variance', [([0, 0, 0], 3, 3, 0),
                                                        ([0, 0, 10], 1.5, 2, .25)])
def test_active_day_session_load(offsets, mean, maximum, variance):
    # Different buckets, residual bucket, and missing capacity still count as sessions.
    p = problem([item(1), item(2, duration_category='UNDER_1_HOUR'),
                 item(3, is_residual=True)], capacity={})
    f = evaluate(p, [row(i, offset, rank=i) for i, offset in enumerate(offsets, 1)])
    assert f.active_day_count == len(set(offsets))
    assert f.mean_sessions_per_active_day == mean
    assert f.max_sessions_on_day == maximum
    assert f.daily_session_load_variance == variance


def test_load_excludes_unknown_and_unusable_rows_but_keeps_usable_partial_rows():
    p = problem([item(1)])
    f = evaluate(p, [row(1, 0, 50), replace(row(1, 1, 50), scheduled_date=None), row(999, 10)],
                 ValidationResult((PlanViolation('malformed'),)))
    assert f.active_day_count == f.mean_sessions_per_active_day == f.max_sessions_on_day == 1
    assert f.daily_session_load_variance == 0.0
    f = evaluate(p, [replace(row(1), scheduled_date=None), row(999, 10)], ValidationResult(()))
    assert f.active_day_count == 0
    assert f.mean_sessions_per_active_day is f.max_sessions_on_day is f.daily_session_load_variance is None
