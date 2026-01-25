"""
Serializers for user data export (Sprint-9, Phase-2).

This module provides the contribution export serializer as part of
DATA_RIGHTS_V1 compliance (Right to Data Access).

PHILOSOPHY:
Export is a user right, not system introspection. Users receive
all their own data in a deterministic, reproducible format.

EXPORT V1 SEMANTICS (FROZEN):
- Atomic: Complete dataset in single response
- Non-paginated: All contributions returned
- Non-filterable: No query parameters alter output
- Deterministic: Same data produces identical output (except generated_at)

Any change to these semantics requires a new export version.

WHAT IS EXPORTED:
- User metadata (user_id, account creation date)
- Contribution records (id, type, timestamps, payload)

WHAT IS EXPLICITLY EXCLUDED:
- contributor_fingerprint (internal evaluation identifier)
- device_id (internal tracking)
- context (system metadata)
- Canonical entities (Stops, Routes)
- Evaluation artifacts
- Moderation artifacts

INVARIANTS ENFORCED:
- P2-INV-8: User data rights preserved
- INV-D1: No system-internal identifiers (except user-generated contribution_id)
- INV-D4: No leaking contributor_fingerprint
"""

from django.utils import timezone
from rest_framework import serializers


# BLOCKED FIELDS - These must NEVER appear in export output
BLOCKED_EXPORT_FIELDS = frozenset([
    "id",                       # Server-generated UUID (internal)
    "contributor",              # User reference (FK)
    "contributor_id",           # User ID (FK)
    "contributor_fingerprint",  # Evaluation identity (INV-D4)
    "device_id",                # Internal tracking
    "context",                  # System metadata
    "created_at",               # Model timestamp (internal)
    "updated_at",               # Model timestamp (internal)
    "moderation_status",        # Internal moderation state
])


class ContributionExportSerializer(serializers.Serializer):
    """
    Serializer for individual contribution records in export.

    Exports user-facing data only. Uses explicit whitelist approach.

    INCLUDED FIELDS (v1):
    - contribution_id: User-generated idempotency key (client_generated_id)
    - contribution_type: Type of observation
    - observed_at: When user observed this (user-provided)
    - submitted_at: When server received this (GDPR requires receipt time)
    - subject_ref: What this contribution is about
    - payload: Raw evidence data

    EXCLUDED FIELDS:
    - id (server-generated, internal)
    - contributor_fingerprint (evaluation identity)
    - device_id, context (internal tracking)
    """

    contribution_id = serializers.UUIDField(
        help_text="User-generated idempotency key for this contribution."
    )

    contribution_type = serializers.CharField(
        help_text="Type of observation submitted."
    )

    observed_at = serializers.DateTimeField(
        help_text="When the user observed this (user-provided timestamp)."
    )

    submitted_at = serializers.DateTimeField(
        help_text="When the server received this contribution."
    )

    subject_ref = serializers.JSONField(
        help_text="What this contribution is about (location, entity reference)."
    )

    payload = serializers.JSONField(
        help_text="Raw evidence data submitted by the user."
    )

    def to_representation(self, instance):
        """
        Convert a ContributionEvent to export format.

        Uses explicit whitelist - only listed fields are exported.
        """
        result = {
            "contribution_id": str(instance.client_generated_id),
            "contribution_type": instance.contribution_type,
            "observed_at": instance.observed_at.isoformat(),
            "submitted_at": instance.submitted_at.isoformat(),
            "subject_ref": instance.subject_ref,
            "payload": instance.payload,
        }

        # Defense-in-depth: verify no blocked fields leaked
        for key in result.keys():
            if key in BLOCKED_EXPORT_FIELDS:
                raise ValueError(
                    f"SECURITY: Blocked field '{key}' in export output. "
                    "This is a programming error."
                )

        return result


class ContributionExportListSerializer(serializers.Serializer):
    """
    Wrapper serializer for the complete export response.

    Provides metadata about the export along with contributions.

    EXPORT V1 ENVELOPE:
    - export_version: "v1" (frozen)
    - generated_at: ISO-8601 timestamp of export generation
    - user: Informational section (user_id, created_at)
    - contributions: List of contribution records

    NOTE: The export endpoint is only accessible to users with the
    required capabilities (i.e., not deleted users). The user section
    contains minimal metadata (user_id and account creation date),
    which may be retained for compliance purposes in the data model.
    """

    def to_representation(self, data):
        """
        Build the complete export response.

        Args:
            data: Dict with 'contributions' queryset and 'user' object

        Returns:
            Complete export envelope with metadata and contributions
        """
        contributions = data.get("contributions", [])
        user = data.get("user")

        contribution_serializer = ContributionExportSerializer(
            contributions, many=True
        )

        return {
            "export_version": "v1",
            "generated_at": timezone.now().isoformat(),
            "user": {
                "user_id": str(user.id) if user else None,
                "created_at": user.date_joined.isoformat() if user else None,
            },
            "contributions": contribution_serializer.data,
        }
