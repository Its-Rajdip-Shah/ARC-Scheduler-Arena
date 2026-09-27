"""Pure paired trials over supplied immutable scheduling problems."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import date
from decimal import Decimal
from enum import Enum
import json
from math import isfinite
from time import perf_counter

from arena.evaluation.performance import PerformanceVector, evaluate_plan
from arena.scheduling.domain import SchedulePlan, ScheduleProblem
from arena.scheduling.registry import SchedulingAlgorithm
from arena.scheduling.validation import ValidationResult, validate_plan
from arena.search import (
    AdaptiveLargeNeighbourhoodSearch, HillClimber, LargeNeighbourhoodSearch,
    PlanObjective, PlanObjectiveConfig, SearchState, SimulatedAnnealing,
    TabuSearch, VariableNeighbourhoodSearch, score_state,
)

Engine = (HillClimber | VariableNeighbourhoodSearch | TabuSearch |
          SimulatedAnnealing | LargeNeighbourhoodSearch | AdaptiveLargeNeighbourhoodSearch)
_ENGINE_TYPES = (HillClimber, VariableNeighbourhoodSearch, TabuSearch,
                 SimulatedAnnealing, LargeNeighbourhoodSearch, AdaptiveLargeNeighbourhoodSearch)


@dataclass(frozen=True, slots=True)
class WorkloadCase:
    workload_id: str
    family: str
    problem: ScheduleProblem
    workload_seed: int | None = None


@dataclass(frozen=True, slots=True)
class ConstructorArm:
    arm_id: str
    algorithm: SchedulingAlgorithm


@dataclass(frozen=True, slots=True)
class ImproverArm:
    arm_id: str
    engine: Engine | None


@dataclass(frozen=True, slots=True)
class TrialRecord:
    workload_id: str
    family: str
    workload_seed: int | None
    run_seed: int
    constructor_id: str
    improver_id: str
    constructor_config_json: str
    improver_config_json: str | None
    status: str
    initial_plan: SchedulePlan | None
    final_plan: SchedulePlan | None
    initial_validation: ValidationResult | None
    final_validation: ValidationResult | None
    initial_performance: PerformanceVector | None
    final_performance: PerformanceVector | None
    initial_objective: PlanObjective | None
    final_objective: PlanObjective | None
    constructor_seconds: float
    improver_seconds: float | None
    total_seconds: float
    iterations: int | None
    evaluations: int | None
    termination_reason: str | None
    error_type: str | None
    error_message: str | None


def _class_name(value):
    return f'{type(value).__module__}.{type(value).__qualname__}'


def _normalize(value):
    """Only declared configuration data; never fall back to repr or __dict__."""
    if isinstance(value, Enum):
        return _normalize(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        if not value.__dataclass_params__.frozen:
            raise TypeError('Configuration dataclasses must be frozen')
        return {'class': _class_name(value),
                'fields': {f.name: _normalize(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, Mapping):
        result = {}
        for key, entry in value.items():
            normalized_key = _normalize(key)
            if isinstance(normalized_key, (dict, list)):
                raise TypeError('Configuration mapping keys must be scalar')
            key_text = normalized_key if isinstance(normalized_key, str) else _dump(normalized_key)
            if key_text in result:
                raise ValueError('Configuration mapping keys collide after normalization')
            result[key_text] = _normalize(entry)
        return {key: result[key] for key in sorted(result)}
    if isinstance(value, (tuple, list)):
        return [_normalize(v) for v in value]
    if isinstance(value, frozenset):
        return sorted((_normalize(v) for v in value), key=_dump)
    if type(value) is date:
        return value.isoformat()
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError('Configuration Decimal must be finite')
        return str(value)
    if value is None or type(value) in (bool, str, int):
        return value
    if type(value) is float:
        if not isfinite(value):
            raise ValueError('Configuration float must be finite')
        return value
    raise TypeError(f'Unsupported configuration type: {_class_name(value)}')


def _dump(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _config_json(algorithm):
    data = {'class': _class_name(algorithm)}
    if hasattr(algorithm, 'config'):
        data['config'] = _normalize(algorithm.config)
    return _dump(data)


def _identifier(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a nonempty string')


def _prepare(case, constructor, improver, seed, objective):
    if not isinstance(case, WorkloadCase) or not isinstance(case.problem, ScheduleProblem):
        raise TypeError('Expected WorkloadCase with ScheduleProblem')
    if not isinstance(constructor, ConstructorArm) or not isinstance(improver, ImproverArm):
        raise TypeError('Expected ConstructorArm and ImproverArm')
    for value, name in ((case.workload_id, 'workload_id'), (case.family, 'family'),
                        (constructor.arm_id, 'constructor_id'), (improver.arm_id, 'improver_id')):
        _identifier(value, name)
    if type(seed) is not int or (case.workload_seed is not None and type(case.workload_seed) is not int):
        raise ValueError('Seeds must be exact integers')
    if not callable(getattr(constructor.algorithm, 'solve', None)):
        raise TypeError('Constructor must implement solve(problem)')
    if not isinstance(objective, PlanObjectiveConfig):
        raise TypeError('comparison_objective must be PlanObjectiveConfig')
    _normalize(objective)
    engine = improver.engine
    if engine is not None:
        if type(engine) not in _ENGINE_TYPES:
            raise TypeError('Unsupported improver engine class')
        if engine.config.objective != objective:
            raise ValueError('Improver objective must equal comparison_objective')
        for name in ('max_iterations', 'max_evaluations'):
            value = getattr(engine.config, name)
            if type(value) is not int or value < 0:
                raise ValueError(f'{name} must be an explicit nonnegative integer')
        if any(f.name == 'seed' for f in fields(engine.config)):
            engine = type(engine)(replace(engine.config, seed=seed))
    return engine, _config_json(constructor.algorithm), None if engine is None else _config_json(engine)


def run_trial(case: WorkloadCase, constructor_arm: ConstructorArm,
              improver_arm: ImproverArm, run_seed: int,
              comparison_objective: PlanObjectiveConfig) -> TrialRecord:
    """Run one cell; algorithm failures are records, observer errors propagate."""
    context = (f'workload={case.workload_id}, constructor={constructor_arm.arm_id}, '
               f'improver={improver_arm.arm_id}')
    try:
        engine, constructor_json, improver_json = _prepare(
            case, constructor_arm, improver_arm, run_seed, comparison_objective)
    except Exception as exc:
        exc.add_note(context)
        raise
    started = perf_counter()
    data = dict(workload_id=case.workload_id, family=case.family,
                workload_seed=case.workload_seed, run_seed=run_seed,
                constructor_id=constructor_arm.arm_id, improver_id=improver_arm.arm_id,
                constructor_config_json=constructor_json, improver_config_json=improver_json,
                initial_plan=None, final_plan=None, initial_validation=None, final_validation=None,
                initial_performance=None, final_performance=None, initial_objective=None,
                final_objective=None, constructor_seconds=0.0, improver_seconds=None,
                iterations=None, evaluations=None, termination_reason=None,
                error_type=None, error_message=None)

    def finish(status, error=None):
        if error is not None:
            data.update(error_type=type(error).__name__, error_message=str(error))
        return TrialRecord(**data, status=status, total_seconds=perf_counter() - started)

    tick = perf_counter()
    try:
        plan = constructor_arm.algorithm.solve(case.problem)
        if not isinstance(plan, SchedulePlan):
            raise TypeError('Constructor must return SchedulePlan')
    except Exception as exc:
        data['constructor_seconds'] = perf_counter() - tick
        return finish('constructor_error', exc)
    data['constructor_seconds'] = perf_counter() - tick
    data['initial_plan'] = plan
    try:
        validation = validate_plan(case.problem, plan)
        data['initial_validation'] = validation
        data['initial_performance'] = evaluate_plan(case.problem, plan, validation)
    except Exception as exc:
        exc.add_note(context)
        raise
    if validation.violations:
        return finish('constructor_invalid')
    if validation.infeasibilities:
        return finish('constructor_infeasible')
    try:
        initial = SearchState.from_plan(case.problem, plan)
    except ValueError as exc:
        return finish('constructor_unsearchable', exc)
    try:
        data['initial_objective'] = score_state(initial, comparison_objective)
    except Exception as exc:
        exc.add_note(context)
        raise
    if engine is None:
        for field in ('plan', 'validation', 'performance', 'objective'):
            data['final_' + field] = data['initial_' + field]
        data.update(iterations=0, evaluations=0, termination_reason='no_improver', improver_seconds=0.0)
        return finish('ok')
    tick = perf_counter()
    try:
        result = engine.improve_plan(case.problem, plan)
    except Exception as exc:
        data['improver_seconds'] = perf_counter() - tick
        return finish('improver_error', exc)
    data['improver_seconds'] = perf_counter() - tick
    try:
        if result.initial_state != initial:
            raise ValueError('Improver initial_state differs from converted constructor plan')
        if not isinstance(result.final_state, SearchState) or result.final_state.problem != case.problem:
            raise ValueError('Improver final_state must belong to the supplied problem')
        final_plan = result.final_state.to_plan()
        iterations, evaluations, reason = result.iterations, result.evaluations, result.termination_reason
    except Exception as exc:
        return finish('improver_error', exc)
    try:
        final_validation = validate_plan(case.problem, final_plan)
        final_performance = evaluate_plan(case.problem, final_plan, final_validation)
        final_objective = score_state(result.final_state, comparison_objective)
    except Exception as exc:
        exc.add_note(context)
        raise
    try:
        if final_objective != result.final_objective:
            raise ValueError('Improver final_objective differs from independently recomputed score')
        if final_validation.violations or final_validation.infeasibilities:
            raise ValueError('Improver final plan is not feasible')
    except Exception as exc:
        return finish('improver_error', exc)
    data.update(final_plan=final_plan, final_validation=final_validation,
                final_performance=final_performance, final_objective=final_objective,
                iterations=iterations, evaluations=evaluations, termination_reason=reason)
    return finish('ok')


def run_grid(workloads: Sequence[WorkloadCase], constructors: Sequence[ConstructorArm],
             improvers: Sequence[ImproverArm], seeds: Sequence[int],
             comparison_objective: PlanObjectiveConfig) -> tuple[TrialRecord, ...]:
    """Validate the entire matrix before running, preserving caller order."""
    groups = (workloads, constructors, improvers, seeds)
    if any(not isinstance(g, Sequence) or isinstance(g, (str, bytes)) or not g for g in groups):
        raise ValueError('Grid inputs must be nonempty sequences')
    workloads, constructors, improvers, seeds = map(tuple, groups)
    if any(type(seed) is not int for seed in seeds):
        raise ValueError('Seeds must be exact integers')
    for values in ([w.workload_id for w in workloads], [c.arm_id for c in constructors],
                   [i.arm_id for i in improvers], seeds):
        if len(set(values)) != len(values):
            raise ValueError('Grid IDs and seeds must be unique within their category')
    for w in workloads:
        for c in constructors:
            for i in improvers:
                for seed in seeds:
                    _prepare(w, c, i, seed, comparison_objective)
    return tuple(run_trial(w, c, i, seed, comparison_objective)
                 for w in workloads for c in constructors for i in improvers for seed in seeds)
