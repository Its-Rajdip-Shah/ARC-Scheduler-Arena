"""Read-only workload features from canonical inputs only.

Visible nodes with no visible parent are roots (including children of deleted
parents). Empty fractions are 0.0; empty depth mean/std and branching mean are
None; empty maximum depth/branching are 0. Depth uses population std deviation.
`today` supplies explicit context for slack, deadline and demand horizons.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from datetime import date, timedelta
import json
import math
from statistics import mean, median, pstdev

from planning.models import (
    ACTIONABLE_TYPES, SPLITTABLE_DURATION_CATEGORIES, DurationCategory,
    PlanningDependency, PlanningItem, ProgressSegment,
)


@dataclass(frozen=True)
class WorkloadFeatures:
    """Ordered immutable raw values and separate immutable correlation support.

    to_mapping returns a fresh JSON/CSV-compatible row; None serializes as null.
    Correlation support never enters the numeric feature vector.
    """

    raw: tuple[tuple[str, int | float | None], ...]
    support: tuple[tuple[str, int], ...] = ()

    def to_mapping(self) -> dict[str, int | float | None]:
        return dict(self.raw)

    @property
    def corr_support(self) -> dict[str, int]:
        return dict(self.support)

    def to_serializable(self) -> dict:
        return {"features": self.to_mapping(), "correlation_support": self.corr_support}

    def to_json(self) -> str:
        return canonical_json(self.to_serializable())


@dataclass(frozen=True)
class WorkloadPopulations:
    total: frozenset[int]
    visible: frozenset[int]
    active: frozenset[int]
    actionable: frozenset[int]
    frontier: frozenset[int]
    executable: frozenset[int]
    blocked: frozenset[int]


def _populations(items: dict[int, dict]) -> WorkloadPopulations:
    total = frozenset(items)
    visible = frozenset(i for i in total if not items[i]["is_deleted"])
    active = frozenset(i for i in visible if not items[i]["is_completed"])
    actionable = frozenset(i for i in active if items[i]["item_type"] in ACTIONABLE_TYPES)
    active_parents = {items[i]["parent_id"] for i in active}
    frontier = actionable - active_parents
    blocked = frozenset(PlanningDependency.objects.filter(
        dependent_id__in=frontier, prerequisite_id__in=active,
    ).values_list("dependent_id", flat=True))
    return WorkloadPopulations(total, visible, active, actionable, frontier, frontier - blocked, blocked)


DURATION_FEATURES = (
    (DurationCategory.UNDER_20_MINUTES, "duration_under_20_fraction"),
    (DurationCategory.UNDER_1_HOUR, "duration_under_1h_fraction"),
    (DurationCategory.UNDER_4_HOURS, "duration_under_4h_fraction"),
    (DurationCategory.UNDER_8_HOURS, "duration_under_8h_fraction"),
    (DurationCategory.UNDER_16_HOURS, "duration_under_16h_fraction"),
    (DurationCategory.OVER_16_HOURS, "duration_over_16h_fraction"),
)


def characterize_workload(user, today: date) -> WorkloadFeatures:
    """Characterize a user's S/H/D/P/T/A/G/L/C/I inputs without scheduling or writing state."""
    items = {row["id"]: row for row in PlanningItem.objects.filter(user=user).order_by("id").values(
        "id", "parent_id", "item_type", "is_deleted", "is_completed",
        "start_date", "due_date", "manual_requested_date", "duration_category",
        "priority_position", "expired_manual_requested_date", "percent_completed",
    )}
    populations = _populations(items)
    raw = {f"item_count_{name}": len(getattr(populations, name)) for name in (
        "total", "visible", "active", "actionable", "frontier", "executable", "blocked",
    )}
    dates = [items[i][field] for i in sorted(populations.actionable)
             for field in ("start_date", "due_date", "manual_requested_date")
             if items[i][field] is not None]
    raw["temporal_span_days"] = (max(dates) - min(dates)).days if dates else None

    visible = populations.visible
    parents = {i: items[i]["parent_id"] for i in visible if items[i]["parent_id"] in visible}
    children = Counter(parents.values())
    depths = {}
    for node in sorted(visible):
        path, seen = [], set()
        current = node
        while current not in depths:
            if current in seen:
                raise ValueError("Visible hierarchy contains a cycle")
            seen.add(current)
            path.append(current)
            if current not in parents:
                break
            current = parents[current]
        depth = depths[current] if current in depths else -1
        for ancestor in reversed(path):
            depth += 1
            depths[ancestor] = depth
    values = list(depths.values())
    raw.update(
        hierarchy_root_fraction=(len(visible) - len(parents)) / len(visible) if visible else 0.0,
        hierarchy_parent_fraction=len(children) / len(visible) if visible else 0.0,
        hierarchy_frontier_fraction=len(populations.frontier) / len(populations.actionable) if populations.actionable else 0.0,
        hierarchy_mean_depth=mean(values) if values else None,
        hierarchy_max_depth=max(values, default=0),
        hierarchy_depth_std=pstdev(values) if values else None,
        hierarchy_mean_branching=mean(children.values()) if children else None,
        hierarchy_max_branching=max(children.values(), default=0),
    )
    durations = Counter(items[i]["duration_category"] for i in populations.frontier)
    unknown = durations.keys() - {category for category, _ in DURATION_FEATURES}
    if unknown:
        raise ValueError(f"Unknown frontier duration categories: {sorted(unknown)!r}")
    count = len(populations.frontier)
    fractions = [durations[category] / count if count else 0.0 for category, _ in DURATION_FEATURES]
    raw.update((name, fraction) for (_, name), fraction in zip(DURATION_FEATURES, fractions))
    raw["duration_entropy"] = -sum(p * math.log(p) for p in fractions if p) / math.log(6) if count else None
    raw["duration_long_fraction"] = sum(fractions[3:])
    frontier = [items[i] for i in sorted(populations.frontier)]
    visible_actionable = frozenset(i for i in visible if items[i]["item_type"] in ACTIONABLE_TYPES)
    edges = list(PlanningDependency.objects.filter(
        prerequisite_id__in=visible_actionable, dependent_id__in=visible_actionable,
    ).order_by("prerequisite_id", "dependent_id").values_list("prerequisite_id", "dependent_id"))
    raw.update(_priority_features(
        [row["priority_position"] for row in frontier if row["priority_position"] is not None],
        frontier_count=len(frontier),
    ))
    raw.update(_temporal_features(frontier, today))
    raw.update(_anchor_features(frontier))
    raw.update(_dependency_features(visible_actionable, edges, len(populations.blocked), len(frontier)))
    raw.update(_lifecycle_features(items, populations, visible_actionable, set(children)))
    raw.update(_demand_features(frontier, today))
    correlations, support = _interaction_features(
        items, populations, visible_actionable, depths, edges, today,
    )
    raw.update(correlations)
    return WorkloadFeatures(tuple(raw.items()), tuple(support.items()))


class FeatureEvaluationError(ValueError):
    """Canonical input cannot be evaluated under the feature definitions."""


def _fraction(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def _collision(dates):
    return 1 - len(set(dates)) / len(dates) if len(dates) >= 2 else 0.0


def _priority_features(positions, frontier_count=None):
    """Describe explicit priority coverage over the canonical frontier.

    Priority positions are ordinal. Frozen ARC gives prioritized frontier items
    a strict ordering, so tie/entropy/quartile descriptors are not meaningful
    workload dimensions.
    """
    n = len(positions)
    denominator = n if frontier_count is None else frontier_count
    return dict(
        priority_count=n,
        priority_coverage_fraction=_fraction(n, denominator),
    )


def _temporal_features(frontier, today):
    n = len(frontier)
    releases = [row["start_date"] for row in frontier if row["start_date"] is not None]
    deadlines = [row["due_date"] for row in frontier if row["due_date"] is not None]
    windows = [(row["due_date"] - row["start_date"]).days for row in frontier
               if row["start_date"] is not None and row["due_date"] is not None]
    slack = [(row["due_date"] - max(today, row["start_date"] or today)).days
             for row in frontier if row["due_date"] is not None]
    raw = dict(
        temporal_release_fraction=_fraction(len(releases), n),
        temporal_deadline_fraction=_fraction(len(deadlines), n),
        temporal_both_fraction=_fraction(len(windows), n),
        temporal_unconstrained_fraction=_fraction(n - len(releases) - len(deadlines) + len(windows), n),
        temporal_window_mean_days=mean(windows) if windows else None,
        temporal_window_median_days=median(windows) if windows else None,
        temporal_window_std_days=pstdev(windows) if windows else None,
        deadline_slack_mean_days=mean(slack) if slack else None,
        deadline_slack_median_days=median(slack) if slack else None,
        deadline_slack_min_days=min(slack) if slack else None,
    )
    for days in (1, 3, 7):
        raw[f"deadline_within_{days}d_fraction"] = _fraction(sum(0 <= (due - today).days <= days for due in deadlines), len(deadlines))
    raw.update(
        overdue_fraction=_fraction(sum(due < today for due in deadlines), len(deadlines)),
        deadline_collision_index=_collision(deadlines),
        release_collision_index=_collision(releases),
    )
    return raw


def _anchor_features(frontier):
    anchored = [row for row in frontier if row["manual_requested_date"] is not None]
    both = [row for row in anchored if row["due_date"] is not None]
    return dict(
        anchor_count=len(anchored),
        anchor_fraction=_fraction(len(anchored), len(frontier)),
        anchor_collision_index=_collision([row["manual_requested_date"] for row in anchored]),
        # The explicit formula uses all anchored items here; relationships below
        # use only anchored items with a deadline.
        anchor_with_deadline_fraction=_fraction(len(both), len(anchored)),
        anchor_before_deadline_fraction=sum(row["manual_requested_date"] < row["due_date"] for row in both) / len(both) if both else None,
        anchor_after_deadline_fraction=sum(row["manual_requested_date"] > row["due_date"] for row in both) / len(both) if both else None,
        anchor_deadline_same_day_fraction=sum(row["manual_requested_date"] == row["due_date"] for row in both) / len(both) if both else None,
        expired_anchor_history_fraction=_fraction(sum(row["expired_manual_requested_date"] is not None for row in frontier), len(frontier)),
    )


def _dependency_features(nodes, edges, blocked_count, frontier_count):
    """Deterministic Kahn traversal; longest path is measured in edges."""
    incoming = dict.fromkeys(sorted(nodes), 0)
    outgoing = {node: [] for node in sorted(nodes)}
    for source, target in sorted(edges):
        incoming[target] += 1
        outgoing[source].append(target)
    remaining = incoming.copy()
    ready = deque(node for node in incoming if not incoming[node])
    lengths = dict.fromkeys(incoming, 0)
    visited = 0
    while ready:
        node = ready.popleft()
        visited += 1
        for target in outgoing[node]:
            lengths[target] = max(lengths[target], lengths[node] + 1)
            remaining[target] -= 1
            if remaining[target] == 0:
                ready.append(target)
    if visited != len(nodes):
        raise FeatureEvaluationError("Dependency graph contains a cycle")
    n = len(nodes)
    return dict(
        dependency_edge_count=len(edges),
        dependency_density=len(edges) / (n * (n - 1)) if n > 1 else 0.0,
        dependency_blocked_fraction=_fraction(blocked_count, frontier_count),
        dependency_mean_indegree=len(edges) / n if n else None,
        dependency_max_indegree=max(incoming.values(), default=0),
        dependency_mean_outdegree=len(edges) / n if n else None,
        dependency_max_outdegree=max((len(targets) for targets in outgoing.values()), default=0),
        dependency_longest_chain=max(lengths.values(), default=0),
        dependency_root_fraction=_fraction(sum(value == 0 for value in incoming.values()), n),
        dependency_sink_fraction=_fraction(sum(not targets for targets in outgoing.values()), n),
    )


def _semantic_progress(row):
    """Frozen progress.py semantics: atomic work has no partial progress."""
    if row["is_completed"]:
        return 1.0
    if row["duration_category"] in SPLITTABLE_DURATION_CATEGORIES:
        return float(row["percent_completed"]) / 100
    return 0.0


def _lifecycle_features(items, populations, visible_actionable, visible_parents):
    rows = [items[i] for i in sorted(visible_actionable)]
    progress = [_semantic_progress(row) for row in rows]
    n = len(rows)
    segments = ProgressSegment.objects.filter(item_id__in=visible_actionable, is_completed=True).count()
    # Frozen _scheduler_eligible's is_residual annotation means visible children
    # on unfinished frontier work. Reproduce its canonical hierarchy predicate
    # without invoking scheduling or excluding dependency-blocked closure work.
    residual = populations.frontier & visible_parents
    return dict(
        lifecycle_completed_fraction=_fraction(sum(row["is_completed"] for row in rows), n),
        lifecycle_commenced_fraction=_fraction(sum(not row["is_completed"] and 0 < p < 1 for row, p in zip(rows, progress)), n),
        lifecycle_unstarted_fraction=_fraction(sum(not row["is_completed"] and p == 0 for row, p in zip(rows, progress)), n),
        lifecycle_mean_progress=mean(progress) if progress else None,
        lifecycle_progress_std=pstdev(progress) if progress else None,
        lifecycle_residual_fraction=_fraction(len(residual), n),
        lifecycle_decomposed_parent_fraction=_fraction(len(visible_actionable & visible_parents), n),
        lifecycle_blocked_fraction=_fraction(len(populations.blocked), len(populations.frontier)),
        confirmed_progress_segment_count=segments,
        confirmed_progress_segment_density=_fraction(segments, n),
    )


# THESE ARE CHARACTERIZATION UNITS, NOT HOURS. No scheduler capacity policy.
DURATION_WEIGHTS = {
    DurationCategory.UNDER_20_MINUTES: 1,
    DurationCategory.UNDER_1_HOUR: 2,
    DurationCategory.UNDER_4_HOURS: 4,
    DurationCategory.UNDER_8_HOURS: 8,
    DurationCategory.UNDER_16_HOURS: 16,
    DurationCategory.OVER_16_HOURS: 24,
}


def _demand_features(frontier, today):
    masses = [DURATION_WEIGHTS[row["duration_category"]] * (1 - _semantic_progress(row)) for row in frontier]
    due = {days: [index for index, row in enumerate(frontier)
                  if row["due_date"] is not None and row["due_date"] <= today + timedelta(days=days)]
           for days in (1, 3, 7, 14)}
    raw = dict(workload_mass_total=sum(masses))
    for days in (3, 7, 14):
        raw[f"workload_mass_due_{days}d"] = sum(masses[index] for index in due[days])
    raw["pressure_frontier_count"] = len(frontier)
    for days in (1, 3, 7, 14):
        raw[f"pressure_due_{days}d_count"] = len(due[days])
    raw["pressure_long_due_7d_fraction"] = _fraction(sum(frontier[index]["duration_category"] in SPLITTABLE_DURATION_CATEGORIES for index in due[7]), len(due[7]))
    raw["pressure_anchored_7d_fraction"] = _fraction(sum(row["manual_requested_date"] is not None and row["manual_requested_date"] <= today + timedelta(days=7) for row in frontier), len(frontier))
    return raw


CORRELATION_NAMES = (
    "corr_priority_deadline_urgency",
    "corr_duration_priority",
    "corr_duration_deadline_urgency",
    "corr_hierarchy_depth_duration",
    "corr_hierarchy_depth_priority",
    "corr_dependency_depth_deadline_urgency",
    "corr_progress_priority",
    "corr_progress_deadline_urgency",
)


def canonical_json(value) -> str:
    """Stable JSON bytes when UTF-8 encoded; undefined values stay null."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _average_ranks(values):
    """One-based average ranks, retaining original observation order."""
    ordered = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        rank = (start + 1 + end) / 2
        for index in ordered[start:end]:
            ranks[index] = rank
        start = end
    return ranks


def spearman(pairs) -> float | None:
    """Pearson correlation of average ranks of complete paired observations.

    Callers filter missing observations; no imputation occurs here. Undefined
    with fewer than two observations or either variable's ranks constant.
    """
    pairs = list(pairs)
    if len(pairs) < 2:
        return None
    x = _average_ranks([pair[0] for pair in pairs])
    y = _average_ranks([pair[1] for pair in pairs])
    center = (len(pairs) + 1) / 2
    dx, dy = [v - center for v in x], [v - center for v in y]
    xx, yy = sum(v * v for v in dx), sum(v * v for v in dy)
    if not xx or not yy:
        return None
    value = sum(a * b for a, b in zip(dx, dy)) / math.sqrt(xx * yy)
    return max(-1.0, min(1.0, value))


def _dependency_depths(nodes, edges):
    """Longest prerequisite path to each visible actionable node, in edges."""
    incoming = dict.fromkeys(sorted(nodes), 0)
    children = {node: [] for node in incoming}
    for source, target in sorted(edges):
        incoming[target] += 1
        children[source].append(target)
    ready = deque(node for node in incoming if incoming[node] == 0)
    depths = dict.fromkeys(incoming, 0)
    visited = 0
    while ready:
        source = ready.popleft()
        visited += 1
        for target in children[source]:
            depths[target] = max(depths[target], depths[source] + 1)
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    if visited != len(nodes):
        raise FeatureEvaluationError("Dependency graph contains a cycle")
    return depths


def _interaction_features(items, populations, visible_actionable, hierarchy_depths, edges, today):
    ordinal_duration = {category: rank for rank, (category, _) in enumerate(DURATION_FEATURES, 1)}
    dependency_depths = _dependency_depths(visible_actionable, edges)
    variables = {}
    for node in sorted(visible_actionable):
        row = items[node]
        variables[node] = {
            # Negative position reverses ordinal orientation; Spearman then
            # ranks it, so numeric priority gaps have no cardinal meaning.
            "priority": -row["priority_position"] if row["priority_position"] is not None else None,
            "duration": ordinal_duration.get(row["duration_category"]),
            "urgency": -(row["due_date"] - today).days if row["due_date"] is not None else None,
            "hierarchy": hierarchy_depths.get(node),
            "dependency": dependency_depths[node],
            "progress": _semantic_progress(row),
        }
    definitions = (
        ("priority", "urgency", populations.frontier),
        ("duration", "priority", populations.frontier),
        ("duration", "urgency", populations.frontier),
        ("hierarchy", "duration", populations.frontier),
        ("hierarchy", "priority", populations.frontier),
        ("dependency", "urgency", visible_actionable),
        ("progress", "priority", visible_actionable),
        ("progress", "urgency", visible_actionable),
    )
    correlations, support = {}, {}
    for name, (x, y, nodes) in zip(CORRELATION_NAMES, definitions):
        pairs = [(variables[node][x], variables[node][y]) for node in sorted(nodes)
                 if variables[node][x] is not None and variables[node][y] is not None]
        correlations[name] = spearman(pairs)
        support[name] = len(pairs)
    return correlations, support
