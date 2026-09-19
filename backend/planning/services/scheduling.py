"""Global, capacity-constrained execution dates and atomic Timeline operations."""
from collections import Counter
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from planning.models import DurationCategory, PlanningItem, SchedulingOverload, SchedulingPreference, SchedulingState
from planning.services import history, leaf_order_sync, priority

BUCKET_FIELDS = {
    DurationCategory.UNDER_20_MIN: 'under_20',
    DurationCategory.MIN_20_TO_60: 'minutes_20_to_60',
    DurationCategory.OVER_60_MIN: 'over_60',
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
    """All active actionable work that must own an execution date.

    Scheduling eligibility is deliberately broader than priority eligibility:
    TASK/ASSIGNMENT items remain schedulable even when they have children.
    Structural GOAL items are excluded by actionable().
    """
    return (
        PlanningItem.objects.for_user(user)
        .actionable()
        .filter(is_completed=False, is_deleted=False)
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
    priority._lock(user)
    priority.reconcile(user)
    limits = capacities(user)
    overloaded = set(SchedulingOverload.objects.filter(user=user, allowed=True).values_list('date', flat=True))
    items = sorted(_scheduler_eligible(user), key=_scheduling_order)
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
        if item.schedule_is_manual and item.scheduled_date:
            day = item.scheduled_date
            code = _validate_date(item, day, today)
            if code:
                conflicts.append(_conflict(item, code))
            if usage[(day, bucket)] >= limits[bucket] and day not in overloaded:
                conflicts.append(_conflict(item, 'capacity_exceeded'))
            usage[(day, bucket)] += 1
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
    return {'changed_ids': [item.pk for item in changed], 'conflicts': conflicts}


@transaction.atomic
def daily_schedule(user, today=None):
    """Run global maintenance once per local day, without user undo history."""
    today = today or timezone.localdate()
    priority._lock(user)
    state, _ = SchedulingState.objects.get_or_create(user=user)
    mode = 'global' if state.last_global_date != today else 'minimal'
    result = schedule(user, today, mode=mode)
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
    item.scheduled_date, item.schedule_is_manual = day, True
    item.save(update_fields=['scheduled_date', 'schedule_is_manual'])
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
