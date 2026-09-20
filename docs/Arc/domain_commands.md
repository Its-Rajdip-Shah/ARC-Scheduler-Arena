# ARC Domain Commands

Every meaningful state-changing UI action maps to a command of this kind. Names are architectural, not mandatory API names.

## Task lifecycle
- `create_task`
- `edit_task`
- `delete_task`
- `restore_task`
- `undo_last_operation` / validated inverse operation

## Hierarchy
- `add_child`
- `remove_child` (or delete/reparent child)
- `reparent_task`
- `decompose_task`

## Completion/progress
- `complete_atomic_task`
- `reopen_atomic_task`
- `complete_progress_segment`
- `reopen_progress_segment`
- `complete_residual_parent`
- `reopen_completed_parent_or_child`

## Priority
- `set_priority`
- `move_priority_before`
- `move_priority_after`

## Dependencies
- `add_dependency(prerequisite, dependent)`
- `remove_dependency`

## Temporal constraints
- `set_release_date`
- `clear_release_date`
- `set_deadline`
- `clear_deadline`

## Duration
- `set_duration_category`

## Manual scheduling intent
- `set_anchor(date)`
- `move_anchor(date)`
- `remove_anchor`
- `promote_to_today`
- `return_to_automatic_scheduling`

## Execution convenience
- `set_current_focus`
- `clear_current_focus`

These do not normally trigger canonical planning mutation beyond convenience state.

## Scheduler/reconciliation operations
- `reconcile_domain_state(now)`
- `generate_schedule`
- `change_scheduler_flavour`

`generate_schedule` cannot mutate canonical user facts.

## Command processing pipeline

1. Interpret user intent.
2. Build prospective canonical mutation.
3. Validate hard invariants.
4. Detect warnings/conflicts/infeasibility introduced by explicit choice.
5. If confirmation is required, do not commit until user chooses.
6. Commit atomically.
7. Reconcile derived state.
8. Reschedule if planning-relevant.
9. Reproject every affected view.

## Actions that are NOT domain commands

- opening Focus queue;
- collapsing Planner hierarchy;
- viewing tomorrow;
- executing rank #3 before rank #1 without explicitly changing the plan;
- dragging visually until the user drops/commits an interpreted planning action;
- scheduler recomputation itself.
