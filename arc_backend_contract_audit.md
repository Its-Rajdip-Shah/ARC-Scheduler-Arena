
================================================================================
FILE: backend/planning/models.py
================================================================================
"""The planning hierarchy, tags, assignment detail and contextual timezones.

Covers FR-05 to FR-14. The self-referencing PlanningItem table holds roots,
goals, tasks and assignments in one hierarchy; the rules that operate on it
(cycle detection, priority ordering, execution scheduling) live in
planning/services/ in Phase 4 rather than here.
"""

from datetime import timedelta

from django.db import models
from django.db.models import Count, F, Q

from core.models import OwnedModel, TimestampedModel


class ItemType(models.TextChoices):
    GOAL = 'GOAL', 'Goal'
    TASK = 'TASK', 'Task'
    ASSIGNMENT = 'ASSIGNMENT', 'Assignment'


#: Types that can be scheduled, prioritised and completed. Goals are
#: containers, so they never take a priority position or a timeline slot.
ACTIONABLE_TYPES = (ItemType.TASK, ItemType.ASSIGNMENT)

#: FR-12: overdue work at most this many days past due shows in Recent,
#: anything older shows in Backlog.
RECENT_OVERDUE_DAYS = 7


class DurationCategory(models.TextChoices):
    UNDER_20_MIN = 'UNDER_20_MIN', 'Under 20 minutes'
    MIN_20_TO_60 = 'MIN_20_TO_60', '20 to 60 minutes'
    OVER_60_MIN = 'OVER_60_MIN', 'Over 60 minutes'


class CanvasObjectType(models.TextChoices):
    COURSE = 'COURSE', 'Course'
    ASSIGNMENT = 'ASSIGNMENT', 'Assignment'


class Tag(OwnedModel):
    """A reusable, user-owned label (FR-07, FR-08)."""

    id = models.BigAutoField(primary_key=True, db_column='tag_id')
    name = models.CharField(max_length=100)

    class Meta:
        db_table = 'tags'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='uniq_tag_name_per_user'),
        ]

    def __str__(self):
        return self.name


class PlanningItemQuerySet(models.QuerySet):
    def visible(self):
        """Items currently visible in the planner (not soft-deleted)."""
        return self.filter(is_deleted=False)

    def for_user(self, user):
        return self.visible().filter(user=user)

    def roots(self):
        return self.filter(parent__isnull=True)

    def actionable(self):
        return self.filter(item_type__in=ACTIONABLE_TYPES)

    def active(self):
        return self.filter(is_completed=False)

    def priority_eligible(self):
        """Incomplete actionable items with no incomplete visible children."""
        return (
            self.actionable()
            .active()
            .visible()
            .annotate(
                incomplete_child_count=Count(
                    'children',
                    filter=Q(
                        children__is_completed=False,
                        children__is_deleted=False,
                    ),
                )
            )
            .filter(incomplete_child_count=0)
        )

    def fixed(self):
        """Items with a real deadline. Only these can become overdue."""
        return self.filter(due_date__isnull=False)

    def without_deadline(self):
        """Items without a deadline, independent of their execution date."""
        return self.filter(due_date__isnull=True)

    def overdue(self, today):
        return self.actionable().active().fixed().filter(due_date__lt=today)

    def recent_overdue(self, today):
        cutoff = today - timedelta(days=RECENT_OVERDUE_DAYS)
        return self.overdue(today).filter(due_date__gte=cutoff)

    def backlog(self, today):
        cutoff = today - timedelta(days=RECENT_OVERDUE_DAYS)
        return self.overdue(today).filter(due_date__lt=cutoff)

    def in_window(self, start, end):
        """Execution dates and factual constraint ranges intersecting the window."""
        return self.filter(
            Q(scheduled_date__range=(start, end))
            | Q(start_date__range=(start, end))
            | Q(due_date__range=(start, end))
            | Q(start_date__lte=end, due_date__gte=start)
        )

    def search(self, term):
        """FR-08: match on title, description or attached tag name."""
        return self.filter(
            Q(title__icontains=term)
            | Q(description__icontains=term)
            | Q(tags__name__icontains=term)
        ).distinct()


class PlanningItem(OwnedModel, TimestampedModel):
    """A root, goal, task or assignment in the user's planning hierarchy."""

    id = models.BigAutoField(primary_key=True, db_column='planning_item_id')
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children',
        db_column='parent_id',
    )
    item_type = models.CharField(max_length=10, choices=ItemType.choices)
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    sibling_order = models.PositiveIntegerField(default=1)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    # Planned execution date, independent of release/deadline constraints.
    scheduled_date = models.DateField(null=True, blank=True)
    schedule_is_manual = models.BooleanField(default=False)
    priority_restore_context = models.JSONField(default=dict, blank=True)
    duration_category = models.CharField(
        max_length=12, choices=DurationCategory.choices, default=DurationCategory.MIN_20_TO_60
    )
    priority_position = models.PositiveIntegerField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    # Soft deletion keeps rows intact while DELETE remains undoable.
    # Once no history entry can restore the deletion, history GC may
    # permanently remove the row.
    is_deleted = models.BooleanField(default=False, db_index=True)
    canvas_object_type = models.CharField(
        max_length=10, choices=CanvasObjectType.choices, null=True, blank=True
    )
    canvas_object_id = models.CharField(max_length=100, null=True, blank=True)
    tags = models.ManyToManyField(
        Tag, through='PlanningItemTag', related_name='planning_items', blank=True
    )

    objects = PlanningItemQuerySet.as_manager()

    class Meta:
        db_table = 'planning_items'
        ordering = ['sibling_order', 'id']
        constraints = [
            # FR-09: one global priority order per user, each active task in
            # exactly one row. No condition= is needed because Postgres treats
            # NULLs as distinct, so any number of completed or non-actionable
            # items can sit at NULL. Deferring the check to COMMIT is what lets
            # the Phase 4 reorder renumber rows in a single bulk_update instead
            # of shuffling them through a temporary offset range; a condition=
            # would rule deferral out, since Postgres cannot defer a partial
            # index.
            models.UniqueConstraint(
                fields=['user', 'priority_position'],
                name='uniq_user_priority_position',
                deferrable=models.Deferrable.DEFERRED,
            ),
            # FR-05: re-syncing Canvas updates these rows instead of
            # duplicating them.
            models.UniqueConstraint(
                fields=['user', 'canvas_object_type', 'canvas_object_id'],
                condition=Q(canvas_object_id__isnull=False),
                name='uniq_canvas_object_per_user',
            ),
            # FR-06: the trivial cycle. Deeper cycles need an ancestor walk and
            # are rejected by planning.services.hierarchy in Phase 4.
            models.CheckConstraint(
                condition=~Q(id=F('parent_id')),
                name='planning_item_no_self_parent',
            ),
            models.CheckConstraint(
                condition=Q(priority_position__gte=1) | Q(priority_position__isnull=True),
                name='planning_item_priority_position_positive',
            ),
        ]

    def __str__(self):
        return f'[{self.item_type}] {self.title}'

    @property
    def is_actionable(self):
        return self.item_type in ACTIONABLE_TYPES

    @property
    def has_deadline(self):
        """Whether this item has a factual deadline constraint."""
        return self.due_date is not None


class PlanningHistoryEntry(OwnedModel):
    """One reversible user action in the planner.

    before_state and after_state contain planner snapshots so one history
    entry can represent an operation affecting multiple rows, such as moving
    siblings or completing an entire subtree.
    """

    class ActionType(models.TextChoices):
        CREATE = 'CREATE', 'Create'
        UPDATE = 'UPDATE', 'Update'
        DELETE = 'DELETE', 'Delete'
        MOVE = 'MOVE', 'Move'
        COMPLETE = 'COMPLETE', 'Complete'
        PRIORITY = 'PRIORITY', 'Priority'
        SCHEDULE = 'SCHEDULE', 'Schedule'

    id = models.BigAutoField(primary_key=True)
    action_type = models.CharField(max_length=10, choices=ActionType.choices)
    before_state = models.JSONField(default=dict)
    after_state = models.JSONField(default=dict)
    is_undone = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'planning_history_entries'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['user', 'is_undone', '-id'],
                name='planning_history_user_idx',
            ),
        ]

    def __str__(self):
        state = 'undone' if self.is_undone else 'applied'
        return f'{self.action_type} #{self.pk} ({state})'


class PlanningItemTag(models.Model):
    """Junction resolving the PlanningItem/Tag many-to-many (FR-07, FR-08).

    The ERD uses a composite primary key. Django requires a surrogate key, so
    the pair is enforced with a unique constraint instead; the guarantee that
    a tag cannot attach to the same item twice is identical.
    """

    id = models.BigAutoField(primary_key=True, db_column='planning_item_tag_id')
    planning_item = models.ForeignKey(
        PlanningItem, on_delete=models.CASCADE, db_column='planning_item_id'
    )
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, db_column='tag_id')

    class Meta:
        db_table = 'planning_item_tags'
        constraints = [
            models.UniqueConstraint(
                fields=['planning_item', 'tag'], name='uniq_planning_item_tag'
            ),
        ]

    def __str__(self):
        return f'{self.planning_item_id}:{self.tag_id}'


class AssignmentDetail(models.Model):
    """Assignment-only fields, kept out of PlanningItem (FR-05, FR-07, FR-14).

    primary_key=True on the OneToOneField reproduces the ERD's shared primary
    key, giving the 1-to-0..1 relationship exactly.
    """

    planning_item = models.OneToOneField(
        PlanningItem,
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='planning_item_id',
        related_name='assignment_detail',
    )
    weight_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    # FR-14: NULL means unmarked and must never be displayed or totalled as 0.
    mark_achieved = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    submission_url = models.URLField(max_length=1000, null=True, blank=True)
    marks_position = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'assignment_details'
        ordering = ['marks_position']

    def __str__(self):
        return f'Assignment detail for {self.planning_item_id}'


class Timezone(OwnedModel):
    """A named contextual period on the timeline (FR-13).

    Nothing to do with django.utils.timezone: this is a user-defined date
    range such as a semester, teaching week, exam period or break. Separate
    rows are allowed to overlap.
    """

    id = models.BigAutoField(primary_key=True, db_column='timezone_id')
    title = models.CharField(max_length=150)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        db_table = 'timezones'
        ordering = ['start_date', 'id']
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F('start_date')),
                name='timezone_end_not_before_start',
            ),
        ]

    def __str__(self):
        return f'{self.title} ({self.start_date} to {self.end_date})'


class SchedulingPreference(OwnedModel):
    """Normal daily slot capacity for each duration bucket."""
    under_20 = models.PositiveSmallIntegerField(default=5)
    minutes_20_to_60 = models.PositiveSmallIntegerField(default=4)
    over_60 = models.PositiveSmallIntegerField(default=3)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user'], name='uniq_scheduling_preferences_user')]


class SchedulingOverload(OwnedModel):
    """An explicit permission to exceed normal capacity on one calendar date."""
    date = models.DateField()
    allowed = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'date'], name='uniq_scheduling_overload_day')]


class SchedulingState(OwnedModel):
    """Daily maintenance state, deliberately outside user undo snapshots."""
    last_global_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user'], name='uniq_scheduling_state_user')]

================================================================================
FILE: backend/planning/queries.py
================================================================================
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

================================================================================
FILE: backend/planning/serializers.py
================================================================================
"""Payload shapes for the planning API.

Every relation a client is allowed to name goes through
UserScopedPrimaryKeyRelatedField. Filtering a viewset's queryset stops a user
reading someone else's rows, but does nothing about a payload that references
a foreign primary key, which is how a stolen parent or tag would otherwise
leak its title back through the response (FR-03).
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.serializers import UserScopedPrimaryKeyRelatedField
from planning.models import (
    AssignmentDetail,
    ItemType,
    PlanningItem,
    PlanningItemTag,
    Tag,
    Timezone,
)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('A tag needs a name.')
        user = self.context['request'].user
        clash = Tag.objects.filter(user=user, name__iexact=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError('You already have a tag with this name.')
        return value


class TimezoneSerializer(serializers.ModelSerializer):
    """FR-13. Overlapping ranges are allowed, so only the ordering is checked."""

    class Meta:
        model = Timezone
        fields = ['id', 'title', 'start_date', 'end_date']

    def validate(self, attrs):
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {'end_date': 'A timezone cannot end before it starts.'}
            )
        return attrs


class AssignmentDetailSerializer(serializers.ModelSerializer):
    """FR-14. mark_achieved stays nullable: unmarked is not zero."""

    class Meta:
        model = AssignmentDetail
        fields = ['weight_percent', 'mark_achieved', 'submission_url', 'marks_position']


class PlanningItemSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = UserScopedPrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.all(), source='tags', required=False,
        write_only=True,
    )
    parent = UserScopedPrimaryKeyRelatedField(
        queryset=PlanningItem.objects.all(), required=False, allow_null=True
    )
    assignment_detail = AssignmentDetailSerializer(required=False, allow_null=True)
    has_deadline = serializers.BooleanField(read_only=True)

    class Meta:
        model = PlanningItem
        fields = [
            'id', 'parent', 'item_type', 'title', 'description', 'sibling_order',
            'start_date', 'due_date', 'scheduled_date', 'duration_category',
            'priority_position', 'is_completed', 'has_deadline',
            'canvas_object_type', 'canvas_object_id',
            'tags', 'tag_ids', 'assignment_detail',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'priority_position', 'scheduled_date', 'canvas_object_type',
            'canvas_object_id', 'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        item_type = attrs.get('item_type', getattr(self.instance, 'item_type', None))
        if attrs.get('assignment_detail') and item_type != ItemType.ASSIGNMENT:
            raise serializers.ValidationError({
                'assignment_detail': 'Only an assignment can carry assignment detail.'
            })

        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        due = attrs.get('due_date', getattr(self.instance, 'due_date', None))
        if start and due and due < start:
            raise serializers.ValidationError(
                {'due_date': 'A due date cannot fall before the start date.'}
            )
        return attrs

    def validate_parent(self, value):
        """FR-06. The service owns the rule; this only surfaces it as a 400."""
        from django.core.exceptions import ValidationError as DjangoValidationError

        from planning.services import hierarchy

        instance = self.instance or PlanningItem(
            user=self.context['request'].user,
            item_type=self.initial_data.get('item_type', ItemType.TASK),
            title='',
        )
        try:
            hierarchy.validate_parent(instance, value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value

    def create(self, validated_data):
        from planning.services import scheduling

        detail = validated_data.pop('assignment_detail', None)
        tags = validated_data.pop('tags', None)
        user = validated_data.pop('user')

        parent = validated_data.get('parent')
        validated_data.setdefault(
            'sibling_order',
            PlanningItem.objects.filter(user=user, parent=parent).count() + 1,
        )

        item = PlanningItem.objects.create(user=user, **validated_data)

        if detail:
            AssignmentDetail.objects.create(planning_item=item, **detail)
        if tags:
            self._set_tags(item, tags)

        # Reconcile global priority because creating a child can make its
        # parent no longer priority-eligible.
        scheduling.schedule(user)
        item.refresh_from_db()
        return item

    def update(self, instance, validated_data):
        detail = validated_data.pop('assignment_detail', serializers.empty)
        tags = validated_data.pop('tags', serializers.empty)
        validated_data.pop('user', None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if detail is not serializers.empty:
            self._set_detail(instance, detail)
        if tags is not serializers.empty:
            self._set_tags(instance, tags)

        if {'item_type', 'start_date', 'due_date', 'duration_category', 'parent', 'is_completed', 'scheduled_date', 'schedule_is_manual'} & validated_data.keys():
            from planning.services import scheduling
            scheduling.schedule(instance.user)
        instance.refresh_from_db()
        return instance

    def _set_detail(self, item, detail):
        if detail is None:
            AssignmentDetail.objects.filter(planning_item=item).delete()
            return
        AssignmentDetail.objects.update_or_create(planning_item=item, defaults=detail)

    def _set_tags(self, item, tags):
        """Rewrite the junction rows rather than using the m2m manager, so the
        explicit through model stays the single way rows are created."""
        PlanningItemTag.objects.filter(planning_item=item).delete()
        PlanningItemTag.objects.bulk_create(
            [PlanningItemTag(planning_item=item, tag=tag) for tag in tags]
        )


class PlanningItemTreeSerializer(serializers.ModelSerializer):
    """A Text View node (FR-06). ``children`` is filled in by the view, which
    already has the whole tree in memory."""

    tags = TagSerializer(many=True, read_only=True)
    assignment_detail = AssignmentDetailSerializer(read_only=True)
    depth = serializers.IntegerField(read_only=True)
    children = serializers.SerializerMethodField()

    #: Recursive, so the schema describes children as a list of nodes rather
    #: than trying to expand the nesting forever.
    _children_schema = {'type': 'array', 'items': {'type': 'object'}}

    class Meta:
        model = PlanningItem
        fields = [
            'id', 'parent', 'item_type', 'title', 'description', 'depth',
            'sibling_order', 'start_date', 'due_date', 'scheduled_date',
            'duration_category', 'priority_position', 'is_completed',
            'tags', 'assignment_detail', 'children',
        ]

    @extend_schema_field(_children_schema)
    def get_children(self, item):
        return PlanningItemTreeSerializer(
            getattr(item, 'child_nodes', []), many=True, context=self.context
        ).data


class RootRefSerializer(serializers.ModelSerializer):
    """The root an item hangs from, for grouping in the Priority and Timeline
    views."""

    class Meta:
        model = PlanningItem
        fields = ['id', 'title', 'item_type']


class PriorityRowSerializer(serializers.Serializer):
    """One row of the Priority View (FR-09)."""

    position = serializers.IntegerField(source='priority_position')
    item_id = serializers.IntegerField(source='id')
    title = serializers.CharField()
    item_type = serializers.CharField()
    duration_category = serializers.CharField(allow_null=True)
    due_date = serializers.DateField(allow_null=True)
    scheduled_date = serializers.DateField(allow_null=True)
    root = RootRefSerializer()


class ReorderSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    new_position = serializers.IntegerField()


class MoveSerializer(serializers.Serializer):
    parent_id = UserScopedPrimaryKeyRelatedField(
        queryset=PlanningItem.objects.all(), allow_null=True
    )
    sibling_order = serializers.IntegerField(required=False, min_value=1)


class CompleteSerializer(serializers.Serializer):
    completed = serializers.BooleanField(default=True)


class TimelineItemSerializer(serializers.ModelSerializer):
    """A dated item on the Timeline (FR-10, FR-11)."""

    overdue = serializers.SerializerMethodField()
    submission_url = serializers.CharField(source='assignment_detail.submission_url', read_only=True, allow_null=True, default=None)
    hierarchy_path = serializers.SerializerMethodField()
    has_children = serializers.SerializerMethodField()

    class Meta:
        model = PlanningItem
        fields = [
            'id', 'parent', 'title', 'item_type', 'start_date', 'due_date', 'scheduled_date',
            'schedule_is_manual', 'duration_category', 'is_completed', 'priority_position',
            'overdue', 'submission_url', 'hierarchy_path', 'has_children',
        ]

    @extend_schema_field(serializers.BooleanField())
    def get_overdue(self, item):
        from django.utils import timezone
        return bool(not item.is_completed and item.due_date and item.due_date < timezone.localdate())

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_hierarchy_path(self, item):
        return self.context.get('paths', {}).get(item.pk, [])

    @extend_schema_field(serializers.BooleanField())
    def get_has_children(self, item):
        return bool(getattr(item, 'has_children', False))


class OverdueEntrySerializer(serializers.Serializer):
    """One Recent or Backlog row (FR-12)."""

    item = TimelineItemSerializer()
    days_overdue = serializers.IntegerField()
    hierarchy_path = serializers.ListField(child=serializers.CharField())


class MarkRowSerializer(serializers.Serializer):
    """One assessment in the Marks View (FR-14)."""

    id = serializers.IntegerField()
    title = serializers.CharField()
    weight_percent = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    mark_achieved = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    submission_url = serializers.CharField(allow_null=True)
    marks_position = serializers.IntegerField(allow_null=True)
    due_date = serializers.DateField(allow_null=True)


class MarkGroupSerializer(serializers.Serializer):
    root = RootRefSerializer()
    assessments = MarkRowSerializer(many=True)
    total_weight = serializers.DecimalField(max_digits=7, decimal_places=2)
    total_marks = serializers.DecimalField(max_digits=7, decimal_places=2)
    unmarked_count = serializers.IntegerField()


class MarksReorderSerializer(serializers.Serializer):
    ordered_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


class ScheduleMoveSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    date = serializers.DateField()
    allow_overload = serializers.BooleanField(default=False)


class ScheduleReplaceSerializer(serializers.Serializer):
    replacement_id = serializers.IntegerField()
    displaced_id = serializers.IntegerField()
    allow_overload = serializers.BooleanField(default=False)


class ScheduleCapacitySerializer(serializers.Serializer):
    under_20 = serializers.IntegerField(min_value=0, max_value=32767, required=False)
    minutes_20_to_60 = serializers.IntegerField(min_value=0, max_value=32767, required=False)
    over_60 = serializers.IntegerField(min_value=0, max_value=32767, required=False)


class ScheduleOverloadSerializer(serializers.Serializer):
    date = serializers.DateField()
    allowed = serializers.BooleanField()



class ScheduleResultSerializer(serializers.Serializer):
    changed_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    conflicts = serializers.ListField(child=serializers.DictField())

================================================================================
FILE: backend/planning/views.py
================================================================================
"""The planning API: Text View, Priority View, Timeline, Overdue and Marks.

Every viewset here is user-scoped through core.mixins.UserScopedMixin, so a
cross-user identifier falls out of the queryset and surfaces as 404 rather
than 403 (FR-03). The business rules live in planning/services and are only
called from here.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import UserScopedMixin
from planning import queries
from planning.models import AssignmentDetail, ItemType, PlanningItem, SchedulingOverload, Tag, Timezone
from planning.serializers import (
    AssignmentDetailSerializer,
    ScheduleMoveSerializer,
    ScheduleResultSerializer,
    ScheduleReplaceSerializer,
    ScheduleCapacitySerializer,
    ScheduleOverloadSerializer,
    CompleteSerializer,
    MarkGroupSerializer,
    MarksReorderSerializer,
    MoveSerializer,
    OverdueEntrySerializer,
    PlanningItemSerializer,
    PlanningItemTreeSerializer,
    PriorityRowSerializer,
    ReorderSerializer,
    RootRefSerializer,
    TagSerializer,
    TimelineItemSerializer,
    TimezoneSerializer,
)
from planning.services import hierarchy, leaf_order_sync, overdue, priority, scheduling
from planning.services import history


def _as_400(exc):
    """Re-raise a service-level Django ValidationError as a DRF 400."""
    return ValidationError({'detail': exc.messages})


def _date_param(request, name, default):
    raw = request.query_params.get(name)
    if not raw:
        return default
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        raise ValidationError({name: 'Expected a date as YYYY-MM-DD.'})


def _root_lookup(user):
    """{item_id: root descriptor} for every item the user owns.

    The Priority, Timeline and Marks views all group rows under the root of
    their tree. Resolving that per row would be a query each; this loads the
    id/parent/title columns once and walks them in memory instead.
    """
    parents = queries.parent_map(user.pk)
    meta = {
        pk: {'id': pk, 'title': title, 'item_type': item_type}
        for pk, title, item_type in PlanningItem.objects.visible().filter(user=user).values_list(
            'id', 'title', 'item_type'
        )
    }
    return {pk: meta[queries.root_of(parents, pk)] for pk in meta}


def ensure_scheduled(user):
    """Re-evaluate current capacity and eligibility; same-day changes matter."""
    return scheduling.daily_schedule(user, timezone.localdate())


class TagViewSet(UserScopedMixin, viewsets.ModelViewSet):
    """FR-07, FR-08: /api/planning/tags/"""

    serializer_class = TagSerializer
    queryset = Tag.objects.all()


class TimezoneViewSet(UserScopedMixin, viewsets.ModelViewSet):
    """FR-13: /api/planning/timezones/"""

    serializer_class = TimezoneSerializer
    queryset = Timezone.objects.all()


class AssignmentDetailViewSet(UserScopedMixin, viewsets.ModelViewSet):
    """FR-14: direct edits to one assessment's weighting and mark.

    Keyed by planning_item_id, since AssignmentDetail shares its primary key
    with the item it describes.
    """

    serializer_class = AssignmentDetailSerializer
    queryset = AssignmentDetail.objects.select_related('planning_item')
    user_field = 'planning_item__user'
    http_method_names = ['get', 'put', 'patch', 'head', 'options']


@extend_schema_view(
    list=extend_schema(
        description='Flat list of planning items.',
        parameters=[
            OpenApiParameter('type', enum=[choice.value for choice in ItemType]),
            OpenApiParameter('completed', OpenApiTypes.BOOL),
            OpenApiParameter(
                'root', OpenApiTypes.INT,
                description="Restrict to one root's subtree, the root included.",
            ),
            OpenApiParameter('from', OpenApiTypes.DATE, description='Requires "to".'),
            OpenApiParameter('to', OpenApiTypes.DATE, description='Requires "from".'),
        ],
    )
)
class PlanningItemViewSet(UserScopedMixin, viewsets.ModelViewSet):
    """FR-06 to FR-08: /api/planning/items/"""

    serializer_class = PlanningItemSerializer
    queryset = PlanningItem.objects.all()
    filter_backends = [SearchFilter]
    search_fields = ['title', 'description', 'tags__name']

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .visible()
            .select_related('assignment_detail', 'parent')
            .prefetch_related('tags')
        )
        params = self.request.query_params

        if (item_type := params.get('type')):
            queryset = queryset.filter(item_type=item_type.upper())

        completed = params.get('completed')
        if completed is not None:
            if completed.lower() in {'true', '1'}:
                queryset = queryset.filter(is_completed=True)
            elif completed.lower() in {'false', '0'}:
                queryset = queryset.filter(is_completed=False)

        if (root := params.get('root')):
            # One root's whole subtree, the root included.
            try:
                root_id = int(root)
            except ValueError:
                raise ValidationError({'root': 'Expected a planning item id.'})
            ids = queries.descendant_ids(self.request.user.pk, root_id)
            queryset = queryset.filter(pk__in=[root_id] + ids)

        start, end = params.get('from'), params.get('to')
        if start and end:
            queryset = queryset.in_window(
                _date_param(self.request, 'from', None),
                _date_param(self.request, 'to', None),
            )

        return queryset.distinct()

    @transaction.atomic
    def perform_create(self, serializer):
        # Creating an item may change the global priority ordering.
        priority_before = history.capture_priority(self.request.user, include_unpositioned=True)

        instance = serializer.save(user=self.request.user)

        item_after = history.capture_items(
            self.request.user,
            [instance.pk],
        )
        priority_after = history.capture_priority(self.request.user, include_unpositioned=True)

        history.record_checkpoint(
            self.request.user,
            'CREATE',
            {
                'delete_ids': [instance.pk],
                'priority': priority_before,
            },
            {
                'items': item_after,
                'priority': priority_after,
            },
        )

    @transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.instance

        before = history.capture_items(
            self.request.user,
            [instance.pk],
        )

        updated = serializer.save()

        after = history.capture_items(
            self.request.user,
            [updated.pk],
        )

        history.record_checkpoint(
            self.request.user,
            'UPDATE',
            {'items': before},
            {'items': after},
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        parent = instance.parent
        parent_id = instance.parent_id
        user = instance.user

        # Resolve the complete subtree BEFORE hiding anything.
        subtree_ids = [
            instance.pk,
            *queries.descendant_ids(user.pk, instance.pk),
        ]

        siblings_before = history.capture_siblings(user, parent_id)
        priority_before = history.capture_priority(user, include_unpositioned=True)

        # The original rows, PKs, hierarchy, tags and assignment details
        # remain intact while DELETE is undoable.
        PlanningItem.objects.filter(
            user=user,
            pk__in=subtree_ids,
        ).update(is_deleted=True)

        # Deleting a child can make its parent priority-eligible.
        scheduling.schedule(user)

        hierarchy.reindex_siblings(user, parent)

        siblings_after = history.capture_siblings(user, parent_id)
        priority_after = history.capture_priority(user, include_unpositioned=True)

        history.record_checkpoint(
            user,
            'DELETE',
            {
                'soft_delete': {
                    'ids': subtree_ids,
                    'value': False,
                },
                'siblings': siblings_before,
                'priority': priority_before,
            },
            {
                'soft_delete': {
                    'ids': subtree_ids,
                    'value': True,
                },
                'siblings': siblings_after,
                'priority': priority_after,
            },
        )

    @extend_schema(
        responses=PlanningItemTreeSerializer(many=True),
        description='The whole hierarchy for the Text View, nested, in display order.',
    )
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """FR-06: the indented Text View.

        One recursive CTE fixes order and depth, then one ORM query loads the
        rows. Nesting them in memory avoids the query per node that walking
        children relation by relation would cost.
        """
        rows = queries.tree_rows(request.user.pk)
        if not rows:
            return Response([])

        items = {
            item.pk: item
            for item in PlanningItem.objects.filter(pk__in=[row[0] for row in rows])
            .select_related('assignment_detail')
            .prefetch_related('tags')
        }

        roots = []
        for item_id, depth in rows:
            item = items[item_id]
            item.depth = depth
            item.child_nodes = []
            if item.parent_id is None:
                roots.append(item)
            else:
                items[item.parent_id].child_nodes.append(item)

        return Response(
            PlanningItemTreeSerializer(roots, many=True, context={'request': request}).data
        )

    @extend_schema(request=MoveSerializer, responses=PlanningItemSerializer)
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def move(self, request, pk=None):
        """FR-06: re-parent, refusing any move that would close a cycle."""
        item = self.get_object()
        serializer = MoveSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        priority_before = history.capture_priority(request.user, include_unpositioned=True)
        old_parent_id = item.parent_id
        new_parent_id = serializer.validated_data['parent_id']

        affected_parent_ids = {old_parent_id, new_parent_id}

        siblings_before = []
        for parent_id in affected_parent_ids:
            siblings_before.extend(
                history.capture_siblings(request.user, parent_id)
            )

        try:
            hierarchy.set_parent(item, new_parent_id)
        except DjangoValidationError as exc:
            raise _as_400(exc)

        order = serializer.validated_data.get('sibling_order')
        if order is not None:
            siblings = list(
                hierarchy._siblings(request.user, item.parent)
                .exclude(pk=item.pk)
            )

            # Insert the moved item at the requested 1-based position.
            index = max(0, min(order - 1, len(siblings)))
            siblings.insert(index, item)

            # Persist the resulting sibling order explicitly.
            for sibling_order, sibling in enumerate(siblings, start=1):
                if sibling.sibling_order != sibling_order:
                    sibling.sibling_order = sibling_order
                    sibling.save(update_fields=['sibling_order'])

        leaf_order_sync.from_planner(item)
        scheduling.schedule(request.user)
        item.refresh_from_db()

        siblings_after = []
        for parent_id in affected_parent_ids:
            siblings_after.extend(
                history.capture_siblings(request.user, parent_id)
            )

        before = {'siblings': siblings_before}
        after = {'siblings': siblings_after}
        priority_after = history.capture_priority(request.user, include_unpositioned=True)
        if priority_before != priority_after:
            before['priority'] = priority_before
            after['priority'] = priority_after

        history.record_checkpoint(
            request.user,
            'MOVE',
            before,
            after,
        )

        return Response(self.get_serializer(item).data)

    @extend_schema(
        request=CompleteSerializer,
        responses=inline_serializer(
            'PlanningItemCompleteResponse',
            {
                'item': PlanningItemSerializer(),
                'affected_ids': serializers.ListField(child=serializers.IntegerField()),
            },
        ),
    )
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def complete(self, request, pk=None):
        """FR-08: completing a parent completes everything beneath it."""
        item = self.get_object()
        serializer = CompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data['completed']:
            affected_ids = [
                item.pk,
                *queries.descendant_ids(request.user.pk, item.pk),
            ]
        else:
            affected_ids = [item.pk]

        items_before = history.capture_items(
            request.user,
            affected_ids,
        )
        priority_before = history.capture_priority(request.user, include_unpositioned=True)

        if serializer.validated_data['completed']:
            affected = hierarchy.complete_subtree(item)
        else:
            hierarchy.reopen(item)
            affected = [item.pk]

        items_after = history.capture_items(
            request.user,
            affected_ids,
        )
        priority_after = history.capture_priority(request.user, include_unpositioned=True)

        history.record_checkpoint(
            request.user,
            'COMPLETE',
            {
                'items': items_before,
                'priority': priority_before,
            },
            {
                'items': items_after,
                'priority': priority_after,
            },
        )

        item.refresh_from_db()
        return Response({
            'item': self.get_serializer(item).data,
            'affected_ids': affected,
        })

    @action(detail=False, methods=['get'], url_path='history-status')
    def history_status(self, request):
        return Response(history.history_status(request.user))

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def undo(self, request):
        entry = history.undo(request.user)

        if entry is None:
            return Response({
                'changed': False,
                **history.history_status(request.user),
            })

        return Response({
            'changed': True,
            'action_type': entry.action_type,
            **history.history_status(request.user),
        })

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def redo(self, request):
        entry = history.redo(request.user)

        if entry is None:
            return Response({
                'changed': False,
                **history.history_status(request.user),
            })

        return Response({
            'changed': True,
            'action_type': entry.action_type,
            **history.history_status(request.user),
        })


def _priority_rows(user, items):
    if not items:
        return []
    roots = _root_lookup(user)
    rows = [
        {
            'priority_position': item.priority_position,
            'id': item.pk,
            'title': item.title,
            'item_type': item.item_type,
            'duration_category': item.duration_category,
            'due_date': item.due_date,
            'scheduled_date': item.scheduled_date,
            'root': roots[item.pk],
        }
        for item in items
    ]
    return PriorityRowSerializer(rows, many=True).data


class PriorityView(APIView):
    """FR-09: GET /api/planning/priority/"""

    @extend_schema(responses=PriorityRowSerializer(many=True))
    def get(self, request):
        return Response(_priority_rows(request.user, list(priority.ordered(request.user))))


class PriorityReorderView(APIView):
    """FR-09: POST /api/planning/priority/reorder/"""

    @extend_schema(request=ReorderSerializer, responses=PriorityRowSerializer(many=True))
    @transaction.atomic
    def post(self, request):
        serializer = ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        before = {
            'priority': history.capture_priority(request.user),
            'leaf_siblings': history.capture_leaf_order(request.user),
        }

        try:
            priority.reorder(
                request.user,
                serializer.validated_data['item_id'],
                serializer.validated_data['new_position'],
            )
            leaf_order_sync.from_priority(request.user)
            scheduling.schedule(request.user)
        except DjangoValidationError as exc:
            raise _as_400(exc)

        after = {
            'priority': history.capture_priority(request.user),
            'leaf_siblings': history.capture_leaf_order(request.user),
        }

        history.record_checkpoint(
            request.user,
            'PRIORITY',
            before,
            after,
        )

        items = list(priority.ordered(request.user))

        # Return the authoritative global priority order.
        return Response(_priority_rows(request.user, items))


class TimelineView(APIView):
    """FR-10, FR-11, FR-13: GET /api/planning/timeline/?from=&to="""

    @extend_schema(
        parameters=[
            OpenApiParameter('from', OpenApiTypes.DATE, description='Defaults to 7 days ago.'),
            OpenApiParameter('to', OpenApiTypes.DATE, description='Defaults to 28 days ahead.'),
        ],
        responses=inline_serializer(
            'TimelineResponse',
            {
                'conflicts': serializers.ListField(child=serializers.DictField()),
                'capacities': serializers.DictField(child=serializers.IntegerField()),
                'overload': serializers.ListField(child=serializers.DictField()),
                'range': serializers.DictField(child=serializers.DateField()),
                'timezones': TimezoneSerializer(many=True),
                'groups': inline_serializer(
                    'TimelineGroup',
                    {
                        'root': RootRefSerializer(),
                        'items': TimelineItemSerializer(many=True),
                    },
                    many=True,
                ),
            },
        ),
    )
    def get(self, request):
        today = timezone.localdate()
        start = _date_param(request, 'from', today - timedelta(days=7))
        end = _date_param(request, 'to', today + timedelta(days=28))
        if end < start:
            raise ValidationError({'to': 'The end of the range precedes its start.'})
        schedule_result = ensure_scheduled(request.user)

        items = list(
            PlanningItem.objects.for_user(request.user)
            .actionable()
            .in_window(start, end)
            .annotate(
                has_children=Exists(
                    PlanningItem.objects.filter(parent_id=OuterRef('pk'))
                )
            )
            .select_related('assignment_detail')
            .order_by('id')
        )

        roots = _root_lookup(request.user)
        grouped = {}
        for item in items:
            root = roots[item.pk]
            grouped.setdefault(root['id'], (root, []))[1].append(item)

        parents = queries.parent_map(request.user.pk)
        meta = dict(PlanningItem.objects.for_user(request.user).values_list('pk', 'title'))
        paths = {item.pk: [{'id': pk, 'title': meta[pk]} for pk in reversed(queries.ancestor_chain(parents, item.pk))]
                 for item in items}
        groups = []
        for root, members in grouped.values():
            members.sort(key=lambda i: (i.scheduled_date is None, i.scheduled_date or end,
                                       i.priority_position is None, i.priority_position or 0, i.pk))
            groups.append({
                'root': root,
                'items': TimelineItemSerializer(members, many=True, context={'paths': paths}).data,
            })
        groups.sort(key=lambda group: group['root']['title'])

        zones = Timezone.objects.filter(
            user=request.user, start_date__lte=end, end_date__gte=start
        )

        return Response({
            'range': {'from': start.isoformat(), 'to': end.isoformat()},
            'timezones': TimezoneSerializer(zones, many=True).data,
            'groups': groups,
            'conflicts': schedule_result['conflicts'],
            'capacities': scheduling.capacities(request.user),
            'overload': list(SchedulingOverload.objects.filter(
                user=request.user, date__range=(start, end),
            ).order_by('date').values('date', 'allowed')),
        })


class OverdueView(APIView):
    """FR-12: GET /api/planning/overdue/"""

    @extend_schema(
        responses=inline_serializer(
            'OverdueResponse',
            {
                'recent': OverdueEntrySerializer(many=True),
                'backlog': OverdueEntrySerializer(many=True),
            },
        ),
        description='Missed fixed deadlines, split into Recent (within 7 days) and Backlog.',
    )
    def get(self, request):
        buckets = overdue.classify(request.user, timezone.localdate())
        return Response({
            'recent': OverdueEntrySerializer(buckets['recent'], many=True).data,
            'backlog': OverdueEntrySerializer(buckets['backlog'], many=True).data,
        })


class MarksView(APIView):
    """FR-14: GET /api/planning/marks/, grouped by academic subject."""

    @extend_schema(responses=MarkGroupSerializer(many=True))
    def get(self, request):
        assignments = list(
            PlanningItem.objects.for_user(request.user)
            .filter(item_type=ItemType.ASSIGNMENT)
            .select_related('assignment_detail')
            .order_by('id')
        )
        if not assignments:
            return Response([])

        roots = _root_lookup(request.user)
        grouped = {}
        for item in assignments:
            root = roots[item.pk]
            grouped.setdefault(root['id'], (root, []))[1].append(item)

        groups = []
        for root, members in grouped.values():
            rows = []
            total_weight = Decimal('0')
            total_marks = Decimal('0')
            unmarked = 0

            for item in members:
                detail = getattr(item, 'assignment_detail', None)
                weight = detail.weight_percent if detail else None
                mark = detail.mark_achieved if detail else None

                if weight is not None:
                    total_weight += weight
                if mark is None:
                    # FR-14: unmarked is not zero, so it must not pull the
                    # running total down.
                    unmarked += 1
                else:
                    total_marks += mark

                rows.append({
                    'id': item.pk,
                    'title': item.title,
                    'weight_percent': weight,
                    'mark_achieved': mark,
                    'submission_url': detail.submission_url if detail else None,
                    'marks_position': detail.marks_position if detail else None,
                    'due_date': item.due_date,
                })

            rows.sort(key=lambda row: (row['marks_position'] is None,
                                       row['marks_position'] or 0,
                                       row['id']))
            groups.append({
                'root': root,
                'assessments': rows,
                'total_weight': total_weight,
                'total_marks': total_marks,
                'unmarked_count': unmarked,
            })

        groups.sort(key=lambda group: group['root']['title'])
        return Response(MarkGroupSerializer(groups, many=True).data)


class MarksReorderView(APIView):
    """FR-14: POST /api/planning/marks/reorder/"""

    @extend_schema(
        request=MarksReorderSerializer,
        responses=inline_serializer(
            'MarksReorderResponse', {'reordered': serializers.IntegerField()}
        ),
    )
    def post(self, request):
        serializer = MarksReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ordered_ids = serializer.validated_data['ordered_ids']

        details = {
            detail.planning_item_id: detail
            for detail in AssignmentDetail.objects.filter(
                planning_item__user=request.user, planning_item_id__in=ordered_ids
            )
        }
        missing = set(ordered_ids) - set(details)
        if missing:
            raise ValidationError(
                {'ordered_ids': f'Not your assessments: {sorted(missing)}'}
            )

        with transaction.atomic():
            changed = []
            for position, item_id in enumerate(ordered_ids, start=1):
                detail = details[item_id]
                if detail.marks_position != position:
                    detail.marks_position = position
                    changed.append(detail)
            if changed:
                AssignmentDetail.objects.bulk_update(changed, ['marks_position'])

        return Response({'reordered': len(ordered_ids)})


class ScheduleMoveView(APIView):
    @extend_schema(request=ScheduleMoveSerializer, responses={200: ScheduleResultSerializer, 409: ScheduleResultSerializer})
    def post(self, request):
        serializer = ScheduleMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = scheduling.move_to_date(request.user, data['item_id'], data['date'], allow_overload=data['allow_overload'])
        except scheduling.SchedulingConflict as exc:
            return Response({'conflicts': exc.conflicts}, status=409)
        return Response(result)


class ScheduleReplaceView(APIView):
    @extend_schema(request=ScheduleReplaceSerializer, responses={200: ScheduleResultSerializer, 409: ScheduleResultSerializer})
    def post(self, request):
        serializer = ScheduleReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = scheduling.replace(request.user, **serializer.validated_data)
        except scheduling.SchedulingConflict as exc:
            return Response({'conflicts': exc.conflicts}, status=409)
        return Response(result)


class ScheduleCapacityView(APIView):
    @extend_schema(responses=serializers.DictField(child=serializers.IntegerField()))
    def get(self, request):
        return Response(scheduling.capacities(request.user))

    @extend_schema(request=ScheduleCapacitySerializer, responses={200: ScheduleResultSerializer, 409: ScheduleResultSerializer})
    def patch(self, request):
        serializer = ScheduleCapacitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = scheduling.configure(request.user, capacity=serializer.validated_data)
        except scheduling.SchedulingConflict as exc:
            return Response({'conflicts': exc.conflicts}, status=409)
        return Response(result)


class ScheduleOverloadView(APIView):
    @extend_schema(request=ScheduleOverloadSerializer, responses={200: ScheduleResultSerializer, 409: ScheduleResultSerializer})
    def post(self, request):
        serializer = ScheduleOverloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = scheduling.configure(request.user, day=data['date'], overloaded=data['allowed'])
        except scheduling.SchedulingConflict as exc:
            return Response({'conflicts': exc.conflicts}, status=409)
        return Response(result)


class ScheduleRescheduleView(APIView):
    @extend_schema(request=None, responses=ScheduleResultSerializer)
    def post(self, request):
        return Response(scheduling.reschedule(request.user))

================================================================================
FILE: backend/planning/urls.py
================================================================================
"""Routes for the planning API, mounted at /api/planning/.

The literal paths come before the router so that /priority/ and /marks/ are
not shadowed by a router-generated detail route.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from planning import views

router = DefaultRouter()
router.register('items', views.PlanningItemViewSet, basename='planning-item')
router.register('tags', views.TagViewSet, basename='tag')
router.register('timezones', views.TimezoneViewSet, basename='timezone')
router.register(
    'assignment-details', views.AssignmentDetailViewSet, basename='assignment-detail'
)

urlpatterns = [
    path('priority/', views.PriorityView.as_view(), name='priority'),
    path('priority/reorder/', views.PriorityReorderView.as_view(), name='priority-reorder'),
    path('timeline/reschedule/', views.ScheduleRescheduleView.as_view(), name='schedule-reschedule'),
    path('timeline/move/', views.ScheduleMoveView.as_view(), name='schedule-move'),
    path('timeline/replace/', views.ScheduleReplaceView.as_view(), name='schedule-replace'),
    path('timeline/capacity/', views.ScheduleCapacityView.as_view(), name='schedule-capacity'),
    path('timeline/overload/', views.ScheduleOverloadView.as_view(), name='schedule-overload'),
    path('timeline/', views.TimelineView.as_view(), name='timeline'),
    path('overdue/', views.OverdueView.as_view(), name='overdue'),
    path('marks/', views.MarksView.as_view(), name='marks'),
    path('marks/reorder/', views.MarksReorderView.as_view(), name='marks-reorder'),
    path('', include(router.urls)),
]

================================================================================
FILE: backend/planning/services/__init__.py
================================================================================
"""Domain rules over the planning hierarchy.

Each module owns one rule from the requirements and is deliberately free of
HTTP concerns, so it can be tested without a request:

- hierarchy: parent/child structure and cascade completion (FR-06, FR-08)
- priority:  the single global task order (FR-09)
- scheduling: global execution scheduling and roll-forward (FR-11)
- overdue:   Recent and Backlog classification (FR-12)
"""

================================================================================
FILE: backend/planning/services/hierarchy.py
================================================================================
"""Structure of the planning tree: re-parenting and cascade completion.

Covers FR-06 (an item may never become its own ancestor) and FR-08 (completing
a parent completes everything beneath it).
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from planning.models import PlanningItem
from planning.queries import MAX_DEPTH, ancestor_ids, descendant_ids

from . import scheduling


def validate_parent(item, new_parent):
    """Refuse a re-parent that would close a loop (FR-06).

    Moving `item` under `new_parent` creates a cycle exactly when `new_parent`
    is `item` itself or sits somewhere below it. Rather than walking down from
    `item`, which could be a large subtree, this walks up from `new_parent`:
    the move is illegal if `item` appears among its ancestors. Either
    direction is correct, but the upward walk is bounded by tree depth instead
    of by subtree size.
    """
    if new_parent is None:
        return

    if new_parent.user_id != item.user_id:
        raise ValidationError('A planning item cannot be moved under another user\'s item.')

    if item.pk is not None and new_parent.pk == item.pk:
        raise ValidationError('An item cannot be its own parent.')

    chain = ancestor_ids(new_parent.user_id, new_parent.pk)

    if item.pk is not None and item.pk in chain:
        raise ValidationError('An item cannot become its own ancestor.')

    # ancestor_ids stops at MAX_DEPTH. Hitting that cap means either a tree
    # deeper than ARC supports or a cycle that already reached the database;
    # in both cases the answer above cannot be trusted.
    if len(chain) + 1 >= MAX_DEPTH:
        raise ValidationError(
            f'This move would nest the item more than {MAX_DEPTH} levels deep.'
        )


@transaction.atomic
def set_parent(item, new_parent):
    """Validate and apply a re-parent, keeping sibling numbering dense."""
    validate_parent(item, new_parent)
    old_parent = item.parent

    item.parent = new_parent
    item.sibling_order = _next_sibling_order(item.user, new_parent)
    item.save(update_fields=['parent', 'sibling_order', 'updated_at'])

    reindex_siblings(item.user, old_parent)
    reindex_siblings(item.user, new_parent)

    # Moving an item can change leaf eligibility for both its old and new parent.
    scheduling.schedule(item.user)

    item.refresh_from_db(fields=['priority_position'])
    return item


def _siblings(user, parent):
    return PlanningItem.objects.visible().filter(user=user, parent=parent).order_by(
        'sibling_order', 'id'
    )


def _next_sibling_order(user, parent):
    return _siblings(user, parent).count() + 1


@transaction.atomic
def reindex_siblings(user, parent=None):
    """Renumber one parent's children as a dense 1..n.

    Takes the user as well as the parent because ``parent=None`` means "the
    roots", and roots are only meaningful per user.
    """
    changed = []
    for order, child in enumerate(_siblings(user, parent), start=1):
        if child.sibling_order != order:
            child.sibling_order = order
            changed.append(child)
    if changed:
        PlanningItem.objects.bulk_update(changed, ['sibling_order'])
    return changed


@transaction.atomic
def complete_subtree(item):
    """Mark an item and everything under it complete (FR-08).

    Completed tasks leave the priority order, which keeps the FR-09 invariant
    that a position belongs to an active task.
    """
    ids = [item.pk] + descendant_ids(item.user_id, item.pk)
    PlanningItem.objects.visible().filter(user_id=item.user_id, pk__in=ids).update(is_completed=True)
    scheduling.schedule(item.user)
    item.is_completed = True
    return ids


@transaction.atomic
def reopen(item):
    """Mark a single item incomplete again and give it a priority position.

    Deliberately not a cascade: FR-08 only requires completion to propagate
    downwards, and re-opening a root should not silently re-open a subtree the
    user finished individually.
    """
    PlanningItem.objects.visible().filter(pk=item.pk).update(is_completed=False)
    item.is_completed = False
    scheduling.schedule(item.user)
    item.refresh_from_db(fields=['priority_position'])
    return item

================================================================================
FILE: backend/planning/services/history.py
================================================================================
"""Bounded, delta-based undo/redo support for ARC planning mutations.

History stores only rows affected by an action, rather than snapshotting the
entire planner. This keeps storage and restore work proportional to the
mutation itself.
"""

from django.db import transaction

from planning.models import (
    AssignmentDetail,
    DurationCategory,
    PlanningHistoryEntry,
    PlanningItem,
    SchedulingOverload,
    SchedulingPreference,
)

MAX_HISTORY_ENTRIES = 100


# ---------------------------------------------------------------------------
# SERIALISATION
# ---------------------------------------------------------------------------

def serialize_item(item):
    """Capture the complete reversible state of one planning item."""

    assignment = getattr(item, "assignment_detail", None)

    return {
        "id": item.pk,
        "parent_id": item.parent_id,
        "item_type": item.item_type,
        "title": item.title,
        "description": item.description,
        "sibling_order": item.sibling_order,
        "start_date": item.start_date.isoformat() if item.start_date else None,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "scheduled_date": (
            item.scheduled_date.isoformat()
            if item.scheduled_date else None
        ),
        "duration_category": item.duration_category,
        "schedule_is_manual": item.schedule_is_manual,
        "priority_restore_context": item.priority_restore_context,
        "priority_position": item.priority_position,
        "is_completed": item.is_completed,
        "canvas_object_type": item.canvas_object_type,
        "canvas_object_id": item.canvas_object_id,
        "tag_ids": list(
            item.tags.order_by("id").values_list("id", flat=True)
        ),
        "assignment_detail": (
            {
                "weight_percent": (
                    str(assignment.weight_percent)
                    if assignment.weight_percent is not None
                    else None
                ),
                "submission_url": assignment.submission_url,
            }
            if assignment
            else None
        ),
    }


def capture_items(user, item_ids):
    """Capture only the requested items belonging to this user."""

    ids = set(item_ids)

    if not ids:
        return []

    items = (
        PlanningItem.objects
        .filter(user=user, pk__in=ids)
        .select_related("assignment_detail")
        .prefetch_related("tags")
        .order_by("id")
    )

    return [serialize_item(item) for item in items]


def capture_scope(user, queryset):
    """Capture the rows represented by an already-scoped queryset."""

    ids = queryset.values_list("pk", flat=True)
    return capture_items(user, ids)


# ---------------------------------------------------------------------------
# SMALL STATE CAPTURES
# ---------------------------------------------------------------------------

def capture_priority(user, *, include_unpositioned=False):
    """Capture priority membership/order.

    Include null positions and restoration anchors when eligibility can change,
    so undo restores both active membership and future reopening behaviour.
    """

    items = PlanningItem.objects.filter(user=user)
    if not include_unpositioned:
        items = items.exclude(priority_position=None)
    fields = ["id", "priority_position"]
    if include_unpositioned:
        fields.append("priority_restore_context")
    return list(items.order_by("priority_position", "id").values(*fields))


def capture_siblings(user, parent_id):
    """Capture only sibling ordering for one parent/root group."""

    return list(
        PlanningItem.objects
        .filter(user=user, parent_id=parent_id)
        .order_by("sibling_order", "id")
        .values("id", "parent_id", "sibling_order")
    )


def capture_leaf_order(user):
    """Snapshot only synchronizable leaf slots, never parent relationships."""
    from planning.services.leaf_order_sync import leaves

    return list(leaves(user).order_by('pk').values('id', 'sibling_order'))


def _restore_leaf_order(user, states):
    """Restore explicit leaf slots without allowing container writes."""
    from planning.services.leaf_order_sync import leaves

    wanted = {state['id']: state['sibling_order'] for state in states}
    items = list(leaves(user).filter(pk__in=wanted))
    for item in items:
        item.sibling_order = wanted[item.pk]
    if items:
        PlanningItem.objects.bulk_update(items, ['sibling_order'])


# ---------------------------------------------------------------------------
# SOFT-DELETE GARBAGE COLLECTION
# ---------------------------------------------------------------------------

def _delete_ids_from_entry(entry):
    """Return item IDs owned by a DELETE checkpoint."""

    if entry.action_type != "DELETE":
        return set()

    soft_delete = entry.after_state.get("soft_delete", {})

    if not soft_delete.get("value"):
        return set()

    return set(soft_delete.get("ids", []))


def _protected_delete_ids(user, exclude_entry_ids=None):
    """IDs still recoverable through surviving DELETE history."""

    exclude_entry_ids = set(exclude_entry_ids or [])

    entries = (
        PlanningHistoryEntry.objects
        .filter(user=user, action_type="DELETE")
        .exclude(pk__in=exclude_entry_ids)
        .only("id", "action_type", "after_state")
    )

    protected = set()

    for entry in entries:
        protected.update(_delete_ids_from_entry(entry))

    return protected


def _garbage_collect_discarded_entries(user, entries):
    """Hard-delete unreachable rows from discarded DELETE checkpoints.

    A row is removed only when:
    1. its DELETE checkpoint is being permanently discarded,
    2. the row is still soft-deleted, and
    3. no surviving DELETE checkpoint still protects it.
    """

    entries = list(entries)

    if not entries:
        return

    discarded_ids = {entry.pk for entry in entries}

    candidates = set()

    for entry in entries:
        candidates.update(_delete_ids_from_entry(entry))

    if not candidates:
        return

    protected = _protected_delete_ids(
        user,
        exclude_entry_ids=discarded_ids,
    )

    hard_delete_ids = candidates - protected

    if not hard_delete_ids:
        return

    # Only physically remove rows that are STILL deleted.
    #
    # If a DELETE was undone and its redo branch is discarded,
    # those rows are visible again and must remain.
    PlanningItem.objects.filter(
        user=user,
        pk__in=hard_delete_ids,
        is_deleted=True,
    ).delete()


# ---------------------------------------------------------------------------
# HISTORY RECORDING
# ---------------------------------------------------------------------------

def record_checkpoint(
    user,
    action_type,
    before_state,
    after_state,
):
    """Record one user action and invalidate the old redo branch."""

    if before_state == after_state:
        return None

    # Standard undo semantics:
    #
    # A -> B -> C
    #         undo C
    #         perform D
    #
    # C can no longer be redone.
    discarded_redo = list(
        PlanningHistoryEntry.objects.filter(
            user=user,
            is_undone=True,
        )
    )

    _garbage_collect_discarded_entries(
        user,
        discarded_redo,
    )

    if discarded_redo:
        PlanningHistoryEntry.objects.filter(
            pk__in=[entry.pk for entry in discarded_redo],
        ).delete()

    entry = PlanningHistoryEntry.objects.create(
        user=user,
        action_type=action_type,
        before_state=before_state,
        after_state=after_state,
    )

    prune_history(user)

    return entry


def prune_history(user):
    """Keep at most MAX_HISTORY_ENTRIES checkpoints per user."""

    keep_ids = list(
        PlanningHistoryEntry.objects
        .filter(user=user)
        .order_by("-id")
        .values_list("id", flat=True)[:MAX_HISTORY_ENTRIES]
    )

    if keep_ids:
        pruned = list(
            PlanningHistoryEntry.objects
            .filter(user=user)
            .exclude(pk__in=keep_ids)
        )

        _garbage_collect_discarded_entries(
            user,
            pruned,
        )

        if pruned:
            PlanningHistoryEntry.objects.filter(
                pk__in=[entry.pk for entry in pruned],
            ).delete()


# ---------------------------------------------------------------------------
# RESTORATION HELPERS
# ---------------------------------------------------------------------------

def _restore_item_states(user, states):
    """Restore/create only items represented in the supplied delta."""

    if not states:
        return

    ids = [state["id"] for state in states]

    existing = {
        item.pk: item
        for item in PlanningItem.objects.filter(
            user=user,
            pk__in=ids,
        )
    }

    # Pass 1: scalar state without parent FK.
    for state in states:
        values = {
            "user": user,
            "parent": None,
            "item_type": state["item_type"],
            "title": state["title"],
            "description": state["description"],
            "sibling_order": state["sibling_order"],
            "start_date": state["start_date"],
            "due_date": state["due_date"],
            "scheduled_date": state["scheduled_date"],
            "duration_category": state.get("duration_category") or DurationCategory.MIN_20_TO_60,
            "schedule_is_manual": state.get("schedule_is_manual", False),
            "priority_restore_context": state.get("priority_restore_context", {}),
            "priority_position": state["priority_position"],
            "is_completed": state["is_completed"],
            "canvas_object_type": state["canvas_object_type"],
            "canvas_object_id": state["canvas_object_id"],
        }

        item = existing.get(state["id"])

        if item is None:
            item = PlanningItem(id=state["id"], **values)
            item.save(force_insert=True)
            existing[item.pk] = item
        else:
            for field, value in values.items():
                setattr(item, field, value)

            item.save()

    # Pass 2: hierarchy after all required rows exist.
    for state in states:
        item = existing[state["id"]]

        if item.parent_id != state["parent_id"]:
            item.parent_id = state["parent_id"]
            item.save(update_fields=["parent"])

    # Pass 3: M2M + assignment detail.
    for state in states:
        item = existing[state["id"]]

        item.tags.set(state["tag_ids"])

        detail = state["assignment_detail"]

        if detail is None:
            AssignmentDetail.objects.filter(
                planning_item=item
            ).delete()
        else:
            AssignmentDetail.objects.update_or_create(
                planning_item=item,
                defaults={
                    "weight_percent": detail["weight_percent"],
                    "submission_url": detail["submission_url"],
                },
            )


def _restore_priority(user, states):
    """Restore only priority positions represented in a checkpoint."""

    if states is None:
        return

    wanted = {
        state["id"]: state
        for state in states
    }

    if not wanted:
        return

    items = list(
        PlanningItem.objects.filter(
            user=user,
            pk__in=wanted.keys(),
        )
    )

    changed = []

    for item in items:
        state = wanted[item.pk]
        position = state["priority_position"]
        context = state.get("priority_restore_context", item.priority_restore_context)
        if item.priority_position != position or item.priority_restore_context != context:
            item.priority_position = position
            item.priority_restore_context = context
            changed.append(item)

    if changed:
        PlanningItem.objects.bulk_update(
            changed,
            ["priority_position", "priority_restore_context"],
        )


def _restore_siblings(user, states):
    """Restore sibling parent/order values represented by the delta."""

    if not states:
        return

    wanted = {state["id"]: state for state in states}

    items = list(
        PlanningItem.objects.filter(
            user=user,
            pk__in=wanted.keys(),
        )
    )

    changed = []

    for item in items:
        state = wanted[item.pk]

        if (
            item.parent_id != state["parent_id"]
            or item.sibling_order != state["sibling_order"]
        ):
            item.parent_id = state["parent_id"]
            item.sibling_order = state["sibling_order"]
            changed.append(item)

    if changed:
        PlanningItem.objects.bulk_update(
            changed,
            ["parent", "sibling_order"],
        )


def _apply_delta(user, state, action_type):
    """Apply one operation-scoped state payload."""

    if action_type == "PRIORITY":
        # Ignore legacy whole-hierarchy 'siblings' snapshots. New checkpoints
        # explicitly name leaf slots, and restoration cannot write containers.
        _restore_priority(user, state.get("priority"))
        _restore_leaf_order(user, state.get("leaf_siblings", []))
        return

    if action_type == "SCHEDULE":
        _restore_priority(user, state.get('priority'))
        _restore_leaf_order(user, state.get('leaf_siblings', []))
        for row in state.get('schedule', []):
            PlanningItem.objects.filter(user=user, pk=row['id']).update(
                scheduled_date=row['scheduled_date'], schedule_is_manual=row['schedule_is_manual'],
                priority_restore_context=row['priority_restore_context'],
            )
        SchedulingOverload.objects.filter(user=user).delete()
        SchedulingOverload.objects.bulk_create([
            SchedulingOverload(user=user, **row) for row in state.get('overload', [])
        ])
        if state.get('capacity'):
            SchedulingPreference.objects.update_or_create(user=user, defaults=state['capacity'][0])
        else:
            SchedulingPreference.objects.filter(user=user).delete()
        return

    # Soft-delete / restore existing rows in one bulk UPDATE.
    soft_delete = state.get("soft_delete")
    if soft_delete:
        PlanningItem.objects.filter(
            user=user,
            pk__in=soft_delete["ids"],
        ).update(is_deleted=soft_delete["value"])

    # Delete rows that should not exist in this state.
    delete_ids = state.get("delete_ids", [])

    if delete_ids:
        PlanningItem.objects.filter(
            user=user,
            pk__in=delete_ids,
        ).delete()

    # Restore/create complete item states where necessary.
    _restore_item_states(
        user,
        state.get("items", []),
    )

    # Restore lightweight structural deltas.
    _restore_siblings(
        user,
        state.get("siblings", []),
    )

    _restore_priority(
        user,
        state.get("priority"),
    )


# ---------------------------------------------------------------------------
# UNDO / REDO
# ---------------------------------------------------------------------------

@transaction.atomic
def undo(user):
    entry = (
        PlanningHistoryEntry.objects
        .select_for_update()
        .filter(user=user, is_undone=False)
        .order_by("-id")
        .first()
    )

    if entry is None:
        return None

    _apply_delta(user, entry.before_state, entry.action_type)

    entry.is_undone = True
    entry.save(update_fields=["is_undone"])

    return entry


@transaction.atomic
def redo(user):
    # Among undone entries, the lowest ID is the first operation
    # that must be reapplied.
    entry = (
        PlanningHistoryEntry.objects
        .select_for_update()
        .filter(user=user, is_undone=True)
        .order_by("id")
        .first()
    )

    if entry is None:
        return None

    _apply_delta(user, entry.after_state, entry.action_type)

    entry.is_undone = False
    entry.save(update_fields=["is_undone"])

    return entry


def history_status(user):
    history = PlanningHistoryEntry.objects.filter(user=user)

    return {
        "can_undo": history.filter(is_undone=False).exists(),
        "can_redo": history.filter(is_undone=True).exists(),
    }

================================================================================
FILE: backend/planning/services/leaf_order_sync.py
================================================================================
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

================================================================================
FILE: backend/planning/services/overdue.py
================================================================================
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

================================================================================
FILE: backend/planning/services/priority.py
================================================================================
"""The single global task priority order (FR-09).

Every active, actionable task of a user holds exactly one position, numbered
densely from 1, and no two share a number. Completed and non-actionable items
hold NULL. Keeping that invariant is entirely this module's job; the database
backs it up with uniq_user_priority_position.

That constraint is DEFERRABLE INITIALLY DEFERRED, which is what makes the
renumbering below straightforward: a reorder walks positions through states
that contain duplicates, and only the committed result has to be unique. An
immediate constraint would force each write to dodge its neighbour, usually by
shifting everything into a temporary offset range and back again.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from planning.models import PlanningItem


def ordered(user):
    """The user's positioned active tasks, highest priority first."""
    return (
        PlanningItem.objects.for_user(user)
        .actionable()
        .active()
        .exclude(priority_position=None)
        .order_by('priority_position', 'id')
    )


def _lock(user):
    """Serialise concurrent position writes for one user.

    Two simultaneous creates would otherwise read the same MAX and claim the
    same tail position.
    """
    get_user_model().objects.select_for_update().get(pk=user.pk)


@transaction.atomic
def assign_initial_position(task):
    """Place a newly active task at the end of the order.

    Does nothing for goals, completed items, or a task that already holds a
    position, so it is safe to call from a save path.
    """
    if not task.is_actionable or task.is_completed or task.priority_position is not None:
        return task.priority_position

    _lock(task.user)
    highest = (
        PlanningItem.objects.filter(user_id=task.user_id)
        .aggregate(Max('priority_position'))['priority_position__max']
    )
    task.priority_position = (highest or 0) + 1
    task.save(update_fields=['priority_position'])
    return task.priority_position


@transaction.atomic
def renumber(user):
    """Rewrite the order as a dense 1..n, preserving relative sequence."""
    items = list(ordered(user))
    changed = []
    for position, item in enumerate(items, start=1):
        if item.priority_position != position:
            item.priority_position = position
            changed.append(item)
    if changed:
        PlanningItem.objects.bulk_update(changed, ['priority_position'])
    return items


def _remember_departures(user, departing_ids):
    rows = list(PlanningItem.objects.filter(user=user, priority_position__isnull=False)
                .order_by('priority_position', 'pk'))
    ids = [row.pk for row in rows]
    changed = []
    for index, row in enumerate(rows):
        if row.pk in departing_ids:
            row.priority_restore_context = {'before': ids[:index], 'after': ids[index + 1:]}
            changed.append(row)
    if changed:
        PlanningItem.objects.bulk_update(changed, ['priority_restore_context'])


def _insert_restored(ordered_items, item):
    context = item.priority_restore_context
    ids = [row.pk for row in ordered_items]
    following = next((pk for pk in context.get('after', []) if pk in ids), None)
    preceding = next((pk for pk in reversed(context.get('before', [])) if pk in ids), None)
    index = ids.index(following) if following is not None else (ids.index(preceding) + 1 if preceding is not None else len(ids))
    ordered_items.insert(index, item)


def _inherit_departing_descendant_context(user, item, departing):
    """Give a newly exposed frontier ancestor its descendant's vacated slot.

    Existing restore history always wins. Otherwise, if a departing frontier
    item belongs to this item's descendant branch, inherit that item's saved
    neighbour anchors. This works for arbitrary hierarchy depth.
    """
    if item.priority_restore_context:
        return

    by_id = {
        row.pk: row
        for row in PlanningItem.objects.filter(user=user).only(
            'pk', 'parent_id', 'priority_restore_context'
        )
    }

    candidates = []

    for row in departing:
        current = row
        distance = 0

        while current.parent_id is not None:
            distance += 1

            if current.parent_id == item.pk:
                candidates.append((distance, row.pk, row))
                break

            current = by_id.get(current.parent_id)
            if current is None:
                break

    if not candidates:
        return

    # Nearest descendant wins; PK makes ties deterministic.
    _, _, source = min(candidates)

    item.priority_restore_context = dict(source.priority_restore_context or {})
    item.save(update_fields=['priority_restore_context'])


@transaction.atomic
def reconcile(user):
    """Make stored priority positions match current priority eligibility.

    Existing eligible tasks keep their relative order. Newly eligible tasks
    return near surviving anchors, or join the end without prior context.
    Ineligible tasks lose their position. The final order is
    dense from 1..n.
    """
    _lock(user)

    eligible_ids = set(
        PlanningItem.objects.for_user(user)
        .priority_eligible()
        .values_list('pk', flat=True)
    )

    departing_ids = set(PlanningItem.objects.filter(user=user, priority_position__isnull=False)
                        .exclude(pk__in=eligible_ids).values_list('pk', flat=True))
    _remember_departures(user, departing_ids)

    # Capture departing rows after their neighbour contexts have been stored.
    # A newly exposed ancestor can inherit the frontier neighbourhood vacated
    # by a descendant from the same hierarchy branch.
    departing = list(
        PlanningItem.objects.filter(user=user, pk__in=departing_ids)
        .only('pk', 'parent_id', 'priority_restore_context')
    )

    # Remove positions from tasks that are no longer eligible.
    PlanningItem.objects.filter(
        user_id=user.pk,
        priority_position__isnull=False,
    ).exclude(pk__in=eligible_ids).update(priority_position=None)

    # Preserve the relative order of existing eligible tasks.
    positioned = list(
        PlanningItem.objects.filter(
            user_id=user.pk,
            pk__in=eligible_ids,
            priority_position__isnull=False,
        ).order_by('priority_position', 'id')
    )

    # Restore prior neighbours when possible; genuinely new work joins the end.
    unpositioned = list(
        PlanningItem.objects.filter(
            user_id=user.pk,
            pk__in=eligible_ids,
            priority_position=None,
        ).order_by('id')
    )

    ordered_items = positioned
    for item in unpositioned:
        _inherit_departing_descendant_context(user, item, departing)
        _insert_restored(ordered_items, item)

    changed = []
    for position, item in enumerate(ordered_items, start=1):
        if item.priority_position != position:
            item.priority_position = position
            changed.append(item)

    if changed:
        PlanningItem.objects.bulk_update(changed, ['priority_position'])

    return ordered_items


@transaction.atomic
def reorder(user, item_id, new_position):
    """Move one task to a new row and close the gap it left behind.

    Positions outside the current range are clamped rather than rejected, so
    a drag past either end of the Priority View behaves the way it looks.
    """
    _lock(user)
    items = list(ordered(user).select_for_update())

    index = next((i for i, item in enumerate(items) if item.pk == item_id), None)
    if index is None:
        raise ValidationError('That task is not in the priority order.')

    moved = items.pop(index)
    target = max(1, min(int(new_position), len(items) + 1))
    items.insert(target - 1, moved)

    changed = []
    for position, item in enumerate(items, start=1):
        if item.priority_position != position:
            item.priority_position = position
            changed.append(item)
    if changed:
        # Passes through duplicate positions; legal only because the unique
        # constraint is deferred to COMMIT.
        PlanningItem.objects.bulk_update(changed, ['priority_position'])

    return items


@transaction.atomic
def release_position(task):
    """Drop a task out of the order, on completion or before deletion."""
    if task.priority_position is None:
        return
    _remember_departures(task.user, {task.pk})
    task.priority_position = None
    task.save(update_fields=['priority_position'])
    renumber(task.user)


@transaction.atomic
def release_positions(user, item_ids):
    """Remember and release priority for a whole subtree together."""
    _remember_departures(user, set(item_ids))
    PlanningItem.objects.filter(user=user, pk__in=item_ids).exclude(
        priority_position=None
    ).update(priority_position=None)
    renumber(user)


@transaction.atomic
def restore_position(task):
    """Return reopened work near its surviving priority neighbours."""
    if task.priority_position is not None:
        return task.priority_position
    reconcile(task.user)
    task.refresh_from_db(fields=['priority_position'])
    return task.priority_position

================================================================================
FILE: backend/planning/services/scheduling.py
================================================================================
"""Global, capacity-constrained execution dates and atomic Timeline operations."""
from collections import Counter
from datetime import timedelta

from django.db import transaction
from django.db.models import Exists, OuterRef
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


def _expire_past_manual_anchors(user, today):
    """Return expired manual anchors to automatic scheduling control.

    A manual scheduled date is a user placement preference, not a deadline.
    Once that date is in the past for unfinished active work, the anchor
    expires. The factual due_date is deliberately untouched.
    """
    expired = list(
        PlanningItem.objects.for_user(user)
        .filter(
            is_completed=False,
            is_deleted=False,
            schedule_is_manual=True,
            scheduled_date__lt=today,
        )
    )

    if not expired:
        return []

    for item in expired:
        item.schedule_is_manual = False

    PlanningItem.objects.bulk_update(expired, ['schedule_is_manual'])
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

================================================================================
FILE: backend/planning/tests/__init__.py
================================================================================

================================================================================
FILE: backend/planning/tests/conftest.py
================================================================================
"""Shared fixtures for the planning service tests."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from planning.models import ItemType, PlanningItem

User = get_user_model()


@pytest.fixture
def today():
    return timezone.localdate()


@pytest.fixture
def user(db):
    return User.objects.create_user('alice@example.com', 'corr3ct-horse-battery')


@pytest.fixture
def other_user(db):
    return User.objects.create_user('bob@example.com', 'corr3ct-horse-battery')


@pytest.fixture
def chain(user, make_item):
    """A three-deep line: a -> b -> c."""
    a = make_item(user, 'a', ItemType.GOAL)
    b = make_item(user, 'b', ItemType.GOAL, parent=a)
    c = make_item(user, 'c', ItemType.GOAL, parent=b)
    return a, b, c


def positions(user):
    """The user's priority order as a list of (position, title)."""
    return list(
        PlanningItem.objects.for_user(user)
        .exclude(priority_position=None)
        .order_by('priority_position')
        .values_list('priority_position', 'title')
    )

================================================================================
FILE: backend/planning/tests/test_api.py
================================================================================
"""Smoke tests for the planning API.

The rules themselves are tested against the services in the sibling modules.
These tests check the HTTP layer on top: status codes, payload shapes, the
custom actions, and above all that no endpoint will serve or accept another
user's rows (FR-03).
"""

import pyotp
import pytest
from freezegun import freeze_time

from accounts.tests.conftest import login_through_mfa, make_user
from planning.models import (
    AssignmentDetail,
    DurationCategory,
    ItemType,
    PlanningItem,
    Tag,
    Timezone,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def client(api_for, user):
    return api_for(user)


@pytest.fixture
def other_client(api_for, other_user):
    return api_for(other_user)


# --- Items: create, read, update, delete -----------------------------------

def test_creating_a_task_places_it_in_the_priority_order(client):
    response = client.post(
        '/api/planning/items/',
        {'item_type': ItemType.TASK, 'title': 'Read chapter 4'},
        format='json',
    )
    assert response.status_code == 201, response.data
    assert response.data['priority_position'] == 1
    assert response.data['has_deadline'] is False


def test_creating_a_goal_stays_out_of_the_priority_order(client):
    response = client.post(
        '/api/planning/items/',
        {'item_type': ItemType.GOAL, 'title': 'ELEC3609'},
        format='json',
    )
    assert response.status_code == 201, response.data
    assert response.data['priority_position'] is None


def test_a_new_item_is_numbered_after_its_siblings(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    make_item(user, 'first', parent=root)

    response = client.post(
        '/api/planning/items/',
        {'item_type': ItemType.TASK, 'title': 'second', 'parent': root.pk},
        format='json',
    )
    assert response.data['sibling_order'] == 2


def test_creating_an_assignment_with_nested_detail(client):
    response = client.post(
        '/api/planning/items/',
        {
            'item_type': ItemType.ASSIGNMENT,
            'title': 'Assignment 1',
            'due_date': '2026-10-01',
            'assignment_detail': {'weight_percent': '25.00', 'submission_url': 'https://x.test/a'},
        },
        format='json',
    )
    assert response.status_code == 201, response.data
    assert response.data['assignment_detail']['weight_percent'] == '25.00'
    assert response.data['assignment_detail']['mark_achieved'] is None


def test_assignment_detail_is_refused_on_a_plain_task(client):
    response = client.post(
        '/api/planning/items/',
        {
            'item_type': ItemType.TASK,
            'title': 'Not an assignment',
            'assignment_detail': {'weight_percent': '10.00'},
        },
        format='json',
    )
    assert response.status_code == 400


def test_a_due_date_before_the_start_date_is_refused(client):
    response = client.post(
        '/api/planning/items/',
        {
            'item_type': ItemType.TASK,
            'title': 'Backwards',
            'start_date': '2026-10-10',
            'due_date': '2026-10-01',
        },
        format='json',
    )
    assert response.status_code == 400


def test_tags_attach_and_detach_through_tag_ids(client, user, make_item):
    item = make_item(user, 'Tagged')
    reading = Tag.objects.create(user=user, name='reading')
    lab = Tag.objects.create(user=user, name='lab')

    response = client.patch(
        f'/api/planning/items/{item.pk}/',
        {'tag_ids': [reading.pk, lab.pk]},
        format='json',
    )
    assert response.status_code == 200, response.data
    assert {tag['name'] for tag in response.data['tags']} == {'lab', 'reading'}

    response = client.patch(
        f'/api/planning/items/{item.pk}/', {'tag_ids': []}, format='json'
    )
    assert response.data['tags'] == []


def test_priority_position_cannot_be_set_directly(client, user, make_item):
    make_item(user, 'first', priority_position=1)
    item = make_item(user, 'second', priority_position=2)

    response = client.patch(
        f'/api/planning/items/{item.pk}/', {'priority_position': 1}, format='json'
    )
    # Read-only on the serializer: the write is dropped rather than honoured,
    # because reordering has to go through /priority/reorder/ (FR-09).
    assert response.status_code == 200
    assert response.data['priority_position'] == 2


def test_deleting_an_item_keeps_the_order_dense(client, user, make_item):
    first = make_item(user, 'first', priority_position=1)
    make_item(user, 'second', priority_position=2)
    make_item(user, 'third', priority_position=3)

    assert client.delete(f'/api/planning/items/{first.pk}/').status_code == 204
    assert list(
        PlanningItem.objects.for_user(user)
        .exclude(priority_position=None)
        .order_by('priority_position')
        .values_list('priority_position', 'title')
    ) == [(1, 'second'), (2, 'third')]


# --- Items: filtering -------------------------------------------------------

def test_the_list_filters_by_type_and_completion(client, user, make_item):
    make_item(user, 'goal', ItemType.GOAL)
    make_item(user, 'open task')
    make_item(user, 'done task', is_completed=True)

    titles = lambda response: {row['title'] for row in response.data['results']}

    assert titles(client.get('/api/planning/items/?type=goal')) == {'goal'}
    assert titles(client.get('/api/planning/items/?completed=false')) == {'goal', 'open task'}
    assert titles(client.get('/api/planning/items/?completed=true')) == {'done task'}


def test_the_list_filters_to_one_root_subtree(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    child = make_item(user, 'week 1', parent=root)
    make_item(user, 'grandchild', parent=child)
    make_item(user, 'unrelated', ItemType.GOAL)

    response = client.get(f'/api/planning/items/?root={root.pk}')
    assert {row['title'] for row in response.data['results']} == {
        'ELEC3609', 'week 1', 'grandchild'
    }


def test_search_matches_title_and_tag_name(client, user, make_item):
    tagged = make_item(user, 'Unremarkable title')
    tagged.tags.add(Tag.objects.create(user=user, name='thermodynamics'))
    make_item(user, 'Thermodynamics reading')

    response = client.get('/api/planning/items/?search=thermo')
    assert len(response.data['results']) == 2


def test_a_search_hit_is_not_duplicated_by_its_tags(client, user, make_item):
    """Joining tags to search their names can fan a row out; distinct() is
    what keeps one item one result."""
    item = make_item(user, 'Reading week')
    for name in ('reading', 'reading-group'):
        item.tags.add(Tag.objects.create(user=user, name=name))

    response = client.get('/api/planning/items/?search=reading')
    assert len(response.data['results']) == 1


def test_a_bad_root_parameter_is_a_400_not_a_500(client):
    assert client.get('/api/planning/items/?root=abc').status_code == 400


# --- Items: tree ------------------------------------------------------------

def test_the_tree_nests_children_under_their_parent(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    week = make_item(user, 'Week 1', ItemType.GOAL, parent=root)
    make_item(user, 'Watch lecture', parent=week)

    response = client.get('/api/planning/items/tree/')
    assert response.status_code == 200

    assert len(response.data) == 1
    top = response.data[0]
    assert (top['title'], top['depth']) == ('ELEC3609', 0)
    assert (top['children'][0]['title'], top['children'][0]['depth']) == ('Week 1', 1)
    assert top['children'][0]['children'][0]['title'] == 'Watch lecture'


def test_the_tree_orders_siblings_by_sibling_order(client, user, make_item):
    root = make_item(user, 'root', ItemType.GOAL)
    make_item(user, 'third', parent=root, sibling_order=3)
    make_item(user, 'first', parent=root, sibling_order=1)
    make_item(user, 'second', parent=root, sibling_order=2)

    children = client.get('/api/planning/items/tree/').data[0]['children']
    assert [child['title'] for child in children] == ['first', 'second', 'third']


def test_the_tree_is_empty_for_a_new_account(client):
    response = client.get('/api/planning/items/tree/')
    assert response.status_code == 200
    assert response.data == []


def test_the_tree_never_includes_another_users_items(client, other_user, make_item):
    make_item(other_user, 'Their course', ItemType.GOAL)
    assert client.get('/api/planning/items/tree/').data == []


# --- Items: move ------------------------------------------------------------

def test_move_reparents_an_item(client, user, make_item):
    root = make_item(user, 'root', ItemType.GOAL)
    item = make_item(user, 'floating')

    response = client.post(
        f'/api/planning/items/{item.pk}/move/', {'parent_id': root.pk}, format='json'
    )
    assert response.status_code == 200, response.data
    assert response.data['parent'] == root.pk


def test_move_to_the_top_level_is_allowed(client, chain):
    _, _, c = chain
    response = client.post(
        f'/api/planning/items/{c.pk}/move/', {'parent_id': None}, format='json'
    )
    assert response.status_code == 200
    assert response.data['parent'] is None


def test_move_refuses_a_cycle(client, chain):
    """FR-06: a -> b -> c, so moving a under c would close the loop."""
    a, _, c = chain
    response = client.post(
        f'/api/planning/items/{a.pk}/move/', {'parent_id': c.pk}, format='json'
    )
    assert response.status_code == 400, response.data
    a.refresh_from_db()
    assert a.parent_id is None


def test_move_refuses_an_item_under_itself(client, user, make_item):
    item = make_item(user, 'lonely', ItemType.GOAL)
    response = client.post(
        f'/api/planning/items/{item.pk}/move/', {'parent_id': item.pk}, format='json'
    )
    assert response.status_code == 400


def test_move_refuses_another_users_parent(client, user, other_user, make_item):
    """FR-03: theirs is invisible, so naming it reads as a bad id, not as
    confirmation that it exists."""
    mine = make_item(user, 'mine')
    theirs = make_item(other_user, 'theirs', ItemType.GOAL)

    response = client.post(
        f'/api/planning/items/{mine.pk}/move/', {'parent_id': theirs.pk}, format='json'
    )
    assert response.status_code == 400
    mine.refresh_from_db()
    assert mine.parent_id is None


# --- Items: complete --------------------------------------------------------

def test_complete_cascades_to_the_whole_subtree(client, user, make_item):
    """FR-08."""
    root = make_item(user, 'root', ItemType.GOAL)
    child = make_item(user, 'child', parent=root)
    grandchild = make_item(user, 'grandchild', parent=child)

    response = client.post(f'/api/planning/items/{root.pk}/complete/', {}, format='json')
    assert response.status_code == 200, response.data
    assert set(response.data['affected_ids']) == {root.pk, child.pk, grandchild.pk}
    assert all(
        item.is_completed
        for item in PlanningItem.objects.filter(pk__in=[root.pk, child.pk, grandchild.pk])
    )


def test_completing_a_task_gives_up_its_priority_position(client, user, make_item):
    first = make_item(user, 'first', priority_position=1)
    make_item(user, 'second', priority_position=2)

    client.post(f'/api/planning/items/{first.pk}/complete/', {}, format='json')

    first.refresh_from_db()
    assert first.priority_position is None
    assert PlanningItem.objects.get(title='second').priority_position == 1


def test_reopening_does_not_cascade(client, user, make_item):
    root = make_item(user, 'root', ItemType.GOAL, is_completed=True)
    child = make_item(user, 'child', parent=root, is_completed=True)

    response = client.post(
        f'/api/planning/items/{root.pk}/complete/', {'completed': False}, format='json'
    )
    assert response.data['affected_ids'] == [root.pk]
    child.refresh_from_db()
    assert child.is_completed is True


def test_reopening_a_task_returns_it_to_the_priority_order(client, user, make_item):
    make_item(user, 'active', priority_position=1)
    done = make_item(user, 'done', is_completed=True)

    client.post(f'/api/planning/items/{done.pk}/complete/', {'completed': False},
                format='json')
    done.refresh_from_db()
    assert done.priority_position == 2


# --- Priority ---------------------------------------------------------------

def test_priority_lists_active_tasks_in_order_with_their_root(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    make_item(user, 'second', parent=root, priority_position=2,
              duration_category=DurationCategory.OVER_60_MIN)
    make_item(user, 'first', parent=root, priority_position=1)

    response = client.get('/api/planning/priority/')
    assert response.status_code == 200
    assert [(row['position'], row['title']) for row in response.data] == [
        (1, 'first'), (2, 'second')
    ]
    assert response.data[0]['root']['title'] == 'ELEC3609'


def test_priority_excludes_goals_and_completed_tasks(client, user, make_item):
    make_item(user, 'goal', ItemType.GOAL)
    make_item(user, 'done', is_completed=True)
    make_item(user, 'active', priority_position=1)

    response = client.get('/api/planning/priority/')
    assert [row['title'] for row in response.data] == ['active']


def test_reorder_moves_a_task_and_returns_the_whole_order(client, user, make_item):
    """FR-09."""
    for position, title in enumerate(['a', 'b', 'c', 'd'], start=1):
        make_item(user, title, priority_position=position)

    target = PlanningItem.objects.get(title='d')
    response = client.post(
        '/api/planning/priority/reorder/',
        {'item_id': target.pk, 'new_position': 1},
        format='json',
    )
    assert response.status_code == 200, response.data
    assert [row['title'] for row in response.data] == ['d', 'a', 'b', 'c']
    assert [row['position'] for row in response.data] == [1, 2, 3, 4]


def test_reorder_clamps_a_position_past_the_end(client, user, make_item):
    for position, title in enumerate(['a', 'b'], start=1):
        make_item(user, title, priority_position=position)

    target = PlanningItem.objects.get(title='a')
    response = client.post(
        '/api/planning/priority/reorder/',
        {'item_id': target.pk, 'new_position': 999},
        format='json',
    )
    assert [row['title'] for row in response.data] == ['b', 'a']


def test_reorder_refuses_an_unpositioned_item(client, user, make_item):
    goal = make_item(user, 'goal', ItemType.GOAL)
    response = client.post(
        '/api/planning/priority/reorder/',
        {'item_id': goal.pk, 'new_position': 1},
        format='json',
    )
    assert response.status_code == 400


def test_reorder_refuses_another_users_task(client, other_user, make_item):
    """FR-03: their order must be untouchable even by id."""
    theirs = make_item(other_user, 'theirs', priority_position=1)
    response = client.post(
        '/api/planning/priority/reorder/',
        {'item_id': theirs.pk, 'new_position': 1},
        format='json',
    )
    assert response.status_code == 400
    theirs.refresh_from_db()
    assert theirs.priority_position == 1


# --- Timeline ---------------------------------------------------------------

@freeze_time('2026-09-14')
def test_the_timeline_groups_dated_items_under_their_root(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    make_item(user, 'Quiz', parent=root, due_date='2026-09-16')
    make_item(user, 'Lab', parent=root, due_date='2026-09-15')

    response = client.get('/api/planning/timeline/')
    assert response.status_code == 200
    assert response.data['range']['from'] == '2026-09-07'
    assert response.data['range']['to'] == '2026-10-12'

    assert len(response.data['groups']) == 1
    group = response.data['groups'][0]
    assert group['root']['title'] == 'ELEC3609'
    assert [item['title'] for item in group['items']] == ['Quiz', 'Lab']


@freeze_time('2026-09-14')
def test_the_timeline_separates_execution_dates_and_deadlines(client, user, make_item):
    """FR-11: the client has to be able to tell a real deadline from an ARC
    suggestion."""
    make_item(user, 'Fixed', ItemType.GOAL)  # a root to group under
    make_item(user, 'Deadline', due_date='2026-09-20')
    make_item(user, 'Whenever', scheduled_date='2026-09-20')

    items = {
        item['title']: item
        for group in client.get('/api/planning/timeline/').data['groups']
        for item in group['items']
    }
    assert items['Deadline']['due_date'] == '2026-09-20'
    assert items['Deadline']['scheduled_date'] == '2026-09-14'
    assert items['Whenever']['due_date'] is None
    assert items['Whenever']['scheduled_date'] == '2026-09-14'  # daily global optimisation


@freeze_time('2026-09-14')
def test_the_timeline_honours_an_explicit_range(client, user, make_item):
    make_item(user, 'Inside', due_date='2026-09-20')
    make_item(user, 'Outside', due_date='2026-11-01')

    response = client.get('/api/planning/timeline/?from=2026-09-15&to=2026-09-30')
    titles = [item['title'] for group in response.data['groups'] for item in group['items']]
    assert titles == ['Inside']


def test_the_timeline_refuses_a_backwards_range(client):
    response = client.get('/api/planning/timeline/?from=2026-09-30&to=2026-09-01')
    assert response.status_code == 400


def test_the_timeline_refuses_an_unparseable_date(client):
    assert client.get('/api/planning/timeline/?from=soon&to=2026-09-30').status_code == 400


@freeze_time('2026-09-14')
def test_the_timeline_includes_overlapping_timezones(client, user):
    """FR-13."""
    Timezone.objects.create(
        user=user, title='Semester 2', start_date='2026-07-27', end_date='2026-11-01'
    )
    Timezone.objects.create(
        user=user, title='Summer break', start_date='2026-12-01', end_date='2027-02-01'
    )

    response = client.get('/api/planning/timeline/')
    assert [zone['title'] for zone in response.data['timezones']] == ['Semester 2']


@freeze_time('2026-09-14')
def test_reading_the_timeline_rolls_neglected_adaptive_tasks_forward(client, user, make_item):
    """FR-11: a task ARC scheduled for last week should not still sit in the
    past the next time the user looks."""
    stale = make_item(user, 'Neglected', scheduled_date='2026-09-01', priority_position=1)

    client.get('/api/planning/timeline/')

    stale.refresh_from_db()
    assert stale.scheduled_date.isoformat() == '2026-09-14'
    assert stale.due_date is None


@freeze_time('2026-09-14')
def test_the_timeline_never_includes_another_users_items(client, other_user, make_item):
    make_item(other_user, 'Their quiz', due_date='2026-09-15')
    assert client.get('/api/planning/timeline/').data['groups'] == []


# --- Overdue ----------------------------------------------------------------

@freeze_time('2026-09-14')
def test_overdue_splits_recent_from_backlog(client, user, make_item):
    """FR-12: the boundary is seven days."""
    make_item(user, 'Yesterday', due_date='2026-09-13')
    make_item(user, 'A week ago', due_date='2026-09-07')
    make_item(user, 'Ancient', due_date='2026-08-01')

    response = client.get('/api/planning/overdue/')
    assert response.status_code == 200
    assert [row['item']['title'] for row in response.data['recent']] == [
        'A week ago', 'Yesterday'
    ]
    assert [row['item']['title'] for row in response.data['backlog']] == ['Ancient']
    assert response.data['recent'][1]['days_overdue'] == 1


@freeze_time('2026-09-14')
def test_overdue_reports_the_hierarchy_path(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    week = make_item(user, 'Week 5', ItemType.GOAL, parent=root)
    make_item(user, 'Quiz', parent=week, due_date='2026-09-13')

    row = client.get('/api/planning/overdue/').data['recent'][0]
    assert row['hierarchy_path'] == ['ELEC3609', 'Week 5', 'Quiz']


@freeze_time('2026-09-14')
def test_adaptive_and_completed_items_are_never_overdue(client, user, make_item):
    """FR-11 and FR-12: an adaptive task has no deadline to miss."""
    make_item(user, 'Adaptive', scheduled_date='2026-09-01')
    make_item(user, 'Done', due_date='2026-09-01', is_completed=True)
    make_item(user, 'Goal', ItemType.GOAL, due_date='2026-09-01')

    response = client.get('/api/planning/overdue/')
    assert response.data == {'recent': [], 'backlog': []}


@freeze_time('2026-09-14')
def test_overdue_never_includes_another_users_items(client, other_user, make_item):
    make_item(other_user, 'Their missed quiz', due_date='2026-09-01')
    assert client.get('/api/planning/overdue/').data == {'recent': [], 'backlog': []}


# --- Marks ------------------------------------------------------------------

def test_marks_group_by_subject_and_total_only_what_is_marked(client, user, make_item):
    """FR-14: an unmarked assessment is unmarked, not zero."""
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    marked = make_item(user, 'Assignment 1', ItemType.ASSIGNMENT, parent=root)
    unmarked = make_item(user, 'Assignment 2', ItemType.ASSIGNMENT, parent=root)
    AssignmentDetail.objects.create(
        planning_item=marked, weight_percent='25.00', mark_achieved='18.50'
    )
    AssignmentDetail.objects.create(planning_item=unmarked, weight_percent='30.00')

    response = client.get('/api/planning/marks/')
    assert response.status_code == 200

    group = response.data[0]
    assert group['root']['title'] == 'ELEC3609'
    assert group['total_weight'] == '55.00'
    assert group['total_marks'] == '18.50'
    assert group['unmarked_count'] == 1
    assert group['assessments'][1]['mark_achieved'] is None


def test_marks_separate_one_subject_from_another(client, user, make_item):
    for title in ('ELEC3609', 'COMP2123'):
        root = make_item(user, title, ItemType.GOAL)
        make_item(user, f'{title} quiz', ItemType.ASSIGNMENT, parent=root)

    response = client.get('/api/planning/marks/')
    assert [group['root']['title'] for group in response.data] == ['COMP2123', 'ELEC3609']


def test_an_assignment_without_detail_still_appears(client, user, make_item):
    """Canvas gives ARC assignments with no weighting, and those must not
    vanish from the Marks View."""
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    make_item(user, 'Imported quiz', ItemType.ASSIGNMENT, parent=root)

    group = client.get('/api/planning/marks/').data[0]
    assert group['assessments'][0]['title'] == 'Imported quiz'
    assert group['assessments'][0]['weight_percent'] is None
    assert group['unmarked_count'] == 1


def test_marks_are_empty_without_assignments(client, user, make_item):
    make_item(user, 'Just a task')
    assert client.get('/api/planning/marks/').data == []


def test_marks_reorder_renumbers_the_group(client, user, make_item):
    root = make_item(user, 'ELEC3609', ItemType.GOAL)
    details = []
    for title in ('a', 'b', 'c'):
        item = make_item(user, title, ItemType.ASSIGNMENT, parent=root)
        details.append(AssignmentDetail.objects.create(planning_item=item))

    ordered_ids = [details[2].pk, details[0].pk, details[1].pk]
    response = client.post(
        '/api/planning/marks/reorder/', {'ordered_ids': ordered_ids}, format='json'
    )
    assert response.status_code == 200, response.data
    assert response.data == {'reordered': 3}

    group = client.get('/api/planning/marks/').data[0]
    assert [row['title'] for row in group['assessments']] == ['c', 'a', 'b']


def test_marks_reorder_refuses_another_users_assessment(client, other_user, make_item):
    """FR-03."""
    theirs = make_item(other_user, 'theirs', ItemType.ASSIGNMENT)
    detail = AssignmentDetail.objects.create(planning_item=theirs, marks_position=1)

    response = client.post(
        '/api/planning/marks/reorder/', {'ordered_ids': [detail.pk]}, format='json'
    )
    assert response.status_code == 400
    detail.refresh_from_db()
    assert detail.marks_position == 1


def test_a_mark_can_be_recorded_through_the_detail_endpoint(client, user, make_item):
    item = make_item(user, 'Assignment 1', ItemType.ASSIGNMENT)
    AssignmentDetail.objects.create(planning_item=item, weight_percent='25.00')

    response = client.patch(
        f'/api/planning/assignment-details/{item.pk}/',
        {'mark_achieved': '21.00'},
        format='json',
    )
    assert response.status_code == 200, response.data
    assert response.data['mark_achieved'] == '21.00'


def test_another_users_assignment_detail_is_a_404(other_client, user, make_item):
    """FR-03: 404 rather than 403, so the API does not confirm it exists."""
    item = make_item(user, 'Assignment 1', ItemType.ASSIGNMENT)
    AssignmentDetail.objects.create(planning_item=item)

    response = other_client.patch(
        f'/api/planning/assignment-details/{item.pk}/',
        {'mark_achieved': '100.00'},
        format='json',
    )
    assert response.status_code == 404


# --- Tags and timezones -----------------------------------------------------

def test_a_duplicate_tag_name_is_a_400_not_a_500(client, user):
    Tag.objects.create(user=user, name='reading')
    response = client.post('/api/planning/tags/', {'name': 'Reading'}, format='json')
    assert response.status_code == 400


def test_two_users_may_hold_the_same_tag_name(client, other_user):
    Tag.objects.create(user=other_user, name='reading')
    response = client.post('/api/planning/tags/', {'name': 'reading'}, format='json')
    assert response.status_code == 201


def test_a_tag_id_from_another_user_is_refused(client, other_user, make_item, user):
    theirs = Tag.objects.create(user=other_user, name='theirs')
    response = client.post(
        '/api/planning/items/',
        {'item_type': ItemType.TASK, 'title': 'Mine', 'tag_ids': [theirs.pk]},
        format='json',
    )
    assert response.status_code == 400


def test_a_timezone_cannot_end_before_it_starts(client):
    response = client.post(
        '/api/planning/timezones/',
        {'title': 'Backwards', 'start_date': '2026-10-01', 'end_date': '2026-09-01'},
        format='json',
    )
    assert response.status_code == 400


def test_overlapping_timezones_are_allowed(client):
    """FR-13: a teaching week sits inside a semester, so overlap is normal."""
    payload = {'start_date': '2026-07-27', 'end_date': '2026-11-01'}
    assert client.post(
        '/api/planning/timezones/', {'title': 'Semester 2', **payload}, format='json'
    ).status_code == 201
    assert client.post(
        '/api/planning/timezones/',
        {'title': 'Week 5', 'start_date': '2026-08-24', 'end_date': '2026-08-30'},
        format='json',
    ).status_code == 201


# --- Isolation and authentication ------------------------------------------

def test_every_planning_endpoint_refuses_an_anonymous_request(db, api):
    for path in (
        '/api/planning/items/',
        '/api/planning/items/tree/',
        '/api/planning/tags/',
        '/api/planning/timezones/',
        '/api/planning/priority/',
        '/api/planning/timeline/',
        '/api/planning/overdue/',
        '/api/planning/marks/',
    ):
        assert api.get(path).status_code == 401, path


def test_the_item_list_shows_only_your_own_items(client, user, other_user, make_item):
    """FR-03: identically titled rows for two users is exactly the case a
    naive queryset would leak."""
    mine = make_item(user, 'Read chapter 4')
    make_item(other_user, 'Read chapter 4')

    response = client.get('/api/planning/items/')
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == mine.pk


def test_another_users_item_is_a_404(client, other_user, make_item):
    theirs = make_item(other_user, 'theirs')
    assert client.get(f'/api/planning/items/{theirs.pk}/').status_code == 404
    assert client.delete(f'/api/planning/items/{theirs.pk}/').status_code == 404
    assert client.patch(
        f'/api/planning/items/{theirs.pk}/', {'title': 'hijacked'}, format='json'
    ).status_code == 404
    theirs.refresh_from_db()
    assert theirs.title == 'theirs'


def test_a_real_bearer_token_reaches_the_planning_api(api, db, make_item):
    """The rest of this module force-authenticates; this one proves the
    ArcJWTAuthentication wiring works end to end."""
    secret = pyotp.random_base32()
    user = make_user('token@example.com', secret)
    make_item(user, 'Read chapter 4')

    tokens = login_through_mfa(api, user, secret)
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

    response = api.get('/api/planning/items/')
    assert response.status_code == 200
    assert response.data['results'][0]['title'] == 'Read chapter 4'

================================================================================
FILE: backend/planning/tests/test_hierarchy.py
================================================================================
"""Cycle prevention and cascade completion (FR-06, FR-08)."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from planning.models import ItemType, PlanningItem
from planning.services import hierarchy

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------
# Cycle prevention (FR-06)
# --------------------------------------------------------------------------

def test_a_root_parent_is_always_allowed(chain):
    a, _, _ = chain
    assert hierarchy.validate_parent(a, None) is None


def test_a_normal_nesting_is_allowed(user, make_item, chain):
    a, _, c = chain
    loose = make_item(user, 'loose')
    assert hierarchy.validate_parent(loose, c) is None


def test_an_item_cannot_be_its_own_parent(chain):
    a, _, _ = chain
    with pytest.raises(ValidationError, match='its own parent'):
        hierarchy.validate_parent(a, a)


def test_an_item_cannot_move_under_its_direct_child(chain):
    a, b, _ = chain
    with pytest.raises(ValidationError, match='its own ancestor'):
        hierarchy.validate_parent(a, b)


def test_an_item_cannot_move_under_a_distant_descendant(chain):
    """The a -> b -> c -> a case: c is two levels below a, so parenting a
    under c would close the loop."""
    a, _, c = chain
    with pytest.raises(ValidationError, match='its own ancestor'):
        hierarchy.validate_parent(a, c)


def test_a_middle_item_cannot_move_under_its_own_descendant(chain):
    _, b, c = chain
    with pytest.raises(ValidationError, match='its own ancestor'):
        hierarchy.validate_parent(b, c)


def test_a_descendant_may_move_up_to_the_root(chain):
    a, _, c = chain
    assert hierarchy.validate_parent(c, a) is None


def test_an_item_cannot_be_parented_under_another_users_item(user, other_user, make_item):
    mine = make_item(user, 'mine')
    theirs = make_item(other_user, 'theirs')
    with pytest.raises(ValidationError, match="another user's item"):
        hierarchy.validate_parent(mine, theirs)


def test_an_unsaved_item_can_be_parented_anywhere_in_its_own_tree(user, chain):
    a, _, c = chain
    fresh = PlanningItem(user=user, title='fresh', item_type=ItemType.TASK)
    assert hierarchy.validate_parent(fresh, c) is None


def test_nesting_deeper_than_max_depth_is_refused(user, make_item, monkeypatch):
    monkeypatch.setattr(hierarchy, 'MAX_DEPTH', 4)
    parent = None
    for index in range(4):
        parent = make_item(user, f'level-{index}', ItemType.GOAL, parent=parent)

    with pytest.raises(ValidationError, match='levels deep'):
        hierarchy.validate_parent(make_item(user, 'too-deep'), parent)


def test_the_database_refuses_a_self_parent_even_without_the_service(chain):
    """The check constraint is the backstop if a future code path forgets to
    call validate_parent."""
    a, _, _ = chain
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PlanningItem.objects.filter(pk=a.pk).update(parent_id=a.pk)


# --------------------------------------------------------------------------
# set_parent and sibling ordering
# --------------------------------------------------------------------------

def test_set_parent_moves_the_item_and_renumbers_both_sides(user, make_item):
    left = make_item(user, 'left', ItemType.GOAL)
    right = make_item(user, 'right', ItemType.GOAL)
    first = make_item(user, 'first', parent=left)
    second = make_item(user, 'second', parent=left)

    hierarchy.set_parent(first, right)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.parent_id == right.pk
    # 'second' was number 2 and is now the only child, so it becomes 1.
    assert second.sibling_order == 1
    assert first.sibling_order == 1


def test_set_parent_refuses_a_cycle(chain):
    a, _, c = chain
    with pytest.raises(ValidationError):
        hierarchy.set_parent(a, c)
    a.refresh_from_db()
    assert a.parent_id is None


def test_reindex_siblings_closes_gaps(user, make_item):
    root = make_item(user, 'root', ItemType.GOAL)
    children = [make_item(user, f'child-{i}', parent=root) for i in range(4)]
    PlanningItem.objects.filter(pk=children[1].pk).update(sibling_order=99)

    hierarchy.reindex_siblings(user, root)

    orders = list(
        PlanningItem.objects.filter(parent=root).order_by('sibling_order')
        .values_list('sibling_order', flat=True)
    )
    assert orders == [1, 2, 3, 4]


def test_reindex_siblings_handles_roots(user, make_item):
    make_item(user, 'r1', ItemType.GOAL)
    second = make_item(user, 'r2', ItemType.GOAL)
    PlanningItem.objects.filter(pk=second.pk).update(sibling_order=50)

    hierarchy.reindex_siblings(user, None)

    orders = list(
        PlanningItem.objects.filter(parent=None).order_by('sibling_order')
        .values_list('sibling_order', flat=True)
    )
    assert orders == [1, 2]


# --------------------------------------------------------------------------
# Cascade completion (FR-08)
# --------------------------------------------------------------------------

def test_completing_a_parent_completes_every_descendant(user, make_item):
    root = make_item(user, 'root', ItemType.GOAL)
    mid = make_item(user, 'mid', ItemType.GOAL, parent=root)
    leaf = make_item(user, 'leaf', parent=mid)
    sibling_leaf = make_item(user, 'sibling-leaf', parent=root)

    hierarchy.complete_subtree(root)

    for item in (root, mid, leaf, sibling_leaf):
        item.refresh_from_db()
        assert item.is_completed is True


def test_completing_a_subtree_leaves_the_rest_alone(user, make_item):
    root = make_item(user, 'root', ItemType.GOAL)
    inside = make_item(user, 'inside', parent=root)
    outside = make_item(user, 'outside')

    hierarchy.complete_subtree(root)

    inside.refresh_from_db()
    outside.refresh_from_db()
    assert inside.is_completed is True
    assert outside.is_completed is False


def test_completing_a_task_releases_its_priority_position(user, make_item):
    from planning.services import priority

    first = make_item(user, 'first')
    second = make_item(user, 'second')
    third = make_item(user, 'third')
    for task in (first, second, third):
        priority.assign_initial_position(task)

    hierarchy.complete_subtree(second)

    second.refresh_from_db()
    assert second.priority_position is None
    # The survivors close the gap rather than leaving a hole at 2.
    assert sorted(
        PlanningItem.objects.for_user(user)
        .exclude(priority_position=None)
        .values_list('priority_position', flat=True)
    ) == [1, 2]


def test_completion_does_not_cross_into_another_user(user, other_user, make_item):
    mine = make_item(user, 'shared-title', ItemType.GOAL)
    theirs = make_item(other_user, 'shared-title', ItemType.GOAL)

    hierarchy.complete_subtree(mine)

    theirs.refresh_from_db()
    assert theirs.is_completed is False


def test_reopening_restores_a_priority_position(user, make_item):
    from planning.services import priority

    task = make_item(user, 'task')
    priority.assign_initial_position(task)
    hierarchy.complete_subtree(task)

    hierarchy.reopen(task)

    task.refresh_from_db()
    assert task.is_completed is False
    assert task.priority_position == 1


def test_reopening_a_parent_does_not_reopen_its_children(user, make_item):
    root = make_item(user, 'root', ItemType.GOAL)
    child = make_item(user, 'child', parent=root)
    hierarchy.complete_subtree(root)

    hierarchy.reopen(root)

    root.refresh_from_db()
    child.refresh_from_db()
    assert root.is_completed is False
    assert child.is_completed is True

================================================================================
FILE: backend/planning/tests/test_history.py
================================================================================
import pytest

from planning.models import PlanningHistoryEntry, PlanningItem
from planning.services import history


pytestmark = pytest.mark.django_db


def make_item(user, title, parent=None, sibling_order=0, completed=False):
    return PlanningItem.objects.create(
        user=user,
        title=title,
        item_type="TASK",
        parent=parent,
        sibling_order=sibling_order,
        is_completed=completed,
    )


def checkpoint(user, action, before, after):
    return history.record_checkpoint(user, action, before, after)


@pytest.mark.parametrize("action_type", ["PRIORITY", "MOVE"])
def test_legacy_priority_history_ignores_siblings_but_move_restores_them(user, action_type):
    first = make_item(user, "First", sibling_order=10)
    second = make_item(user, "Second", sibling_order=20)
    PlanningItem.objects.filter(pk=first.pk).update(priority_position=2)
    PlanningItem.objects.filter(pk=second.pk).update(priority_position=1)
    before = {
        "priority": [
            {"id": first.pk, "priority_position": 1},
            {"id": second.pk, "priority_position": 2},
        ],
        "siblings": [
            {"id": first.pk, "parent_id": None, "sibling_order": 2},
            {"id": second.pk, "parent_id": None, "sibling_order": 1},
        ],
    }
    after = {
        "priority": history.capture_priority(user),
        "siblings": [
            {"id": first.pk, "parent_id": None, "sibling_order": 1},
            {"id": second.pk, "parent_id": None, "sibling_order": 2},
        ],
    }
    entry = checkpoint(user, action_type, before, after)

    for restore, expected, undone in [(history.undo, before, True), (history.redo, after, False)]:
        assert restore(user).pk == entry.pk
        assert history.capture_priority(user) == expected["priority"]
        first.refresh_from_db()
        second.refresh_from_db()
        assert (first.parent_id, second.parent_id) == (None, None)
        assert (first.sibling_order, second.sibling_order) == (
            (10, 20) if action_type == "PRIORITY" else
            tuple(state["sibling_order"] for state in expected["siblings"])
        )
        entry.refresh_from_db()
        assert entry.is_undone is undone
        assert entry.before_state == before
        assert entry.after_state == after


def test_update_undo_redo(user):
    item = make_item(user, "Before")

    before = history.capture_items(user, [item.pk])

    item.title = "After"
    item.save(update_fields=["title"])

    after = history.capture_items(user, [item.pk])
    checkpoint(user, "UPDATE", {"items": before}, {"items": after})

    history.undo(user)
    item.refresh_from_db()
    assert item.title == "Before"

    history.redo(user)
    item.refresh_from_db()
    assert item.title == "After"


def test_create_undo_redo(user):
    item = make_item(user, "Created")
    item_id = item.pk

    created = history.capture_items(user, [item_id])

    checkpoint(
        user,
        "CREATE",
        {"delete_ids": [item_id]},
        {"items": created},
    )

    history.undo(user)
    assert not PlanningItem.objects.filter(pk=item_id).exists()

    history.redo(user)
    restored = PlanningItem.objects.get(pk=item_id)
    assert restored.title == "Created"


def test_delete_subtree_undo_redo(user):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)

    ids = [parent.pk, child.pk]

    # DELETE now preserves the actual rows and hides them.
    PlanningItem.objects.filter(pk__in=ids).update(is_deleted=True)

    checkpoint(
        user,
        "DELETE",
        {
            "soft_delete": {
                "ids": ids,
                "value": False,
            },
        },
        {
            "soft_delete": {
                "ids": ids,
                "value": True,
            },
        },
    )

    assert PlanningItem.objects.filter(
        pk__in=ids,
        is_deleted=True,
    ).count() == 2

    history.undo(user)

    restored_parent = PlanningItem.objects.get(pk=parent.pk)
    restored_child = PlanningItem.objects.get(pk=child.pk)

    assert restored_parent.is_deleted is False
    assert restored_child.is_deleted is False
    assert restored_child.parent_id == restored_parent.pk

    history.redo(user)

    assert PlanningItem.objects.filter(
        pk__in=ids,
        is_deleted=True,
    ).count() == 2


def test_move_undo_redo(user):
    root_a = make_item(user, "A", sibling_order=0)
    root_b = make_item(user, "B", sibling_order=1)
    child = make_item(user, "Child", parent=root_a, sibling_order=0)

    before = history.capture_items(user, [child.pk])

    child.parent = root_b
    child.sibling_order = 0
    child.save(update_fields=["parent", "sibling_order"])

    after = history.capture_items(user, [child.pk])

    checkpoint(
        user,
        "MOVE",
        {"items": before},
        {"items": after},
    )

    history.undo(user)
    child.refresh_from_db()
    assert child.parent_id == root_a.pk

    history.redo(user)
    child.refresh_from_db()
    assert child.parent_id == root_b.pk


def test_completion_states_undo_redo(user):
    parent = make_item(user, "Parent", completed=False)
    child = make_item(user, "Child", parent=parent, completed=False)

    ids = [parent.pk, child.pk]
    before = history.capture_items(user, ids)

    PlanningItem.objects.filter(pk__in=ids).update(is_completed=True)

    after = history.capture_items(user, ids)

    checkpoint(
        user,
        "COMPLETE",
        {"items": before},
        {"items": after},
    )

    history.undo(user)

    assert not PlanningItem.objects.get(pk=parent.pk).is_completed
    assert not PlanningItem.objects.get(pk=child.pk).is_completed

    history.redo(user)

    assert PlanningItem.objects.get(pk=parent.pk).is_completed
    assert PlanningItem.objects.get(pk=child.pk).is_completed


def test_new_action_after_undo_discards_redo_branch(user):
    item = make_item(user, "A")

    before_a = history.capture_items(user, [item.pk])
    item.title = "B"
    item.save(update_fields=["title"])
    after_b = history.capture_items(user, [item.pk])

    checkpoint(user, "UPDATE", {"items": before_a}, {"items": after_b})

    history.undo(user)

    item.refresh_from_db()
    before_c = history.capture_items(user, [item.pk])

    item.title = "C"
    item.save(update_fields=["title"])
    after_c = history.capture_items(user, [item.pk])

    checkpoint(user, "UPDATE", {"items": before_c}, {"items": after_c})

    assert not PlanningHistoryEntry.objects.filter(
        user=user,
        is_undone=True,
    ).exists()

    assert history.redo(user) is None


def test_history_is_capped_at_100(user):
    item = make_item(user, "Start")

    for i in range(105):
        before = history.capture_items(user, [item.pk])

        item.title = f"Edit {i}"
        item.save(update_fields=["title"])

        after = history.capture_items(user, [item.pk])

        checkpoint(
            user,
            "UPDATE",
            {"items": before},
            {"items": after},
        )

    assert PlanningHistoryEntry.objects.filter(user=user).count() == 100


def test_history_status(user):
    item = make_item(user, "A")

    before = history.capture_items(user, [item.pk])
    item.title = "B"
    item.save(update_fields=["title"])
    after = history.capture_items(user, [item.pk])

    checkpoint(user, "UPDATE", {"items": before}, {"items": after})

    assert history.history_status(user) == {
        "can_undo": True,
        "can_redo": False,
    }

    history.undo(user)

    assert history.history_status(user) == {
        "can_undo": False,
        "can_redo": True,
    }


def test_discarded_redo_delete_does_not_remove_restored_rows(user):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)
    ids = [parent.pk, child.pk]

    PlanningItem.objects.filter(pk__in=ids).update(is_deleted=True)

    checkpoint(
        user,
        "DELETE",
        {
            "soft_delete": {"ids": ids, "value": False},
        },
        {
            "soft_delete": {"ids": ids, "value": True},
        },
    )

    # Restore subtree; DELETE checkpoint is now on redo branch.
    history.undo(user)

    assert PlanningItem.objects.filter(
        pk__in=ids,
        is_deleted=False,
    ).count() == 2

    # New action destroys redo branch and triggers GC.
    other = make_item(user, "Other")

    before = history.capture_items(user, [other.pk])
    other.title = "Changed"
    other.save(update_fields=["title"])
    after = history.capture_items(user, [other.pk])

    checkpoint(
        user,
        "UPDATE",
        {"items": before},
        {"items": after},
    )

    # Because the deleted subtree had been restored, GC must keep it.
    assert PlanningItem.objects.filter(pk__in=ids).count() == 2


def test_pruned_delete_hard_deletes_still_deleted_rows(user):
    doomed = make_item(user, "Doomed")
    doomed_id = doomed.pk

    PlanningItem.objects.filter(pk=doomed_id).update(is_deleted=True)

    checkpoint(
        user,
        "DELETE",
        {
            "soft_delete": {
                "ids": [doomed_id],
                "value": False,
            },
        },
        {
            "soft_delete": {
                "ids": [doomed_id],
                "value": True,
            },
        },
    )

    other = make_item(user, "Other")

    # Push the DELETE checkpoint beyond the 100-entry history boundary.
    for i in range(100):
        before = history.capture_items(user, [other.pk])

        other.title = f"Change {i}"
        other.save(update_fields=["title"])

        after = history.capture_items(user, [other.pk])

        checkpoint(
            user,
            "UPDATE",
            {"items": before},
            {"items": after},
        )

    assert PlanningHistoryEntry.objects.filter(user=user).count() == 100

    # DELETE checkpoint is gone and its row was still soft-deleted,
    # therefore it is now permanently unreachable and should be gone.
    assert not PlanningItem.objects.filter(pk=doomed_id).exists()

================================================================================
FILE: backend/planning/tests/test_independent_ordering.py
================================================================================
"""Container organisation is independent; eligible sibling leaves share priority order."""

import pytest

from planning.models import ItemType, PlanningHistoryEntry, PlanningItem
from planning.services import history

pytestmark = pytest.mark.django_db


def sibling_state(user):
    return list(PlanningItem.objects.filter(user=user).order_by('pk').values_list(
        'pk', 'parent_id', 'sibling_order',
    ))


def planner_order(client):
    response = client.get('/api/planning/items/tree/')
    assert response.status_code == 200, response.data

    def structure(nodes):
        return [(node['id'], node['sibling_order'], structure(node['children'])) for node in nodes]

    return structure(response.data)


def test_priority_reorder_and_history_leave_containers_unchanged(user, other_user, api_for, make_item):
    client = api_for(user)
    root_z = make_item(user, 'Z root', ItemType.GOAL, sibling_order=1)
    root_a = make_item(user, 'A root', ItemType.GOAL, sibling_order=2)
    first = make_item(user, 'First', parent=root_a, sibling_order=1, priority_position=1)
    second = make_item(user, 'Second', parent=root_z, sibling_order=1, priority_position=2)
    third = make_item(user, 'Third', parent=root_a, sibling_order=2, priority_position=3)
    make_item(other_user, 'Other', sibling_order=7, priority_position=1)
    siblings_before = sibling_state(user)
    other_before = list(PlanningItem.objects.filter(user=other_user).values())
    tree_before = planner_order(client)
    before = history.capture_priority(user)

    response = client.post('/api/planning/priority/reorder/', {
        'item_id': third.pk, 'new_position': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    assert [(row['item_id'], row['position']) for row in response.data] == [
        (third.pk, 1), (first.pk, 2), (second.pk, 3),
    ]
    after = history.capture_priority(user)
    assert after == [
        {'id': third.pk, 'priority_position': 1},
        {'id': first.pk, 'priority_position': 2},
        {'id': second.pk, 'priority_position': 3},
    ]
    entry = PlanningHistoryEntry.objects.get(user=user)
    assert entry.action_type == 'PRIORITY'
    assert entry.before_state['priority'] == before
    assert entry.after_state['priority'] == after
    assert 'leaf_siblings' in entry.before_state
    siblings_after = sibling_state(user)
    tree_after = planner_order(client)
    assert siblings_after != siblings_before
    assert tree_after[1][2][0][0] == third.pk
    assert [(node[0], node[1]) for node in tree_after] == [(node[0], node[1]) for node in tree_before]

    for action, expected, undone in [('undo', before, True), ('redo', after, False)]:
        response = client.post(f'/api/planning/items/{action}/', {}, format='json')
        assert response.status_code == 200, response.data
        assert response.data['changed'] is True
        assert response.data['action_type'] == 'PRIORITY'
        assert history.capture_priority(user) == expected
        assert sibling_state(user) == (siblings_before if undone else siblings_after)
        assert planner_order(client) == (tree_before if undone else tree_after)
        assert list(PlanningItem.objects.filter(user=other_user).values()) == other_before
        entry.refresh_from_db()
        assert entry.is_undone is undone
    assert PlanningHistoryEntry.objects.filter(user=user).count() == 1
    assert not PlanningHistoryEntry.objects.filter(user=other_user).exists()


@pytest.mark.parametrize('reparent', [False, True])
def test_planner_leaf_move_updates_only_required_priority(
    user, api_for, make_item, reparent,
):
    client = api_for(user)
    root = make_item(user, 'Root', ItemType.GOAL, sibling_order=1)
    destination = make_item(user, 'Destination', ItemType.GOAL, sibling_order=2) if reparent else root
    first = make_item(user, 'Alpha', parent=root, sibling_order=1, priority_position=1)
    last = make_item(user, 'Zulu', parent=root, sibling_order=2, priority_position=2)
    priority_before = history.capture_priority(user)

    response = client.post(f'/api/planning/items/{last.pk}/move/', {
        'parent_id': destination.pk, 'sibling_order': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    last.refresh_from_db()
    assert (last.parent_id, last.sibling_order) == (destination.pk, 1)
    response = client.get('/api/planning/items/tree/')
    assert response.status_code == 200
    node = next(node for node in response.data if node['id'] == destination.pk)
    assert [child['id'] for child in node['children']] == (
        [last.pk] if reparent else [last.pk, first.pk]
    )
    assert history.capture_priority(user) == (priority_before if reparent else [
        {'id': last.pk, 'priority_position': 1},
        {'id': first.pk, 'priority_position': 2},
    ])


def test_create_complete_reopen_and_delete_reconcile_parent_eligibility(user, api_for, make_item):
    client = api_for(user)
    parent = make_item(user, 'Parent', priority_position=1)
    existing = make_item(user, 'Existing', priority_position=2)

    def assert_priority(*items):
        assert history.capture_priority(user) == [
            {'id': item_id, 'priority_position': position}
            for position, item_id in enumerate(items, start=1)
        ]
        assert set(PlanningItem.objects.for_user(user).priority_eligible()
                   .values_list('pk', flat=True)) == set(items)
        parent.refresh_from_db()
        assert parent.is_completed is False
        assert parent.priority_position == (items.index(parent.pk) + 1 if parent.pk in items else None)

    response = client.post('/api/planning/items/', {
        'title': 'Child', 'item_type': 'TASK', 'parent': parent.pk,
    }, format='json')
    assert response.status_code == 201, response.data
    child_id = response.data['id']
    assert_priority(existing.pk, child_id)

    for completed, expected in [(True, (parent.pk, existing.pk)), (False, (existing.pk, child_id))]:
        response = client.post(f'/api/planning/items/{child_id}/complete/', {
            'completed': completed,
        }, format='json')
        assert response.status_code == 200, response.data
        assert_priority(*expected)

    response = client.delete(f'/api/planning/items/{child_id}/')
    assert response.status_code == 204
    assert_priority(parent.pk, existing.pk)


def test_reparent_reconciles_both_parents_and_preserves_remaining_priority_order(user, api_for, make_item):
    old_parent = make_item(user, 'Old parent')
    new_parent = make_item(user, 'New parent', priority_position=2)
    child = make_item(user, 'Child', parent=old_parent, priority_position=1)
    existing = make_item(user, 'Existing', priority_position=3)

    response = api_for(user).post(f'/api/planning/items/{child.pk}/move/', {
        'parent_id': new_parent.pk, 'sibling_order': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    assert history.capture_priority(user) == [
        {'id': child.pk, 'priority_position': 1},
        {'id': existing.pk, 'priority_position': 2},
        {'id': old_parent.pk, 'priority_position': 3},
    ]
    new_parent.refresh_from_db()
    old_parent.refresh_from_db()
    assert new_parent.priority_position is None
    assert old_parent.is_completed is False

================================================================================
FILE: backend/planning/tests/test_leaf_order_sync.py
================================================================================
"""Leaf synchronization and reversible actions through the planning API."""
import pytest
from planning.models import ItemType, PlanningHistoryEntry, PlanningItem
from planning.services import history

pytestmark = pytest.mark.django_db


def state(user):
    return list(PlanningItem.objects.filter(user=user).order_by('pk').values_list(
        'pk', 'parent_id', 'sibling_order', 'priority_position',
    ))


def assert_roundtrip(client, user, before, after):
    for action, expected in [('undo', before), ('redo', after)]:
        response = client.post(f'/api/planning/items/{action}/', {}, format='json')
        assert response.status_code == 200, response.data
        assert response.data['changed'] is True
        assert state(user) == expected


def test_cross_root_priority_sync_preserves_mixed_container_slots_and_history(user, other_user, api_for, make_item):
    client = api_for(user)
    root_a = make_item(user, 'Root A', ItemType.GOAL, sibling_order=1)
    root_b = make_item(user, 'Root B', ItemType.GOAL, sibling_order=2)
    a1 = make_item(user, 'A1', parent=root_a, sibling_order=1, priority_position=1)
    container = make_item(user, 'Container', ItemType.GOAL, parent=root_a, sibling_order=2)
    a2 = make_item(user, 'A2', parent=root_a, sibling_order=3, priority_position=4)
    b1 = make_item(user, 'B1', parent=root_b, sibling_order=1, priority_position=2)
    b2 = make_item(user, 'B2', parent=root_b, sibling_order=2, priority_position=3)
    make_item(other_user, 'Other', sibling_order=9, priority_position=1)
    before, other_before = state(user), state(other_user)
    response = client.post('/api/planning/priority/reorder/', {
        'item_id': a2.pk, 'new_position': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    assert [row['item_id'] for row in response.data] == [a2.pk, a1.pk, b1.pk, b2.pk]
    for item, expected in [(root_a, 1), (root_b, 2), (container, 2), (a2, 1), (a1, 3), (b1, 1), (b2, 2)]:
        item.refresh_from_db()
        assert item.sibling_order == expected
    tree = client.get('/api/planning/items/tree/').data
    assert [node['id'] for node in tree] == [root_a.pk, root_b.pk]
    assert [node['id'] for node in tree[0]['children']] == [a2.pk, container.pk, a1.pk]
    entry = PlanningHistoryEntry.objects.get(user=user)
    assert {s['id'] for s in entry.before_state['leaf_siblings']} == {a1.pk, a2.pk, b1.pk, b2.pk}
    assert 'siblings' not in entry.before_state
    assert_roundtrip(client, user, before, state(user))
    assert state(other_user) == other_before


@pytest.mark.parametrize('move_up', [True, False])
def test_planner_leaf_move_uses_single_global_reorder_and_history(user, other_user, api_for, make_item, move_up):
    client = api_for(user)
    root = make_item(user, 'Root', ItemType.GOAL, sibling_order=1)
    a = make_item(user, 'A', parent=root, sibling_order=1, priority_position=1)
    x = make_item(user, 'X', sibling_order=2, priority_position=2)
    y = make_item(user, 'Y', sibling_order=3, priority_position=3)
    b = make_item(user, 'B', parent=root, sibling_order=2, priority_position=4)
    make_item(other_user, 'Other', sibling_order=5, priority_position=1)
    before, other_before = state(user), state(other_user)
    moved = b if move_up else a
    response = client.post(f'/api/planning/items/{moved.pk}/move/', {
        'parent_id': root.pk, 'sibling_order': 1 if move_up else 2,
    }, format='json')
    assert response.status_code == 200, response.data
    expected = [b.pk, a.pk, x.pk, y.pk] if move_up else [x.pk, y.pk, b.pk, a.pk]
    assert [s['id'] for s in history.capture_priority(user)] == expected
    assert list(PlanningItem.objects.filter(parent=root).order_by('sibling_order')
                .values_list('pk', flat=True)) == [b.pk, a.pk]
    assert_roundtrip(client, user, before, state(user))
    assert state(other_user) == other_before


def test_parent_only_move_and_history_do_not_change_priority(user, api_for, make_item):
    client = api_for(user)
    a = make_item(user, 'A', ItemType.GOAL, sibling_order=1)
    b = make_item(user, 'B', ItemType.GOAL, sibling_order=2)
    make_item(user, 'A leaf', parent=a, sibling_order=1, priority_position=1)
    make_item(user, 'B leaf', parent=b, sibling_order=1, priority_position=2)
    before = state(user)
    priority_before = history.capture_priority(user)
    response = client.post(f'/api/planning/items/{b.pk}/move/', {
        'parent_id': None, 'sibling_order': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    assert history.capture_priority(user) == priority_before
    b.refresh_from_db()
    assert b.sibling_order == 1
    entry = PlanningHistoryEntry.objects.get(user=user)
    assert set(entry.before_state) == {'siblings'}
    assert set(entry.after_state) == {'siblings'}
    assert_roundtrip(client, user, before, state(user))


def test_actionable_container_is_not_a_sync_leaf(user, api_for, make_item):
    container = make_item(user, 'Container', sibling_order=1, priority_position=2)
    make_item(user, 'Done child', parent=container, is_completed=True, sibling_order=1)
    leaf = make_item(user, 'Leaf', sibling_order=2, priority_position=1)
    before = state(user)
    response = api_for(user).post('/api/planning/priority/reorder/', {
        'item_id': container.pk, 'new_position': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    container.refresh_from_db()
    leaf.refresh_from_db()
    assert (container.sibling_order, leaf.sibling_order) == (1, 2)
    assert_roundtrip(api_for(user), user, before, state(user))


def test_reparent_history_restores_eligibility_positions(user, api_for, make_item):
    client = api_for(user)
    old = make_item(user, 'Old', sibling_order=1)
    new = make_item(user, 'New', sibling_order=2, priority_position=2)
    child = make_item(user, 'Child', parent=old, sibling_order=1, priority_position=1)
    before = state(user)
    response = client.post(f'/api/planning/items/{child.pk}/move/', {
        'parent_id': new.pk, 'sibling_order': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    assert [s['id'] for s in history.capture_priority(user)] == [child.pk, old.pk]
    assert_roundtrip(client, user, before, state(user))


def test_priority_history_never_restores_container_slots_even_in_leaf_payload(user, api_for, make_item):
    container = make_item(user, 'Container', sibling_order=3, priority_position=1)
    make_item(user, 'Done', parent=container, sibling_order=1, is_completed=True)
    leaf = make_item(user, 'Leaf', sibling_order=4, priority_position=2)
    before = state(user)
    history.record_checkpoint(user, 'PRIORITY', {
        'priority': [{'id': leaf.pk, 'priority_position': 1}, {'id': container.pk, 'priority_position': 2}],
        'siblings': [{'id': container.pk, 'parent_id': None, 'sibling_order': 99}],
        'leaf_siblings': [{'id': container.pk, 'sibling_order': 98}],
    }, {
        'priority': history.capture_priority(user),
        'siblings': [{'id': container.pk, 'parent_id': None, 'sibling_order': 97}],
        'leaf_siblings': [{'id': container.pk, 'sibling_order': 96}],
    })
    client = api_for(user)
    for action in ['undo', 'redo']:
        response = client.post(f'/api/planning/items/{action}/', {}, format='json')
        assert response.status_code == 200, response.data
        container.refresh_from_db()
        assert container.sibling_order == 3
    assert state(user) == before


@pytest.mark.parametrize('above', [True, False])
def test_leaf_crosses_recursive_container_boundary(user, other_user, api_for, make_item, above):
    client = api_for(user)
    root = make_item(user, 'Root', ItemType.GOAL, sibling_order=1)
    a = make_item(user, 'A', parent=root, sibling_order=1 if above else 2)
    f = make_item(user, 'F', parent=root, sibling_order=2 if above else 1)
    b = make_item(user, 'B', parent=a, sibling_order=1)
    e = make_item(user, 'E', parent=a, sibling_order=2)
    d = make_item(user, 'D', parent=a, sibling_order=3)
    d1 = make_item(user, 'D1', parent=d, sibling_order=1)
    c = make_item(user, 'C', parent=a, sibling_order=4)
    make_item(user, 'Completed', parent=a, sibling_order=5, is_completed=True)
    make_item(user, 'Deleted', parent=a, sibling_order=6, is_deleted=True)
    other_root = make_item(user, 'Other root', ItemType.GOAL, sibling_order=2)
    x, y, z = [make_item(user, title, parent=other_root, sibling_order=i)
               for i, title in enumerate(['X', 'Y', 'Z'], 1)]
    rest = [b, x, e, y, d1, c, z]
    initial = rest[:6] + [f, z] if above else [f] + rest
    for position, node in enumerate(initial, 1):
        PlanningItem.objects.filter(pk=node.pk).update(priority_position=position)
    make_item(other_user, 'Other user', priority_position=1, sibling_order=8)
    before, other_before = state(user), state(other_user)

    response = client.post(f'/api/planning/items/{f.pk}/move/', {
        'parent_id': root.pk, 'sibling_order': 1 if above else 2,
    }, format='json')
    assert response.status_code == 200, response.data
    expected = [f] + rest if above else rest[:6] + [f, z]
    assert [row['id'] for row in history.capture_priority(user)] == [node.pk for node in expected]
    a.refresh_from_db()
    d.refresh_from_db()
    assert a.priority_position is None
    assert d.priority_position is None
    assert a.sibling_order == (2 if above else 1)
    assert d.sibling_order == 3
    assert PlanningHistoryEntry.objects.filter(user=user).count() == 1
    assert_roundtrip(client, user, before, state(user))
    assert state(other_user) == other_before


def test_leaf_between_interleaved_container_boundaries(user, api_for, make_item):
    root = make_item(user, 'Root', ItemType.GOAL, sibling_order=1)
    a = make_item(user, 'A', ItemType.GOAL, parent=root, sibling_order=1)
    b = make_item(user, 'B', ItemType.GOAL, parent=root, sibling_order=2)
    leaf = make_item(user, 'Leaf', parent=root, sibling_order=3, priority_position=5)
    a1 = make_item(user, 'A1', parent=a, sibling_order=1, priority_position=1)
    b1 = make_item(user, 'B1', parent=b, sibling_order=1, priority_position=2)
    a2 = make_item(user, 'A2', parent=a, sibling_order=2, priority_position=3)
    b2 = make_item(user, 'B2', parent=b, sibling_order=2, priority_position=4)
    before = state(user)
    client = api_for(user)
    response = client.post(f'/api/planning/items/{leaf.pk}/move/', {
        'parent_id': root.pk, 'sibling_order': 2,
    }, format='json')
    assert response.status_code == 200, response.data
    assert [row['id'] for row in history.capture_priority(user)] == [a1.pk, a2.pk, leaf.pk, b1.pk, b2.pk]
    assert_roundtrip(client, user, before, state(user))

================================================================================
FILE: backend/planning/tests/test_overdue.py
================================================================================
"""Recent and Backlog classification (FR-12)."""

from datetime import date, timedelta

import pytest
from freezegun import freeze_time

from planning.models import ItemType
from planning.services import overdue

pytestmark = pytest.mark.django_db

FROZEN = '2026-09-14'
TODAY = date(2026, 9, 14)


def days(offset):
    return TODAY + timedelta(days=offset)


def bucket_titles(result, bucket):
    return [entry['item'].title for entry in result[bucket]]


@pytest.fixture
def root(user, make_item):
    return make_item(user, 'ELEC3609', ItemType.GOAL)


# --------------------------------------------------------------------------
# The Recent / Backlog boundary
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    'days_past, expected',
    [
        (1, 'recent'),
        (3, 'recent'),
        (6, 'recent'),
        (7, 'recent'),   # "seven days or less" is Recent
        (8, 'backlog'),  # "more than seven days" is Backlog
        (30, 'backlog'),
    ],
)
@freeze_time(FROZEN)
def test_the_seven_day_boundary(user, make_item, root, days_past, expected):
    make_item(user, 'task', parent=root, due_date=days(-days_past))

    result = overdue.classify(user, TODAY)

    assert bucket_titles(result, expected) == ['task']
    other = 'backlog' if expected == 'recent' else 'recent'
    assert bucket_titles(result, other) == []


@freeze_time(FROZEN)
def test_work_due_today_is_not_yet_overdue(user, make_item, root):
    make_item(user, 'task', parent=root, due_date=TODAY)

    result = overdue.classify(user, TODAY)

    assert result == {'recent': [], 'backlog': []}


@freeze_time(FROZEN)
def test_future_work_is_not_overdue(user, make_item, root):
    make_item(user, 'task', parent=root, due_date=days(5))
    assert overdue.classify(user, TODAY) == {'recent': [], 'backlog': []}


# --------------------------------------------------------------------------
# What can and cannot be overdue
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_an_adaptive_task_is_never_overdue(user, make_item, root):
    """The structural point: no due_date means FR-11 reschedules it instead."""
    make_item(user, 'adaptive', parent=root, scheduled_date=days(-20))

    assert overdue.classify(user, TODAY) == {'recent': [], 'backlog': []}


@freeze_time(FROZEN)
def test_a_completed_task_is_never_overdue(user, make_item, root):
    make_item(user, 'done', parent=root, due_date=days(-10), is_completed=True)
    assert overdue.classify(user, TODAY) == {'recent': [], 'backlog': []}


@freeze_time(FROZEN)
def test_a_goal_is_never_overdue(user, make_item, root):
    """Goals are containers; only tasks and assignments are actionable."""
    make_item(user, 'goal', ItemType.GOAL, parent=root, due_date=days(-10))
    assert overdue.classify(user, TODAY) == {'recent': [], 'backlog': []}


@freeze_time(FROZEN)
def test_an_overdue_assignment_is_included(user, make_item, root):
    make_item(user, 'report', ItemType.ASSIGNMENT, parent=root, due_date=days(-2))
    assert bucket_titles(overdue.classify(user, TODAY), 'recent') == ['report']


# --------------------------------------------------------------------------
# Presentation details the wireframe needs
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_entries_carry_the_hierarchy_path(user, make_item, root):
    mid = make_item(user, 'Assignment 2', ItemType.GOAL, parent=root)
    make_item(user, 'Draft the ERD', parent=mid, due_date=days(-2))

    entry = overdue.classify(user, TODAY)['recent'][0]

    assert entry['hierarchy_path'] == ['ELEC3609', 'Assignment 2', 'Draft the ERD']


@freeze_time(FROZEN)
def test_a_root_level_task_has_a_single_element_path(user, make_item):
    make_item(user, 'lonely', due_date=days(-1))
    entry = overdue.classify(user, TODAY)['recent'][0]
    assert entry['hierarchy_path'] == ['lonely']


@freeze_time(FROZEN)
def test_entries_report_how_late_they_are(user, make_item, root):
    make_item(user, 'task', parent=root, due_date=days(-4))
    assert overdue.classify(user, TODAY)['recent'][0]['days_overdue'] == 4


@freeze_time(FROZEN)
def test_the_oldest_work_is_listed_first_in_each_bucket(user, make_item, root):
    make_item(user, 'newer', parent=root, due_date=days(-2))
    make_item(user, 'older', parent=root, due_date=days(-5))
    make_item(user, 'ancient', parent=root, due_date=days(-40))
    make_item(user, 'old', parent=root, due_date=days(-12))

    result = overdue.classify(user, TODAY)

    assert bucket_titles(result, 'recent') == ['older', 'newer']
    assert bucket_titles(result, 'backlog') == ['ancient', 'old']


# --------------------------------------------------------------------------
# Isolation and helpers
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_only_the_requested_users_work_is_returned(user, other_user, make_item):
    make_item(user, 'mine', due_date=days(-2))
    make_item(other_user, 'theirs', due_date=days(-2))

    assert bucket_titles(overdue.classify(user, TODAY), 'recent') == ['mine']
    assert bucket_titles(overdue.classify(other_user, TODAY), 'recent') == ['theirs']


@freeze_time(FROZEN)
def test_is_overdue_matches_the_queryset(user, make_item, root):
    late = make_item(user, 'late', parent=root, due_date=days(-1))
    adaptive = make_item(user, 'adaptive', parent=root, scheduled_date=days(-1))
    goal = make_item(user, 'goal', ItemType.GOAL, parent=root, due_date=days(-1))

    assert overdue.is_overdue(late, TODAY) is True
    assert overdue.is_overdue(adaptive, TODAY) is False
    assert overdue.is_overdue(goal, TODAY) is False

================================================================================
FILE: backend/planning/tests/test_priority_restoration.py
================================================================================
import pytest
from planning.models import ItemType, PlanningItem
from planning.services import hierarchy, history, priority

pytestmark = pytest.mark.django_db


def ids(user):
    return list(priority.ordered(user).values_list('pk', flat=True))


def test_completed_priority_returns_between_surviving_neighbours(user, other_user, make_item):
    a, b, c = [make_item(user, title) for title in 'ABC']
    other = make_item(other_user, 'Other', priority_position=1)
    priority.reconcile(user)
    hierarchy.complete_subtree(b)
    assert ids(user) == [a.pk, c.pk]
    hierarchy.reopen(b)
    assert ids(user) == [a.pk, b.pk, c.pk]
    assert ids(other_user) == [other.pk]


def test_subtree_completion_reopening_and_deleted_anchor(user, make_item):
    root = make_item(user, 'Root', ItemType.GOAL)
    a, b, c = [make_item(user, title, parent=root) for title in 'ABC']
    priority.reconcile(user)
    hierarchy.complete_subtree(root)
    assert ids(user) == []
    hierarchy.reopen(c)
    hierarchy.reopen(a)
    hierarchy.reopen(b)
    assert ids(user) == [a.pk, b.pk, c.pk]
    hierarchy.complete_subtree(b)
    PlanningItem.objects.filter(pk=c.pk).update(is_deleted=True)
    priority.reconcile(user)
    hierarchy.reopen(b)
    assert ids(user) == [a.pk, b.pk]


def test_completion_history_and_eligibility_restoration(user, api_for, make_item):
    client = api_for(user)
    a, b, c = [make_item(user, title) for title in 'ABC']
    priority.reconcile(user)
    before = history.capture_items(user, [b.pk])
    assert client.post(f'/api/planning/items/{b.pk}/complete/', {}, format='json').status_code == 200
    after = history.capture_items(user, [b.pk])
    history.undo(user)
    assert ids(user) == [a.pk, b.pk, c.pk]
    assert history.capture_items(user, [b.pk]) == before
    history.redo(user)
    assert ids(user) == [a.pk, c.pk]
    assert history.capture_items(user, [b.pk]) == after
    response = client.post(f'/api/planning/items/{b.pk}/complete/', {'completed': False}, format='json')
    assert response.status_code == 200
    assert ids(user) == [a.pk, b.pk, c.pk]


def test_parent_eligibility_history_restores_membership_and_anchors(user, api_for, make_item):
    client = api_for(user)
    parent = make_item(user, 'Parent', priority_position=1)
    other = make_item(user, 'Other', priority_position=2)
    before_create = history.capture_priority(user, include_unpositioned=True)
    response = client.post('/api/planning/items/', {
        'title': 'Child', 'item_type': 'TASK', 'parent': parent.pk,
    }, format='json')
    assert response.status_code == 201
    child_id = response.data['id']
    before_complete = history.capture_priority(user, include_unpositioned=True)
    assert client.post(f'/api/planning/items/{child_id}/complete/', {}, format='json').status_code == 200
    assert ids(user) == [parent.pk, other.pk]
    after_complete = history.capture_priority(user, include_unpositioned=True)
    history.undo(user)
    assert history.capture_priority(user, include_unpositioned=True) == before_complete
    assert ids(user) == [other.pk, child_id]
    history.redo(user)
    assert history.capture_priority(user, include_unpositioned=True) == after_complete
    history.undo(user)
    history.undo(user)
    assert history.capture_priority(user, include_unpositioned=True) == before_create
    history.redo(user)
    assert history.capture_priority(user, include_unpositioned=True) == before_complete


def test_legacy_history_with_null_estimate_uses_default(user, make_item):
    from planning.models import DurationCategory

    item = make_item(user, 'Old task')
    state = history.capture_items(user, [item.pk])
    state[0]['duration_category'] = None
    entry = history.record_checkpoint(user, 'UPDATE', {'items': state},
                                      {'items': history.capture_items(user, [item.pk])})
    assert entry is not None
    assert history.undo(user) is not None
    item.refresh_from_db()
    assert item.duration_category == DurationCategory.MIN_20_TO_60
    assert history.redo(user) is not None
    item.refresh_from_db()
    assert item.duration_category == DurationCategory.MIN_20_TO_60


def test_new_parent_inherits_final_child_frontier_slot(user, make_item):
    """A newly exposed parent inherits the frontier neighbourhood it replaces."""
    before = make_item(user, 'Before')
    parent = make_item(user, 'Parent', ItemType.ASSIGNMENT)
    child = make_item(user, 'Final child', parent=parent)
    after = make_item(user, 'After')

    priority.reconcile(user)

    # Establish a deterministic frontier where the child sits between neighbours.
    priority.reorder(user, before.pk, 1)
    priority.reorder(user, child.pk, 2)
    priority.reorder(user, after.pk, 3)
    assert ids(user) == [before.pk, child.pk, after.pk]

    # Parent has never itself occupied the priority frontier.
    parent.refresh_from_db()
    assert parent.priority_position is None
    assert not parent.priority_restore_context

    hierarchy.complete_subtree(child)

    # Completing the final child exposes Parent. Its logical frontier slot
    # should replace the child rather than being appended to the end.
    assert ids(user) == [before.pk, parent.pk, after.pk]


def test_non_final_child_completion_does_not_promote_parent(user, make_item):
    """Parent stays outside the frontier while another incomplete child remains."""
    before = make_item(user, 'Before')
    parent = make_item(user, 'Parent', ItemType.ASSIGNMENT)
    first = make_item(user, 'First child', parent=parent)
    remaining = make_item(user, 'Remaining child', parent=parent)
    after = make_item(user, 'After')

    priority.reconcile(user)
    priority.reorder(user, before.pk, 1)
    priority.reorder(user, first.pk, 2)
    priority.reorder(user, remaining.pk, 3)
    priority.reorder(user, after.pk, 4)

    hierarchy.complete_subtree(first)

    current = ids(user)

    assert parent.pk not in current
    assert remaining.pk in current


def test_deeply_exposed_ancestor_inherits_descendant_frontier_slot(user, make_item):
    """Frontier-slot inheritance works across more than one hierarchy level."""
    before = make_item(user, 'Before')
    ancestor = make_item(user, 'Ancestor', ItemType.ASSIGNMENT)
    middle = make_item(user, 'Middle', parent=ancestor)
    leaf = make_item(user, 'Leaf', parent=middle)
    after = make_item(user, 'After')

    priority.reconcile(user)
    priority.reorder(user, before.pk, 1)
    priority.reorder(user, leaf.pk, 2)
    priority.reorder(user, after.pk, 3)

    hierarchy.complete_subtree(leaf)
    hierarchy.complete_subtree(middle)

    assert ids(user) == [before.pk, ancestor.pk, after.pk]


def test_existing_restore_context_wins_over_descendant_context(user, make_item):
    """A returning item's own history must not be overwritten by inheritance."""
    before = make_item(user, 'Before')
    parent = make_item(user, 'Parent', ItemType.ASSIGNMENT)
    after = make_item(user, 'After')

    priority.reconcile(user)
    priority.reorder(user, parent.pk, 2)

    # Creating a child removes Parent from the frontier and records Parent's
    # own restoration context.
    child = make_item(user, 'Child', parent=parent)
    priority.reconcile(user)

    parent.refresh_from_db()
    original_context = dict(parent.priority_restore_context)
    assert original_context

    hierarchy.complete_subtree(child)

    parent.refresh_from_db()

    assert parent.priority_restore_context == original_context
    assert ids(user) == [before.pk, parent.pk, after.pk]


def test_unrelated_new_work_does_not_inherit_departing_context(user, make_item):
    """Frontier inheritance is restricted to ancestors of departing work."""
    before = make_item(user, 'Before')
    parent = make_item(user, 'Parent', ItemType.ASSIGNMENT)
    child = make_item(user, 'Child', parent=parent)
    after = make_item(user, 'After')

    priority.reconcile(user)
    priority.reorder(user, before.pk, 1)
    priority.reorder(user, child.pk, 2)
    priority.reorder(user, after.pk, 3)

    unrelated = make_item(user, 'Unrelated')
    hierarchy.complete_subtree(child)

    current = ids(user)

    assert current.index(parent.pk) == 1
    assert current.index(unrelated.pk) > current.index(after.pk)

================================================================================
FILE: backend/planning/tests/test_priority.py
================================================================================
"""The single global priority order (FR-09)."""

import random

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

from planning.models import ItemType, PlanningItem
from planning.services import priority

from .conftest import positions

pytestmark = pytest.mark.django_db


@pytest.fixture
def tasks(user, make_item):
    """Five positioned tasks, named for their starting position."""
    created = [make_item(user, f't{i}') for i in range(1, 6)]
    for task in created:
        priority.assign_initial_position(task)
    return created


def titles(user):
    return [title for _, title in positions(user)]


# --------------------------------------------------------------------------
# Initial placement
# --------------------------------------------------------------------------

def test_positions_start_at_one_and_increment(user, tasks):
    assert positions(user) == [(1, 't1'), (2, 't2'), (3, 't3'), (4, 't4'), (5, 't5')]


def test_goals_never_take_a_position(user, make_item):
    goal = make_item(user, 'goal', ItemType.GOAL)
    assert priority.assign_initial_position(goal) is None
    goal.refresh_from_db()
    assert goal.priority_position is None


def test_completed_tasks_never_take_a_position(user, make_item):
    done = make_item(user, 'done', is_completed=True)
    assert priority.assign_initial_position(done) is None


def test_assigning_twice_is_a_no_op(user, make_item):
    task = make_item(user, 'task')
    first = priority.assign_initial_position(task)
    assert priority.assign_initial_position(task) == first


def test_each_user_has_an_independent_order(user, other_user, make_item, tasks):
    theirs = make_item(other_user, 'theirs')
    priority.assign_initial_position(theirs)
    # Position 1 is already taken by alice; bob still starts at 1.
    assert theirs.priority_position == 1


# --------------------------------------------------------------------------
# Reordering
# --------------------------------------------------------------------------

def test_moving_a_task_up_shifts_the_others_down(user, tasks):
    priority.reorder(user, tasks[3].pk, 1)
    assert titles(user) == ['t4', 't1', 't2', 't3', 't5']


def test_moving_a_task_down_shifts_the_others_up(user, tasks):
    priority.reorder(user, tasks[0].pk, 4)
    assert titles(user) == ['t2', 't3', 't4', 't1', 't5']


def test_moving_a_task_to_its_current_row_changes_nothing(user, tasks):
    before = titles(user)
    priority.reorder(user, tasks[2].pk, 3)
    assert titles(user) == before


def test_a_position_past_the_end_clamps_to_the_end(user, tasks):
    priority.reorder(user, tasks[0].pk, 999)
    assert titles(user) == ['t2', 't3', 't4', 't5', 't1']


def test_a_position_below_one_clamps_to_the_top(user, tasks):
    priority.reorder(user, tasks[4].pk, -5)
    assert titles(user) == ['t5', 't1', 't2', 't3', 't4']


def test_reordering_an_unpositioned_task_is_refused(user, tasks, make_item):
    goal = make_item(user, 'goal', ItemType.GOAL)
    with pytest.raises(ValidationError):
        priority.reorder(user, goal.pk, 1)


def test_reordering_cannot_reach_another_users_task(user, other_user, make_item, tasks):
    theirs = make_item(other_user, 'theirs')
    priority.assign_initial_position(theirs)
    with pytest.raises(ValidationError):
        priority.reorder(user, theirs.pk, 1)


def test_a_swap_needs_no_temporary_offset(user, tasks):
    """Proves the deferred constraint is doing its job: this reorder writes a
    duplicate position mid-transaction and only the committed state is
    checked."""
    priority.reorder(user, tasks[0].pk, 2)
    assert titles(user) == ['t2', 't1', 't3', 't4', 't5']


@pytest.mark.parametrize('seed', range(10))
def test_randomised_reordering_keeps_the_order_dense_and_unique(user, tasks, seed):
    rng = random.Random(seed)
    ids = [task.pk for task in tasks]

    for _ in range(20):
        priority.reorder(user, rng.choice(ids), rng.randint(1, len(ids)))

        current = positions(user)
        numbers = [number for number, _ in current]
        assert numbers == list(range(1, len(ids) + 1)), f'not dense: {numbers}'
        assert len(set(numbers)) == len(numbers), f'duplicates: {numbers}'
        assert len({title for _, title in current}) == len(ids), 'lost a task'


# --------------------------------------------------------------------------
# Leaving and rejoining the order
# --------------------------------------------------------------------------

def test_releasing_a_position_closes_the_gap(user, tasks):
    priority.release_position(tasks[1])
    assert titles(user) == ['t1', 't3', 't4', 't5']
    assert [number for number, _ in positions(user)] == [1, 2, 3, 4]


def test_releasing_twice_is_harmless(user, tasks):
    priority.release_position(tasks[1])
    priority.release_position(tasks[1])
    assert len(positions(user)) == 4


def test_restoring_returns_to_the_previous_relative_position(user, tasks):
    priority.release_position(tasks[0])
    tasks[0].refresh_from_db()

    priority.restore_position(tasks[0])

    assert titles(user) == ['t1', 't2', 't3', 't4', 't5']


def test_releasing_many_positions_at_once_renumbers_the_rest(user, tasks):
    priority.release_positions(user, [tasks[0].pk, tasks[2].pk, tasks[4].pk])
    assert positions(user) == [(1, 't2'), (2, 't4')]


def test_renumber_repairs_a_sparse_order(user, tasks):
    PlanningItem.objects.filter(pk=tasks[0].pk).update(priority_position=40)
    PlanningItem.objects.filter(pk=tasks[1].pk).update(priority_position=70)

    priority.renumber(user)

    numbers = [number for number, _ in positions(user)]
    assert numbers == [1, 2, 3, 4, 5]
    # 40 and 70 sorted after the untouched 3, 4, 5.
    assert titles(user) == ['t3', 't4', 't5', 't1', 't2']


# --------------------------------------------------------------------------
# The database backstop
# --------------------------------------------------------------------------

def test_the_database_refuses_a_duplicate_position(user, tasks):
    """Because the constraint is deferred, the duplicate is tolerated until
    the check runs. Forcing it early is the only way to observe the rejection
    from inside a transaction, and it doubles as proof that the deferral in
    the migration is real."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PlanningItem.objects.filter(pk=tasks[0].pk).update(
                priority_position=tasks[1].priority_position
            )
            with connection.cursor() as cursor:
                cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')


def test_the_database_allows_many_null_positions(user, make_item):
    for index in range(10):
        make_item(user, f'goal-{index}', ItemType.GOAL)
    assert PlanningItem.objects.for_user(user).filter(priority_position=None).count() == 10

================================================================================
FILE: backend/planning/tests/test_scheduling_lifecycle.py
================================================================================
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from planning.models import ItemType, PlanningHistoryEntry, PlanningItem, SchedulingPreference, SchedulingState
from planning.services import history, priority, scheduling, hierarchy

pytestmark = pytest.mark.django_db
TODAY = date(2026, 9, 14)


@pytest.fixture(autouse=True)
def clock():
    with freeze_time('2026-09-14'):
        yield


def refresh(*items):
    for item in items:
        item.refresh_from_db()


def test_create_edit_and_title_lifecycle(user, api_for, make_item):
    client = api_for(user)
    future = make_item(user, 'Future', scheduled_date=TODAY + timedelta(days=8))
    response = client.post('/api/planning/items/', {'title': 'New', 'item_type': 'TASK'}, format='json')
    assert response.status_code == 201
    item = PlanningItem.objects.get(pk=response.data['id'])
    assert item.scheduled_date == TODAY
    response = client.patch(f'/api/planning/items/{item.pk}/', {'start_date': '2026-09-17'}, format='json')
    assert response.status_code == 200
    refresh(item, future)
    assert item.scheduled_date == date(2026, 9, 17)
    assert future.scheduled_date == TODAY + timedelta(days=8)
    with patch.object(scheduling, 'schedule', wraps=scheduling.schedule) as run:
        assert client.patch(f'/api/planning/items/{item.pk}/', {'title': 'Renamed'}, format='json').status_code == 200
        run.assert_not_called()


@pytest.mark.parametrize('limit,code', [(0, 'capacity_disabled'), (1, 'no_capacity_before_deadline')])
def test_total_scheduling_at_capacity_limit(user, make_item, limit, code):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=limit)
    release = TODAY + timedelta(days=2)
    items = [make_item(user, str(i), start_date=release, due_date=release) for i in range(3)]
    result = scheduling.schedule(user)
    refresh(*items)
    assert all(item.scheduled_date == release for item in items)
    assert any(conflict['code'] == code for conflict in result['conflicts'])
    assert scheduling.schedule(user)['changed_ids'] == []


def test_global_bubbles_minimal_preserves_and_missed_rolls(user, make_item):
    future = make_item(user, 'Future', scheduled_date=TODAY + timedelta(days=7))
    missed = make_item(user, 'Missed', scheduled_date=TODAY - timedelta(days=3))
    legacy = make_item(user, 'Poster Submission', due_date=TODAY + timedelta(days=13))
    scheduling.schedule(user)
    refresh(future, missed, legacy)
    assert future.scheduled_date == TODAY + timedelta(days=7)
    assert missed.scheduled_date == legacy.scheduled_date == TODAY
    scheduling.schedule(user, mode='global')
    refresh(future)
    assert future.scheduled_date == TODAY
    assert scheduling.schedule(user, mode='global')['changed_ids'] == []


@pytest.mark.parametrize('mode', ['minimal', 'global'])
def test_manual_dates_preserved_even_when_invalid(user, make_item, mode):
    past = make_item(user, 'Past fixed', schedule_is_manual=True, scheduled_date=TODAY - timedelta(days=1))
    future = make_item(user, 'Future fixed', schedule_is_manual=True, scheduled_date=TODAY + timedelta(days=10), due_date=TODAY + timedelta(days=5))
    result = scheduling.schedule(user, mode=mode)
    refresh(past, future)
    assert past.scheduled_date == TODAY - timedelta(days=1)
    assert future.scheduled_date == TODAY + timedelta(days=10)
    assert {c['code'] for c in result['conflicts']} >= {'past_date', 'after_deadline'}


def test_overdue_frozen_and_legacy_repaired_and_visible(user, make_item, api_for):
    due = TODAY - timedelta(days=2)
    existing = make_item(user, 'Old', due_date=due, scheduled_date=due - timedelta(days=1))
    legacy = make_item(user, 'Legacy', start_date=due - timedelta(days=3), due_date=due)
    scheduling.schedule(user, mode='global')
    refresh(existing, legacy)
    assert existing.scheduled_date == due - timedelta(days=1)
    assert legacy.scheduled_date == due
    assert scheduling.schedule(user, mode='global')['changed_ids'] == []
    response = api_for(user).get('/api/planning/overdue/')
    assert response.status_code == 200
    overdue_ids = {row['item']['id'] for bucket in ('recent', 'backlog') for row in response.data[bucket]}
    assert {legacy.pk, existing.pk} <= overdue_ids


def test_daily_local_date_once_isolated_and_history_free(user, other_user, make_item, api_for):
    future = make_item(user, 'Future', scheduled_date=TODAY + timedelta(days=8))
    other = make_item(other_user, 'Other', scheduled_date=TODAY + timedelta(days=8))
    client = api_for(user)
    with patch.object(scheduling, 'schedule', wraps=scheduling.schedule) as run:
        assert client.get('/api/planning/timeline/').status_code == 200
        assert run.call_args.kwargs['mode'] == 'global'
        assert client.get('/api/planning/timeline/').status_code == 200
        assert run.call_args.kwargs['mode'] == 'minimal'
        with freeze_time('2026-09-15'):
            assert client.get('/api/planning/timeline/').status_code == 200
            assert run.call_args.kwargs['mode'] == 'global'
    refresh(future, other)
    assert future.scheduled_date == TODAY + timedelta(days=1)
    assert other.scheduled_date == TODAY + timedelta(days=8)
    assert SchedulingState.objects.get(user=user).last_global_date == TODAY + timedelta(days=1)
    assert not SchedulingState.objects.filter(user=other_user).exists()
    assert not PlanningHistoryEntry.objects.filter(user=user).exists()


def test_completion_frees_capacity_without_bubbling(user, make_item, api_for):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    done = make_item(user, 'Done', scheduled_date=TODAY)
    later = make_item(user, 'Later', scheduled_date=TODAY + timedelta(days=1))
    assert api_for(user).post(f'/api/planning/items/{done.pk}/complete/', {'completed': True}, format='json').status_code == 200
    refresh(later)
    assert later.scheduled_date == TODAY + timedelta(days=1)
    scheduling.schedule(user, mode='global')
    refresh(later)
    assert later.scheduled_date == TODAY


def test_reschedule_auth_isolation_history_and_noop(user, other_user, api, api_for, make_item):
    assert api.post('/api/planning/timeline/reschedule/').status_code in (401, 403)
    mine = make_item(user, 'Mine', scheduled_date=TODAY + timedelta(days=7))
    theirs = make_item(other_user, 'Theirs')
    client = api_for(user)
    response = client.post('/api/planning/timeline/reschedule/')
    assert response.status_code == 200
    assert mine.pk in response.data['changed_ids']
    assert response.data['conflicts'] == []
    refresh(mine, theirs)
    assert mine.scheduled_date == TODAY
    assert theirs.scheduled_date is None
    assert client.post('/api/planning/timeline/reschedule/').data['changed_ids'] == []
    assert PlanningHistoryEntry.objects.filter(user=user, action_type='SCHEDULE').count() == 1
    history.undo(user)
    refresh(mine)
    assert mine.scheduled_date == TODAY + timedelta(days=7)
    history.redo(user)
    refresh(mine)
    assert mine.scheduled_date == TODAY


def test_daily_failure_does_not_mark_maintenance_complete(user):
    with patch.object(scheduling, 'schedule', side_effect=RuntimeError('failed')):
        with pytest.raises(RuntimeError):
            scheduling.daily_schedule(user)
    assert not SchedulingState.objects.filter(user=user).exists()


def test_global_empty_capacity_moves_forward_and_release_is_hard(user, make_item):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    fixed = make_item(user, 'Fixed', schedule_is_manual=True, scheduled_date=TODAY)
    first = make_item(user, 'First')
    second = make_item(user, 'Second')
    released = make_item(user, 'Released', start_date=TODAY + timedelta(days=6))
    scheduling.schedule(user, mode='global')
    refresh(fixed, first, second, released)
    assert fixed.scheduled_date == TODAY
    assert first.scheduled_date == TODAY + timedelta(days=1)
    assert second.scheduled_date == TODAY + timedelta(days=2)
    assert released.scheduled_date == released.start_date


# --------------------------------------------------------------------------
# Scheduler eligibility invariant
# --------------------------------------------------------------------------

def test_global_schedule_excludes_parent_with_unfinished_children(user, make_item):
    """Only execution-frontier work receives an execution date."""
    assignment = make_item(user, 'Parent assignment', ItemType.ASSIGNMENT)
    child = make_item(user, 'Child task', parent=assignment)

    scheduling.schedule(user, mode='global')
    refresh(assignment, child)

    assert assignment.scheduled_date is None
    assert child.scheduled_date is not None


def test_global_schedule_gives_every_frontier_item_an_execution_date(user, make_item):
    """Global scheduling schedules active frontier work, not decomposed parents."""
    assignment = make_item(user, 'Assignment', ItemType.ASSIGNMENT)
    task = make_item(user, 'Task')
    nested = make_item(user, 'Nested task', parent=assignment)

    scheduling.schedule(user, mode='global')
    refresh(assignment, task, nested)

    assert assignment.scheduled_date is None
    assert task.scheduled_date is not None
    assert nested.scheduled_date is not None


def test_completed_children_expose_parent_to_scheduler(user, make_item):
    """A parent becomes schedulable once no unfinished children remain."""
    assignment = make_item(user, 'Parent assignment', ItemType.ASSIGNMENT)
    child = make_item(
        user,
        'Completed child',
        parent=assignment,
        is_completed=True,
    )

    scheduling.schedule(user, mode='global')
    refresh(assignment, child)

    assert assignment.scheduled_date is not None



def test_goal_remains_outside_scheduler_eligibility(user, make_item):
    """Structural goals do not acquire execution dates."""
    goal = make_item(user, 'Goal', ItemType.GOAL)
    make_item(user, 'Goal child', parent=goal)

    scheduling.schedule(user, mode='global')
    goal.refresh_from_db()

    assert goal.scheduled_date is None


def test_parent_outside_priority_frontier_is_also_outside_scheduler(user, make_item):
    """Decomposed parents belong to neither execution nor priority frontier."""
    assignment = make_item(user, 'Parent assignment', ItemType.ASSIGNMENT)
    make_item(user, 'Child task', parent=assignment)

    priority.reconcile(user)

    assert not PlanningItem.objects.for_user(user).priority_eligible().filter(
        pk=assignment.pk
    ).exists()

    scheduling.schedule(user, mode='global')
    assignment.refresh_from_db()

    assert assignment.scheduled_date is None


def test_global_reschedule_clears_parent_date_when_child_reopens(user, make_item):
    """Reopening a child demotes its parent and clears stale automatic execution."""
    parent = make_item(user, 'Report', ItemType.ASSIGNMENT)
    child = make_item(user, 'Draft', parent=parent, is_completed=True)

    scheduling.schedule(user, mode='global')
    parent.refresh_from_db()
    assert parent.scheduled_date is not None

    child.is_completed = False
    child.save(update_fields=['is_completed'])

    scheduling.schedule(user, mode='global')
    refresh(parent, child)

    assert parent.scheduled_date is None
    assert child.scheduled_date is not None


def test_global_reschedule_clears_parent_date_when_child_added(user, make_item):
    """Adding unfinished child work demotes an already scheduled parent."""
    parent = make_item(user, 'Submit project', ItemType.ASSIGNMENT)

    scheduling.schedule(user, mode='global')
    parent.refresh_from_db()
    assert parent.scheduled_date is not None

    child = make_item(user, 'Final review', parent=parent)

    scheduling.schedule(user, mode='global')
    refresh(parent, child)

    assert parent.scheduled_date is None
    assert child.scheduled_date is not None


def test_anchored_parent_loses_execution_anchor_when_child_added(user, make_item):
    parent = make_item(user, 'Anchored parent', ItemType.ASSIGNMENT)

    scheduling.schedule(user, mode='global')
    parent.refresh_from_db()

    parent.schedule_is_manual = True
    parent.save(update_fields=['schedule_is_manual'])

    make_item(user, 'New child', parent=parent)

    scheduling.schedule(user, mode='global')
    parent.refresh_from_db()

    assert parent.scheduled_date is None
    assert parent.schedule_is_manual is False


def test_anchored_parent_loses_execution_anchor_when_child_reopens(user, make_item):
    parent = make_item(user, 'Anchored parent', ItemType.ASSIGNMENT)
    child = make_item(user, 'Child', parent=parent, is_completed=True)

    scheduling.schedule(user, mode='global')
    parent.refresh_from_db()

    parent.schedule_is_manual = True
    parent.save(update_fields=['schedule_is_manual'])

    hierarchy.reopen(child)

    parent.refresh_from_db()
    child.refresh_from_db()

    assert parent.scheduled_date is None
    assert parent.schedule_is_manual is False
    assert child.scheduled_date is not None


def test_anchored_parent_loses_execution_anchor_when_child_restored(user, make_item):
    parent = make_item(user, 'Anchored parent', ItemType.ASSIGNMENT)
    child = make_item(user, 'Child', parent=parent)
    child.is_deleted = True
    child.save(update_fields=['is_deleted'])

    scheduling.schedule(user, mode='global')
    parent.refresh_from_db()

    parent.schedule_is_manual = True
    parent.save(update_fields=['schedule_is_manual'])

    child.is_deleted = False
    child.save(update_fields=['is_deleted'])

    scheduling.schedule(user, mode='global')
    parent.refresh_from_db()
    child.refresh_from_db()

    assert parent.scheduled_date is None
    assert parent.schedule_is_manual is False
    assert child.scheduled_date is not None


def test_moving_child_under_anchored_parent_invalidates_parent_anchor(user, make_item):
    source = make_item(user, 'Source', ItemType.ASSIGNMENT)
    target = make_item(user, 'Anchored target', ItemType.ASSIGNMENT)
    child = make_item(user, 'Moving child', parent=source)

    scheduling.schedule(user, mode='global')
    target.refresh_from_db()

    target.schedule_is_manual = True
    target.save(update_fields=['schedule_is_manual'])

    hierarchy.set_parent(child, target)

    target.refresh_from_db()
    child.refresh_from_db()

    assert target.scheduled_date is None
    assert target.schedule_is_manual is False
    assert child.scheduled_date is not None


def test_daily_schedule_expires_past_manual_anchor(user, make_item):
    today = date(2026, 9, 20)

    item = make_item(
        user,
        'Expired anchor',
        scheduled_date=today - timedelta(days=1),
        schedule_is_manual=True,
        due_date=today + timedelta(days=10),
    )

    result = scheduling.daily_schedule(user, today=today)

    item.refresh_from_db()

    assert item.schedule_is_manual is False
    assert item.pk in result['expired_anchor_ids']
    assert item.due_date == today + timedelta(days=10)
    assert item.scheduled_date >= today


def test_anchor_today_does_not_expire(user, make_item):
    today = date(2026, 9, 20)

    item = make_item(
        user,
        'Anchor today',
        scheduled_date=today,
        schedule_is_manual=True,
        due_date=today + timedelta(days=10),
    )

    result = scheduling.daily_schedule(user, today=today)

    item.refresh_from_db()

    assert item.schedule_is_manual is True
    assert item.scheduled_date == today
    assert item.pk not in result['expired_anchor_ids']


def test_future_anchor_does_not_expire(user, make_item):
    today = date(2026, 9, 20)

    item = make_item(
        user,
        'Future anchor',
        scheduled_date=today + timedelta(days=3),
        schedule_is_manual=True,
        due_date=today + timedelta(days=10),
    )

    scheduling.daily_schedule(user, today=today)

    item.refresh_from_db()

    assert item.schedule_is_manual is True
    assert item.scheduled_date == today + timedelta(days=3)


def test_expired_anchor_does_not_create_overdue_semantics(user, make_item):
    today = date(2026, 9, 20)

    item = make_item(
        user,
        'Expired preference but live deadline',
        scheduled_date=today - timedelta(days=3),
        schedule_is_manual=True,
        due_date=today + timedelta(days=7),
    )

    scheduling.daily_schedule(user, today=today)

    item.refresh_from_db()

    assert item.schedule_is_manual is False
    assert item.due_date == today + timedelta(days=7)
    assert item.scheduled_date >= today

================================================================================
FILE: backend/planning/tests/test_scheduling.py
================================================================================
"""Global capacity roll-forward.

The clock is frozen throughout so that "yesterday" and "today" mean something
stable, and so the idempotency tests can run the sweep twice inside one day.
"""

from datetime import date, timedelta

import pytest
from freezegun import freeze_time

from planning.models import ItemType, PlanningItem, SchedulingPreference
from planning.services import priority, scheduling

pytestmark = pytest.mark.django_db

FROZEN = '2026-09-14'
TODAY = date(2026, 9, 14)


def days(offset):
    return TODAY + timedelta(days=offset)


def schedule_of(user):
    return dict(
        PlanningItem.objects.for_user(user)
        .exclude(scheduled_date=None)
        .values_list('title', 'scheduled_date')
    )


@pytest.fixture
def root(user, make_item):
    return make_item(user, 'course', ItemType.GOAL)


# --------------------------------------------------------------------------
# Initial placement
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_an_adaptive_task_with_no_date_gets_one(user, make_item, root):
    task = make_item(user, 'task', parent=root)
    assert task.scheduled_date is None

    scheduling.roll_forward_adaptive(user, TODAY)

    task.refresh_from_db()
    assert task.scheduled_date == TODAY


@freeze_time(FROZEN)
def test_a_future_date_is_left_alone(user, make_item, root):
    task = make_item(user, 'task', parent=root, scheduled_date=days(5))

    scheduling.roll_forward_adaptive(user, TODAY)

    task.refresh_from_db()
    assert task.scheduled_date == days(5)


@freeze_time(FROZEN)
def test_a_task_with_an_expired_deadline_recovers_last_legal_date(user, make_item, root):
    fixed = make_item(user, 'fixed', parent=root, due_date=days(-5))

    scheduling.roll_forward_adaptive(user, TODAY)

    fixed.refresh_from_db()
    assert fixed.scheduled_date == fixed.due_date


@freeze_time(FROZEN)
def test_goals_are_not_scheduled(user, make_item, root):
    sub_goal = make_item(user, 'sub-goal', ItemType.GOAL, parent=root)

    scheduling.roll_forward_adaptive(user, TODAY)

    sub_goal.refresh_from_db()
    assert sub_goal.scheduled_date is None


@freeze_time(FROZEN)
def test_completed_tasks_are_not_scheduled(user, make_item, root):
    done = make_item(user, 'done', parent=root, scheduled_date=days(-3), is_completed=True)

    scheduling.roll_forward_adaptive(user, TODAY)

    done.refresh_from_db()
    assert done.scheduled_date == days(-3)


# --------------------------------------------------------------------------
# Roll-forward
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_yesterdays_unfinished_task_moves_to_today(user, make_item, root):
    task = make_item(user, 'task', parent=root, scheduled_date=days(-1))

    scheduling.roll_forward_adaptive(user, TODAY)

    task.refresh_from_db()
    assert task.scheduled_date == TODAY


@freeze_time(FROZEN)
def test_a_long_neglected_task_lands_on_today_not_one_day_later(user, make_item, root):
    """Moving strictly one day per run would leave a task abandoned for a
    month still sitting in the past."""
    task = make_item(user, 'task', parent=root, scheduled_date=days(-30))

    scheduling.roll_forward_adaptive(user, TODAY)

    task.refresh_from_db()
    assert task.scheduled_date == TODAY


@freeze_time(FROZEN)
def test_an_overdue_task_is_rescheduled_rather_than_marked_overdue(user, make_item, root):
    """The FR-11 / FR-12 split: no due_date means no overdue state."""
    task = make_item(user, 'task', parent=root, scheduled_date=days(-4))

    scheduling.roll_forward_adaptive(user, TODAY)

    task.refresh_from_db()
    assert task.scheduled_date == TODAY
    assert not PlanningItem.objects.for_user(user).overdue(TODAY).exists()


# --------------------------------------------------------------------------
# Collision cascade
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_a_collision_pushes_the_lower_priority_task_along(user, make_item, root):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    first = make_item(user, 'first', parent=root, scheduled_date=days(-1))
    second = make_item(user, 'second', parent=root, scheduled_date=TODAY)
    priority.assign_initial_position(first)
    priority.assign_initial_position(second)

    scheduling.roll_forward_adaptive(user, TODAY)

    assert schedule_of(user) == {'first': TODAY, 'second': days(1)}


@freeze_time(FROZEN)
def test_a_collision_cascades_down_a_whole_run(user, make_item, root):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    made = []
    for index, offset in enumerate([-1, 0, 1, 2]):
        item = make_item(user, f'task-{index}', parent=root, scheduled_date=days(offset))
        priority.assign_initial_position(item)
        made.append(item)

    scheduling.roll_forward_adaptive(user, TODAY)

    assert schedule_of(user) == {
        'task-0': TODAY,
        'task-1': days(1),
        'task-2': days(2),
        'task-3': days(3),
    }


@freeze_time(FROZEN)
def test_priority_order_decides_who_moves(user, make_item, root):
    """Both tasks want today; the one lower down the Priority View yields."""
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    low = make_item(user, 'low', parent=root, scheduled_date=TODAY)
    high = make_item(user, 'high', parent=root, scheduled_date=TODAY)
    priority.assign_initial_position(low)
    priority.assign_initial_position(high)
    priority.reorder(user, high.pk, 1)

    scheduling.roll_forward_adaptive(user, TODAY)

    assert schedule_of(user) == {'high': TODAY, 'low': days(1)}


@freeze_time(FROZEN)
def test_collisions_are_resolved_globally_across_roots(user, make_item):
    """Different roots share the same user capacity."""
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    first_root = make_item(user, 'course-a', ItemType.GOAL)
    second_root = make_item(user, 'course-b', ItemType.GOAL)
    a = make_item(user, 'a-task', parent=first_root, scheduled_date=TODAY)
    b = make_item(user, 'b-task', parent=second_root, scheduled_date=TODAY)
    priority.assign_initial_position(a)
    priority.assign_initial_position(b)

    scheduling.roll_forward_adaptive(user, TODAY)

    assert schedule_of(user) == {'a-task': TODAY, 'b-task': days(1)}


@freeze_time(FROZEN)
def test_a_deeply_nested_task_groups_by_its_root(user, make_item, root):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    mid = make_item(user, 'mid', ItemType.GOAL, parent=root)
    deep = make_item(user, 'deep', parent=mid, scheduled_date=TODAY)
    shallow = make_item(user, 'shallow', parent=root, scheduled_date=TODAY)
    priority.assign_initial_position(shallow)
    priority.assign_initial_position(deep)

    scheduling.roll_forward_adaptive(user, TODAY)

    # Same root despite different depths, so one of them must move.
    assert sorted(schedule_of(user).values()) == [TODAY, days(1)]


# --------------------------------------------------------------------------
# Guarantees
# --------------------------------------------------------------------------

@freeze_time(FROZEN)
def test_due_dates_are_never_modified(user, make_item, root):
    """The central promise of FR-11: ARC reschedules its own suggestions and
    leaves real deadlines alone."""
    fixed = make_item(user, 'fixed', parent=root, due_date=days(-10), start_date=days(-20))
    adaptive = make_item(user, 'adaptive', parent=root, scheduled_date=days(-10))
    before = dict(
        PlanningItem.objects.for_user(user).values_list('id', 'due_date')
    )

    scheduling.roll_forward_adaptive(user, TODAY)

    after = dict(PlanningItem.objects.for_user(user).values_list('id', 'due_date'))
    assert after == before
    fixed.refresh_from_db()
    assert fixed.start_date == days(-20)
    adaptive.refresh_from_db()
    assert adaptive.scheduled_date == TODAY


@freeze_time(FROZEN)
def test_running_twice_in_one_day_changes_nothing_the_second_time(user, make_item, root):
    for index, offset in enumerate([-5, -3, 0, 1]):
        item = make_item(user, f'task-{index}', parent=root, scheduled_date=days(offset))
        priority.assign_initial_position(item)

    scheduling.roll_forward_adaptive(user, TODAY)
    after_first = schedule_of(user)

    changed = scheduling.roll_forward_adaptive(user, TODAY)

    assert changed == []
    assert schedule_of(user) == after_first


@freeze_time(FROZEN)
def test_no_adaptive_task_is_left_in_the_past(user, make_item, root):
    for index, offset in enumerate([-9, -4, -1, 0]):
        item = make_item(user, f'task-{index}', parent=root, scheduled_date=days(offset))
        priority.assign_initial_position(item)

    scheduling.roll_forward_adaptive(user, TODAY)

    assert all(value >= TODAY for value in schedule_of(user).values())


@freeze_time(FROZEN)
def test_another_users_schedule_is_untouched(user, other_user, make_item):
    mine_root = make_item(user, 'course', ItemType.GOAL)
    theirs_root = make_item(other_user, 'course', ItemType.GOAL)
    make_item(user, 'mine', parent=mine_root, scheduled_date=days(-3))
    theirs = make_item(other_user, 'theirs', parent=theirs_root, scheduled_date=days(-3))

    scheduling.roll_forward_adaptive(user, TODAY)

    theirs.refresh_from_db()
    assert theirs.scheduled_date == days(-3)


@freeze_time(FROZEN)
def test_a_user_with_nothing_to_schedule_is_a_no_op(user):
    assert scheduling.roll_forward_adaptive(user, TODAY) == []


def test_scheduler_does_not_schedule_parent_with_unfinished_child(user):
    """Decomposed parents are not execution-schedulable."""
    from planning.models import PlanningItem
    from planning.services.scheduling import schedule

    parent = PlanningItem.objects.create(
        user=user,
        title="Assignment 2",
        item_type="ASSIGNMENT",
    )
    child = PlanningItem.objects.create(
        user=user,
        title="Implement scheduler",
        item_type="TASK",
        parent=parent,
    )

    schedule(user)

    parent.refresh_from_db()
    child.refresh_from_db()

    assert parent.scheduled_date is None
    assert child.scheduled_date is not None


def test_parent_becomes_schedulable_when_children_complete(user):
    """Completing the frontier exposes its parent as the new frontier."""
    from planning.models import PlanningItem
    from planning.services.scheduling import schedule

    parent = PlanningItem.objects.create(
        user=user,
        title="Assignment 2",
        item_type="ASSIGNMENT",
    )
    child = PlanningItem.objects.create(
        user=user,
        title="Implement scheduler",
        item_type="TASK",
        parent=parent,
        is_completed=True,
    )

    schedule(user)

    parent.refresh_from_db()

    assert parent.scheduled_date is not None

================================================================================
FILE: backend/planning/tests/test_state_semantics.py
================================================================================
"""
ARC state-semantics certification.

These tests are deliberately distinct from scheduling-invariant tests.

Invariant tests ask:
    "Is this database/schedule legal?"

These tests ask:
    "Did a legitimate state transition preserve the intended meaning of
     every piece of unrelated ARC data, recompute derived state correctly,
     and avoid stale/ghost state?"

Every scheduler-relevant mutation family should have an explicit contract
here before scheduler-algorithm experimentation begins.
"""

from dataclasses import dataclass
from enum import Enum


class Effect(str, Enum):
    PRESERVE = "preserve"
    CHANGE = "change"
    CLEAR = "clear"
    RECOMPUTE = "recompute"
    RESTORE = "restore"
    INACTIVE = "inactive"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class TransitionContract:
    name: str
    hierarchy: Effect
    lifecycle: Effect
    factual_data: Effect
    priority: Effect
    scheduling: Effect
    anchor: Effect
    duration: Effect


TRANSITION_CONTRACTS = (
    # CRUD / ordinary factual edits
    TransitionContract(
        "create_root",
        Effect.CHANGE, Effect.PRESERVE, Effect.CHANGE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.PRESERVE, Effect.CHANGE,
    ),
    TransitionContract(
        "create_child",
        Effect.CHANGE, Effect.PRESERVE, Effect.CHANGE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.PRESERVE, Effect.CHANGE,
    ),
    TransitionContract(
        "edit_title",
        Effect.PRESERVE, Effect.PRESERVE, Effect.CHANGE,
        Effect.PRESERVE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.PRESERVE,
    ),
    TransitionContract(
        "edit_duration",
        Effect.PRESERVE, Effect.PRESERVE, Effect.CHANGE,
        Effect.PRESERVE, Effect.RECOMPUTE,
        Effect.PRESERVE, Effect.CHANGE,
    ),
    TransitionContract(
        "edit_release",
        Effect.PRESERVE, Effect.PRESERVE, Effect.CHANGE,
        Effect.PRESERVE, Effect.RECOMPUTE,
        Effect.PRESERVE, Effect.PRESERVE,
    ),
    TransitionContract(
        "edit_deadline",
        Effect.PRESERVE, Effect.PRESERVE, Effect.CHANGE,
        Effect.PRESERVE, Effect.RECOMPUTE,
        Effect.PRESERVE, Effect.PRESERVE,
    ),

    # Hierarchy
    TransitionContract(
        "add_first_child",
        Effect.CHANGE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.INACTIVE,
    ),
    TransitionContract(
        "reparent_leaf",
        Effect.CHANGE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "reparent_subtree",
        Effect.CHANGE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),

    # Completion
    TransitionContract(
        "complete_leaf",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "complete_subtree",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "reopen_leaf",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "reopen_parent_only",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),

    # The semantic ambiguity we explicitly discovered.
    TransitionContract(
        "final_child_completed_parent_becomes_frontier",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.UNRESOLVED,
    ),

    # Delete / restore
    TransitionContract(
        "delete_leaf",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "delete_subtree",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "restore_leaf",
        Effect.PRESERVE, Effect.CHANGE, Effect.RESTORE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RESTORE, Effect.RESTORE,
    ),
    TransitionContract(
        "restore_subtree",
        Effect.PRESERVE, Effect.CHANGE, Effect.RESTORE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RESTORE, Effect.RESTORE,
    ),

    # Priority
    TransitionContract(
        "priority_reorder",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.CHANGE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.PRESERVE,
    ),
    TransitionContract(
        "frontier_priority_departure",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "frontier_priority_restoration",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.RESTORE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),

    # Anchors
    TransitionContract(
        "create_anchor",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.CHANGE,
        Effect.CHANGE, Effect.PRESERVE,
    ),
    TransitionContract(
        "move_anchor",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.CHANGE,
        Effect.CHANGE, Effect.PRESERVE,
    ),
    TransitionContract(
        "remove_anchor",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.RECOMPUTE,
        Effect.CLEAR, Effect.PRESERVE,
    ),
    TransitionContract(
        "expire_anchor",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.RECOMPUTE,
        Effect.CLEAR, Effect.PRESERVE,
    ),

    # Time itself is a mutation of scheduler context.
    TransitionContract(
        "advance_today",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),

    # Reversible / compound transitions.
    TransitionContract(
        "undo",
        Effect.RESTORE, Effect.RESTORE, Effect.RESTORE,
        Effect.RESTORE, Effect.RESTORE,
        Effect.RESTORE, Effect.RESTORE,
    ),
    TransitionContract(
        "redo",
        Effect.RESTORE, Effect.RESTORE, Effect.RESTORE,
        Effect.RESTORE, Effect.RESTORE,
        Effect.RESTORE, Effect.RESTORE,
    ),
)


def test_transition_contract_registry_has_unique_names():
    names = [contract.name for contract in TRANSITION_CONTRACTS]
    assert len(names) == len(set(names))


def test_only_known_semantic_question_is_parent_residual_duration():
    unresolved = [
        (contract.name, field)
        for contract in TRANSITION_CONTRACTS
        for field in (
            "hierarchy",
            "lifecycle",
            "factual_data",
            "priority",
            "scheduling",
            "anchor",
            "duration",
        )
        if getattr(contract, field) == Effect.UNRESOLVED
    ]

    assert unresolved == [
        ("final_child_completed_parent_becomes_frontier", "duration")
    ]


# ---------------------------------------------------------------------------
# Factual-data integrity
# ---------------------------------------------------------------------------

import pytest
from datetime import date, timedelta

from planning.models import PlanningItem, ItemType, DurationCategory
from planning.services import scheduling


@pytest.fixture
def semantic_user(django_user_model):
    return django_user_model.objects.create_user(
        email="semantic-user@example.com",
        password="test",
    )


def _semantic_item(user, title="Original", **overrides):
    """Create a richly populated item so preservation tests can detect loss."""
    values = {
        "title": title,
        "item_type": ItemType.TASK,
        "duration_category": DurationCategory.MIN_20_TO_60,
        "start_date": date(2026, 9, 22),
        "due_date": date(2026, 10, 10),
        "is_completed": False,
        "is_deleted": False,
    }
    values.update(overrides)
    return PlanningItem.objects.create(user=user, **values)


def _factual_snapshot(item):
    """Fields whose meaning must not silently drift during unrelated edits."""
    item.refresh_from_db()
    return {
        "title": item.title,
        "item_type": item.item_type,
        "duration_category": item.duration_category,
        "start_date": item.start_date,
        "due_date": item.due_date,
        "parent_id": item.parent_id,
        "is_completed": item.is_completed,
        "is_deleted": item.is_deleted,
    }


@pytest.mark.django_db
def test_title_edit_preserves_all_other_factual_data(semantic_user):
    item = _semantic_item(semantic_user)
    before = _factual_snapshot(item)

    item.title = "Renamed only"
    item.save(update_fields=["title"])

    after = _factual_snapshot(item)

    assert after == {
        **before,
        "title": "Renamed only",
    }


@pytest.mark.django_db
def test_duration_edit_preserves_unrelated_factual_data(semantic_user):
    item = _semantic_item(semantic_user)
    before = _factual_snapshot(item)

    item.duration_category = DurationCategory.OVER_60_MIN
    item.save(update_fields=["duration_category"])

    after = _factual_snapshot(item)

    assert after == {
        **before,
        "duration_category": DurationCategory.OVER_60_MIN,
    }


@pytest.mark.django_db
def test_release_edit_preserves_unrelated_factual_data(semantic_user):
    item = _semantic_item(semantic_user)
    before = _factual_snapshot(item)

    new_release = date(2026, 9, 25)
    item.start_date = new_release
    item.save(update_fields=["start_date"])

    after = _factual_snapshot(item)

    assert after == {
        **before,
        "start_date": new_release,
    }


@pytest.mark.django_db
def test_deadline_edit_preserves_unrelated_factual_data(semantic_user):
    item = _semantic_item(semantic_user)
    before = _factual_snapshot(item)

    new_due = date(2026, 10, 20)
    item.due_date = new_due
    item.save(update_fields=["due_date"])

    after = _factual_snapshot(item)

    assert after == {
        **before,
        "due_date": new_due,
    }


@pytest.mark.django_db
def test_repeated_factual_edits_do_not_accumulate_semantic_drift(semantic_user):
    item = _semantic_item(semantic_user)
    original = _factual_snapshot(item)

    # Hammer mutable factual properties repeatedly.
    for i in range(50):
        item.title = f"Temporary {i}"
        item.duration_category = (
            DurationCategory.OVER_60_MIN
            if i % 2
            else DurationCategory.UNDER_20_MIN
        )
        item.start_date = date(2026, 9, 22) + timedelta(days=i % 5)
        item.due_date = date(2026, 10, 10) + timedelta(days=i % 7)
        item.save()

    # Return every edited factual property to its starting value.
    item.title = original["title"]
    item.duration_category = original["duration_category"]
    item.start_date = original["start_date"]
    item.due_date = original["due_date"]
    item.save()

    assert _factual_snapshot(item) == original


@pytest.mark.django_db
def test_title_change_is_scheduler_metamorphic(semantic_user):
    """
    A title contains no scheduling semantics.

    Renaming an item must therefore leave its scheduling result unchanged.
    """
    today = date(2026, 9, 20)

    item = _semantic_item(
        semantic_user,
        start_date=today,
        due_date=today + timedelta(days=10),
    )

    scheduling.schedule(semantic_user, today=today, mode="global")
    item.refresh_from_db()

    before = (
        item.scheduled_date,
        item.schedule_is_manual,
        item.priority_position,
    )

    item.title = "Completely different words"
    item.save(update_fields=["title"])

    scheduling.schedule(semantic_user, today=today, mode="global")
    item.refresh_from_db()

    after = (
        item.scheduled_date,
        item.schedule_is_manual,
        item.priority_position,
    )

    assert after == before


# ---------------------------------------------------------------------------
# Hierarchy / execution-frontier semantic integrity
# ---------------------------------------------------------------------------

from planning.services import hierarchy


def _semantic_state(item):
    """Full scheduler-relevant semantic state of one PlanningItem."""
    item.refresh_from_db()
    return {
        # Identity / factual meaning
        "title": item.title,
        "item_type": item.item_type,
        "description": item.description,
        "duration_category": item.duration_category,
        "start_date": item.start_date,
        "due_date": item.due_date,

        # Structure
        "parent_id": item.parent_id,
        "sibling_order": item.sibling_order,

        # Lifecycle
        "is_completed": item.is_completed,
        "is_deleted": item.is_deleted,

        # Scheduling-derived state
        "scheduled_date": item.scheduled_date,
        "schedule_is_manual": item.schedule_is_manual,
        "priority_position": item.priority_position,
        "priority_restore_context": item.priority_restore_context,
    }


def _factual_meaning(item):
    """
    Data whose meaning must survive hierarchy/scheduler transitions unless
    that transition explicitly targets the field.
    """
    state = _semantic_state(item)
    return {
        key: state[key]
        for key in (
            "title",
            "item_type",
            "description",
            "duration_category",
            "start_date",
            "due_date",
        )
    }


def _is_execution_frontier(item):
    item.refresh_from_db()

    if (
        item.is_completed
        or item.is_deleted
        or item.item_type not in (ItemType.TASK, ItemType.ASSIGNMENT)
    ):
        return False

    return not PlanningItem.objects.filter(
        user=item.user,
        parent=item,
        is_completed=False,
        is_deleted=False,
    ).exists()


@pytest.mark.django_db
def test_adding_first_child_preserves_parent_factual_meaning(semantic_user):
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Assignment",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
        due_date=today + timedelta(days=14),
    )

    scheduling.schedule(semantic_user, today=today, mode="global")
    parent.refresh_from_db()

    assert _is_execution_frontier(parent)
    before = _factual_meaning(parent)

    child = _semantic_item(
        semantic_user,
        "Implementation",
        parent=parent,
        start_date=today,
        due_date=today + timedelta(days=10),
    )

    scheduling.schedule(semantic_user, today=today, mode="global")

    assert _factual_meaning(parent) == before
    assert not _is_execution_frontier(parent)
    assert _is_execution_frontier(child)

    parent.refresh_from_db()
    assert parent.scheduled_date is None
    assert child.scheduled_date is not None


@pytest.mark.django_db
def test_reopening_child_demotes_exposed_parent_without_factual_damage(
    semantic_user,
):
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Assignment",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
        due_date=today + timedelta(days=14),
    )
    child = _semantic_item(
        semantic_user,
        "Implementation",
        parent=parent,
        start_date=today,
        due_date=today + timedelta(days=10),
        is_completed=True,
    )

    scheduling.schedule(semantic_user, today=today, mode="global")
    assert _is_execution_frontier(parent)

    parent_before = _factual_meaning(parent)
    child_before = _factual_meaning(child)

    hierarchy.reopen(child)

    assert _factual_meaning(parent) == parent_before
    assert _factual_meaning(child) == child_before
    assert not _is_execution_frontier(parent)
    assert _is_execution_frontier(child)

    parent.refresh_from_db()
    assert parent.scheduled_date is None


@pytest.mark.django_db
def test_final_child_completion_exposes_parent_without_factual_damage(
    semantic_user,
):
    """
    This intentionally does NOT yet assert the correct residual duration.

    It proves all other parent meaning survives the frontier transition while
    keeping residual-parent duration as our explicit unresolved contract.
    """
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Large assignment",
        item_type=ItemType.ASSIGNMENT,
        duration_category=DurationCategory.OVER_60_MIN,
        start_date=today,
        due_date=today + timedelta(days=14),
    )
    child = _semantic_item(
        semantic_user,
        "Final child",
        parent=parent,
        start_date=today,
        due_date=today + timedelta(days=10),
    )

    parent_before = _factual_meaning(parent)

    hierarchy.complete_subtree(child)

    assert _is_execution_frontier(parent)

    # Check everything except duration, whose frontier semantics are unresolved.
    after = _factual_meaning(parent)
    for field in (
        "title",
        "item_type",
        "description",
        "start_date",
        "due_date",
    ):
        assert after[field] == parent_before[field]


@pytest.mark.django_db
def test_reparent_leaf_preserves_child_factual_meaning_and_reconciles_both_branches(
    semantic_user,
):
    today = date(2026, 9, 20)

    source = _semantic_item(
        semantic_user,
        "Source",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
        due_date=today + timedelta(days=20),
    )
    target = _semantic_item(
        semantic_user,
        "Target",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
        due_date=today + timedelta(days=20),
    )
    child = _semantic_item(
        semantic_user,
        "Movable child",
        parent=source,
        start_date=today,
        due_date=today + timedelta(days=10),
    )

    child_before = _factual_meaning(child)

    scheduling.schedule(semantic_user, today=today, mode="global")

    assert not _is_execution_frontier(source)
    assert _is_execution_frontier(target)
    assert _is_execution_frontier(child)

    hierarchy.set_parent(child, target)

    assert _factual_meaning(child) == child_before
    assert child.parent_id == target.pk

    # Source lost its unfinished child and becomes executable.
    assert _is_execution_frontier(source)

    # Target gained the unfinished child and becomes structural.
    assert not _is_execution_frontier(target)

    target.refresh_from_db()
    assert target.scheduled_date is None


@pytest.mark.django_db
def test_reparent_subtree_preserves_descendant_meaning(semantic_user):
    today = date(2026, 9, 20)

    source = _semantic_item(
        semantic_user,
        "Source",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
    )
    target = _semantic_item(
        semantic_user,
        "Target",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
    )
    branch = _semantic_item(
        semantic_user,
        "Branch",
        item_type=ItemType.ASSIGNMENT,
        parent=source,
        start_date=today,
    )
    leaf = _semantic_item(
        semantic_user,
        "Deep leaf",
        parent=branch,
        duration_category=DurationCategory.OVER_60_MIN,
        start_date=today + timedelta(days=1),
        due_date=today + timedelta(days=12),
    )

    branch_before = _factual_meaning(branch)
    leaf_before = _factual_meaning(leaf)

    hierarchy.set_parent(branch, target)

    assert _factual_meaning(branch) == branch_before
    assert _factual_meaning(leaf) == leaf_before

    branch.refresh_from_db()
    leaf.refresh_from_db()

    assert branch.parent_id == target.pk
    assert leaf.parent_id == branch.pk


@pytest.mark.django_db
def test_parent_frontier_round_trip_does_not_accumulate_semantic_drift(
    semantic_user,
):
    """
    Repeated structural <-> frontier transitions must not progressively
    corrupt factual parent/child data.
    """
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Stable parent",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
        due_date=today + timedelta(days=30),
    )
    child = _semantic_item(
        semantic_user,
        "Stable child",
        parent=parent,
        start_date=today,
        due_date=today + timedelta(days=20),
    )

    parent_original = _factual_meaning(parent)
    child_original = _factual_meaning(child)

    for _ in range(25):
        hierarchy.complete_subtree(child)

        assert _is_execution_frontier(parent)

        hierarchy.reopen(child)

        assert not _is_execution_frontier(parent)
        assert _is_execution_frontier(child)

    assert _factual_meaning(parent) == parent_original
    assert _factual_meaning(child) == child_original


# ---------------------------------------------------------------------------
# Completion / deletion / restoration / priority semantic integrity
# ---------------------------------------------------------------------------

from planning.services import priority


def _active_frontier_ids(user):
    """Current execution frontier, independent of ordering."""
    items = PlanningItem.objects.filter(
        user=user,
        is_completed=False,
        is_deleted=False,
        item_type__in=(ItemType.TASK, ItemType.ASSIGNMENT),
    )
    return {
        item.pk
        for item in items
        if _is_execution_frontier(item)
    }


@pytest.mark.django_db
def test_complete_subtree_changes_only_lifecycle_not_factual_meaning(
    semantic_user,
):
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Branch",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
        due_date=today + timedelta(days=20),
    )
    child = _semantic_item(
        semantic_user,
        "Child",
        parent=parent,
        duration_category=DurationCategory.OVER_60_MIN,
        start_date=today + timedelta(days=1),
        due_date=today + timedelta(days=10),
    )
    grandchild = _semantic_item(
        semantic_user,
        "Grandchild",
        parent=child,
        start_date=today + timedelta(days=2),
        due_date=today + timedelta(days=8),
    )

    factual_before = {
        x.pk: _factual_meaning(x)
        for x in (parent, child, grandchild)
    }

    hierarchy.complete_subtree(parent)

    for item in (parent, child, grandchild):
        item.refresh_from_db()
        assert item.is_completed is True
        assert _factual_meaning(item) == factual_before[item.pk]
        assert item.scheduled_date is None
        assert item.priority_position is None


@pytest.mark.django_db
def test_reopen_parent_only_does_not_silently_reopen_descendants(
    semantic_user,
):
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Parent",
        item_type=ItemType.ASSIGNMENT,
        is_completed=True,
        start_date=today,
    )
    child = _semantic_item(
        semantic_user,
        "Child",
        parent=parent,
        is_completed=True,
        start_date=today,
    )
    grandchild = _semantic_item(
        semantic_user,
        "Grandchild",
        parent=child,
        is_completed=True,
        start_date=today,
    )

    child_before = _factual_meaning(child)
    grandchild_before = _factual_meaning(grandchild)

    hierarchy.reopen(parent)

    parent.refresh_from_db()
    child.refresh_from_db()
    grandchild.refresh_from_db()

    assert parent.is_completed is False
    assert child.is_completed is True
    assert grandchild.is_completed is True

    assert _factual_meaning(child) == child_before
    assert _factual_meaning(grandchild) == grandchild_before

    # Completed descendants do not prevent the reopened parent being frontier.
    assert _is_execution_frontier(parent)


@pytest.mark.django_db
def test_reopening_descendant_demotes_parent_and_preserves_factual_state(
    semantic_user,
):
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Parent",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
    )
    child = _semantic_item(
        semantic_user,
        "Child",
        parent=parent,
        is_completed=True,
        start_date=today,
    )

    scheduling.schedule(semantic_user, today=today, mode="global")
    assert _is_execution_frontier(parent)

    parent_before = _factual_meaning(parent)
    child_before = _factual_meaning(child)

    hierarchy.reopen(child)
    scheduling.schedule(semantic_user, today=today, mode="global")

    assert not _is_execution_frontier(parent)
    assert _is_execution_frontier(child)
    assert _factual_meaning(parent) == parent_before
    assert _factual_meaning(child) == child_before

    parent.refresh_from_db()
    assert parent.scheduled_date is None
    assert parent.priority_position is None


@pytest.mark.django_db
def test_priority_neighbourhood_survives_frontier_departure_and_return(
    semantic_user,
):
    """
    B leaving and later returning to the frontier should restore it to its
    meaningful priority neighbourhood rather than append it arbitrarily.
    """
    today = date(2026, 9, 20)

    a = _semantic_item(semantic_user, "A", start_date=today)
    b = _semantic_item(semantic_user, "B", start_date=today)
    c = _semantic_item(semantic_user, "C", start_date=today)

    # Raw test construction bypasses ARC's normal scheduling boundary.
    # Production schedule() always reconciles priority eligibility first.
    priority.reconcile(semantic_user)

    priority.reorder(semantic_user, a.pk, 1)
    priority.reorder(semantic_user, b.pk, 2)
    priority.reorder(semantic_user, c.pk, 3)

    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()

    assert [a.priority_position, b.priority_position, c.priority_position] == [1, 2, 3]

    # Adding an unfinished child removes B from the execution frontier.
    child = _semantic_item(
        semantic_user,
        "B child",
        parent=b,
        start_date=today,
    )
    scheduling.schedule(semantic_user, today=today, mode="global")

    b.refresh_from_db()
    assert not _is_execution_frontier(b)
    assert b.priority_position is None

    # Completing that child exposes B again.
    hierarchy.complete_subtree(child)
    scheduling.schedule(semantic_user, today=today, mode="global")

    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()

    assert _is_execution_frontier(b)
    assert [a.priority_position, b.priority_position, c.priority_position] == [1, 2, 3]


@pytest.mark.django_db
def test_repeated_priority_frontier_round_trip_has_no_order_drift(
    semantic_user,
):
    today = date(2026, 9, 20)

    a = _semantic_item(semantic_user, "A", start_date=today)
    b = _semantic_item(semantic_user, "B", start_date=today)
    c = _semantic_item(semantic_user, "C", start_date=today)

    # Raw test construction bypasses ARC's normal scheduling boundary.
    # Production schedule() always reconciles priority eligibility first.
    priority.reconcile(semantic_user)

    priority.reorder(semantic_user, a.pk, 1)
    priority.reorder(semantic_user, b.pk, 2)
    priority.reorder(semantic_user, c.pk, 3)

    child = _semantic_item(
        semantic_user,
        "B child",
        parent=b,
        is_completed=True,
        start_date=today,
    )

    for _ in range(25):
        hierarchy.reopen(child)
        scheduling.schedule(semantic_user, today=today, mode="global")

        hierarchy.complete_subtree(child)
        scheduling.schedule(semantic_user, today=today, mode="global")

        a.refresh_from_db()
        b.refresh_from_db()
        c.refresh_from_db()

        assert [a.priority_position, b.priority_position, c.priority_position] == [1, 2, 3]


@pytest.mark.django_db
def test_soft_delete_preserves_factual_row_data(semantic_user):
    """
    Soft deletion itself must not destroy factual meaning.

    This exercises the model state directly; API/history round-trip behaviour
    is certified separately.
    """
    item = _semantic_item(
        semantic_user,
        "Delete me",
        description="Important factual description",
    )

    before = _factual_meaning(item)

    item.is_deleted = True
    item.save(update_fields=["is_deleted"])

    assert _factual_meaning(item) == before

    item.refresh_from_db()
    assert item.is_deleted is True


@pytest.mark.django_db
def test_delete_restore_round_trip_preserves_factual_meaning(
    semantic_user,
):
    item = _semantic_item(
        semantic_user,
        "Round trip",
        description="Must survive",
        duration_category=DurationCategory.OVER_60_MIN,
        start_date=date(2026, 9, 25),
        due_date=date(2026, 10, 8),
    )

    original = _factual_meaning(item)

    for _ in range(25):
        item.is_deleted = True
        item.save(update_fields=["is_deleted"])

        item.is_deleted = False
        item.save(update_fields=["is_deleted"])

    assert _factual_meaning(item) == original

================================================================================
FILE: backend/planning/tests/test_tenant_isolation.py
================================================================================
"""Cross-tenant isolation matrix (FR-03).

The planning DefaultRouter is the source of truth: every registered viewset
that owns a detail lookup is asked, as user B, to GET, PATCH and DELETE user
A's primary keys. A new viewset cannot ship without being included in this
sweep, which is the point of iterating ``router.registry`` rather than a
hand-maintained URL list.

Write-path cases sit beside the sweep. Queryset scoping only hides rows on
read; a payload that names a foreign ``parent``, ``tag_ids`` or priority
``item_id`` has to be rejected by UserScopedPrimaryKeyRelatedField / the
priority service, or user B could still attach themselves to user A's tree.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.mixins import (
    DestroyModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)

from canvas_integration.models import SyncLog, SyncStatus
from canvas_integration.urls import router as canvas_router
from core.mixins import UserScopedMixin
from planning.models import (
    AssignmentDetail,
    ItemType,
    PlanningItem,
    PlanningItemTag,
    Tag,
    Timezone,
)
from planning.urls import router as planning_router

pytestmark = pytest.mark.django_db

User = get_user_model()

#: 404 is the intended response (the row falls out of the scoped queryset).
#: 403 is accepted if an object-level permission fires first. Either way the
#: API must not confirm that the foreign object exists by returning it.
HIDDEN = {403, 404}

OWNED_ROUTERS = (
    ('/api/planning/', planning_router),
    ('/api/canvas/', canvas_router),
)

PATCH_BODIES = {
    'planning-item': {'title': 'hijacked'},
    'tag': {'name': 'hijacked'},
    'timezone': {'title': 'hijacked'},
    'assignment-detail': {'mark_achieved': '99.00'},
    'sync-log': {'error_message': 'hijacked'},
}


def _owned_viewsets():
    """(base_url, prefix, viewset, basename) for every user-scoped registration."""
    rows = []
    for base, router in OWNED_ROUTERS:
        for prefix, viewset, basename in router.registry:
            if issubclass(viewset, UserScopedMixin):
                rows.append((base, prefix, viewset, basename))
    return rows


def _http_allowed(viewset, method):
    return method.lower() in set(viewset.http_method_names)


def _detail_attempts(base, prefix, viewset):
    """GET / PATCH / DELETE on the canonical detail URL, plus every @action
    that takes a lookup (move, complete, …)."""
    pk_url = f'{base}{prefix}/{{pk}}/'
    attempts = []

    if issubclass(viewset, RetrieveModelMixin) and _http_allowed(viewset, 'get'):
        attempts.append(('GET', pk_url, None))
    if issubclass(viewset, UpdateModelMixin) and _http_allowed(viewset, 'patch'):
        attempts.append(('PATCH', pk_url, None))
    if issubclass(viewset, UpdateModelMixin) and _http_allowed(viewset, 'put'):
        attempts.append(('PUT', pk_url, None))
    if issubclass(viewset, DestroyModelMixin) and _http_allowed(viewset, 'delete'):
        attempts.append(('DELETE', pk_url, None))

    for action in viewset.get_extra_actions():
        if not action.detail:
            continue
        action_url = f'{base}{prefix}/{{pk}}/{action.url_path}/'
        for method in action.mapping:
            if _http_allowed(viewset, method):
                attempts.append((method.upper(), action_url, action.url_path))
    return attempts


def _detail_matrix():
    cases = []
    for base, prefix, viewset, basename in _owned_viewsets():
        for method, url_template, action in _detail_attempts(base, prefix, viewset):
            label = f'{method} {prefix}' + (f'/{action}' if action else '')
            cases.append((label, basename, method, url_template))
    return cases


DETAIL_CASES = _detail_matrix()


@pytest.fixture
def user_a(db):
    return User.objects.create_user('alice@example.com', 'corr3ct-horse-battery')


@pytest.fixture
def user_b(db):
    return User.objects.create_user('bob@example.com', 'corr3ct-horse-battery')


@pytest.fixture
def client_b(api_for, user_b):
    return api_for(user_b)


@pytest.fixture
def alice_rows(user_a, make_item):
    """One row of each owned type, identical in shape to what user B will get
    so a leaked title would be distinguishable only by id (FR-03)."""
    root = make_item(user_a, 'Shared-looking course', ItemType.GOAL)
    task = make_item(
        user_a, 'Shared-looking task', parent=root, priority_position=1,
    )
    assignment = make_item(
        user_a, 'Shared-looking assignment', ItemType.ASSIGNMENT,
        parent=root, due_date='2026-10-01', priority_position=2,
    )
    detail = AssignmentDetail.objects.create(
        planning_item=assignment, weight_percent='25.00', mark_achieved='12.00',
    )
    tag = Tag.objects.create(user=user_a, name='shared-looking')
    PlanningItemTag.objects.create(planning_item=task, tag=tag)
    timezone = Timezone.objects.create(
        user=user_a, title='Semester 2',
        start_date='2026-07-27', end_date='2026-11-01',
    )
    sync_log = SyncLog.objects.create(user=user_a, status=SyncStatus.SUCCESS)

    return {
        'planning-item': task,
        'tag': tag,
        'timezone': timezone,
        'assignment-detail': detail,
        'sync-log': sync_log,
        'root': root,
        'assignment': assignment,
    }


def _pk_for(basename, rows):
    obj = rows[basename]
    return obj.pk


def _snapshot(user_a):
    """Enough of Alice's state to prove a write did not sneak through."""
    return {
        'item_titles': list(
            PlanningItem.objects.filter(user=user_a).order_by('id').values_list('title', flat=True)
        ),
        'tag_names': list(
            Tag.objects.filter(user=user_a).order_by('id').values_list('name', flat=True)
        ),
        'timezone_titles': list(
            Timezone.objects.filter(user=user_a).order_by('id').values_list('title', flat=True)
        ),
        'marks': list(
            AssignmentDetail.objects.filter(planning_item__user=user_a)
            .order_by('planning_item_id')
            .values_list('mark_achieved', flat=True)
        ),
        'positions': list(
            PlanningItem.objects.filter(user=user_a)
            .exclude(priority_position=None)
            .order_by('priority_position')
            .values_list('priority_position', 'title')
        ),
        'item_count': PlanningItem.objects.filter(user=user_a).count(),
    }


@pytest.mark.parametrize(
    'label, basename, method, url_template',
    DETAIL_CASES,
    ids=[case[0] for case in DETAIL_CASES],
)
def test_detail_route_hides_foreign_objects(
    label, basename, method, url_template, client_b, alice_rows, user_a,
):
    """FR-03: user B cannot read, mutate or delete user A's rows by id."""
    before = _snapshot(user_a)
    pk = _pk_for(basename, alice_rows)
    url = url_template.format(pk=pk)
    body = PATCH_BODIES.get(basename, {})
    response = client_b.generic(method, url, data=body, format='json')

    assert response.status_code in HIDDEN, (
        f'{label} against Alice\'s #{pk} returned {response.status_code} '
        f'({getattr(response, "data", None)!r}); expected {sorted(HIDDEN)}'
    )
    # A 200 would have leaked or mutated. A 400 that echoes the foreign title
    # would also confirm the row exists, so only 403/404 are allowed here.
    assert _snapshot(user_a) == before


def test_the_router_matrix_covers_every_owned_viewset():
    """Guard the sweep itself: if a UserScoped viewset is registered without a
    retrieve/update/destroy mixin, the parametrize list would silently skip it."""
    covered = {basename for _, basename, _, _ in DETAIL_CASES}
    registered = {basename for _, _, _, basename in _owned_viewsets()}
    assert registered <= covered, (
        f'These user-scoped viewsets have no detail attempts: {registered - covered}'
    )
    assert {'planning-item', 'tag', 'timezone', 'assignment-detail'} <= registered


def test_list_routes_never_include_foreign_ids(client_b, alice_rows, user_b, make_item):
    """User B's own rows may appear; Alice's primary keys must not."""
    make_item(user_b, 'Bob\'s own task')
    alice_ids = {
        'planning-item': {alice_rows['planning-item'].pk, alice_rows['root'].pk,
                          alice_rows['assignment'].pk},
        'tag': {alice_rows['tag'].pk},
        'timezone': {alice_rows['timezone'].pk},
        'assignment-detail': {alice_rows['assignment-detail'].pk},
        'sync-log': {alice_rows['sync-log'].pk},
    }

    for base, prefix, viewset, basename in _owned_viewsets():
        if not hasattr(viewset, 'list') or not _http_allowed(viewset, 'get'):
            continue
        response = client_b.get(f'{base}{prefix}/')
        assert response.status_code == 200, f'GET {base}{prefix}/ -> {response.status_code}'
        payload = response.data
        rows = payload.get('results', payload) if isinstance(payload, dict) else payload
        seen = {row['id'] for row in rows}
        leaked = seen & alice_ids[basename]
        assert not leaked, f'GET {base}{prefix}/ leaked Alice ids {leaked}'


# --- Write-path: naming a foreign key in a payload --------------------------

def test_create_rejects_a_foreign_parent(client_b, alice_rows, user_a, user_b):
    before = _snapshot(user_a)
    response = client_b.post(
        '/api/planning/items/',
        {
            'item_type': ItemType.TASK,
            'title': 'Bob hanging off Alice',
            'parent': alice_rows['root'].pk,
        },
        format='json',
    )
    assert response.status_code in {400, 403, 404}, response.data
    assert PlanningItem.objects.filter(user=user_b).count() == 0
    assert _snapshot(user_a) == before


def test_create_rejects_a_foreign_tag(client_b, alice_rows, user_a, user_b):
    before = _snapshot(user_a)
    response = client_b.post(
        '/api/planning/items/',
        {
            'item_type': ItemType.TASK,
            'title': 'Bob wearing Alice\'s tag',
            'tag_ids': [alice_rows['tag'].pk],
        },
        format='json',
    )
    assert response.status_code in {400, 403, 404}, response.data
    assert PlanningItem.objects.filter(user=user_b).count() == 0
    assert not PlanningItemTag.objects.filter(tag=alice_rows['tag'], planning_item__user=user_b).exists()
    assert _snapshot(user_a) == before


def test_move_rejects_a_foreign_parent(client_b, alice_rows, user_a, user_b, make_item):
    bob_item = make_item(user_b, 'Bob\'s task')
    before = _snapshot(user_a)
    response = client_b.post(
        f'/api/planning/items/{bob_item.pk}/move/',
        {'parent_id': alice_rows['root'].pk},
        format='json',
    )
    assert response.status_code in {400, 403, 404}, response.data
    bob_item.refresh_from_db()
    assert bob_item.parent_id is None
    assert _snapshot(user_a) == before


def test_reorder_rejects_a_foreign_priority_item(client_b, alice_rows, user_a, user_b, make_item):
    make_item(user_b, 'Bob\'s task', priority_position=1)
    before = _snapshot(user_a)
    response = client_b.post(
        '/api/planning/priority/reorder/',
        {'item_id': alice_rows['planning-item'].pk, 'new_position': 1},
        format='json',
    )
    assert response.status_code in {400, 403, 404}, response.data
    assert _snapshot(user_a) == before


def test_marks_reorder_rejects_a_foreign_assessment(client_b, alice_rows, user_a):
    before = _snapshot(user_a)
    response = client_b.post(
        '/api/planning/marks/reorder/',
        {'ordered_ids': [alice_rows['assignment-detail'].pk]},
        format='json',
    )
    assert response.status_code in {400, 403, 404}, response.data
    assert _snapshot(user_a) == before

================================================================================
FILE: backend/planning/tests/test_timeline_scheduling.py
================================================================================
from datetime import date, timedelta

import pytest
from freezegun import freeze_time

from planning.models import (AssignmentDetail, DurationCategory, ItemType, PlanningHistoryEntry,
                             PlanningItem, SchedulingOverload, SchedulingPreference)
from planning.services import history, priority, scheduling

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen_clock():
    with freeze_time('2026-09-14'):
        yield
TODAY = date(2026, 9, 14)


def snapshot(user):
    return scheduling._snapshot(user)


@pytest.mark.parametrize('bucket,limit', [(DurationCategory.UNDER_20_MIN, 5), (DurationCategory.MIN_20_TO_60, 4), (DurationCategory.OVER_60_MIN, 3)])
def test_capacity_is_global_and_priority_ordered(user, make_item, bucket, limit):
    roots = [make_item(user, str(i), ItemType.GOAL) for i in range(2)]
    items = [make_item(user, str(i), parent=roots[i % 2], duration_category=bucket) for i in range(limit + 1)]
    priority.reconcile(user)
    priority.reorder(user, items[-1].pk, 1)
    result = scheduling.schedule(user, TODAY)
    assert result['conflicts'] == []
    for item in items:
        item.refresh_from_db()
    assert items[-1].scheduled_date == TODAY
    assert items[-2].scheduled_date == TODAY + timedelta(days=1)
    assert sum(item.scheduled_date == TODAY for item in items) == limit


def test_release_deadline_assignment_interval_and_overdue(user, make_item):
    task = make_item(user, 'Task', start_date=TODAY + timedelta(days=1), due_date=TODAY + timedelta(days=1))
    assignment = make_item(user, 'Assignment', ItemType.ASSIGNMENT, start_date=TODAY, due_date=TODAY + timedelta(days=9))
    past = make_item(user, 'Overdue', due_date=TODAY - timedelta(days=1))
    result = scheduling.schedule(user, TODAY)
    task.refresh_from_db()
    assignment.refresh_from_db()
    past.refresh_from_db()
    assert task.scheduled_date == task.due_date
    assert assignment.scheduled_date == TODAY
    assert past.scheduled_date == past.due_date
    assert past.due_date == TODAY - timedelta(days=1)
    assert result['conflicts'] == [{'item_id': past.pk, 'code': 'overdue'}]


def test_missed_manual_work_retains_user_dates(user, make_item):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    first = make_item(user, 'First', scheduled_date=TODAY - timedelta(days=3), schedule_is_manual=True)
    second = make_item(user, 'Second', scheduled_date=TODAY - timedelta(days=1), schedule_is_manual=True)
    scheduling.schedule(user, TODAY)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.scheduled_date == TODAY - timedelta(days=3)
    assert second.scheduled_date == TODAY - timedelta(days=1)
    assert scheduling.schedule(user, TODAY)['changed_ids'] == []


def test_manual_move_overload_and_undo_redo(user, other_user, make_item):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    first = make_item(user, 'First', scheduled_date=TODAY, schedule_is_manual=True)
    second = make_item(user, 'Second')
    third = make_item(user, 'Third')
    theirs = make_item(other_user, 'Other', scheduled_date=TODAY - timedelta(days=5))
    before = snapshot(user)
    with pytest.raises(scheduling.SchedulingConflict):
        scheduling.move_to_date(user, second.pk, TODAY)
    assert snapshot(user) == before
    scheduling.move_to_date(user, second.pk, TODAY, allow_overload=True)
    after = snapshot(user)
    assert SchedulingOverload.objects.get(user=user, date=TODAY).allowed
    first.refresh_from_db(); second.refresh_from_db(); third.refresh_from_db(); theirs.refresh_from_db()
    assert first.scheduled_date == second.scheduled_date == TODAY
    assert third.scheduled_date > TODAY  # overload never expands automatic capacity
    assert theirs.scheduled_date == TODAY - timedelta(days=5)
    assert PlanningHistoryEntry.objects.filter(user=user).count() == 1
    history.undo(user)
    assert snapshot(user) == before
    history.redo(user)
    assert snapshot(user) == after


@pytest.mark.parametrize('overload', [False, True])
def test_replacement_execution_intent_and_history(user, make_item, overload):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=2)
    a, b, c, d = [make_item(user, title) for title in 'ABCD']
    scheduling.schedule(user, TODAY)
    before = snapshot(user)
    scheduling.replace(user, d.pk, a.pk, allow_overload=overload)
    after = snapshot(user)
    assert [row.pk for row in priority.ordered(user)] == [d.pk, b.pk, a.pk, c.pk]
    a.refresh_from_db(); b.refresh_from_db(); d.refresh_from_db()
    assert d.scheduled_date == b.scheduled_date == TODAY
    assert a.scheduled_date == (TODAY if overload else TODAY + timedelta(days=1))
    assert PlanningHistoryEntry.objects.filter(user=user).count() == 1
    history.undo(user); assert snapshot(user) == before
    history.redo(user); assert snapshot(user) == after


def test_replacement_deadline_conflict_rolls_back_everything(user, make_item):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    a = make_item(user, 'A', due_date=TODAY)
    d = make_item(user, 'D')
    scheduling.schedule(user, TODAY)
    before = snapshot(user)
    with pytest.raises(scheduling.SchedulingConflict) as exc:
        scheduling.replace(user, d.pk, a.pk)
    assert exc.value.conflicts == [{'item_id': a.pk, 'code': 'no_capacity_before_deadline'}]
    assert snapshot(user) == before
    assert not PlanningHistoryEntry.objects.filter(user=user).exists()


@pytest.mark.parametrize('offset,code', [(-1, 'past_date'), (0, 'before_start'), (4, 'after_deadline')])
def test_exact_move_constraint_conflicts(user, make_item, offset, code):
    item = make_item(user, 'Task', start_date=TODAY + timedelta(days=1), due_date=TODAY + timedelta(days=3))
    before = snapshot(user)
    with pytest.raises(scheduling.SchedulingConflict) as exc:
        scheduling.move_to_date(user, item.pk, TODAY + timedelta(days=offset))
    assert exc.value.conflicts == [{'item_id': item.pk, 'code': code}]
    assert snapshot(user) == before


def test_timeline_api_context_and_tenant_scoped_operations(user, other_user, api_for, make_item):
    client = api_for(user)
    root = make_item(user, 'Root', ItemType.GOAL)
    task = make_item(user, 'Assignment', ItemType.ASSIGNMENT, parent=root, due_date=TODAY + timedelta(days=5))
    AssignmentDetail.objects.create(planning_item=task, submission_url='https://example.com/submit')
    other = make_item(other_user, 'Private')
    response = client.get('/api/planning/timeline/')
    assert response.status_code == 200, response.data
    row = response.data['groups'][0]['items'][0]
    assert row['scheduled_date'] == TODAY.isoformat()
    assert row['due_date'] != row['scheduled_date']
    assert row['submission_url'] == 'https://example.com/submit'
    assert row['hierarchy_path'] == [{'id': root.pk, 'title': root.title}]
    assert row['overdue'] is False
    before = snapshot(user)
    response = client.post('/api/planning/timeline/move/', {'item_id': other.pk, 'date': TODAY.isoformat()}, format='json')
    assert response.status_code == 409
    assert response.data['conflicts'][0]['code'] == 'not_eligible'
    assert snapshot(user) == before


def test_estimate_defaults_and_null_rejected(user, api_for):
    client = api_for(user)
    response = client.post('/api/planning/items/', {'title': 'Default', 'item_type': 'TASK'}, format='json')
    assert response.status_code == 201
    assert response.data['duration_category'] == DurationCategory.MIN_20_TO_60
    response = client.post('/api/planning/items/', {'title': 'Invalid', 'item_type': 'TASK', 'duration_category': None}, format='json')
    assert response.status_code == 400


def test_capacity_preferences_and_disabled_bucket(user, api_for, make_item):
    client = api_for(user)
    item = make_item(user, 'Task')
    response = client.patch('/api/planning/timeline/capacity/', {'minutes_20_to_60': 1}, format='json')
    assert response.status_code == 200, response.data
    assert scheduling.capacities(user)[DurationCategory.MIN_20_TO_60] == 1
    before = snapshot(user)
    response = client.patch('/api/planning/timeline/capacity/', {'minutes_20_to_60': 0}, format='json')
    assert response.status_code == 409
    assert snapshot(user) == before
    assert PlanningItem.objects.get(pk=item.pk).scheduled_date == TODAY


def test_manual_endpoints_report_changes_and_overload_is_tenant_owned(user, other_user, api_for, make_item):
    client = api_for(user)
    a, b = [make_item(user, title) for title in 'AB']
    SchedulingOverload.objects.create(user=other_user, date=TODAY, allowed=True)
    response = client.post('/api/planning/timeline/move/', {
        'item_id': a.pk, 'date': TODAY.isoformat(),
    }, format='json')
    assert response.status_code == 200, response.data
    assert a.pk in response.data['changed_ids']
    response = client.post('/api/planning/timeline/replace/', {
        'replacement_id': b.pk, 'displaced_id': a.pk,
    }, format='json')
    assert response.status_code == 200, response.data
    assert b.pk in response.data['changed_ids']
    assert client.get('/api/planning/timeline/').data['overload'] == []
    response = client.post('/api/planning/timeline/overload/', {
        'date': TODAY.isoformat(), 'allowed': True,
    }, format='json')
    assert response.status_code == 200, response.data
    assert len(client.get('/api/planning/timeline/').data['overload']) == 1
    history.undo(user)
    assert not SchedulingOverload.objects.filter(user=user).exists()
    assert SchedulingOverload.objects.filter(user=other_user, allowed=True).exists()
    history.redo(user)
    assert SchedulingOverload.objects.filter(user=user, allowed=True).exists()


def test_timeline_keeps_constraint_span_when_execution_is_outside_window(user, api_for, make_item):
    item = make_item(user, 'Long assignment', ItemType.ASSIGNMENT,
                     start_date=TODAY - timedelta(days=10), due_date=TODAY + timedelta(days=30),
                     scheduled_date=TODAY - timedelta(days=1), is_completed=True)
    response = api_for(user).get('/api/planning/timeline/', {
        'from': TODAY.isoformat(), 'to': (TODAY + timedelta(days=7)).isoformat(),
    })
    assert response.status_code == 200
    row = next(row for group in response.data['groups'] for row in group['items'] if row['id'] == item.pk)
    assert row['scheduled_date'] == (TODAY - timedelta(days=1)).isoformat()
    assert row['due_date'] == (TODAY + timedelta(days=30)).isoformat()


@pytest.mark.parametrize('bucket,limit', [
    (DurationCategory.UNDER_20_MIN, 5),
    (DurationCategory.MIN_20_TO_60, 4),
    (DurationCategory.OVER_60_MIN, 3),
])
def test_timeline_load_schedules_unscheduled_work_globally_without_history(user, other_user, api_for, make_item, bucket, limit):
    roots = [make_item(user, title, ItemType.GOAL) for title in ('A', 'B')]
    items = [make_item(user, str(i), parent=roots[i % 2], duration_category=bucket)
             for i in range(limit + 1)]
    other = make_item(other_user, 'Private', duration_category=bucket)
    priority.reconcile(user)
    # Include an existing redo branch: reads must preserve history, not just its count.
    history.record_checkpoint(user, 'PRIORITY', {'priority': []}, {'priority': history.capture_priority(user)})
    PlanningHistoryEntry.objects.filter(user=user).update(is_undone=True)
    history_before = list(PlanningHistoryEntry.objects.filter(user=user).values())
    response = api_for(user).get('/api/planning/timeline/')
    assert response.status_code == 200
    rows = {row['id']: row for group in response.data['groups'] for row in group['items']}
    assert [rows[item.pk]['scheduled_date'] for item in items] == [
        TODAY.isoformat()
    ] * limit + [(TODAY + timedelta(days=1)).isoformat()]
    assert response.data['conflicts'] == []
    assert api_for(user).get('/api/planning/timeline/').data == response.data
    assert list(PlanningHistoryEntry.objects.filter(user=user).values()) == history_before
    other.refresh_from_db()
    assert other.scheduled_date is None
    assert other.priority_position is None


def test_timeline_read_respects_preferences_manual_overload_and_constraints(user, api_for, make_item):
    SchedulingPreference.objects.create(user=user, minutes_20_to_60=1)
    SchedulingOverload.objects.create(user=user, date=TODAY, allowed=True)
    manual = [make_item(user, title, scheduled_date=TODAY, schedule_is_manual=True)
              for title in ('Manual A', 'Manual B')]
    missed = make_item(user, 'Missed', scheduled_date=TODAY - timedelta(days=2))
    assignment = make_item(user, 'Assignment', ItemType.ASSIGNMENT,
                           start_date=TODAY + timedelta(days=2), due_date=TODAY + timedelta(days=2))
    overdue = make_item(user, 'Overdue', due_date=TODAY - timedelta(days=1))
    response = api_for(user).get('/api/planning/timeline/')
    assert response.status_code == 200
    for item in [*manual, missed, assignment, overdue]:
        item.refresh_from_db()
    assert all(item.scheduled_date == TODAY and item.schedule_is_manual for item in manual)
    assert missed.scheduled_date == TODAY + timedelta(days=1)
    assert assignment.scheduled_date == assignment.start_date == assignment.due_date
    assert overdue.due_date == TODAY - timedelta(days=1)
    assert overdue.scheduled_date == overdue.due_date
    assert response.data['conflicts'] == [{'item_id': overdue.pk, 'code': 'overdue'}]
    assert not PlanningHistoryEntry.objects.filter(user=user).exists()

================================================================================
FILE: backend/planning/migrations/__init__.py
================================================================================

================================================================================
FILE: backend/planning/migrations/0001_initial.py
================================================================================
# Generated by Django 6.1.1 on 2026-09-14 10:47

import django.db.models.constraints
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlanningItem',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='created_at')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='updated_at')),
                ('id', models.BigAutoField(db_column='planning_item_id', primary_key=True, serialize=False)),
                ('item_type', models.CharField(choices=[('GOAL', 'Goal'), ('TASK', 'Task'), ('ASSIGNMENT', 'Assignment')], max_length=10)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True, null=True)),
                ('sibling_order', models.PositiveIntegerField(default=1)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('scheduled_date', models.DateField(blank=True, null=True)),
                ('duration_category', models.CharField(blank=True, choices=[('UNDER_20_MIN', 'Under 20 minutes'), ('MIN_20_TO_60', '20 to 60 minutes'), ('OVER_60_MIN', 'Over 60 minutes')], max_length=12, null=True)),
                ('priority_position', models.PositiveIntegerField(blank=True, null=True)),
                ('is_completed', models.BooleanField(default=False)),
                ('canvas_object_type', models.CharField(blank=True, choices=[('COURSE', 'Course'), ('ASSIGNMENT', 'Assignment')], max_length=10, null=True)),
                ('canvas_object_id', models.CharField(blank=True, max_length=100, null=True)),
                ('parent', models.ForeignKey(blank=True, db_column='parent_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='planning.planningitem')),
                ('user', models.ForeignKey(db_column='user_id', on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'planning_items',
                'ordering': ['sibling_order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='AssignmentDetail',
            fields=[
                ('planning_item', models.OneToOneField(db_column='planning_item_id', on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='assignment_detail', serialize=False, to='planning.planningitem')),
                ('weight_percent', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('mark_achieved', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ('submission_url', models.URLField(blank=True, max_length=1000, null=True)),
                ('marks_position', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'db_table': 'assignment_details',
                'ordering': ['marks_position'],
            },
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(db_column='tag_id', primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('user', models.ForeignKey(db_column='user_id', on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'tags',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='PlanningItemTag',
            fields=[
                ('id', models.BigAutoField(db_column='planning_item_tag_id', primary_key=True, serialize=False)),
                ('planning_item', models.ForeignKey(db_column='planning_item_id', on_delete=django.db.models.deletion.CASCADE, to='planning.planningitem')),
                ('tag', models.ForeignKey(db_column='tag_id', on_delete=django.db.models.deletion.CASCADE, to='planning.tag')),
            ],
            options={
                'db_table': 'planning_item_tags',
            },
        ),
        migrations.AddField(
            model_name='planningitem',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='planning_items', through='planning.PlanningItemTag', to='planning.tag'),
        ),
        migrations.CreateModel(
            name='Timezone',
            fields=[
                ('id', models.BigAutoField(db_column='timezone_id', primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=150)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('user', models.ForeignKey(db_column='user_id', on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'timezones',
                'ordering': ['start_date', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='tag',
            constraint=models.UniqueConstraint(fields=('user', 'name'), name='uniq_tag_name_per_user'),
        ),
        migrations.AddConstraint(
            model_name='planningitemtag',
            constraint=models.UniqueConstraint(fields=('planning_item', 'tag'), name='uniq_planning_item_tag'),
        ),
        migrations.AddConstraint(
            model_name='planningitem',
            constraint=models.UniqueConstraint(deferrable=django.db.models.constraints.Deferrable['DEFERRED'], fields=('user', 'priority_position'), name='uniq_user_priority_position'),
        ),
        migrations.AddConstraint(
            model_name='planningitem',
            constraint=models.UniqueConstraint(condition=models.Q(('canvas_object_id__isnull', False)), fields=('user', 'canvas_object_type', 'canvas_object_id'), name='uniq_canvas_object_per_user'),
        ),
        migrations.AddConstraint(
            model_name='planningitem',
            constraint=models.CheckConstraint(condition=models.Q(('id', models.F('parent_id')), _negated=True), name='planning_item_no_self_parent'),
        ),
        migrations.AddConstraint(
            model_name='planningitem',
            constraint=models.CheckConstraint(condition=models.Q(('priority_position__gte', 1), ('priority_position__isnull', True), _connector='OR'), name='planning_item_priority_position_positive'),
        ),
        migrations.AddConstraint(
            model_name='timezone',
            constraint=models.CheckConstraint(condition=models.Q(('end_date__gte', models.F('start_date'))), name='timezone_end_not_before_start'),
        ),
    ]

================================================================================
FILE: backend/planning/migrations/0002_planninghistoryentry.py
================================================================================
# Generated by Django 6.1.1 on 2026-09-17 03:23

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlanningHistoryEntry',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('action_type', models.CharField(choices=[('CREATE', 'Create'), ('UPDATE', 'Update'), ('DELETE', 'Delete'), ('MOVE', 'Move'), ('COMPLETE', 'Complete')], max_length=10)),
                ('before_state', models.JSONField(default=dict)),
                ('after_state', models.JSONField(default=dict)),
                ('is_undone', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(db_column='user_id', on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'planning_history_entries',
                'ordering': ['-id'],
                'indexes': [models.Index(fields=['user', 'is_undone', '-id'], name='planning_history_user_idx')],
            },
        ),
    ]

================================================================================
FILE: backend/planning/migrations/0003_planningitem_is_deleted.py
================================================================================
# Generated by Django 6.1.1 on 2026-09-17 03:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0002_planninghistoryentry'),
    ]

    operations = [
        migrations.AddField(
            model_name='planningitem',
            name='is_deleted',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]

================================================================================
FILE: backend/planning/migrations/0004_planningitem_priority_restore_context_and_more.py
================================================================================
# Generated by Django 6.1.1 on 2026-09-18 19:48

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0003_planningitem_is_deleted'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='planningitem',
            name='priority_restore_context',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='planningitem',
            name='schedule_is_manual',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='planninghistoryentry',
            name='action_type',
            field=models.CharField(choices=[('CREATE', 'Create'), ('UPDATE', 'Update'), ('DELETE', 'Delete'), ('MOVE', 'Move'), ('COMPLETE', 'Complete'), ('PRIORITY', 'Priority'), ('SCHEDULE', 'Schedule')], max_length=10),
        ),
        migrations.AlterField(
            model_name='planningitem',
            name='duration_category',
            field=models.CharField(choices=[('UNDER_20_MIN', 'Under 20 minutes'), ('MIN_20_TO_60', '20 to 60 minutes'), ('OVER_60_MIN', 'Over 60 minutes')], default='MIN_20_TO_60', max_length=12),
        ),
        migrations.CreateModel(
            name='SchedulingOverload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('allowed', models.BooleanField(default=True)),
                ('user', models.ForeignKey(db_column='user_id', on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('user', 'date'), name='uniq_scheduling_overload_day')],
            },
        ),
        migrations.CreateModel(
            name='SchedulingPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('under_20', models.PositiveSmallIntegerField(default=5)),
                ('minutes_20_to_60', models.PositiveSmallIntegerField(default=4)),
                ('over_60', models.PositiveSmallIntegerField(default=3)),
                ('user', models.ForeignKey(db_column='user_id', on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('user',), name='uniq_scheduling_preferences_user')],
            },
        ),
    ]

================================================================================
FILE: backend/planning/migrations/0005_scheduling_state.py
================================================================================
# Generated by Django 6.1.1 on 2026-09-19 08:38

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0004_planningitem_priority_restore_context_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SchedulingState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_global_date', models.DateField(blank=True, null=True)),
                ('user', models.ForeignKey(db_column='user_id', on_delete=django.db.models.deletion.CASCADE, related_name='%(class)ss', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('user',), name='uniq_scheduling_state_user')],
            },
        ),
    ]

================================================================================
FILE: arena/algorithms/__init__.py
================================================================================

================================================================================
FILE: arena/algorithms/arc_baseline.py
================================================================================
"""A0 — current ARC production scheduler, unchanged."""

from planning.models import PlanningItem
from planning.services.scheduling import reschedule


NAME = "A0 — Current ARC Scheduler"


def run(user, today):
    anchored_before = {
        item.id: item.scheduled_date
        for item in PlanningItem.objects.filter(
            user=user,
            schedule_is_manual=True,
            is_deleted=False,
        )
    }

    completed_before = {
        item.id: item.scheduled_date
        for item in PlanningItem.objects.filter(
            user=user,
            is_completed=True,
            is_deleted=False,
        )
    }

    result = reschedule(user, today=today)

    return {
        "algorithm": NAME,
        "anchored_before": anchored_before,
        "completed_before": completed_before,
        "arc_result": result,
    }

================================================================================
FILE: arena/evaluation/__init__.py
================================================================================

================================================================================
FILE: arena/evaluation/invariants.py
================================================================================
"""Hard-invariant validation shared by every Arena scheduler."""

from __future__ import annotations

from dataclasses import dataclass

from planning.models import PlanningItem


@dataclass(frozen=True)
class Violation:
    kind: str
    item_id: int
    title: str
    detail: str


def actionable_items(user):
    return PlanningItem.objects.filter(
        user=user,
        is_deleted=False,
        is_completed=False,
        item_type__in=("TASK", "ASSIGNMENT"),
    )


def execution_frontier(user):
    """Incomplete actionable items with no incomplete visible children."""
    candidates = actionable_items(user).prefetch_related("children")

    return [
        item
        for item in candidates
        if not item.children.filter(
            is_deleted=False,
            is_completed=False,
        ).exists()
    ]


def validate_schedule(
    user,
    *,
    benchmark_today,
    anchored_before=None,
    completed_before=None,
):
    violations: list[Violation] = []
    frontier_ids = {item.id for item in execution_frontier(user)}

    scheduled = PlanningItem.objects.filter(
        user=user,
        is_deleted=False,
        is_completed=False,
        scheduled_date__isnull=False,
    )

    for item in scheduled:
        if item.item_type not in ("TASK", "ASSIGNMENT"):
            violations.append(
                Violation(
                    "non_actionable_scheduled",
                    item.id,
                    item.title,
                    f"{item.item_type} scheduled on {item.scheduled_date}",
                )
            )
            continue

        if item.id not in frontier_ids:
            violations.append(
                Violation(
                    "non_frontier_scheduled",
                    item.id,
                    item.title,
                    "item has unfinished child work",
                )
            )

        if not item.schedule_is_manual and item.scheduled_date < benchmark_today:
            violations.append(
                Violation(
                    "scheduled_in_past",
                    item.id,
                    item.title,
                    f"{item.scheduled_date} < benchmark today {benchmark_today}",
                )
            )

        if item.start_date and item.scheduled_date < item.start_date:
            violations.append(
                Violation(
                    "before_release",
                    item.id,
                    item.title,
                    f"{item.scheduled_date} < release {item.start_date}",
                )
            )

        if item.due_date and item.scheduled_date > item.due_date:
            violations.append(
                Violation(
                    "after_deadline",
                    item.id,
                    item.title,
                    f"{item.scheduled_date} > deadline {item.due_date}",
                )
            )

    current = {
        item.id: item
        for item in PlanningItem.objects.filter(user=user)
    }

    for item_id, original_date in (anchored_before or {}).items():
        item = current.get(item_id)
        if item is None or item.scheduled_date != original_date:
            violations.append(
                Violation(
                    "anchor_moved",
                    item_id,
                    item.title if item else "<missing>",
                    f"{original_date} -> "
                    f"{item.scheduled_date if item else '<missing>'}",
                )
            )

    for item_id, original_date in (completed_before or {}).items():
        item = current.get(item_id)
        if item is None or item.scheduled_date != original_date:
            violations.append(
                Violation(
                    "completed_item_changed",
                    item_id,
                    item.title if item else "<missing>",
                    f"{original_date} -> "
                    f"{item.scheduled_date if item else '<missing>'}",
                )
            )

    return violations

================================================================================
FILE: arena/evaluation/lifecycle.py
================================================================================
"""Dynamic scheduling lifecycle checks for ARC Scheduler Arena."""

from __future__ import annotations

from dataclasses import dataclass

from planning.models import PlanningItem

from arena.evaluation.invariants import execution_frontier, validate_schedule


@dataclass(frozen=True)
class ScheduleSnapshot:
    scheduled: tuple[tuple[int, object], ...]
    frontier: tuple[int, ...]


def snapshot(user) -> ScheduleSnapshot:
    scheduled = tuple(
        PlanningItem.objects.filter(
            user=user,
            is_deleted=False,
            is_completed=False,
            scheduled_date__isnull=False,
        )
        .order_by("id")
        .values_list("id", "scheduled_date")
    )

    frontier = tuple(
        sorted(item.id for item in execution_frontier(user))
    )

    return ScheduleSnapshot(
        scheduled=scheduled,
        frontier=frontier,
    )


def schedule_map(user):
    return dict(
        PlanningItem.objects.filter(
            user=user,
            is_deleted=False,
            is_completed=False,
        ).values_list("id", "scheduled_date")
    )


def movement_count(before, after):
    keys = set(before) & set(after)
    return sum(before[k] != after[k] for k in keys)


def validate_transition(
    user,
    *,
    today,
    anchored_before,
    completed_before,
):
    return validate_schedule(
        user,
        benchmark_today=today,
        anchored_before=anchored_before,
        completed_before=completed_before,
    )

================================================================================
FILE: arena/experiments/__init__.py
================================================================================

================================================================================
FILE: arena/experiments/run_baseline.py
================================================================================
"""Run the current ARC scheduler against an Arena benchmark scenario."""

from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django

django.setup()

from accounts.models import User
from planning.models import PlanningItem

from arena.algorithms.arc_baseline import NAME, run
from arena.datasets.importer import load_scenario, _rows
from arena.evaluation.invariants import execution_frontier, validate_schedule


def full_title(item):
    parts = [item.title]
    parent = item.parent

    while parent is not None:
        parts.append(parent.title)
        parent = parent.parent

    return " | ".join(reversed(parts))


def main():
    scenario = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "realistic_normal_semester"
    )

    print("=" * 72)
    print("ARC SCHEDULER ARENA")
    print("=" * 72)
    print(f"Scenario:  {scenario}")
    print(f"Algorithm: {NAME}")
    print()

    scenario_meta = next(
        row for row in _rows("scenarios.csv")
        if row["scenario"] == scenario
    )
    benchmark_today = date.fromisoformat(scenario_meta["today"])

    load_scenario(scenario)

    user = User.objects.get(email="arena@local.test")

    all_items = PlanningItem.objects.filter(
        user=user,
        is_deleted=False,
    )

    frontier_before = execution_frontier(user)

    print("PRE-RUN")
    print("-" * 72)
    print(f"Planning items:      {all_items.count()}")
    print(f"Execution frontier: {len(frontier_before)}")
    print()

    result = run(user, benchmark_today)

    violations = validate_schedule(
        user,
        benchmark_today=benchmark_today,
        anchored_before=result["anchored_before"],
        completed_before=result["completed_before"],
    )

    scheduled = (
        PlanningItem.objects
        .filter(
            user=user,
            is_deleted=False,
            is_completed=False,
            scheduled_date__isnull=False,
        )
        .select_related("parent")
        .order_by("scheduled_date", "priority_position", "id")
    )

    print("SCHEDULE")
    print("-" * 72)

    current_date = None

    for item in scheduled:
        if item.scheduled_date != current_date:
            current_date = item.scheduled_date
            print()
            print(current_date)

        anchor = " ⚓" if item.schedule_is_manual else ""
        priority = (
            f"P{item.priority_position}"
            if item.priority_position is not None
            else "P-"
        )

        print(
            f"  {priority:<5} "
            f"{full_title(item)}{anchor}"
        )

    print()
    print("=" * 72)
    print("VALIDATION")
    print("=" * 72)

    if not violations:
        print("PASS — no hard-invariant violations")
    else:
        counts = Counter(v.kind for v in violations)

        print(f"FAIL — {len(violations)} violation(s)")
        print()

        for kind, count in sorted(counts.items()):
            print(f"  {kind:<28} {count}")

        print()
        print("DETAILS")
        print("-" * 72)

        for violation in violations:
            print(
                f"[{violation.kind}] "
                f"{violation.title}: "
                f"{violation.detail}"
            )

    print()
    print("=" * 72)
    print(
        f"Scheduled: {scheduled.count()} | "
        f"Frontier before run: {len(frontier_before)} | "
        f"Violations: {len(violations)}"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()

================================================================================
FILE: arena/experiments/run_invariant_gauntlet.py
================================================================================
"""Run A0 through every micro hard-invariant benchmark."""

from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django

django.setup()

from accounts.models import User
from planning.models import PlanningItem

from arena.algorithms.arc_baseline import NAME, run
from arena.datasets.importer import _rows, load_scenario
from arena.evaluation.invariants import (
    execution_frontier,
    validate_schedule,
)


def main():
    scenario_rows = [
        row
        for row in _rows("scenarios.csv")
        if row["family"] == "micro"
    ]

    print("=" * 78)
    print("A0 HARD-INVARIANT GAUNTLET")
    print(f"Algorithm: {NAME}")
    print("=" * 78)

    results = []

    for meta in scenario_rows:
        scenario = meta["scenario"]
        benchmark_today = date.fromisoformat(meta["today"])

        try:
            # Fresh DB state for every scenario.
            load_scenario(scenario)

            user = User.objects.get(email="arena@local.test")

            frontier_before = len(execution_frontier(user))

            result = run(user, benchmark_today)

            violations = validate_schedule(
                user,
                benchmark_today=benchmark_today,
                anchored_before=result["anchored_before"],
                completed_before=result["completed_before"],
            )

            scheduled = PlanningItem.objects.filter(
                user=user,
                is_deleted=False,
                is_completed=False,
                scheduled_date__isnull=False,
            ).count()

            results.append(
                {
                    "scenario": scenario,
                    "passed": not violations,
                    "violations": violations,
                    "frontier": frontier_before,
                    "scheduled": scheduled,
                    "error": None,
                }
            )

        except Exception as exc:
            results.append(
                {
                    "scenario": scenario,
                    "passed": False,
                    "violations": [],
                    "frontier": None,
                    "scheduled": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    print()
    print(f"{'SCENARIO':<38} {'RESULT':<8} {'FRONTIER':>8} {'SCHEDULED':>10}")
    print("-" * 78)

    for result in results:
        status = "PASS" if result["passed"] else "FAIL"

        frontier = (
            str(result["frontier"])
            if result["frontier"] is not None
            else "-"
        )
        scheduled = (
            str(result["scheduled"])
            if result["scheduled"] is not None
            else "-"
        )

        print(
            f"{result['scenario']:<38} "
            f"{status:<8} "
            f"{frontier:>8} "
            f"{scheduled:>10}"
        )

    failures = [r for r in results if not r["passed"]]

    if failures:
        print()
        print("=" * 78)
        print("FAILURE DETAILS")
        print("=" * 78)

        for result in failures:
            print()
            print(result["scenario"])
            print("-" * len(result["scenario"]))

            if result["error"]:
                print(f"ERROR: {result['error']}")
                continue

            counts = Counter(v.kind for v in result["violations"])

            for kind, count in sorted(counts.items()):
                print(f"{kind:<30} {count}")

            for violation in result["violations"]:
                print(
                    f"  [{violation.kind}] "
                    f"{violation.title}: {violation.detail}"
                )

    passed = sum(r["passed"] for r in results)
    total = len(results)

    print()
    print("=" * 78)
    print(f"RESULT: {passed}/{total} micro scenarios passed")
    print("=" * 78)

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

================================================================================
FILE: arena/experiments/run_lifecycle_gauntlet.py
================================================================================
"""Exercise ARC through realistic hierarchy/state transitions."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django

django.setup()

from accounts.models import User
from planning.models import PlanningItem, SchedulingPreference
from planning.services import scheduling

from arena.evaluation.invariants import execution_frontier
from arena.evaluation.lifecycle import (
    schedule_map,
    snapshot,
    validate_transition,
)


TODAY = date(2026, 9, 20)


def reset():
    PlanningItem.objects.all().delete()
    SchedulingPreference.objects.all().delete()
    User.objects.filter(email="lifecycle@arena.test").delete()

    user = User.objects.create_user(
        email="lifecycle@arena.test",
        password="arena-local-only",
    )

    SchedulingPreference.objects.create(
        user=user,
        under_20=5,
        minutes_20_to_60=4,
        over_60=3,
    )

    return user


def item(
    user,
    title,
    *,
    kind="TASK",
    parent=None,
    due_days=14,
    completed=False,
    manual=False,
    scheduled=None,
):
    return PlanningItem.objects.create(
        user=user,
        title=title,
        item_type=kind,
        parent=parent,
        due_date=TODAY + timedelta(days=due_days),
        is_completed=completed,
        schedule_is_manual=manual,
        scheduled_date=scheduled,
    )


def reschedule_and_validate(user):
    anchored_before = {
        x.id: x.scheduled_date
        for x in PlanningItem.objects.filter(
            user=user,
            schedule_is_manual=True,
            is_deleted=False,
        )
    }

    completed_before = {
        x.id: x.scheduled_date
        for x in PlanningItem.objects.filter(
            user=user,
            is_completed=True,
            is_deleted=False,
        )
    }

    scheduling.reschedule(user, today=TODAY)

    return validate_transition(
        user,
        today=TODAY,
        anchored_before=anchored_before,
        completed_before=completed_before,
    )


def assert_clean(user):
    violations = reschedule_and_validate(user)
    assert not violations, violations


def test_progressive_frontier_exposure():
    user = reset()

    assignment = item(user, "Assignment", kind="ASSIGNMENT")
    section = item(user, "Implementation", parent=assignment)
    leaf_a = item(user, "Build backend", parent=section)
    leaf_b = item(user, "Write tests", parent=section)

    assert_clean(user)

    frontier = {x.id for x in execution_frontier(user)}
    assert leaf_a.id in frontier
    assert leaf_b.id in frontier
    assert section.id not in frontier
    assert assignment.id not in frontier

    leaf_a.is_completed = True
    leaf_a.save(update_fields=["is_completed"])
    assert_clean(user)

    frontier = {x.id for x in execution_frontier(user)}
    assert leaf_b.id in frontier
    assert section.id not in frontier

    leaf_b.is_completed = True
    leaf_b.save(update_fields=["is_completed"])
    assert_clean(user)

    section.refresh_from_db()
    frontier = {x.id for x in execution_frontier(user)}

    assert section.id in frontier
    assert section.scheduled_date is not None
    assert assignment.id not in frontier

    section.is_completed = True
    section.save(update_fields=["is_completed"])
    assert_clean(user)

    assignment.refresh_from_db()
    frontier = {x.id for x in execution_frontier(user)}

    assert assignment.id in frontier
    assert assignment.scheduled_date is not None


def test_reopening_child_demotes_parent():
    user = reset()

    parent = item(user, "Report", kind="ASSIGNMENT")
    child = item(user, "Draft", parent=parent, completed=True)

    assert_clean(user)

    parent.refresh_from_db()
    assert parent.scheduled_date is not None

    child.is_completed = False
    child.save(update_fields=["is_completed"])

    assert_clean(user)

    parent.refresh_from_db()
    child.refresh_from_db()

    frontier = {x.id for x in execution_frontier(user)}

    assert parent.id not in frontier
    assert parent.scheduled_date is None
    assert child.id in frontier
    assert child.scheduled_date is not None


def test_adding_child_demotes_scheduled_parent():
    user = reset()

    parent = item(user, "Submit project", kind="ASSIGNMENT")

    assert_clean(user)
    parent.refresh_from_db()
    assert parent.scheduled_date is not None

    child = item(user, "Final review", parent=parent)

    assert_clean(user)

    parent.refresh_from_db()
    child.refresh_from_db()

    assert parent.scheduled_date is None
    assert child.scheduled_date is not None


def test_completing_one_leaf_does_not_expose_parent_early():
    user = reset()

    parent = item(user, "Assignment", kind="ASSIGNMENT")
    a = item(user, "Part A", parent=parent)
    b = item(user, "Part B", parent=parent)

    assert_clean(user)

    a.is_completed = True
    a.save(update_fields=["is_completed"])

    assert_clean(user)

    parent.refresh_from_db()
    b.refresh_from_db()

    assert parent.scheduled_date is None
    assert b.scheduled_date is not None


def test_anchor_survives_other_completions():
    user = reset()

    parent = item(user, "Coursework", kind="ASSIGNMENT")

    anchored = item(
        user,
        "Presentation",
        parent=parent,
        manual=True,
        scheduled=TODAY + timedelta(days=5),
    )

    other = item(user, "Research", parent=parent)

    assert_clean(user)

    other.is_completed = True
    other.save(update_fields=["is_completed"])

    assert_clean(user)

    anchored.refresh_from_db()
    assert anchored.scheduled_date == TODAY + timedelta(days=5)


def test_reschedule_is_idempotent():
    user = reset()

    parent = item(user, "Project", kind="ASSIGNMENT")

    for n in range(8):
        item(
            user,
            f"Task {n + 1}",
            parent=parent,
            due_days=5 + n,
        )

    assert_clean(user)
    first = snapshot(user)

    assert_clean(user)
    second = snapshot(user)

    assert first == second


def test_repeated_completion_sequence_remains_valid():
    user = reset()

    root = item(user, "Large Assignment", kind="ASSIGNMENT")

    phase_a = item(user, "Research Phase", parent=root)
    phase_b = item(user, "Build Phase", parent=root)
    phase_c = item(user, "Report Phase", parent=root)

    leaves = [
        item(user, "Find sources", parent=phase_a),
        item(user, "Read papers", parent=phase_a),
        item(user, "Implement core", parent=phase_b),
        item(user, "Integration tests", parent=phase_b),
        item(user, "Draft report", parent=phase_c),
        item(user, "Proofread", parent=phase_c),
    ]

    assert_clean(user)

    for leaf in leaves:
        leaf.is_completed = True
        leaf.save(update_fields=["is_completed"])
        assert_clean(user)

    for phase in (phase_a, phase_b, phase_c):
        phase.refresh_from_db()

    assert all(
        phase.id in {x.id for x in execution_frontier(user)}
        for phase in (phase_a, phase_b, phase_c)
    )


TESTS = [
    test_progressive_frontier_exposure,
    test_reopening_child_demotes_parent,
    test_adding_child_demotes_scheduled_parent,
    test_completing_one_leaf_does_not_expose_parent_early,
    test_anchor_survives_other_completions,
    test_reschedule_is_idempotent,
    test_repeated_completion_sequence_remains_valid,
]


def main():
    print("=" * 78)
    print("A0 DYNAMIC LIFECYCLE GAUNTLET")
    print("=" * 78)

    failures = []

    for test in TESTS:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as exc:
            failures.append((test.__name__, exc))
            print(f"FAIL  {test.__name__}")
            print(f"      {type(exc).__name__}: {exc}")

    print()
    print("=" * 78)
    print(f"RESULT: {len(TESTS) - len(failures)}/{len(TESTS)} lifecycle tests passed")
    print("=" * 78)

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

================================================================================
FILE: arena/experiments/run_state_machine_torture.py
================================================================================
"""Deterministic state-machine torture test for ARC scheduling infrastructure."""

from __future__ import annotations

import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django
django.setup()

from accounts.models import User
from planning.models import PlanningItem, SchedulingPreference
from planning.services import hierarchy, scheduling

from arena.evaluation.invariants import validate_schedule


TODAY = date(2026, 9, 20)

SEEDS = 100
STEPS_PER_SEED = 100
INITIAL_ITEMS = 20


def reset(seed):
    PlanningItem.objects.all().delete()
    SchedulingPreference.objects.all().delete()
    User.objects.filter(email="torture@arena.test").delete()

    user = User.objects.create_user(
        email="torture@arena.test",
        password="arena-local-only",
    )

    SchedulingPreference.objects.create(
        user=user,
        under_20=5,
        minutes_20_to_60=4,
        over_60=3,
    )

    rng = random.Random(seed)

    roots = []

    for i in range(4):
        roots.append(
            PlanningItem.objects.create(
                user=user,
                title=f"Root {i}",
                item_type="ASSIGNMENT",
                due_date=TODAY + timedelta(days=rng.randint(10, 40)),
            )
        )

    existing = list(roots)

    for i in range(INITIAL_ITEMS - len(roots)):
        parent = rng.choice(existing)

        child = PlanningItem.objects.create(
            user=user,
            title=f"Initial {i}",
            item_type="TASK",
            parent=parent,
            due_date=TODAY + timedelta(days=rng.randint(2, 40)),
        )

        existing.append(child)

    return user, rng


def active(user):
    return list(
        PlanningItem.objects.filter(
            user=user,
            is_deleted=False,
        )
    )


def reschedule_and_validate(user):
    anchors = dict(
        PlanningItem.objects.filter(
            user=user,
            schedule_is_manual=True,
            is_deleted=False,
        ).values_list("id", "scheduled_date")
    )

    completed = dict(
        PlanningItem.objects.filter(
            user=user,
            is_completed=True,
            is_deleted=False,
        ).values_list("id", "scheduled_date")
    )

    scheduling.reschedule(user, today=TODAY)

    violations = validate_schedule(
        user,
        benchmark_today=TODAY,
        anchored_before=anchors,
        completed_before=completed,
    )

    if violations:
        raise AssertionError(
            "; ".join(
                f"{v.kind}:{v.item_id}:{v.detail}"
                for v in violations
            )
        )


def op_complete(user, rng):
    candidates = [
        x for x in active(user)
        if not x.is_completed
    ]
    if not candidates:
        return "complete:no-op"

    item = rng.choice(candidates)
    hierarchy.complete_subtree(item)
    return f"complete:{item.id}"


def op_reopen(user, rng):
    candidates = [
        x for x in active(user)
        if x.is_completed
    ]
    if not candidates:
        return "reopen:no-op"

    item = rng.choice(candidates)
    hierarchy.reopen(item)
    return f"reopen:{item.id}"


def op_add_child(user, rng):
    candidates = [
        x for x in active(user)
        if not x.is_completed and not x.schedule_is_manual
    ]
    if not candidates:
        return "add_child:no-op"

    parent = rng.choice(candidates)

    child = PlanningItem.objects.create(
        user=user,
        title=f"Generated child {rng.randrange(1_000_000)}",
        item_type="TASK",
        parent=parent,
        due_date=TODAY + timedelta(days=rng.randint(1, 45)),
    )

    return f"add_child:{parent.id}->{child.id}"


def op_delete(user, rng):
    candidates = [
        x for x in active(user)
        if not x.schedule_is_manual
    ]
    if not candidates:
        return "delete:no-op"

    item = rng.choice(candidates)
    item.is_deleted = True
    item.save(update_fields=["is_deleted"])

    return f"delete:{item.id}"


def op_restore(user, rng):
    candidates = list(
        PlanningItem.objects.filter(
            user=user,
            is_deleted=True,
            schedule_is_manual=False,
        )
    )

    if not candidates:
        return "restore:no-op"

    item = rng.choice(candidates)
    item.is_deleted = False
    item.save(update_fields=["is_deleted"])

    return f"restore:{item.id}"


def op_reparent(user, rng):
    candidates = [
        x for x in active(user)
        if not x.is_completed and not x.schedule_is_manual
    ]

    if len(candidates) < 2:
        return "reparent:no-op"

    rng.shuffle(candidates)

    for item in candidates:
        possible = [x for x in candidates if x.pk != item.pk]
        rng.shuffle(possible)

        for parent in possible:
            try:
                hierarchy.set_parent(item, parent)
                return f"reparent:{item.id}->{parent.id}"
            except Exception:
                continue

    return "reparent:no-op"


def op_change_release(user, rng):
    candidates = [
        x for x in active(user)
        if not x.is_completed and not x.schedule_is_manual
    ]
    if not candidates:
        return "release:no-op"

    item = rng.choice(candidates)

    latest = max(0, (item.due_date - TODAY).days if item.due_date else 30)
    offset = rng.randint(0, latest)

    item.start_date = TODAY + timedelta(days=offset)
    item.save(update_fields=["start_date"])

    return f"release:{item.id}:{item.start_date}"


def op_change_due(user, rng):
    candidates = [
        x for x in active(user)
        if not x.is_completed and not x.schedule_is_manual
    ]
    if not candidates:
        return "due:no-op"

    item = rng.choice(candidates)

    earliest = (
        max(TODAY, item.start_date)
        if item.start_date
        else TODAY
    )

    item.due_date = earliest + timedelta(days=rng.randint(0, 45))
    item.save(update_fields=["due_date"])

    return f"due:{item.id}:{item.due_date}"


OPERATIONS = [
    op_complete,
    op_reopen,
    op_add_child,
    op_delete,
    op_restore,
    op_reparent,
    op_change_release,
    op_change_due,
]


def run_seed(seed):
    user, rng = reset(seed)
    history = []

    reschedule_and_validate(user)

    for step in range(STEPS_PER_SEED):
        op = rng.choice(OPERATIONS)

        try:
            description = op(user, rng)
            history.append(description)

            reschedule_and_validate(user)

            # Idempotence check after every mutation.
            before = dict(
                PlanningItem.objects.filter(user=user)
                .values_list("id", "scheduled_date")
            )

            reschedule_and_validate(user)

            after = dict(
                PlanningItem.objects.filter(user=user)
                .values_list("id", "scheduled_date")
            )

            assert before == after, "reschedule is not idempotent"

        except Exception as exc:
            print()
            print("=" * 78)
            print("STATE-MACHINE FAILURE")
            print("=" * 78)
            print(f"seed:      {seed}")
            print(f"step:      {step}")
            print(f"operation: {history[-1] if history else '<initial>'}")
            print(f"error:     {type(exc).__name__}: {exc}")
            print()
            print("REPLAY HISTORY")
            print("-" * 78)

            for i, event in enumerate(history):
                print(f"{i:03d}  {event}")

            raise


def main():
    print("=" * 78)
    print("ARC SEEDED STATE-MACHINE TORTURE")
    print(
        f"{SEEDS} seeds × {STEPS_PER_SEED} transitions "
        f"= {SEEDS * STEPS_PER_SEED:,} states"
    )
    print("=" * 78)

    for seed in range(SEEDS):
        run_seed(seed)

        if (seed + 1) % 10 == 0:
            print(f"PASS  seeds 0–{seed}")

    print()
    print("=" * 78)
    print(
        f"PASS — {SEEDS * STEPS_PER_SEED:,} "
        "state transitions survived"
    )
    print("=" * 78)


if __name__ == "__main__":
    main()

================================================================================
FILE: arena/experiments/run_transition_matrix.py
================================================================================
"""ARC infrastructure certification: deterministic hierarchy/state transitions."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django
django.setup()

from accounts.models import User
from planning.models import PlanningItem, SchedulingPreference
from planning.services import hierarchy, scheduling

from arena.evaluation.invariants import execution_frontier, validate_schedule


TODAY = date(2026, 9, 20)


def reset():
    PlanningItem.objects.all().delete()
    SchedulingPreference.objects.all().delete()
    User.objects.filter(email="certification@arena.test").delete()

    user = User.objects.create_user(
        email="certification@arena.test",
        password="arena-local-only",
    )

    SchedulingPreference.objects.create(
        user=user,
        under_20=5,
        minutes_20_to_60=4,
        over_60=3,
    )

    return user


def make(
    user,
    title,
    *,
    parent=None,
    kind="TASK",
    completed=False,
    deleted=False,
    manual=False,
    scheduled=None,
    release=None,
    due=None,
):
    return PlanningItem.objects.create(
        user=user,
        title=title,
        parent=parent,
        item_type=kind,
        is_completed=completed,
        is_deleted=deleted,
        schedule_is_manual=manual,
        scheduled_date=scheduled,
        start_date=release,
        due_date=due or TODAY + timedelta(days=30),
    )


def run_and_assert(user):
    anchors = dict(
        PlanningItem.objects.filter(
            user=user,
            schedule_is_manual=True,
            is_deleted=False,
        ).values_list("id", "scheduled_date")
    )

    completed = dict(
        PlanningItem.objects.filter(
            user=user,
            is_completed=True,
            is_deleted=False,
        ).values_list("id", "scheduled_date")
    )

    scheduling.reschedule(user, today=TODAY)

    violations = validate_schedule(
        user,
        benchmark_today=TODAY,
        anchored_before=anchors,
        completed_before=completed,
    )

    assert not violations, violations


def frontier_ids(user):
    return {x.id for x in execution_frontier(user)}


def test_complete_final_child_exposes_parent():
    u = reset()
    p = make(u, "Parent", kind="ASSIGNMENT")
    c = make(u, "Child", parent=p)

    run_and_assert(u)
    assert c.id in frontier_ids(u)
    assert p.id not in frontier_ids(u)

    hierarchy.complete_subtree(c)
    run_and_assert(u)

    p.refresh_from_db()
    assert p.id in frontier_ids(u)
    assert p.scheduled_date is not None


def test_reopen_child_demotes_parent():
    u = reset()
    p = make(u, "Parent", kind="ASSIGNMENT")
    c = make(u, "Child", parent=p, completed=True)

    run_and_assert(u)
    assert p.id in frontier_ids(u)

    hierarchy.reopen(c)
    run_and_assert(u)

    p.refresh_from_db()
    c.refresh_from_db()

    assert p.id not in frontier_ids(u)
    assert p.scheduled_date is None
    assert c.id in frontier_ids(u)


def test_completed_child_of_frontier_reopened():
    """Explicit regression for parent→frontier→parent transition."""
    u = reset()

    root = make(u, "Root", kind="ASSIGNMENT")
    leaf = make(u, "Leaf", parent=root)
    child = make(u, "Previously completed child", parent=leaf, completed=True)

    run_and_assert(u)

    leaf.refresh_from_db()
    assert leaf.id in frontier_ids(u)
    assert leaf.scheduled_date is not None

    hierarchy.reopen(child)
    run_and_assert(u)

    leaf.refresh_from_db()
    child.refresh_from_db()

    assert leaf.id not in frontier_ids(u)
    assert leaf.scheduled_date is None
    assert child.id in frontier_ids(u)
    assert child.scheduled_date is not None


def test_only_final_sibling_completion_exposes_parent():
    u = reset()
    p = make(u, "Parent", kind="ASSIGNMENT")
    a = make(u, "A", parent=p)
    b = make(u, "B", parent=p)

    run_and_assert(u)

    hierarchy.complete_subtree(a)
    run_and_assert(u)
    assert p.id not in frontier_ids(u)

    hierarchy.complete_subtree(b)
    run_and_assert(u)
    assert p.id in frontier_ids(u)


def test_add_child_demotes_frontier_parent():
    u = reset()
    p = make(u, "Parent", kind="ASSIGNMENT")

    run_and_assert(u)
    assert p.id in frontier_ids(u)

    c = make(u, "New child", parent=p)
    run_and_assert(u)

    p.refresh_from_db()

    assert p.id not in frontier_ids(u)
    assert p.scheduled_date is None
    assert c.id in frontier_ids(u)


def test_delete_final_child_exposes_parent():
    u = reset()
    p = make(u, "Parent", kind="ASSIGNMENT")
    c = make(u, "Child", parent=p)

    run_and_assert(u)

    c.is_deleted = True
    c.save(update_fields=["is_deleted"])
    run_and_assert(u)

    assert p.id in frontier_ids(u)


def test_restore_child_demotes_parent():
    u = reset()
    p = make(u, "Parent", kind="ASSIGNMENT")
    c = make(u, "Child", parent=p, deleted=True)

    run_and_assert(u)
    assert p.id in frontier_ids(u)

    c.is_deleted = False
    c.save(update_fields=["is_deleted"])
    run_and_assert(u)

    p.refresh_from_db()

    assert p.id not in frontier_ids(u)
    assert p.scheduled_date is None
    assert c.id in frontier_ids(u)


def test_move_child_recomputes_both_parents():
    u = reset()

    a = make(u, "Parent A", kind="ASSIGNMENT")
    b = make(u, "Parent B", kind="ASSIGNMENT")
    c = make(u, "Child", parent=a)

    run_and_assert(u)

    hierarchy.set_parent(c, b)
    run_and_assert(u)

    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()

    assert a.id in frontier_ids(u)
    assert b.id not in frontier_ids(u)
    assert c.id in frontier_ids(u)

    assert a.scheduled_date is not None
    assert b.scheduled_date is None


def test_deep_reopen_propagates_frontier_correctly():
    u = reset()

    a = make(u, "A", kind="ASSIGNMENT")
    b = make(u, "B", parent=a)
    c = make(u, "C", parent=b)
    d = make(u, "D", parent=c, completed=True)

    run_and_assert(u)

    assert c.id in frontier_ids(u)

    hierarchy.reopen(d)
    run_and_assert(u)

    assert d.id in frontier_ids(u)
    assert c.id not in frontier_ids(u)
    assert b.id not in frontier_ids(u)
    assert a.id not in frontier_ids(u)

    hierarchy.complete_subtree(d)
    run_and_assert(u)
    assert c.id in frontier_ids(u)

    hierarchy.complete_subtree(c)
    run_and_assert(u)
    assert b.id in frontier_ids(u)

    hierarchy.complete_subtree(b)
    run_and_assert(u)
    assert a.id in frontier_ids(u)


def test_release_lower_bound():
    u = reset()
    t = make(
        u,
        "Released later",
        release=TODAY + timedelta(days=5),
        due=TODAY + timedelta(days=10),
    )

    run_and_assert(u)
    t.refresh_from_db()

    assert t.scheduled_date >= t.start_date


def test_due_upper_bound():
    u = reset()
    t = make(
        u,
        "Hard deadline",
        due=TODAY + timedelta(days=2),
    )

    run_and_assert(u)
    t.refresh_from_db()

    assert t.scheduled_date <= t.due_date


def test_release_equals_due():
    u = reset()
    exact = TODAY + timedelta(days=4)

    t = make(
        u,
        "One legal day",
        release=exact,
        due=exact,
    )

    run_and_assert(u)
    t.refresh_from_db()

    assert t.scheduled_date == exact


def test_anchor_immutable_under_unrelated_change():
    u = reset()

    anchored = make(
        u,
        "Anchored",
        manual=True,
        scheduled=TODAY + timedelta(days=6),
    )
    other = make(u, "Other")

    run_and_assert(u)

    hierarchy.complete_subtree(other)
    run_and_assert(u)

    anchored.refresh_from_db()
    assert anchored.scheduled_date == TODAY + timedelta(days=6)


def test_unanchor_returns_item_to_scheduler():
    u = reset()

    t = make(
        u,
        "Manual",
        manual=True,
        scheduled=TODAY + timedelta(days=10),
    )

    run_and_assert(u)

    t.schedule_is_manual = False
    t.save(update_fields=["schedule_is_manual"])

    run_and_assert(u)
    t.refresh_from_db()

    assert t.scheduled_date is not None


def test_completed_work_unchanged():
    u = reset()

    historical = TODAY - timedelta(days=3)
    t = make(
        u,
        "Completed",
        completed=True,
        scheduled=historical,
    )

    run_and_assert(u)
    t.refresh_from_db()

    assert t.scheduled_date == historical


def test_deleted_work_excluded():
    u = reset()

    t = make(u, "Deleted", deleted=True)
    run_and_assert(u)

    t.refresh_from_db()
    assert t.id not in frontier_ids(u)


def test_idempotence():
    u = reset()

    p = make(u, "Project", kind="ASSIGNMENT")
    for i in range(10):
        make(u, f"Task {i}", parent=p, due=TODAY + timedelta(days=5 + i))

    run_and_assert(u)

    before = dict(
        PlanningItem.objects.filter(user=u)
        .values_list("id", "scheduled_date")
    )

    run_and_assert(u)

    after = dict(
        PlanningItem.objects.filter(user=u)
        .values_list("id", "scheduled_date")
    )

    assert before == after


def test_determinism_after_reset():
    def produce():
        u = reset()
        p = make(u, "Project", kind="ASSIGNMENT")

        for i in range(12):
            make(
                u,
                f"Task {i}",
                parent=p,
                due=TODAY + timedelta(days=(i % 5) + 2),
            )

        run_and_assert(u)

        return list(
            PlanningItem.objects.filter(
                user=u,
                is_deleted=False,
                is_completed=False,
            )
            .order_by("title")
            .values_list("title", "scheduled_date")
        )

    first = produce()
    second = produce()

    assert first == second


TESTS = [
    test_complete_final_child_exposes_parent,
    test_reopen_child_demotes_parent,
    test_completed_child_of_frontier_reopened,
    test_only_final_sibling_completion_exposes_parent,
    test_add_child_demotes_frontier_parent,
    test_delete_final_child_exposes_parent,
    test_restore_child_demotes_parent,
    test_move_child_recomputes_both_parents,
    test_deep_reopen_propagates_frontier_correctly,
    test_release_lower_bound,
    test_due_upper_bound,
    test_release_equals_due,
    test_anchor_immutable_under_unrelated_change,
    test_unanchor_returns_item_to_scheduler,
    test_completed_work_unchanged,
    test_deleted_work_excluded,
    test_idempotence,
    test_determinism_after_reset,
]


def main():
    print("=" * 78)
    print("ARC INFRASTRUCTURE — TRANSITION MATRIX")
    print("=" * 78)

    failures = []

    for test in TESTS:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as exc:
            failures.append((test.__name__, exc))
            print(f"FAIL  {test.__name__}")
            print(f"      {type(exc).__name__}: {exc}")

    print()
    print("=" * 78)
    print(
        f"RESULT: {len(TESTS) - len(failures)}/{len(TESTS)} "
        "transition tests passed"
    )
    print("=" * 78)

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
