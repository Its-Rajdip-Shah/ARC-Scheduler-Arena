"""Synchronize actionable leaf order without ranking or moving containers."""

from collections import defaultdict

from django.db.models import Exists, OuterRef

from planning.models import PlanningItem
from planning.services import priority


def leaves(user):
    # An actionable parent with completed children still owns a container slot.
    children = PlanningItem.objects.filter(
        user=user, parent_id=OuterRef('pk'), is_deleted=False,
    )
    return (PlanningItem.objects.for_user(user).priority_eligible()
            .filter(~Exists(children)).exclude(priority_position=None))


def from_priority(user):
    """Permute only leaf slots, preserving every container and parent link."""
    groups = defaultdict(list)
    for item in leaves(user).order_by('sibling_order', 'pk'):
        groups[item.parent_id].append(item)
    changed = []
    for siblings in groups.values():
        slots = [item.sibling_order for item in siblings]
        for item, slot in zip(sorted(siblings, key=lambda item: item.priority_position), slots):
            if item.sibling_order != slot:
                item.sibling_order = slot
                changed.append(item)
    if changed:
        PlanningItem.objects.bulk_update(changed, ['sibling_order'])


def from_planner(item):
    """Interpret sibling subtrees as priority boundaries for a moved leaf."""
    if not leaves(item.user).filter(pk=item.pk).exists():
        return

    children = defaultdict(list)
    for node in PlanningItem.objects.for_user(item.user).order_by('sibling_order', 'pk'):
        children[node.parent_id].append(node.pk)
    eligible = set(PlanningItem.objects.for_user(item.user).priority_eligible()
                   .exclude(priority_position=None).values_list('pk', flat=True))

    def boundary(sibling_id):
        # A container represents descendants, not its own position. Traversal
        # through visible, user-scoped rows also excludes deleted subtrees.
        pending = list(children.get(sibling_id, [sibling_id]))
        result = set()
        while pending:
            node_id = pending.pop()
            if node_id in eligible:
                result.add(node_id)
            pending.extend(children.get(node_id, []))
        return result

    siblings = children[item.parent_id]
    index = siblings.index(item.pk)
    before = set().union(*(boundary(pk) for pk in siblings[:index]))
    after = set().union(*(boundary(pk) for pk in siblings[index + 1:]))
    ordered = list(priority.ordered(item.user))

    # If sibling subtrees already interleave globally, moving the leaf alone
    # cannot satisfy both boundaries. Move only conflicting predecessors ahead
    # of the first successor, retaining their existing relative order.
    successor = next((node for node in ordered if node.pk in after), None)
    if successor:
        conflicting = [node.pk for node in ordered
                       if node.pk in before and node.priority_position > successor.priority_position]
        for node_id in conflicting:
            target = next(node.priority_position for node in ordered if node.pk == successor.pk)
            ordered = priority.reorder(item.user, node_id, target)

    remaining = [node.pk for node in ordered if node.pk != item.pk]
    lower = max((i + 1 for i, pk in enumerate(remaining) if pk in before), default=0)
    upper = min((i for i, pk in enumerate(remaining) if pk in after), default=len(remaining))
    current = next(i for i, node in enumerate(ordered) if node.pk == item.pk)
    target = max(lower, min(current, upper))
    if target != current:
        priority.reorder(item.user, item.pk, target + 1)
