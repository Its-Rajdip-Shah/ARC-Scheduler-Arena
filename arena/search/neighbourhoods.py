"""Finite deterministic hard-legal neighbourhoods, independent of objectives."""
from dataclasses import dataclass
from datetime import date
from itertools import combinations, chain

from .moves import Move, RelocateSession, SwapSessions, ShiftItem, apply_move
from .state import SearchState


@dataclass(frozen=True, slots=True)
class NeighbourhoodConfig:
    horizon_days: int
    max_relocation_distance_days: int | None = None

    def __post_init__(self) -> None:
        for value in (self.horizon_days, self.max_relocation_distance_days):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('Bounds must be nonnegative integers')
        if self.horizon_days is None:
            raise ValueError('An explicit horizon is required')

    def _upper(self, state: SearchState) -> int:
        upper = state.problem.today.toordinal() + self.horizon_days
        if upper > date.max.toordinal():
            raise ValueError('Configured horizon exceeds calendar')
        return upper


def _unique(state, moves):
    seen = {state.placements}
    result = []
    for move in moves:
        neighbour = apply_move(state, move)
        if neighbour is not None and neighbour.placements not in seen:
            seen.add(neighbour.placements)
            result.append(move)
    return tuple(result)


def relocate_session_moves(state: SearchState, config: NeighbourhoodConfig) -> tuple[RelocateSession, ...]:
    upper = config._upper(state)
    def candidates():
        for p in state.placements:
            lo, hi = state.problem.today.toordinal(), upper
            distance = config.max_relocation_distance_days
            if distance is not None:
                lo = max(lo, p.scheduled_date.toordinal() - distance)
                hi = min(hi, p.scheduled_date.toordinal() + distance)
            for ordinal in range(lo, hi + 1):
                yield RelocateSession(p.item_id, p.session_index, date.fromordinal(ordinal))
    return _unique(state, candidates())


def swap_session_moves(state: SearchState, config: NeighbourhoodConfig) -> tuple[SwapSessions, ...]:
    upper = config._upper(state)
    return _unique(state, (SwapSessions(a.item_id, a.session_index, b.item_id, b.session_index)
                          for a, b in combinations(state.placements, 2)
                          if max(a.scheduled_date, b.scheduled_date).toordinal() <= upper))


def shift_item_moves(state: SearchState, config: NeighbourhoodConfig) -> tuple[ShiftItem, ...]:
    upper = config._upper(state)
    def candidates():
        for item_id, rows in state.placements_by_item.items():
            lo = state.problem.today.toordinal() - rows[0].scheduled_date.toordinal()
            hi = upper - rows[-1].scheduled_date.toordinal()
            for delta in range(lo, hi + 1):
                if delta:
                    yield ShiftItem(item_id, delta)
    return _unique(state, candidates())


def all_moves(state: SearchState, config: NeighbourhoodConfig) -> tuple[Move, ...]:
    """Relocate, swap, shift order; first move reaching each state wins."""
    return _unique(state, chain(relocate_session_moves(state, config),
                                swap_session_moves(state, config),
                                shift_item_moves(state, config)))
