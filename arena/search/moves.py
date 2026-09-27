"""Pure date transformations; no repair or acceptance policy."""
from dataclasses import dataclass
from datetime import date, timedelta

from .state import SearchState, SessionPlacement


@dataclass(frozen=True, slots=True)
class RelocateSession:
    item_id: int
    session_index: int
    to_date: date


@dataclass(frozen=True, slots=True)
class SwapSessions:
    first_item_id: int
    first_session_index: int
    second_item_id: int
    second_session_index: int


@dataclass(frozen=True, slots=True)
class ShiftItem:
    item_id: int
    delta_days: int


Move = RelocateSession | SwapSessions | ShiftItem


def apply_move(state: SearchState, move: Move) -> SearchState | None:
    """Return a new hard-legal state, or None for illegal/unknown/no-op moves."""
    dates = {(p.item_id, p.session_index): p.scheduled_date for p in state.placements}
    try:
        if isinstance(move, RelocateSession):
            key = (move.item_id, move.session_index)
            if key not in dates or type(move.to_date) is not date:
                return None
            dates[key] = move.to_date
        elif isinstance(move, SwapSessions):
            a = (move.first_item_id, move.first_session_index)
            b = (move.second_item_id, move.second_session_index)
            dates[a], dates[b] = dates[b], dates[a]
        elif isinstance(move, ShiftItem):
            keys = [k for k in dates if k[0] == move.item_id]
            if not keys or type(move.delta_days) is not int:
                return None
            for k in keys:
                dates[k] += timedelta(days=move.delta_days)
        else:
            return None
        neighbour = SearchState(state.problem, tuple(SessionPlacement(*k, d) for k, d in dates.items()))
        return None if neighbour == state else neighbour
    except (KeyError, ValueError, OverflowError):
        return None
