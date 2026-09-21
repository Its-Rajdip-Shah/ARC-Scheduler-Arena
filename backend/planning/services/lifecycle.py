"""Shared validation and reconciliation at canonical command boundaries."""
from django.core.exceptions import ValidationError
from planning.models import PlanningDependency, PlanningItem
from planning.services import priority


def active(item):
    priority._lock(item.user)
    row = PlanningItem.objects.select_for_update().get(pk=item.pk, user=item.user)
    if row.is_deleted:
        raise ValidationError('Deleted work must be restored before editing.')
    return row


def validate_graph(user):
    rows = {row.pk: row for row in PlanningItem.objects.for_user(user)}
    for row in rows.values():
        seen = {row.pk}
        parent = row.parent_id
        while parent is not None:
            if parent in seen or parent not in rows:
                raise ValidationError('Hierarchy is cyclic or references an inactive/foreign parent.')
            seen.add(parent)
            if rows[parent].is_completed and not row.is_completed:
                raise ValidationError('Completed ancestors cannot contain unfinished work.')
            parent = rows[parent].parent_id
    graph = {}
    for a, b in PlanningDependency.objects.filter(prerequisite__user=user).values_list('prerequisite_id', 'dependent_id'):
        if a not in rows or b not in rows:
            raise ValidationError('Dependency endpoints must be active and belong to one user.')
        if rows[b].is_completed and not rows[a].is_completed:
            raise ValidationError('Resolve the dependency before contradicting completion.')
        graph.setdefault(a, set()).add(b)
    # Kahn's algorithm avoids Python recursion limits on large valid graphs.
    incoming = {pk: 0 for pk in rows}
    for targets in graph.values():
        for pk in targets:
            incoming[pk] += 1
    ready = [pk for pk, count in incoming.items() if count == 0]
    seen = 0
    while ready:
        pk = ready.pop()
        seen += 1
        for target in graph.get(pk, ()):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    if seen != len(rows):
        raise ValidationError('Dependency graph contains a cycle.')


def reopen_ancestors(item):
    from planning.queries import ancestor_ids
    ids = ancestor_ids(item.user_id, item.pk)
    # Decomposition preserves historical parent progress; it does not invent
    # progress for children. The returned parent is residual closure work.
    PlanningItem.objects.filter(user=item.user, pk__in=ids).update(is_completed=False)


def finish(user, today=None):
    from planning.services import scheduling, focus
    validate_graph(user)
    priority.reconcile(user)
    result = scheduling.schedule(user, today)
    focus.reconcile_current(user)
    return result
