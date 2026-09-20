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
    SchedulingPreference,
    SchedulingState,
    SPLITTABLE_DURATION_CATEGORIES,
)
from planning.services import history, leaf_order_sync, priority

BUCKET_FIELDS = {
    # Existing preference storage is temporarily mapped onto the frozen
    # six-category duration model. Capacity policy itself is scheduler-owned
    # and will be refined in the scheduler/allocation cluster.
    DurationCategory.UNDER_20_MINUTES: 'under_20',
    DurationCategory.UNDER_1_HOUR: 'minutes_20_to_60',
    DurationCategory.UNDER_4_HOURS: 'over_60',
    DurationCategory.UNDER_8_HOURS: 'over_60',
    DurationCategory.UNDER_16_HOURS: 'over_60',
    DurationCategory.OVER_16_HOURS: 'over_60',
}


class SchedulingConflict(Exception):
    def __init__(self, conflicts):
        self.conflicts = conflicts
        super().__init__('The requested schedule cannot satisfy the constraints.')


def capacities(user):
    settings = SchedulingPreference.objects.filter(user=user).first() or SchedulingPreference()
    return {bucket: getattr(settings, field) for bucket, field in BUCKET_FIELDS.items()}


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
        .annotate(has_unfinished_children=Exists(unfinished_children))
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
    """Repair invariants, or globally reconsider automatic dates when requested.

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
            item.schedule_is_manual = False
        PlanningItem.objects.bulk_update(
            stale,
            ['scheduled_date', 'schedule_is_manual'],
        )

    usage = Counter()
    conflicts, changed, pending = [], [], []

    def assign(item, day):
        if item.scheduled_date != day:
            item.scheduled_date = day
            changed.append(item)

    for item in items:
        bucket = item.duration_category
        if bucket not in limits:
            conflicts.append(_conflict(item, 'duration_required'))
            continue
        if item.due_date and item.due_date < today:
            conflicts.append(_conflict(item, 'overdue'))
            # Legacy NULLs use the last legal execution day. Contradictory
            # release/deadline constraints are reported, never silently edited.
            if item.scheduled_date is None:
                assign(item, item.due_date)
            if item.start_date and item.start_date > item.due_date:
                conflicts.append(_conflict(item, 'before_start'))
            continue
        # Canonical anchor/manual date intent has authority over disposable
        # scheduler proposals. Legacy schedule_is_manual remains supported
        # while old API paths are migrated.
        anchored_day = item.manual_requested_date
        legacy_manual_day = (
            item.scheduled_date
            if item.schedule_is_manual and item.scheduled_date
            else None
        )
        manual_day = anchored_day or legacy_manual_day

        if manual_day:
            day = manual_day
            code = _validate_date(item, day, today)
            if code:
                conflicts.append(_conflict(item, code))
            if usage[(day, bucket)] >= limits[bucket] and day not in overloaded:
                conflicts.append(_conflict(item, 'capacity_exceeded'))
            usage[(day, bucket)] += 1
            assign(item, day)
        else:
            pending.append(item)

    for item in pending:
        bucket = item.duration_category
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

    # Canonical 100% progress and completion must never diverge.
    reconcile_progress(user)

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
        item.manual_requested_date = None
        item.schedule_is_manual = False

    PlanningItem.objects.bulk_update(
        expired,
        ['manual_requested_date', 'schedule_is_manual'],
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
             'schedule_is_manual': item.schedule_is_manual, 'priority_restore_context': item.priority_restore_context}
            for item in PlanningItem.objects.filter(user=user).order_by('pk')
        ],
        'overload': [{'date': row.date.isoformat(), 'allowed': row.allowed}
                     for row in SchedulingOverload.objects.filter(user=user).order_by('date')],
        'capacity': list(SchedulingPreference.objects.filter(user=user).values(*BUCKET_FIELDS.values())),
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
    item.schedule_is_manual = True
    item.save(
        update_fields=[
            'manual_requested_date',
            'scheduled_date',
            'schedule_is_manual',
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
    ids = [row.pk for row in priority.ordered(user) if row.pk != replacement.pk]
    priority.reorder(user, replacement.pk, ids.index(displaced.pk) + 1)
    remaining = [row for row in priority.ordered(user) if row.pk != displaced.pk]
    last = max(i for i, row in enumerate(remaining)
               if row.pk == replacement.pk or row.scheduled_date == day)
    priority.reorder(user, displaced.pk, last + 2)
    replacement.scheduled_date, replacement.schedule_is_manual = day, True
    replacement.save(update_fields=['scheduled_date', 'schedule_is_manual'])
    displaced.schedule_is_manual = SchedulingOverload.objects.filter(user=user, date=day, allowed=True).exists()
    displaced.save(update_fields=['schedule_is_manual'])
    if displaced.schedule_is_manual:
        # The explicit replacement keeps the day's existing normal work; these
        # reservations may exceed capacity, but subsequent automatic work cannot.
        day_ids = [row.pk for row in priority.ordered(user) if row.scheduled_date == day]
        PlanningItem.objects.filter(user=user, pk__in=day_ids).update(schedule_is_manual=True)
    leaf_order_sync.from_priority(user)
    baseline = {pair for pair in baseline if pair[0] not in {replacement.pk, displaced.pk}}
    return _finish(user, before, today, baseline)


@transaction.atomic
def configure(user, *, capacity=None, day=None, overloaded=None, today=None):
    today = today or timezone.localdate()
    before, baseline = _begin(user, today)
    if capacity is not None:
        SchedulingPreference.objects.update_or_create(user=user, defaults=capacity)
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
    item = PlanningItem.objects.select_for_update().get(pk=item.pk)

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

    schedule(item.user)
    item.refresh_from_db()
    return item


anchor = set_anchor
set_manual_requested_date = set_anchor
request_date = set_anchor


@transaction.atomic
def remove_anchor(item: PlanningItem):
    """Explicitly return placement authority to automatic scheduling."""
    item = PlanningItem.objects.select_for_update().get(pk=item.pk)
    item.manual_requested_date = None
    item.schedule_is_manual = False
    item.save(update_fields=["manual_requested_date", "schedule_is_manual"])
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
        if item.duration_category not in _SPLITTABLE_VALUES:
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
