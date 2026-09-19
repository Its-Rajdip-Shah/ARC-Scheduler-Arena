"""Recent and Backlog classification for missed deadlines (FR-12).

Only fixed-date work can be overdue. Work without a due_date
rolls forward under FR-11 and can never appear here; that is the distinction
the Overdue View exists to make.
"""

from planning.models import RECENT_OVERDUE_DAYS, PlanningItem
from planning.queries import ancestor_chain, parent_map


def _overdue_items(user, today):
    return (
        PlanningItem.objects.for_user(user)
        .overdue(today)
        .select_related('assignment_detail')
        .order_by('due_date', 'id')
    )


def classify(user, today):
    """Split the user's overdue work into Recent and Backlog.

    Each entry carries the hierarchy path the wireframe shows, so the user can
    tell which course and assignment the stray task belongs to.
    """
    items = list(_overdue_items(user, today))
    if not items:
        return {'recent': [], 'backlog': []}

    parents = parent_map(user.pk)
    titles = dict(PlanningItem.objects.visible().filter(user=user).values_list('id', 'title'))

    result = {'recent': [], 'backlog': []}
    for item in items:
        days = (today - item.due_date).days
        path = [titles[i] for i in reversed(ancestor_chain(parents, item.pk))]
        entry = {
            'item': item,
            'days_overdue': days,
            'hierarchy_path': path + [item.title],
        }
        bucket = 'recent' if days <= RECENT_OVERDUE_DAYS else 'backlog'
        result[bucket].append(entry)

    return result


def is_overdue(item, today):
    """Whether one item counts as overdue, without touching the database."""
    return bool(
        item.is_actionable
        and not item.is_completed
        and item.due_date
        and item.due_date < today
    )
