"""
Sprint-5B Migration 3/3: Make contributor FK nullable with SET_NULL.

This migration:
1. Changes contributor FK from PROTECT to SET_NULL
2. Makes contributor field nullable

WHY THIS CHANGE:
- Account deletion (Sprint-5A) requires removing user identity
- ContributionEvent must survive account deletion (PH-1, PH-2)
- contributor_fingerprint preserves evaluation identity (Sprint-5B)
- contributor FK is now for ownership/display only

DATA_RIGHTS_V1 COMPLIANCE:
- "Identity is optional. Evidence is permanent. Belief is derived."
- User deletion sets contributor to NULL
- Evidence remains intact with contributor_fingerprint for evaluation

EVALUATION SAFETY:
- All evaluation logic now uses contributor_fingerprint
- Setting contributor to NULL does NOT affect:
  - Independent contributor counts
  - Same-user dampening
  - Cluster contributor_ids
  - Stop creation gates

CRITICAL INVARIANTS PRESERVED:
- INV-E1: ContributionEvent is immutable after creation (payload, geometry, timestamps)
- INV-I1: Contributor independence counted correctly after deletion
- INV-I2: Account deletion does not reduce/inflate contributor counts
- PH-4: Replay determinism (evaluation produces identical results)
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_backfill_contributor_fingerprint"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="contributionevent",
            name="contributor",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "User who submitted this observation. "
                    "May be NULL after account deletion. "
                    "DO NOT use for evaluation - use contributor_fingerprint instead."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="contribution_events",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Add index for contributor_fingerprint queries
        migrations.AddIndex(
            model_name="contributionevent",
            index=models.Index(
                fields=["contributor_fingerprint", "submitted_at"],
                name="core_contri_contrib_fp_idx",
            ),
        ),
    ]
