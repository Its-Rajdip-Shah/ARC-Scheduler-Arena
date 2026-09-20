# ARC Scheduler Arena — Raw Dataset Bundle

Files:
- scenarios.csv — scenario metadata
- items.csv — hierarchy and scheduling-relevant planning items
- capacities.csv — per-scenario capacity configuration
- manifest.json — counts and mapping notes

Important mappings to current ARC:
- `release_date` -> `PlanningItem.start_date`
- `anchored` -> `PlanningItem.schedule_is_manual`
- `parent_key` -> `PlanningItem.parent`
- `scheduled_date` -> `PlanningItem.scheduled_date`

The bundle deliberately contains four benchmark families:
1. micro — correctness and edge cases
2. realistic — human-recognisable semester/project workloads
3. stress — pathological robustness/performance cases
4. random — deterministic seeded statistical coverage

Do not mutate these raw CSVs during algorithm runs. Materialise a fresh scenario into the Arena database for each run.
