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
