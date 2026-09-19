"""Recursive traversals of the PlanningItem hierarchy.

Walking parent_id in Python costs one query per level. These helpers do it in
a single recursive CTE instead, and are shared by four features:

- FR-06 cycle detection, before re-parenting an item
- FR-08 cascade completion, down a subtree
- FR-10 grouping timeline items by their root
- FR-12 showing an overdue item's hierarchy path

Every query is scoped by user_id as well as item id, so a traversal can never
cross into another user's hierarchy (FR-03). MAX_DEPTH bounds the recursion so
that a cycle which somehow reached the database cannot hang a request.
"""

from django.db import connection

MAX_DEPTH = 100

_DESCENDANTS_SQL = """
WITH RECURSIVE subtree (planning_item_id, depth) AS (
    SELECT planning_item_id, 0
      FROM planning_items
     WHERE planning_item_id = %(item_id)s AND user_id = %(user_id)s
    UNION ALL
    SELECT child.planning_item_id, subtree.depth + 1
      FROM planning_items AS child
      JOIN subtree ON child.parent_id = subtree.planning_item_id
     WHERE subtree.depth < %(max_depth)s AND child.user_id = %(user_id)s
)
SELECT planning_item_id FROM subtree WHERE depth > 0
"""

_ANCESTORS_SQL = """
WITH RECURSIVE chain (planning_item_id, parent_id, depth) AS (
    SELECT planning_item_id, parent_id, 0
      FROM planning_items
     WHERE planning_item_id = %(item_id)s AND user_id = %(user_id)s
    UNION ALL
    SELECT ancestor.planning_item_id, ancestor.parent_id, chain.depth + 1
      FROM planning_items AS ancestor
      JOIN chain ON ancestor.planning_item_id = chain.parent_id
     WHERE chain.depth < %(max_depth)s AND ancestor.user_id = %(user_id)s
)
SELECT planning_item_id FROM chain WHERE depth > 0 ORDER BY depth
"""


_TREE_SQL = """
WITH RECURSIVE tree AS (
    SELECT planning_item_id, 0 AS depth,
           ARRAY[sibling_order, planning_item_id] AS path
      FROM planning_items
     WHERE user_id = %(user_id)s
       AND parent_id IS NULL
       AND is_deleted = FALSE
    UNION ALL
    SELECT child.planning_item_id, tree.depth + 1,
           tree.path || ARRAY[child.sibling_order, child.planning_item_id]
      FROM planning_items AS child
      JOIN tree ON child.parent_id = tree.planning_item_id
     WHERE child.user_id = %(user_id)s
       AND child.is_deleted = FALSE
       AND tree.depth < %(max_depth)s
)
SELECT planning_item_id, depth FROM tree ORDER BY path
"""


def tree_rows(user_id):
    """[(item_id, depth)] for the user's whole hierarchy, in display order.

    Ordering by the accumulated path is what puts each child directly beneath
    its parent, so the Text View can render the indentation straight from
    ``depth`` without sorting anything itself.
    """
    with connection.cursor() as cursor:
        cursor.execute(_TREE_SQL, {'user_id': user_id, 'max_depth': MAX_DEPTH})
        return cursor.fetchall()


def _run(sql, user_id, item_id):
    with connection.cursor() as cursor:
        cursor.execute(
            sql,
            {'item_id': item_id, 'user_id': user_id, 'max_depth': MAX_DEPTH},
        )
        return [row[0] for row in cursor.fetchall()]


def descendant_ids(user_id, item_id):
    """Every item below this one, excluding itself. Order is unspecified."""
    return _run(_DESCENDANTS_SQL, user_id, item_id)


def ancestor_ids(user_id, item_id):
    """Every item above this one, nearest parent first, excluding itself."""
    return _run(_ANCESTORS_SQL, user_id, item_id)


def root_id(user_id, item_id):
    """The top of this item's tree, or the item itself when it is a root."""
    ancestors = ancestor_ids(user_id, item_id)
    return ancestors[-1] if ancestors else item_id


# In-memory equivalents, for callers that need the ancestry of many items at
# once. One CTE per item would be a query per row; these load the whole
# parent table once and walk it in Python instead.

def parent_map(user_id):
    """{item_id: parent_id} covering everything this user owns."""
    from planning.models import PlanningItem

    return dict(
        PlanningItem.objects.visible().filter(user_id=user_id).values_list('id', 'parent_id')
    )


def ancestor_chain(parents, item_id):
    """Ancestor ids nearest-first, read from a prefetched parent_map."""
    chain = []
    current = parents.get(item_id)
    while current is not None and len(chain) < MAX_DEPTH:
        chain.append(current)
        current = parents.get(current)
    return chain


def root_of(parents, item_id):
    """The root of this item's tree, read from a prefetched parent_map."""
    chain = ancestor_chain(parents, item_id)
    return chain[-1] if chain else item_id
