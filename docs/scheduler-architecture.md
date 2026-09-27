# ARC Scheduler Architecture

> Status: productionisation scaffold.

## Core separation

ARC Scheduler is built around three independent concerns:

1. Canonical ARC state
2. Scheduler engine
3. Scheduler output

## Dependency direction

ARC domain/database
→ input adapter
→ SchedulerInput contract
→ scheduler engine
→ SchedulerOutput contract
→ output adapter/persistence

The scheduler engine must contain no Django, database, HTTP, or frontend dependency.

## Evolution rule

Internal scheduler-engine changes should require no ARC changes when the input
and output contracts remain compatible.

Input/output contract changes must be explicit, versioned, tested, and reflected
in ARC adapters.
