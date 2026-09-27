"""Deterministic Earliest Feasible scheduling baseline.

This baseline deliberately performs no schedule-quality optimisation.

Policy:
1. respect dependency topological order;
2. respect today/release/anchor constraints;
3. place work at the earliest capacity-feasible dates;
4. preserve ARC's baseline split counts;
5. respect deadlines when feasible;
6. if no capacity exists before a deadline, use the least-loaded legal
   pre-deadline dates and report the resulting overload;
7. never mutate canonical ARC state.

The purpose of this algorithm is to establish a simple experimental floor.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from arena.scheduling.domain import (
    Allocation,
    SchedulePlan,
    ScheduleProblem,
)
from arena.scheduling.mechanics import (
    ATOMIC, SPLIT_COUNTS, effective_bucket,
)


class EarliestFeasible:
    name = "earliest-feasible"

    def solve(
        self,
        problem: ScheduleProblem,
    ) -> SchedulePlan:
        item_by_id = problem.item_by_id

        # Session capacity usage by (date, duration bucket).
        usage: Counter[tuple[date, str]] = Counter()

        # Final completion day of each already-planned prerequisite.
        completion: dict[int, date] = {}

        allocations: list[Allocation] = []
        conflicts: list[str] = []

        # execution_rank is disposable advice local to a day.
        rank_by_day: Counter[date] = Counter()

        for item_id in problem.topological_order():
            item = item_by_id[item_id]

            bucket = effective_bucket(item)

            lower = max(
                problem.today,
                item.release_date or problem.today,
            )

            prerequisite_ids = problem.direct_prerequisites(
                item_id
            )

            if prerequisite_ids:
                # Day-resolution semantics:
                # dependent begins strictly AFTER every prerequisite's
                # final scheduled day.
                lower = max(
                    lower,
                    max(
                        completion[prerequisite_id]
                        + timedelta(days=1)
                        for prerequisite_id
                        in prerequisite_ids
                    ),
                )

            pieces = self._pieces(item)

            if item.anchor_date is not None:
                days = self._anchored_days(
                    item.anchor_date,
                    len(pieces),
                )

                if days[0] < lower:
                    conflicts.append(
                        f"{item_id}:anchor_before_legal_start"
                    )
            else:
                days = self._earliest_days(
                    problem=problem,
                    bucket=bucket,
                    count=len(pieces),
                    lower=lower,
                    due=item.due_date,
                    usage=usage,
                    item_id=item_id,
                    conflicts=conflicts,
                )

            item_allocations: list[Allocation] = []

            for day, percentage in zip(
                days,
                pieces,
                strict=True,
            ):
                usage[(day, bucket)] += 1
                rank_by_day[day] += 1

                allocation = Allocation(
                    item_id=item_id,
                    scheduled_date=day,
                    percentage=percentage,
                    execution_rank=rank_by_day[day],
                )

                allocations.append(allocation)
                item_allocations.append(allocation)

            completion[item_id] = max(
                allocation.scheduled_date
                for allocation in item_allocations
            )

        return SchedulePlan(
            allocations=tuple(allocations),
            conflicts=tuple(conflicts),
            diagnostics=(
                ("policy", "earliest-feasible"),
            ),
        )

    @staticmethod
    def _pieces(item) -> tuple[Decimal, ...]:
        """Historical decomposition, including its tiny-work rounding behavior.

        Kept private so conservation-safe C2 repairs cannot change this baseline.
        """
        remaining = item.remaining_fraction * Decimal('100')
        if remaining <= 0:
            return ()
        bucket = effective_bucket(item)
        if bucket in ATOMIC:
            return (remaining,)
        try:
            count = SPLIT_COUNTS[bucket]
        except KeyError as exc:
            raise ValueError(f'Unknown duration category: {bucket}') from exc
        base = (remaining / Decimal(count)).quantize(Decimal('0.01'))
        pieces = [base] * count
        pieces[-1] += remaining - sum(pieces, Decimal('0'))
        return tuple(piece for piece in pieces if piece > 0)

    @staticmethod
    def _anchored_days(
        anchor: date,
        count: int,
    ) -> tuple[date, ...]:
        # ARC's current split proposal semantics start on scheduled_date and
        # continue on consecutive days.
        return tuple(
            anchor + timedelta(days=index)
            for index in range(count)
        )

    def _earliest_days(
        self,
        *,
        problem: ScheduleProblem,
        bucket: str,
        count: int,
        lower: date,
        due: date | None,
        usage: Counter,
        item_id: int,
        conflicts: list[str],
    ) -> tuple[date, ...]:
        limit = problem.capacity_by_duration.get(bucket)

        if limit is None:
            raise ValueError(
                f"No capacity definition for {bucket}"
            )

        if limit <= 0:
            conflicts.append(
                f"{item_id}:capacity_disabled"
            )

            return tuple(
                lower + timedelta(days=index)
                for index in range(count)
            )

        chosen: list[date] = []
        cursor = lower

        for _ in range(count):
            day = self._earliest_session_day(
                problem=problem,
                bucket=bucket,
                lower=cursor,
                due=due,
                usage=usage,
                reserved=chosen,
                limit=limit,
                item_id=item_id,
                conflicts=conflicts,
            )

            chosen.append(day)
            cursor = day + timedelta(days=1)

        return tuple(chosen)

    @staticmethod
    def _earliest_session_day(
        *,
        problem: ScheduleProblem,
        bucket: str,
        lower: date,
        due: date | None,
        usage: Counter,
        reserved: list[date],
        limit: int,
        item_id: int,
        conflicts: list[str],
    ) -> date:
        reserved_usage = Counter(
            (day, bucket)
            for day in reserved
        )

        def load(day: date) -> int:
            return (
                usage[(day, bucket)]
                + reserved_usage[(day, bucket)]
            )

        day = lower

        # No deadline: simply walk forward until capacity exists.
        if due is None:
            while (
                load(day) >= limit
                and day not in problem.overload_dates
            ):
                day += timedelta(days=1)

            return day

        # Deadline already impossible from precedence/release constraints.
        if lower > due:
            conflicts.append(
                f"{item_id}:after_deadline"
            )

            while (
                load(day) >= limit
                and day not in problem.overload_dates
            ):
                day += timedelta(days=1)

            return day

        # Earliest normal capacity before deadline.
        while day <= due:
            if (
                load(day) < limit
                or day in problem.overload_dates
            ):
                return day

            day += timedelta(days=1)

        # No capacity before deadline. Preserve the deadline if possible,
        # accepting soft overload exactly as ARC's production semantics do.
        candidates = [
            lower + timedelta(days=index)
            for index in range(
                (due - lower).days + 1
            )
        ]

        chosen = min(
            candidates,
            key=lambda candidate: (
                load(candidate),
                candidate,
            ),
        )

        conflicts.append(
            f"{item_id}:no_capacity_before_deadline"
        )

        return chosen


earliest_feasible = EarliestFeasible()
