"""Domain rules over the planning hierarchy.

Each module owns one rule from the requirements and is deliberately free of
HTTP concerns, so it can be tested without a request:

- hierarchy: parent/child structure and cascade completion (FR-06, FR-08)
- priority:  the single global task order (FR-09)
- scheduling: global execution scheduling and roll-forward (FR-11)
- overdue:   Recent and Backlog classification (FR-12)
"""
