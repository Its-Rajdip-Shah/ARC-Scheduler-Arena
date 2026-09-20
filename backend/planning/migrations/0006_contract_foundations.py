from django.db import migrations, models
import django.db.models.deletion
from django.db.models import F, Q


def migrate_old_duration_categories(apps, schema_editor):
    PlanningItem = apps.get_model("planning", "PlanningItem")

    mapping = {
        "UNDER_20_MIN": "UNDER_20_MINUTES",
        "MIN_20_TO_60": "UNDER_1_HOUR",
        "OVER_60_MIN": "UNDER_4_HOURS",
    }

    for old, new in mapping.items():
        PlanningItem.objects.filter(duration_category=old).update(
            duration_category=new
        )


def preserve_legacy_manual_dates(apps, schema_editor):
    PlanningItem = apps.get_model("planning", "PlanningItem")

    PlanningItem.objects.filter(
        schedule_is_manual=True,
        scheduled_date__isnull=False,
        manual_requested_date__isnull=True,
    ).update(
        manual_requested_date=F("scheduled_date")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("planning", "0005_scheduling_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="planningitem",
            name="manual_requested_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="planningitem",
            name="percent_completed",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=5,
            ),
        ),
        migrations.AlterField(
            model_name="planningitem",
            name="duration_category",
            field=models.CharField(
                choices=[
                    ("UNDER_20_MINUTES", "Under 20 minutes"),
                    ("UNDER_1_HOUR", "Under 1 hour"),
                    ("UNDER_4_HOURS", "Under 4 hours"),
                    ("UNDER_8_HOURS", "Under 8 hours"),
                    ("UNDER_16_HOURS", "Under 16 hours"),
                    ("OVER_16_HOURS", "Over 16 hours"),
                ],
                default="UNDER_1_HOUR",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="PlanningDependency",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "dependent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="blocked_by_dependencies",
                        to="planning.planningitem",
                    ),
                ),
                (
                    "prerequisite",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="required_by_dependencies",
                        to="planning.planningitem",
                    ),
                ),
            ],
            options={
                "db_table": "planning_dependencies",
            },
        ),
        migrations.AddConstraint(
            model_name="planningdependency",
            constraint=models.UniqueConstraint(
                fields=("prerequisite", "dependent"),
                name="uniq_planning_dependency_edge",
            ),
        ),
        migrations.AddConstraint(
            model_name="planningdependency",
            constraint=models.CheckConstraint(
                condition=~Q(prerequisite=F("dependent")),
                name="planning_dependency_no_self_edge",
            ),
        ),
        migrations.CreateModel(
            name="ProgressSegment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "percentage",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=5,
                    ),
                ),
                (
                    "scheduled_date",
                    models.DateField(blank=True, null=True),
                ),
                (
                    "is_completed",
                    models.BooleanField(default=False),
                ),
                (
                    "completed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress_segments",
                        to="planning.planningitem",
                    ),
                ),
            ],
            options={
                "db_table": "planning_progress_segments",
                "ordering": ["scheduled_date", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="progresssegment",
            constraint=models.CheckConstraint(
                condition=Q(percentage__gt=0) & Q(percentage__lte=100),
                name="progress_segment_percentage_range",
            ),
        ),

        # Convert existing three-category data before the application begins
        # using the frozen six-category vocabulary.
        migrations.RunPython(
            migrate_old_duration_categories,
            migrations.RunPython.noop,
        ),

        # Preserve legacy explicit manual placements as canonical anchor facts.
        migrations.RunPython(
            preserve_legacy_manual_dates,
            migrations.RunPython.noop,
        ),
    ]
