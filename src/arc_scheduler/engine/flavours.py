"""Frozen C11 production flavour semantics.

This module defines behaviour contracts only.

It deliberately does not choose numerical optimisation weights yet. C11 must
first agree on what each user-facing flavour means, then implement and validate
an objective that satisfies that meaning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


FLAVOUR_CONTRACT_VERSION = "c11-flavours-v1"


class ProductionFlavour(str, Enum):
    LOCK_IN = "lock-in"
    MONK = "monk"


@dataclass(frozen=True, slots=True)
class FlavourContract:
    flavour: ProductionFlavour
    display_name: str
    tagline: str

    invariant_precedence: tuple[str, ...]

    task_continuity_required: bool
    task_continuity_definition: str

    idle_day_policy: str
    load_policy: str
    overload_policy: str
    completion_policy: str
    deadline_policy: str

    explicit_non_goals: tuple[str, ...]


_COMMON_INVARIANT_PRECEDENCE = (
    "canonical_arc_state_is_authoritative",
    "hard_schedule_legality",
    "dependency_correctness",
    "anchor_correctness",
    "release_date_correctness",
    "deadline_and_horizon_semantics",
    "session_piece_conservation",
    "execution_order_validity",
    "flavour_preferences",
)


_COMMON_CONTINUITY = (
    "Once the first session of a splittable item is scheduled, prefer the "
    "remaining sessions to complete the item over the shortest practical "
    "elapsed span. A gap is acceptable when required by hard constraints or "
    "when avoiding unreasonable load. Continuity does not require every "
    "session to occur on the same day and does not justify overload."
)


LOCK_IN = FlavourContract(
    flavour=ProductionFlavour.LOCK_IN,
    display_name="Lock-in",
    tagline=(
        "Get ahead aggressively, build deadline buffer, and keep momentum."
    ),
    invariant_precedence=_COMMON_INVARIANT_PRECEDENCE,
    task_continuity_required=True,
    task_continuity_definition=_COMMON_CONTINUITY,
    idle_day_policy=(
        "Avoid unnecessary idle calendar days while executable unscheduled "
        "work exists. Prefer useful earlier work over leaving usable capacity "
        "empty."
    ),
    load_policy=(
        "Higher daily load is acceptable when it materially advances useful "
        "work or completes started work, but concentration must remain "
        "reasonable."
    ),
    overload_policy=(
        "Overload remains soft rather than becoming a new legality rule, but "
        "must carry a strong penalty. Lock-in may accept more load than Monk; "
        "it must not obtain early completion by creating obviously excessive "
        "daily overload."
    ),
    completion_policy=(
        "Prefer earlier item completion and rapid advancement of dependency "
        "chains. Once an item starts, finishing it promptly is strongly "
        "preferred."
    ),
    deadline_policy=(
        "Build deadline buffer aggressively after respecting releases, "
        "dependencies and anchors."
    ),
    explicit_non_goals=(
        "Do not force all remaining sessions of a large item onto one day.",
        "Do not create overload merely to eliminate an otherwise sensible gap.",
        "Do not violate canonical or scheduling invariants for earlier completion.",
        "Do not require every calendar day to contain work.",
    ),
)


MONK = FlavourContract(
    flavour=ProductionFlavour.MONK,
    display_name="Monk",
    tagline=(
        "Keep the calendar calm and balanced without losing task momentum."
    ),
    invariant_precedence=_COMMON_INVARIANT_PRECEDENCE,
    task_continuity_required=True,
    task_continuity_definition=_COMMON_CONTINUITY,
    idle_day_policy=(
        "Use otherwise-empty usable days when doing so reduces nearby load "
        "concentration. Empty days are acceptable when the surrounding "
        "calendar is already comfortably balanced."
    ),
    load_policy=(
        "Minimise daily load spikes and distribute work across usable days, "
        "preferably keeping each day just below its practical capacity rather "
        "than creating overloaded peaks."
    ),
    overload_policy=(
        "Avoid overload more strongly than Lock-in. First reduce peak excess, "
        "then reduce repeated heavy days and uneven concentration, while still "
        "preserving deadline safety and task continuity."
    ),
    completion_policy=(
        "Once an item starts, keep progressing it and complete it promptly. "
        "Calendar smoothing must not scatter one task across its entire legal "
        "window simply because later dates are available."
    ),
    deadline_policy=(
        "Preserve sensible deadline buffer, but do not front-load work merely "
        "to maximise unused slack when that produces an unnecessarily heavy "
        "calendar."
    ),
    explicit_non_goals=(
        "Do not delay started work until near its deadline merely for symmetry.",
        "Do not maximise the number of active days for its own sake.",
        "Do not create artificial gaps between sessions of one item.",
        "Do not violate canonical or scheduling invariants for balance.",
    ),
)


def frozen_flavour_contracts() -> tuple[FlavourContract, ...]:
    return (
        LOCK_IN,
        MONK,
    )


def flavour_contract_artifact() -> dict:
    contracts = frozen_flavour_contracts()

    return {
        "schema_version": 1,
        "stage": "C11.1",
        "contract_version":
            FLAVOUR_CONTRACT_VERSION,
        "purpose":
            "freeze_production_flavour_semantics",
        "flavour_count":
            len(contracts),
        "flavours": [
            {
                **asdict(contract),
                "flavour":
                    contract.flavour.value,
            }
            for contract in contracts
        ],
        "common_requirements": {
            "canonical_invariants_unchanged":
                True,
            "shared_task_continuity":
                True,
            "automatic_router_required":
                False,
            "flavour_selected_explicitly":
                True,
            "c7_c8_c9_retuning_allowed":
                False,
            "c10_human_findings_used_as_design_evidence":
                True,
        },
        "objective_status":
            "not_yet_parameterized",
        "scheduler_trials_executed":
            0,
    }
