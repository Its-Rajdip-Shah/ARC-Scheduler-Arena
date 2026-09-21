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
    # Frozen ARC duration semantics.
    #
    # Atomic / one-day:
    #   <20m, <1h, <4h
    #
    # Splittable:
    #   <8h, <16h, >16h
    #
    # The labels are intentionally simple while the enum values provide
    # mutually-exclusive semantic buckets to the domain.
    UNDER_20_MINUTES = 'UNDER_20_MINUTES', 'Under 20 minutes'
    UNDER_1_HOUR = 'UNDER_1_HOUR', 'Under 1 hour'
    UNDER_4_HOURS = 'UNDER_4_HOURS', 'Under 4 hours'
    UNDER_8_HOURS = 'UNDER_8_HOURS', 'Under 8 hours'
    UNDER_16_HOURS = 'UNDER_16_HOURS', 'Under 16 hours'
    OVER_16_HOURS = 'OVER_16_HOURS', 'Over 16 hours'


ATOMIC_DURATION_CATEGORIES = (
    DurationCategory.UNDER_20_MINUTES,
    DurationCategory.UNDER_1_HOUR,
    DurationCategory.UNDER_4_HOURS,
)

SPLITTABLE_DURATION_CATEGORIES = (
    DurationCategory.UNDER_8_HOURS,
    DurationCategory.UNDER_16_HOURS,
    DurationCategory.OVER_16_HOURS,
)


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
            .exclude(
                blocked_by_dependencies__prerequisite__is_completed=False,
                blocked_by_dependencies__prerequisite__is_deleted=False,
            )
            .distinct()
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
    execution_rank = models.PositiveIntegerField(null=True, blank=True)

    # Canonical user date intent lives exclusively in manual_requested_date.
    # This is deliberately distinct from
    # scheduled_date, which is a disposable scheduler proposal.
    manual_requested_date = models.DateField(null=True, blank=True)
    # Last missed explicit intent, retained for recovery after hard expiry.
    expired_manual_requested_date = models.DateField(null=True, blank=True)

    priority_restore_context = models.JSONField(default=dict, blank=True)

    duration_category = models.CharField(
        max_length=20,
        choices=DurationCategory.choices,
        default=DurationCategory.UNDER_1_HOUR,
    )

    # Canonical confirmed progress for splittable work. Atomic categories do
    # not use partial-progress semantics and therefore remain at zero until
    # completed.
    percent_completed = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )
    priority_position = models.PositiveIntegerField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    # Soft deletion keeps rows intact while DELETE remains undoable.
    # Once no history entry can restore the deletion, history GC may
    # permanently remove the row.
    is_deleted = models.BooleanField(default=False, db_index=True)

    # Durable lifecycle context used by validated delete/restore.
    #
    # This is deliberately canonical history rather than scheduler state:
    # deletion may suspend hierarchy/dependency/anchor relationships and a
    # later restore must validate those original relationships against the
    # world as it exists at restore time.
    deletion_restore_context = models.JSONField(default=dict, blank=True)

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
            # Immediate uniqueness is enforced on SQLite and PostgreSQL.
            # Priority commands release affected slots before a permutation.
            models.UniqueConstraint(
                fields=['user', 'priority_position'],
                name='uniq_user_priority_position',
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
            models.CheckConstraint(
                condition=Q(percent_completed__gte=0) & Q(percent_completed__lte=100),
                name='planning_item_percent_completed_range',
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


class PlanningDependency(models.Model):
    """Canonical completion-based hard precedence edge.

    prerequisite -> dependent means dependent work cannot become executable
    until the prerequisite is complete.

    This relation is intentionally independent from hierarchy and priority.
    """

    prerequisite = models.ForeignKey(
        PlanningItem,
        on_delete=models.CASCADE,
        related_name='required_by_dependencies',
    )
    dependent = models.ForeignKey(
        PlanningItem,
        on_delete=models.CASCADE,
        related_name='blocked_by_dependencies',
    )

    class Meta:
        db_table = 'planning_dependencies'
        constraints = [
            models.UniqueConstraint(
                fields=['prerequisite', 'dependent'],
                name='uniq_planning_dependency_edge',
            ),
            models.CheckConstraint(
                condition=~Q(prerequisite=F('dependent')),
                name='planning_dependency_no_self_edge',
            ),
        ]

    def __str__(self):
        return f'{self.prerequisite_id} -> {self.dependent_id}'


class SchedulerAllocation(models.Model):
    """Disposable scheduler-owned allocation proposal.

    This is NOT canonical progress and is NOT a semantic PlanningItem child.
    Rows may be freely destroyed/rebuilt whenever ARC reschedules.

    Only explicit user confirmation converts an allocation into durable
    ProgressSegment history and changes PlanningItem.percent_completed.
    """

    item = models.ForeignKey(
        PlanningItem,
        on_delete=models.CASCADE,
        related_name='scheduler_allocations',
    )
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    scheduled_date = models.DateField()
    execution_rank = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'planning_scheduler_allocations'
        ordering = ['scheduled_date', 'execution_rank', 'id']
        constraints = [
            models.CheckConstraint(
                condition=Q(percentage__gt=0) & Q(percentage__lte=100),
                name='scheduler_allocation_percentage_range',
            ),
        ]

    def __str__(self):
        return (
            f'{self.item_id}: {self.percentage}% '
            f'on {self.scheduled_date}'
        )


class ProgressSegment(models.Model):
    """Durable canonical history for confirmed splittable-work progress.

    A ProgressSegment is never a scheduler proposal and never participates in
    the PlanningItem hierarchy. Disposable future proposals live exclusively
    in SchedulerAllocation.
    """

    item = models.ForeignKey(
        PlanningItem,
        on_delete=models.CASCADE,
        related_name='progress_segments',
    )
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    scheduled_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'planning_progress_segments'
        ordering = ['scheduled_date', 'id']
        constraints = [
            models.CheckConstraint(
                condition=Q(percentage__gt=0) & Q(percentage__lte=100),
                name='progress_segment_percentage_range',
            ),
            models.CheckConstraint(
                condition=Q(is_completed=True),
                name='progress_segment_must_be_confirmed',
            ),
        ]

    def __str__(self):
        state = 'confirmed' if self.is_completed else 'proposed'
        return f'{self.item_id}: {self.percentage}% ({state})'


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
