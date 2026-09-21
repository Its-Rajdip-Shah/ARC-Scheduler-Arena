"""Populate the database with two demo users for development and testing.

Both users get the same course names, item titles and tag names on purpose.
Every later FR-03 isolation test asks "did user B see user A's row?", and that
question is only meaningful when the two datasets are indistinguishable by
content alone.

The data also covers each branch the Phase 4 services care about: fixed dates
that are overdue within the Recent window and beyond it into Backlog, scheduled
items carrying a scheduled_date and no deadline, completed items holding no
priority position, and an assignment left unmarked so FR-14 can tell "no mark"
apart from "zero".
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from canvas_integration.models import CanvasConnection, SyncLog, SyncStatus
from planning.services import scheduling
from planning.models import (
    AssignmentDetail,
    CanvasObjectType,
    ItemType,
    PlanningItem,
    PlanningItemTag,
    Tag,
    Timezone,
)

User = get_user_model()

DEMO_PASSWORD = 'arc-demo-pass-1234'
DEMO_USERS = ['alice@example.com', 'bob@example.com']
ADMIN_USER = 'admin@example.com'


class Command(BaseCommand):
    help = 'Create two demo users with identical-looking planning data, plus an admin.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete the demo accounts first. Cascades to all their data.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        emails = DEMO_USERS + [ADMIN_USER]

        if options['reset']:
            deleted, _ = User.objects.filter(email__in=emails).delete()
            self.stdout.write(f'Removed {deleted} row(s) for existing demo accounts.')

        if User.objects.filter(email__in=emails).exists():
            self.stderr.write(
                'Demo accounts already exist. Re-run with --reset to replace them.'
            )
            return

        admin = User.objects.create_superuser(ADMIN_USER, DEMO_PASSWORD)
        admin.last_login = timezone.now() - timedelta(days=1)
        admin.save(update_fields=['last_login'])

        for email in DEMO_USERS:
            user = User.objects.create_user(email, DEMO_PASSWORD)
            self._seed_user(user)

        # One locked, never-logged-in account so FR-16's dashboard has a
        # non-trivial active-user count to report.
        locked = User.objects.create_user('locked@example.com', DEMO_PASSWORD)
        locked.is_locked = True
        locked.save(update_fields=['is_locked'])

        self._report()

    def _seed_user(self, user):
        today = timezone.localdate()

        tags = {
            name: Tag.objects.create(user=user, name=name)
            for name in ('urgent', 'reading', 'group-work')
        }

        # Overlapping ranges are legal under FR-13 and worth seeding.
        Timezone.objects.create(
            user=user, title='Semester 2', start_date=today - timedelta(days=60),
            end_date=today + timedelta(days=60),
        )
        Timezone.objects.create(
            user=user, title='Week 10', start_date=today - timedelta(days=3),
            end_date=today + timedelta(days=4),
        )
        Timezone.objects.create(
            user=user, title='Exam Period', start_date=today + timedelta(days=40),
            end_date=today + timedelta(days=55),
        )

        elec = self._item(user, ItemType.GOAL, 'ELEC3609 Internet Software Platforms')
        assignment_2 = self._item(user, ItemType.GOAL, 'Assignment 2', parent=elec)

        # 12 days past due: Backlog under FR-12.
        report = self._item(
            user, ItemType.ASSIGNMENT, 'Submit system design report',
            parent=assignment_2, due_date=today - timedelta(days=12),
            duration='UNDER_4_HOURS',
            canvas_object_type=CanvasObjectType.ASSIGNMENT, canvas_object_id='canvas-a2-101',
        )
        AssignmentDetail.objects.create(
            planning_item=report, weight_percent='25.00', mark_achieved=None,
            submission_url='https://canvas.example.edu/courses/1/assignments/101',
            marks_position=1,
        )

        # 3 days past due: Recent under FR-12.
        erd = self._item(
            user, ItemType.TASK, 'Draft the ERD', parent=assignment_2,
            due_date=today - timedelta(days=3), duration='UNDER_4_HOURS',
        )

        # No due_date, so FR-11 schedules it and FR-12 can never call it overdue.
        wireframes = self._item(
            user, ItemType.TASK, 'Review wireframes', parent=assignment_2,
            scheduled_date=today + timedelta(days=1), duration='UNDER_1_HOUR',
        )

        quiz = self._item(
            user, ItemType.ASSIGNMENT, 'Quiz 3', parent=elec,
            due_date=today + timedelta(days=5), duration='UNDER_20_MINUTES',
        )
        AssignmentDetail.objects.create(
            planning_item=quiz, weight_percent='10.00', mark_achieved='8.50',
            marks_position=2,
        )

        maths = self._item(user, ItemType.GOAL, 'MATH2021 Vector Calculus')
        problem_set = self._item(
            user, ItemType.TASK, 'Weekly problem set', parent=maths,
            start_date=today, due_date=today + timedelta(days=2), duration='UNDER_4_HOURS',
        )
        revision = self._item(
            user, ItemType.TASK, "Revise Green's theorem", parent=maths,
            scheduled_date=today + timedelta(days=3), duration='UNDER_1_HOUR',
        )
        final = self._item(
            user, ItemType.ASSIGNMENT, 'Final exam', parent=maths,
            due_date=today + timedelta(days=45), duration='UNDER_4_HOURS',
        )
        AssignmentDetail.objects.create(
            planning_item=final, weight_percent='60.00', mark_achieved=None,
            marks_position=3,
        )

        # Completed work keeps no priority position, which is the invariant the
        # deferred unique constraint is there to protect.
        self._item(
            user, ItemType.TASK, 'Set up dev environment', parent=elec,
            is_completed=True, duration='UNDER_1_HOUR',
        )

        for item, names in (
            (report, ('urgent', 'group-work')),
            (erd, ('urgent',)),
            (wireframes, ('reading',)),
            (revision, ('reading',)),
        ):
            for name in names:
                PlanningItemTag.objects.create(planning_item=item, tag=tags[name])

        # FR-09: one global order across roots, positions 1..n, no gaps.
        ordered = [report, erd, problem_set, quiz, wireframes, revision, final]
        for position, item in enumerate(ordered, start=1):
            item.priority_position = position
        PlanningItem.objects.bulk_update(ordered, ['priority_position'])

        from planning.services import lifecycle
        lifecycle.finish(user)

        # Only alice gets Canvas, so the "never connected" path stays covered.
        if user.email == DEMO_USERS[0]:
            CanvasConnection.objects.create(
                user=user,
                api_token_encrypted='canvas~demo~token~do~not~use',
                canvas_user_id='99001',
                last_sync_at=timezone.now() - timedelta(hours=2),
            )
            SyncLog.objects.create(
                user=user, completed_at=timezone.now() - timedelta(hours=2),
                status=SyncStatus.SUCCESS,
            )
            SyncLog.objects.create(
                user=user, started_at=timezone.now() - timedelta(days=1),
                completed_at=timezone.now() - timedelta(days=1),
                status=SyncStatus.FAILED,
                error_message='Canvas returned 401: invalid access token.',
            )

    def _item(self, user, item_type, title, parent=None, duration='UNDER_1_HOUR', **fields):
        siblings = PlanningItem.objects.filter(user=user, parent=parent).count()
        return PlanningItem.objects.create(
            user=user,
            parent=parent,
            item_type=item_type,
            title=title,
            sibling_order=siblings + 1,
            duration_category=duration,
            **fields,
        )

    def _report(self):
        today = timezone.localdate()
        self.stdout.write('')
        self.stdout.write(f'Accounts (password for all: {DEMO_PASSWORD})')
        for user in User.objects.all():
            flags = [f for f, on in (('admin', user.is_admin), ('locked', user.is_locked)) if on]
            self.stdout.write(f'  {user.email:<24} {" ".join(flags) or "standard"}')

        self.stdout.write('')
        self.stdout.write('Row counts')
        for model in (User, PlanningItem, AssignmentDetail, Tag, PlanningItemTag,
                      Timezone, CanvasConnection, SyncLog):
            self.stdout.write(f'  {model.__name__:<20} {model.objects.count()}')

        self.stdout.write('')
        self.stdout.write('Per user')
        for user in User.objects.filter(email__in=DEMO_USERS):
            items = PlanningItem.objects.for_user(user)
            positions = sorted(
                items.exclude(priority_position=None)
                .values_list('priority_position', flat=True)
            )
            self.stdout.write(
                f'  {user.email}: {items.count()} items, '
                f'{items.recent_overdue(today).count()} recent overdue, '
                f'{items.backlog(today).count()} backlog, '
                f'{items.active().actionable().without_deadline().count()} without a deadline, '
                f'priorities {positions}'
            )

        self.stdout.write(self.style.SUCCESS('\nSeed complete.'))
