"""Global, capacity-constrained execution dates and atomic Timeline operations."""
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from planning.models import (
    DurationCategory,
    PlanningItem,
    ProgressSegment,
    SchedulerAllocation,
    SchedulingOverload,
    SchedulingState,
    SPLITTABLE_DURATION_CATEGORIES,
)
from planning.services import history, leaf_order_sync, priority

# Baseline scheduler policy, intentionally replaceable by future algorithm policy.
BASELINE_SCHEDULER_CAPACITY = {
    DurationCategory.UNDER_20_MINUTES: 5,
    DurationCategory.UNDER_1_HOUR: 4,
    DurationCategory.UNDER_4_HOURS: 3,
    DurationCategory.UNDER_8_HOURS: 3,
    DurationCategory.UNDER_16_HOURS: 3,
    DurationCategory.OVER_16_HOURS: 3,
}


class SchedulingConflict(Exception):
    def __init__(self, conflicts):
        self.conflicts = conflicts
        super().__init__('The requested schedule cannot satisfy the constraints.')


def capacities(user):
    return dict(BASELINE_SCHEDULER_CAPACITY)


def _conflict(item, code):
    return {'item_id': item.pk, 'code': code}


def _scheduler_eligible(user):
    """Active execution-frontier work that may own an execution date.

    A decomposed item is structural while it has unfinished visible children.
    Only unfinished actionable frontier items are scheduler candidates.
    """
    unfinished_children = PlanningItem.objects.visible().filter(
        user=user,
        parent_id=OuterRef("pk"),
        is_completed=False,
    )

    return (
        PlanningItem.objects.for_user(user)
        .actionable()
        .filter(is_completed=False, is_deleted=False)
        .annotate(
            has_unfinished_children=Exists(unfinished_children),
            is_residual=Exists(PlanningItem.objects.visible().filter(user=user, parent_id=OuterRef('pk'))),
        )
        .filter(has_unfinished_children=False)
        .exclude(
            blocked_by_dependencies__prerequisite__is_completed=False,
            blocked_by_dependencies__prerequisite__is_deleted=False,
        )
        .distinct()
    )


def _scheduling_order(item):
    """Deterministic order without inventing priority for unpositioned work."""
    positioned = item.priority_position is not None
    return (
        0 if positioned else 1,
        item.priority_position if positioned else 0,
        item.due_date or timezone.datetime.max.date(),
        item.start_date or timezone.datetime.max.date(),
        item.pk,
    )


def _validate_date(item, day, today):
    if day < today:
        return 'past_date'
    if item.start_date and day < item.start_date:
        return 'before_start'
    if item.due_date and day > item.due_date:
        return 'after_deadline'
    return None


@transaction.atomic
def schedule(user, today=None, *, mode='minimal'):
    """Generate proposals from canonical state, reconsidering dates in global mode.

    Capacity is soft when deadlines are infeasible. Release dates remain hard;
    overdue and user-fixed dates are retained, with conflicts reported.
    """
    if mode not in {'minimal', 'global'}:
        raise ValueError('Unknown scheduling mode')
    today = today or timezone.localdate()
    # Scheduling may read/lock canonical priority, but it has no authority
    # to repair or manufacture canonical priority as a side effect.
    priority._lock(user)
    limits = capacities(user)
    overloaded = set(SchedulingOverload.objects.filter(user=user, allowed=True).values_list('date', flat=True))
    items = sorted(_scheduler_eligible(user), key=_scheduling_order)

    # Eligibility reconciliation is required in every scheduling mode.
    # Hierarchy changes can make a previously scheduled item cease to be
    # execution-frontier work. Clear that stale execution state without
    # forcing unrelated valid automatic dates to move.
    eligible_ids = {item.pk for item in items}

    stale = list(
        PlanningItem.objects.for_user(user)
        .actionable()
        .filter(
            is_completed=False,
            is_deleted=False,
            scheduled_date__isnull=False,
        )
        .exclude(pk__in=eligible_ids)
    )

    if stale:
        for item in stale:
            item.scheduled_date = None
        PlanningItem.objects.bulk_update(
            stale,
            ['scheduled_date'],
        )

    usage = Counter()
    conflicts, changed, pending = [], [], []
    for blocked in PlanningItem.objects.for_user(user).filter(
        is_completed=False, manual_requested_date__gte=today,
        blocked_by_dependencies__prerequisite__is_completed=False,
        blocked_by_dependencies__prerequisite__is_deleted=False,
    ).distinct():
        conflicts.append(_conflict(blocked, 'blocked_dependency'))

    def assign(item, day):
        if item.scheduled_date != day:
            item.scheduled_date = day
            changed.append(item)

    for item in items:
        bucket = DurationCategory.UNDER_20_MINUTES if item.is_residual else item.duration_category
        if bucket not in limits:
            conflicts.append(_conflict(item, 'duration_required'))
            continue
        if item.due_date and item.due_date < today:
            conflicts.append(_conflict(item, 'overdue'))
        # Expired intent remains recovery history, never a hard placement.
        manual_day = item.manual_requested_date
        if manual_day and manual_day < today:
            manual_day = None

        if manual_day:
            day = manual_day
            code = _validate_date(item, day, today)
            if code:
                conflicts.append(_conflict(item, code))
            if usage[(day, bucket)] >= limits[bucket] and day not in overloaded:
                conflicts.append(_conflict(item, 'capacity_exceeded'))
            usage[(day, bucket)] += 1
            if item.start_date and day < item.start_date:
                assign(item, None)
                continue
            assign(item, day)
        else:
            pending.append(item)

    for item in pending:
        bucket = DurationCategory.UNDER_20_MINUTES if item.is_residual else item.duration_category
        lower = max(today, item.start_date or today)
        day = lower
        if mode == 'minimal' and item.scheduled_date and not _validate_date(item, item.scheduled_date, today):
            day = item.scheduled_date
        if limits[bucket] == 0:
            conflicts.append(_conflict(item, 'capacity_disabled'))
        else:
            while usage[(day, bucket)] >= limits[bucket] and (not item.due_date or day <= item.due_date):
                day += timedelta(days=1)
        if item.due_date and day > item.due_date:
            # An old suggestion is not a hard bound: try earlier legal space
            # before accepting overload. Choose least-used, then earliest day.
            if lower <= item.due_date:
                candidates = (lower + timedelta(days=i) for i in range((item.due_date - lower).days + 1))
                day = min(candidates, key=lambda candidate: (usage[(candidate, bucket)], candidate))
                if usage[(day, bucket)] >= limits[bucket]:
                    conflicts.append(_conflict(item, 'no_capacity_before_deadline'))
            else:
                day = lower
                conflicts.append(_conflict(item, 'after_deadline'))
        usage[(day, bucket)] += 1
        assign(item, day)
    if changed:
        PlanningItem.objects.bulk_update(changed, ['scheduled_date'])

    # Proposed allocations are disposable scheduler output. Rebuild only the
    # unconfirmed projections; confirmed segments remain canonical progress.
    _reconcile_progress_allocations(user, today)
    # Rank is disposable execution advice, independent of canonical priority.
    ranks = Counter()
    for item in sorted(items, key=lambda row: (row.scheduled_date or timezone.datetime.max.date(), _scheduling_order(row))):
        if item.scheduled_date is not None:
            ranks[item.scheduled_date] += 1
            item.execution_rank = ranks[item.scheduled_date]
        else:
            item.execution_rank = None
    PlanningItem.objects.filter(user=user).exclude(pk__in=eligible_ids).update(execution_rank=None)
    if items:
        PlanningItem.objects.bulk_update(items, ['execution_rank'])
    allocations = list(SchedulerAllocation.objects.filter(item__user=user).select_related('item'))
    ranks = Counter()
    for allocation in sorted(allocations, key=lambda row: (row.scheduled_date, _scheduling_order(row.item))):
        ranks[allocation.scheduled_date] += 1
        allocation.execution_rank = ranks[allocation.scheduled_date]
        if allocation.item.due_date and allocation.scheduled_date > allocation.item.due_date:
            conflict = _conflict(allocation.item, 'allocation_after_deadline')
            if conflict not in conflicts:
                conflicts.append(conflict)
    if allocations:
        SchedulerAllocation.objects.bulk_update(allocations, ['execution_rank'])


    return {'changed_ids': [item.pk for item in changed], 'conflicts': conflicts}


def _expire_past_manual_anchors(user, today):
    """Expire past canonical anchors without manufacturing deadline overdue.

    The hard date commitment disappears once missed. The factual due date is
    untouched. The history layer remains available as the durable record of
    explicit planning actions.
    """
    expired = list(
        PlanningItem.objects.for_user(user)
        .filter(
            is_completed=False,
            is_deleted=False,
            manual_requested_date__lt=today,
        )
    )

    if not expired:
        return []

    for item in expired:
        item.expired_manual_requested_date = item.manual_requested_date
        item.manual_requested_date = None

    PlanningItem.objects.bulk_update(
        expired,
        ['manual_requested_date', 'expired_manual_requested_date'],
    )
    return [item.pk for item in expired]


@transaction.atomic
def daily_schedule(user, today=None):
    """Run global maintenance once per local day, without user undo history."""
    today = today or timezone.localdate()
    priority._lock(user)
    state, _ = SchedulingState.objects.get_or_create(user=user)
    mode = 'global' if state.last_global_date != today else 'minimal'
    expired_anchor_ids = _expire_past_manual_anchors(user, today)
    result = schedule(user, today, mode=mode)
    result['expired_anchor_ids'] = expired_anchor_ids
    if mode == 'global':
        state.last_global_date = today
        state.save(update_fields=['last_global_date'])
    return result


@transaction.atomic
def reschedule(user, today=None):
    """Explicit global optimisation is undoable, including legacy repairs."""
    priority._lock(user)
    before = _snapshot(user)
    result = schedule(user, today, mode='global')
    history.record_checkpoint(user, 'SCHEDULE', before, _snapshot(user))
    return result


def roll_forward_adaptive(user, today):
    """Compatibility entry point; all eligible work now uses the global engine."""
    result = schedule(user, today)
    return list(PlanningItem.objects.filter(user=user, pk__in=result['changed_ids']))


def _snapshot(user):
    return {
        'priority': history.capture_priority(user, include_unpositioned=True),
        'leaf_siblings': history.capture_leaf_order(user),
        'schedule': [
            {'id': item.pk, 'scheduled_date': item.scheduled_date.isoformat() if item.scheduled_date else None,
             'manual_requested_date': item.manual_requested_date.isoformat() if item.manual_requested_date else None, 'priority_restore_context': item.priority_restore_context}
            for item in PlanningItem.objects.filter(user=user).order_by('pk')
        ],
        'overload': [{'date': row.date.isoformat(), 'allowed': row.allowed}
                     for row in SchedulingOverload.objects.filter(user=user).order_by('date')],
    }


def _item(user, item_id):
    item = _scheduler_eligible(user).filter(pk=item_id).first()
    if item is None:
        raise SchedulingConflict([{'item_id': item_id, 'code': 'not_eligible'}])
    return item


def _finish(user, before, today, baseline):
    result = schedule(user, today)
    new_conflicts = [c for c in result['conflicts'] if (c['item_id'], c['code']) not in baseline]
    if new_conflicts:
        raise SchedulingConflict(new_conflicts)
    after = _snapshot(user)
    previous = {row['id']: row for row in before['schedule']}
    result['changed_ids'] = [row['id'] for row in after['schedule'] if previous.get(row['id']) != row]
    history.record_checkpoint(user, 'SCHEDULE', before, after)
    return result


def _begin(user, today):
    priority._lock(user)
    before = _snapshot(user)
    baseline = {(c['item_id'], c['code']) for c in schedule(user, today)['conflicts']}
    return before, baseline


@transaction.atomic
def move_to_date(user, item_id, day, *, allow_overload=False, today=None):
    today = today or timezone.localdate()
    before, baseline = _begin(user, today)
    item = _item(user, item_id)
    code = _validate_date(item, day, today)
    if code:
        raise SchedulingConflict([_conflict(item, code)])
    if not item.duration_category:
        raise SchedulingConflict([_conflict(item, 'duration_required')])
    if allow_overload:
        SchedulingOverload.objects.update_or_create(user=user, date=day, defaults={'allowed': True})
    # Explicit Timeline movement is canonical date intent, not merely a
    # disposable scheduler suggestion. The scheduler may reproduce
    # scheduled_date from this anchor, but cannot silently erase the intent.
    item.manual_requested_date = day
    item.scheduled_date = day
    item.save(
        update_fields=[
            'manual_requested_date',
            'scheduled_date',
        ]
    )
    # Existing conflicts on the manipulated item must not be swallowed.
    baseline = {pair for pair in baseline if pair[0] != item.pk}
    return _finish(user, before, today, baseline)


@transaction.atomic
def replace(user, replacement_id, displaced_id, *, allow_overload=False, today=None):
    today = today or timezone.localdate()
    before, baseline = _begin(user, today)
    replacement, displaced = _item(user, replacement_id), _item(user, displaced_id)
    day = displaced.scheduled_date
    if replacement.pk == displaced.pk or day is None:
        raise SchedulingConflict([_conflict(displaced, 'invalid_replacement')])
    code = _validate_date(replacement, day, today)
    if code:
        raise SchedulingConflict([_conflict(replacement, code)])
    if not replacement.duration_category:
        raise SchedulingConflict([_conflict(replacement, 'duration_required')])
    if allow_overload:
        SchedulingOverload.objects.update_or_create(user=user, date=day, defaults={'allowed': True})
    # Replacement is date intent, not a global importance reorder. A
    # scheduler candidate can legitimately have no current priority position.
    replacement.manual_requested_date = day
    replacement.scheduled_date = day
    replacement.save(update_fields=['manual_requested_date', 'scheduled_date'])
    displaced.manual_requested_date = day if allow_overload else None
    displaced.scheduled_date = day if allow_overload else day + timedelta(days=1)
    displaced.save(update_fields=['manual_requested_date', 'scheduled_date'])
    baseline = {pair for pair in baseline if pair[0] not in {replacement.pk, displaced.pk}}
    return _finish(user, before, today, baseline)


@transaction.atomic
def configure(user, *, day=None, overloaded=None, today=None):
    today = today or timezone.localdate()
    before, baseline = _begin(user, today)
    if day is not None:
        SchedulingOverload.objects.update_or_create(user=user, date=day, defaults={'allowed': overloaded})
    return _finish(user, before, today, baseline)


# ---------------------------------------------------------------------------
# Frozen ARC anchor/manual-intent commands
# ---------------------------------------------------------------------------

@transaction.atomic
def set_anchor(
    item: PlanningItem,
    day,
    *,
    change_deadline=False,
    change_release=False,
    allow_overload=False,
):
    """Set canonical explicit date intent.

    Crossing release/deadline boundaries is never silently repaired. The
    caller must explicitly authorize the corresponding canonical date change.
    """
    from . import lifecycle
    item = lifecycle.active(item)

    if item.is_deleted or item.is_completed:
        raise ValidationError("Only active unfinished work can be anchored.")

    if item.due_date and day > item.due_date:
        if not change_deadline:
            raise ValidationError(
                {"anchor": "Anchor is after deadline; explicitly extend the deadline or cancel."}
            )
        item.due_date = day

    if item.start_date and day < item.start_date:
        if not change_release:
            raise ValidationError(
                {"anchor": "Anchor is before release; explicitly move the release or cancel."}
            )
        item.start_date = day

    item.manual_requested_date = day

    fields = ["manual_requested_date"]
    if change_deadline:
        fields.append("due_date")
    if change_release:
        fields.append("start_date")

    item.save(update_fields=fields)

    if allow_overload:
        SchedulingOverload.objects.update_or_create(
            user=item.user,
            date=day,
            defaults={"allowed": True},
        )

    result = schedule(item.user)
    conflicts = [c for c in result['conflicts'] if c['item_id'] == item.pk and c['code'] == 'capacity_exceeded']
    if conflicts and not allow_overload:
        raise ValidationError('Anchor overload requires explicit confirmation.')
    item.refresh_from_db()
    return item


anchor = set_anchor
set_manual_requested_date = set_anchor
request_date = set_anchor


@transaction.atomic
def remove_anchor(item: PlanningItem):
    """Explicitly return placement authority to automatic scheduling."""
    from . import lifecycle
    item = lifecycle.active(item)
    item.manual_requested_date = None
    item.expired_manual_requested_date = None
    item.save(update_fields=["manual_requested_date", "expired_manual_requested_date"])
    schedule(item.user)
    item.refresh_from_db()
    return item


unanchor = remove_anchor
clear_anchor = remove_anchor
clear_manual_requested_date = remove_anchor


def validate_anchor(item: PlanningItem, day):
    """Return canonical conflicts without mutating state."""
    conflicts = []
    if item.start_date and day < item.start_date:
        conflicts.append("before_release")
    if item.due_date and day > item.due_date:
        conflicts.append("after_deadline")
    return conflicts


@transaction.atomic
def reconcile_anchors(user, today=None):
    """Time reconciliation for expired explicit date intent."""
    today = today or timezone.localdate()
    expired = _expire_past_manual_anchors(user, today)
    result = schedule(user, today)
    result["expired_anchor_ids"] = expired
    return result


# ---------------------------------------------------------------------------
# Frozen ARC splittable-work allocation bridge
# ---------------------------------------------------------------------------

_SPLITTABLE_VALUES = {
    value.value if hasattr(value, "value") else str(value)
    for value in SPLITTABLE_DURATION_CATEGORIES
}


def _allocation_count(category):
    """Session count is scheduler policy, not canonical task identity.

    This baseline merely guarantees genuine splitting for splittable classes;
    later arena algorithms are free to replace these proposal sizes.
    """
    if category == DurationCategory.OVER_16_HOURS:
        return 3
    return 2


def _reconcile_progress_allocations(user, today=None):
    """Rebuild disposable allocations from current canonical remaining work."""

    today = today or timezone.localdate()
    candidates = list(_scheduler_eligible(user))

    # Scheduler proposals are disposable by definition. A rerun may replace
    # every proposal without touching confirmed canonical progress history.
    SchedulerAllocation.objects.filter(item__user=user).delete()

    allocations = []

    for item in candidates:
        if item.is_residual or item.scheduled_date is None or item.duration_category not in _SPLITTABLE_VALUES:
            continue

        remaining = Decimal("100") - Decimal(str(item.percent_completed))
        if remaining <= 0:
            continue

        count = _allocation_count(item.duration_category)
        base = (remaining / count).quantize(Decimal("0.01"))
        pieces = [base] * count
        pieces[-1] += remaining - sum(pieces)

        first_day = (
            item.scheduled_date
            or max(today, item.start_date or today)
        )

        for index, percentage in enumerate(pieces):
            if percentage <= 0:
                continue

            allocations.append(
                SchedulerAllocation(
                    item=item,
                    percentage=percentage,
                    scheduled_date=first_day + timedelta(days=index),
                    execution_rank=index + 1,
                )
            )

    if allocations:
        SchedulerAllocation.objects.bulk_create(allocations)




# Re-export progress lifecycle commands through scheduling because scheduling
# is the primary domain façade consumed by Timeline/Focus and contract tests.
from planning.services.progress import (  # noqa: E402
    complete_segment,
    reopen_segment,
    reconcile_progress,
)

complete_allocation = complete_segment
confirm_progress = complete_segment
record_completed_allocation = complete_segment
uncomplete_segment = reopen_segment
reverse_progress_segment = reopen_segment
