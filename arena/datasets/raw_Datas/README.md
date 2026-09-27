# ARC Scheduler Arena — Raw Dataset Bundle

Files:
- scenarios.csv — scenario metadata
- items.csv — hierarchy and scheduling-relevant planning items
- capacities.csv — obsolete legacy configuration, retained for provenance only; no active consumer. Never canonical state or feature-extractor input.
- manifest.json — counts and mapping notes

Important mappings to current ARC:
- `release_date` -> `PlanningItem.start_date`
- `anchored=True` -> raw `scheduled_date` becomes `PlanningItem.manual_requested_date` (never `schedule_is_manual`)
- `parent_key` -> `PlanningItem.parent`
- `scheduled_date` -> `PlanningItem.scheduled_date`

The bundle deliberately contains four benchmark families:
1. micro — correctness and edge cases
2. realistic — human-recognisable semester/project workloads
3. stress — pathological robustness/performance cases
4. random — deterministic seeded statistical coverage

Do not mutate these raw CSVs during algorithm runs. Materialise a fresh scenario into the Arena database for each run.

Frozen ARC has six duration categories. Existing fixture classes map explicitly:

| Legacy fixture class | Frozen DurationCategory |
| --- | --- |
| UNDER_20_MIN | UNDER_20_MINUTES |
| MIN_20_TO_60 | UNDER_1_HOUR |
| OVER_60_MIN | UNDER_4_HOURS |
| HOURS_1_TO_4 | UNDER_4_HOURS |
| HOURS_4_TO_12 | UNDER_16_HOURS |
| OVER_12_HOURS | OVER_16_HOURS |

This is legacy fixture compatibility, not canonical ARC semantics. Unknown raw
classes fail explicitly. The original scenario and item CSVs are unchanged.

Legacy priority compatibility during materialization:
- Legacy priorities are ordinal and may contain ties; frozen ARC canonical
  priority is a strict total ordering.
- Sort all non-null legacy priorities by ascending value, then original
  `items.csv` row order. Assign dense unique canonical positions `1..N`.
- Null priorities remain unprioritized. CSV data is never rewritten.
- This deterministically linearizes ties, preserving the maximum ordering
  information representable by frozen ARC; it does not claim original ties
  were distinct. This is fixture compatibility only, not ARC domain behavior.
- Import metadata `legacy_priority_linearized` is true exactly when ties were
  broken (dense reassignment alone is not a tie). `legacy_priority_tie_count`
  counts distinct duplicated legacy values, not items or excess occurrences.
  Both appear as report metadata, never in the 91-feature numeric vector.
