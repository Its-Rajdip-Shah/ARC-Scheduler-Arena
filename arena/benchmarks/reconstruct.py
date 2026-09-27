"""Reconstruct and verify frozen ARC Benchmark V1 scenarios.

Benchmark V1 stores the generator controls/seeds and the frozen Φ89
characterization. A scenario is usable for algorithm experiments only when
deterministic regeneration reproduces that frozen characterization.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, get_type_hints

from arena.evaluation.features import characterize_workload
from arena.generation.blueprint import build_blueprint
from arena.generation.materialize import materialize_blueprint
from arena.generation.spec import GenerationSpec
from arena.scheduling.adapter import problem_from_user
from arena.scheduling.domain import ScheduleProblem


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "arena" / "benchmarks" / "v1"

MANIFEST = V1 / "manifest.json"
DESIGNS = V1 / "designs.csv"
WORKLOADS = V1 / "workloads.json"

EXPECTED_VERSION = "v1"
EXPECTED_SCENARIOS = 118
EXPECTED_DIMENSIONS = 89

# Φ89 is generated deterministically, but some dimensions are floating-point
# aggregates/correlations. We compare numerically rather than by JSON text.
ABS_TOL = 1e-12
REL_TOL = 1e-12


class BenchmarkDriftError(RuntimeError):
    """Frozen benchmark semantics no longer reproduce exactly enough."""


@dataclass(frozen=True, slots=True)
class FrozenScenario:
    scenario_id: str
    design_index: int
    replicate_index: int
    seed: int
    today: str
    spec: GenerationSpec
    frozen_features: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ReconstructedScenario:
    frozen: FrozenScenario
    materialized: Any
    problem: ScheduleProblem
    regenerated_features: dict[str, Any]


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _parse_scalar(raw: str, annotation: Any) -> Any:
    """Deserialize one GenerationSpec CSV value using its declared type."""

    # GenerationSpec currently uses concrete enum/scalar annotations.
    # Enum classes are str subclasses, so detect them before plain str.
    if isinstance(annotation, type):
        try:
            from enum import Enum

            if issubclass(annotation, Enum):
                return annotation(raw)
        except TypeError:
            pass

    if annotation is int:
        return int(raw)

    if annotation is float:
        return float(raw)

    if annotation is bool:
        lowered = raw.strip().lower()

        if lowered in {"true", "1", "yes"}:
            return True

        if lowered in {"false", "0", "no"}:
            return False

        raise ValueError(f"Invalid boolean value: {raw!r}")

    if annotation is str:
        return raw

    # Defensive fallback for enum-like declared types.
    if isinstance(annotation, type):
        try:
            return annotation(raw)
        except (TypeError, ValueError):
            pass

    raise TypeError(
        f"Unsupported GenerationSpec field annotation "
        f"{annotation!r} for value {raw!r}"
    )


def _spec_from_design_row(
    row: dict[str, str],
    *,
    seed: int,
) -> GenerationSpec:
    """Reconstruct typed GenerationSpec from one frozen design row."""

    hints = get_type_hints(GenerationSpec)
    values: dict[str, Any] = {}

    for field in fields(GenerationSpec):
        if field.name == "seed":
            values["seed"] = seed
            continue

        if field.name not in row:
            # Frozen designs contain the varying controls. Any absent field
            # deliberately retains the GenerationSpec frozen default.
            continue

        raw = row[field.name]

        if raw == "":
            continue

        values[field.name] = _parse_scalar(
            raw,
            hints[field.name],
        )

    spec = GenerationSpec(**values)
    spec.validate()
    return spec


def load_v1_scenarios() -> tuple[FrozenScenario, ...]:
    """Load all frozen V1 scenarios with typed GenerationSpecs."""

    manifest = _load_json(MANIFEST)
    workloads = _load_json(WORKLOADS)

    if manifest["benchmark_version"] != EXPECTED_VERSION:
        raise BenchmarkDriftError(
            "Unexpected benchmark version."
        )

    if manifest["status"] != "frozen":
        raise BenchmarkDriftError(
            "Benchmark V1 is not marked frozen."
        )

    if len(workloads) != EXPECTED_SCENARIOS:
        raise BenchmarkDriftError(
            "Frozen workload count drifted."
        )

    with DESIGNS.open(
        newline="",
        encoding="utf-8",
    ) as stream:
        design_rows = list(csv.DictReader(stream))

    designs_by_index = {
        int(row["design_index"]): row
        for row in design_rows
    }

    scenarios: list[FrozenScenario] = []

    for workload in workloads:
        metadata = workload["metadata"]

        design_index = int(metadata["design_index"])
        replicate_index = int(metadata["replicate"])
        seed = int(metadata["seed"])

        try:
            design = designs_by_index[design_index]
        except KeyError as exc:
            raise BenchmarkDriftError(
                f"Scenario references unknown design "
                f"{design_index}."
            ) from exc

        features = dict(workload["features"])

        if len(features) != EXPECTED_DIMENSIONS:
            raise BenchmarkDriftError(
                f"{metadata['scenario_id']} is not Φ89."
            )

        scenarios.append(
            FrozenScenario(
                scenario_id=metadata["scenario_id"],
                design_index=design_index,
                replicate_index=replicate_index,
                seed=seed,
                today=metadata["today"],
                spec=_spec_from_design_row(
                    design,
                    seed=seed,
                ),
                frozen_features=features,
            )
        )

    actual_ids = tuple(
        scenario.scenario_id
        for scenario in scenarios
    )
    expected_ids = tuple(manifest["scenario_ids"])

    if actual_ids != expected_ids:
        raise BenchmarkDriftError(
            "Frozen scenario ordering/identity drifted."
        )

    return tuple(scenarios)


def _numbers_equal(
    expected: Any,
    actual: Any,
) -> bool:
    if expected is None or actual is None:
        return expected is actual

    # bool is a subclass of int; compare it exactly.
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected == actual

    if isinstance(expected, (int, float)) and isinstance(
        actual,
        (int, float),
    ):
        expected_f = float(expected)
        actual_f = float(actual)

        if math.isnan(expected_f) or math.isnan(actual_f):
            return (
                math.isnan(expected_f)
                and math.isnan(actual_f)
            )

        return math.isclose(
            expected_f,
            actual_f,
            rel_tol=REL_TOL,
            abs_tol=ABS_TOL,
        )

    return expected == actual


def assert_phi89_matches(
    frozen: dict[str, Any],
    regenerated: dict[str, Any],
    *,
    scenario_id: str,
) -> None:
    """Hard-stop if regenerated characterization differs from V1."""

    frozen_names = set(frozen)
    regenerated_names = set(regenerated)

    # Φ89 is a named feature vector. Dictionary insertion order is not part
    # of the benchmark schema; membership is.
    if frozen_names != regenerated_names:
        missing = sorted(
            frozen_names - regenerated_names
        )
        extra = sorted(
            regenerated_names - frozen_names
        )

        raise BenchmarkDriftError(
            f"{scenario_id}: Φ89 schema drift. "
            f"missing={missing}, extra={extra}"
        )

    mismatches = []

    # Deterministic ordering is useful only for stable diagnostics.
    for name in sorted(frozen_names):
        expected = frozen[name]
        actual = regenerated[name]

        if not _numbers_equal(expected, actual):
            mismatches.append(
                (name, expected, actual)
            )

    if mismatches:
        preview = "; ".join(
            f"{name}: frozen={expected!r}, "
            f"regenerated={actual!r}"
            for name, expected, actual in mismatches[:8]
        )

        raise BenchmarkDriftError(
            f"{scenario_id}: Φ89 semantic drift in "
            f"{len(mismatches)} dimension(s): {preview}"
        )


def reconstruct_scenario(
    scenario: FrozenScenario,
    *,
    email: str | None = None,
) -> ReconstructedScenario:
    """Regenerate, materialize, verify Φ89, then expose algorithm input."""

    from datetime import date

    today = date.fromisoformat(scenario.today)

    blueprint = build_blueprint(scenario.spec)

    materialized = materialize_blueprint(
        blueprint,
        email=(
            email
            or (
                "arena-v1-"
                + scenario.scenario_id
                .replace("_", "-")
                .replace("/", "-")
                + "@local.test"
            )
        ),
    )

    characterized = characterize_workload(
        materialized.user,
        today,
    )

    if hasattr(characterized, "to_mapping"):
        regenerated = dict(characterized.to_mapping())
    elif isinstance(characterized, dict):
        regenerated = dict(characterized)
    else:
        raise TypeError(
            "characterize_workload() returned unsupported "
            f"type: {type(characterized)!r}"
        )

    assert_phi89_matches(
        scenario.frozen_features,
        regenerated,
        scenario_id=scenario.scenario_id,
    )

    # Only after the benchmark guard passes do algorithms receive input.
    problem = problem_from_user(
        materialized.user,
        today,
    )

    return ReconstructedScenario(
        frozen=scenario,
        materialized=materialized,
        problem=problem,
        regenerated_features=regenerated,
    )


def reconstruct_v1_scenario(
    scenario_id: str,
) -> ReconstructedScenario:
    scenarios = load_v1_scenarios()

    for scenario in scenarios:
        if scenario.scenario_id == scenario_id:
            return reconstruct_scenario(scenario)

    raise KeyError(
        f"Unknown Benchmark V1 scenario: {scenario_id}"
    )
