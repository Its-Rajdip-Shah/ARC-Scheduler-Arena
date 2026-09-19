"""Importing Canvas courses and assignments into the planning hierarchy.

FR-05: a course becomes a root PlanningItem and each of its assignments
becomes a child, matched on (canvas_object_type, canvas_object_id) so a
re-sync updates rows instead of duplicating them. Whatever the user has
changed locally is left alone: titles and dates come from Canvas, but the
priority position, completion flag, tags and marks stay as the user left them.

FR-04: every attempt writes a SyncLog row, successful or not, which is what
lets the Connection screen report the last successful sync and the last error.
"""

from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from canvas_integration.client import CanvasClient, CanvasError
from canvas_integration.models import SyncLog, SyncStatus
from planning.models import AssignmentDetail, CanvasObjectType, ItemType, PlanningItem
from planning.services import scheduling


def _as_date(value):
    """Canvas gives ISO timestamps, and omits them freely. Both are normal."""
    if not value:
        return None
    parsed = parse_datetime(value) if isinstance(value, str) else value
    if parsed is None:
        return None
    if timezone.is_aware(parsed):
        parsed = timezone.localtime(parsed)
    return parsed.date() if isinstance(parsed, datetime) else parsed


def _course_title(course):
    """Prefer the short code students recognise, fall back to the full name."""
    return course.get('course_code') or course.get('name') or 'Untitled Canvas course'


def _import_course(user, client, course, counts):
    """Upsert one course and its assignments.

    The Canvas call happens before the transaction opens, so a slow Canvas
    never holds a write transaction open against Postgres.
    """
    assignments = client.assignments(course['id'])

    with transaction.atomic():
        root, created = PlanningItem.objects.update_or_create(
            user=user,
            canvas_object_type=CanvasObjectType.COURSE,
            canvas_object_id=str(course['id']),
            defaults={
                'item_type': ItemType.GOAL,
                'title': _course_title(course),
                'parent': None,
            },
        )
        counts['courses_created' if created else 'courses_updated'] += 1

        for assignment in assignments:
            if assignment.get('id') is None:
                continue
            _import_assignment(user, root, assignment, counts)
        scheduling.schedule(user)


def _import_assignment(user, root, assignment, counts):
    assignment_id = str(assignment['id'])
    due_date = _as_date(assignment.get('due_at'))

    item, created = PlanningItem.objects.update_or_create(
        user=user,
        canvas_object_type=CanvasObjectType.ASSIGNMENT,
        canvas_object_id=assignment_id,
        defaults={
            'item_type': ItemType.ASSIGNMENT,
            'title': assignment.get('name') or 'Untitled Canvas assignment',
            'description': assignment.get('description') or None,
            'parent': root,
            'due_date': due_date,
            'start_date': _as_date(assignment.get('unlock_at')),
        },
    )

    # Canvas exposes points_possible, not a percentage of the unit, so ARC
    # cannot derive weight_percent and leaves it for the user to fill in.
    AssignmentDetail.objects.update_or_create(
        planning_item=item,
        defaults={'submission_url': assignment.get('html_url') or None},
    )

    counts['assignments_created' if created else 'assignments_updated'] += 1


def run_sync(connection, client=None):
    """Pull the user's Canvas courses and assignments, logging the attempt.

    Returns the SyncLog row. Failures are recorded rather than raised, because
    an unreachable Canvas is an expected state the Connection screen has to be
    able to display.
    """
    user = connection.user
    # Opened as FAILED so an attempt that dies mid-flight is not recorded as a
    # success (FR-04).
    log = SyncLog.objects.create(user=user, status=SyncStatus.FAILED)
    client = client or CanvasClient(
        settings.CANVAS_BASE_URL, connection.api_token_encrypted
    )

    counts = {
        'courses_created': 0,
        'courses_updated': 0,
        'assignments_created': 0,
        'assignments_updated': 0,
    }

    try:
        profile = client.whoami()
        courses = client.courses()
        for course in courses:
            if course.get('id') is None:
                continue
            _import_course(user, client, course, counts)
    except CanvasError as exc:
        log.completed_at = timezone.now()
        log.error_message = str(exc)
        log.save(update_fields=['completed_at', 'error_message'])
        return log

    log.status = SyncStatus.SUCCESS
    log.completed_at = timezone.now()
    log.error_message = None
    log.save(update_fields=['status', 'completed_at', 'error_message'])

    connection.canvas_user_id = str(profile.get('id') or '') or None
    connection.last_sync_at = log.completed_at
    connection.save(update_fields=['canvas_user_id', 'last_sync_at'])

    log.counts = counts
    return log
