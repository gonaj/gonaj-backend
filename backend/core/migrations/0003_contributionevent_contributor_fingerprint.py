"""
Sprint-5B Migration 1/3: Add contributor_fingerprint field (nullable initially).

This migration adds the contributor_fingerprint field as nullable to support
a safe migration path. The field will be backfilled in 0004 and made NOT NULL
in the same migration.

WHY NULLABLE INITIALLY:
- Existing rows do not have this value
- We need to backfill from contributor_id before enforcing NOT NULL
- This follows the safe migration pattern: add nullable -> backfill -> enforce NOT NULL

CRITICAL: This field is for EVALUATION purposes and must:
- Be immutable after creation
- Never be NULL for new records
- Survive account deletion (unlike contributor FK)
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_contributionevent"),
    ]

    operations = [
        # Step 1: Add contributor_fingerprint as nullable
        migrations.AddField(
            model_name="contributionevent",
            name="contributor_fingerprint",
            field=models.UUIDField(
                null=True,  # Temporarily nullable for backfill
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
