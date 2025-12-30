"""
Sprint-5B Migration 2/3: Backfill contributor_fingerprint and enforce NOT NULL.

This migration:
1. Backfills contributor_fingerprint from contributor_id for existing rows
2. Enforces NOT NULL on contributor_fingerprint

WHY BACKFILL FROM contributor_id:
- contributor_id is currently always set (PROTECT + NOT NULL)
- The fingerprint represents "contributor at submission time"
- This preserves the invariant that deleted accounts don't collapse contributor counts

DETERMINISM:
- Backfill is deterministic: contributor_fingerprint = contributor_id (the UUID)
- No randomness or timestamp-based values
- Replay produces identical results

SAFETY:
- All existing rows will have valid fingerprints after this migration
- New rows require fingerprint at creation time (model validation)
"""

from django.db import migrations, models


def backfill_contributor_fingerprint(apps, schema_editor):
    """
    Backfill contributor_fingerprint from contributor_id.

    This is safe because:
    - contributor is currently PROTECT and NOT NULL
    - contributor_id is a UUID, same type as contributor_fingerprint
    - Every existing ContributionEvent has a contributor
    """
    ContributionEvent = apps.get_model("core", "ContributionEvent")

    # Batch update for efficiency
    # Use raw SQL for performance on large tables
    # Only backfill where contributor_id is not null (defensive safeguard)
    ContributionEvent.objects.filter(
        contributor_fingerprint__isnull=True,
        contributor_id__isnull=False,
    ).update(contributor_fingerprint=models.F("contributor_id"))


def reverse_backfill(apps, schema_editor):
    """
    Reverse operation: set contributor_fingerprint to NULL.

    Note: This is only for migration rollback during development.
    In production, this should never be called as it would break evaluation.
    """
    ContributionEvent = apps.get_model("core", "ContributionEvent")
    ContributionEvent.objects.update(contributor_fingerprint=None)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_contributionevent_contributor_fingerprint"),
    ]

    operations = [
        # Step 1: Backfill existing rows
        migrations.RunPython(
            backfill_contributor_fingerprint,
            reverse_code=reverse_backfill,
        ),
        # Step 2: Enforce NOT NULL
        migrations.AlterField(
            model_name="contributionevent",
            name="contributor_fingerprint",
            field=models.UUIDField(
                db_index=True,
                editable=False,
                help_text=(
                    "Immutable contributor identity for evaluation purposes. "
                    "This is a non-PII identifier that MUST be used by evaluation logic "
                    "to determine contributor independence. "
                    "Set at creation time from contributor.id and NEVER changes. "
                    "Survives account deletion to preserve INV-I1, INV-I2 invariants."
                ),
            ),
        ),
    ]
