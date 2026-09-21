"""ARC Focus projection.

Focus is deliberately not a planning authority.

Reading Focus never invokes the scheduler and selecting a current item never
changes canonical planning facts. Explicit planning intents such as "do today"
or reprioritisation belong to the normal domain-command boundary.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.utils import timezone
from planning.models import PlanningItem
from planning.services import dependencies, priority, scheduling


# Current-focus selection is convenience/session state only.
#
# It intentionally does not live on PlanningItem. A future API/session layer
# may persist this per session/device without changing planning semantics.
_CURRENT_BY_USER: dict[int, int] = {}


@dataclass(frozen=True)
class FocusCandidate:
    item_id: int
    title: str
    duration_category: str | None
    scheduled_date: date | None
    priority_position: int | None
    execution_rank: int | None = None
    is_current: bool = False


def _ordered_candidates(user):
    """Read the already-produced schedule without triggering replanning."""

    rows = (
        PlanningItem.objects.for_user(user)
        .priority_eligible()
        .filter(
            is_completed=False,
            is_deleted=False,
            scheduled_date__isnull=False,
        )
    )

    current_id = _CURRENT_BY_USER.get(user.pk)

    return sorted(
        (
            FocusCandidate(
                item_id=item.pk,
                title=item.title,
                duration_category=item.duration_category,
                scheduled_date=item.scheduled_date,
                priority_position=item.priority_position,
                execution_rank=item.execution_rank,
                is_current=item.pk == current_id,
            )
            for item in rows if not dependencies.is_blocked(item)
        ),
        key=lambda candidate: (
            candidate.scheduled_date,
            candidate.execution_rank is None,
            candidate.execution_rank or candidate.priority_position or 0,
            candidate.item_id,
        ),
    )


def build(user, today=None):
    """Return Focus queues grouped by canonical duration category.

    `today` is a projection boundary only. Future scheduled candidates remain
    visible as look-ahead choices; merely viewing them does not move them.
    """

    reconcile_current(user)
    candidates = _ordered_candidates(user)
    grouped = defaultdict(list)

    for candidate in candidates:
        grouped[candidate.duration_category].append(candidate)

    return {
        "today": today,
        "groups": dict(grouped),
        "candidates": candidates,
        "current_item_id": _CURRENT_BY_USER.get(user.pk),
    }


get_focus = build
candidates = build
look_ahead = build


def set_current(user, item):
    """Select convenience-only current focus without planning mutation."""

    item_id = item.pk if isinstance(item, PlanningItem) else int(item)

    exists = (
        PlanningItem.objects.for_user(user)
        .actionable()
        .filter(
            pk=item_id,
            is_completed=False,
            is_deleted=False,
        )
        .exists()
    )

    if not exists:
        _CURRENT_BY_USER.pop(user.pk, None)
        return None

    _CURRENT_BY_USER[user.pk] = item_id
    return reconcile_current(user)


select = set_current
set_current_focus = set_current


def clear_current(user):
    _CURRENT_BY_USER.pop(user.pk, None)


clear_current_focus = clear_current


# ---------------------------------------------------------------------------
# Explicit Focus planning commands
# ---------------------------------------------------------------------------

def do_today(item, today=None):
    """Explicitly promote work to today.

    Unlike merely viewing/selecting Focus, this IS planning intent and crosses
    the canonical anchor boundary.
    """

    today = today or date.today()

    # Reuse the canonical anchor command so Focus cannot develop independent
    # date semantics.
    return scheduling.set_anchor(item, today)


promote_to_today = do_today
promote = do_today


def return_to_automatic(item):
    """Remove explicit Focus date intent and return placement to scheduler."""

    return scheduling.remove_anchor(item)


demote = return_to_automatic
clear_do_today = return_to_automatic


@transaction.atomic
def reprioritise(user, item, new_position):
    """Explicit Focus reprioritisation crosses global Priority authority."""

    item_id = item.pk if isinstance(item, PlanningItem) else int(item)

    result = priority.reorder(user, item_id, new_position)

    # Priority is canonical preference; scheduler consumes the resulting
    # canonical order but never owns it.
    scheduling.schedule(user)
    return result


reprioritize = reprioritise
move_priority = reprioritise


def reconcile_current(user):
    """Clear convenience focus when the selected item stops being executable.

    This function mutates ONLY convenience state. It must not repair priority,
    dates, dependencies or any other planning fact.
    """

    item_id = _CURRENT_BY_USER.get(user.pk)

    if item_id is None:
        return None

    item = (
        PlanningItem.objects
        .filter(pk=item_id, user=user)
        .first()
    )

    executable = (
        item is not None
        and not item.is_deleted
        and not item.is_completed
        and item.is_actionable
        and (item.start_date is None or item.start_date <= timezone.localdate())
        and not item.children.filter(
            is_deleted=False,
            is_completed=False,
        ).exists()
        and not dependencies.is_blocked(item)
    )

    if not executable:
        _CURRENT_BY_USER.pop(user.pk, None)
        return None

    return item_id


reconcile = reconcile_current
clear_if_ineligible = reconcile_current
