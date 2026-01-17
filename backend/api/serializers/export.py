"""
Serializers for contribution export (Sprint-5C).

This module provides a dedicated serializer for exporting user contributions
as part of DATA_RIGHTS_V1 compliance (Right to Data Access).

PHILOSOPHY:
Export is about user rights, not system introspection. Users should receive
only the data they directly submitted, in a format that doesn't reveal
internal system mechanics.

WHAT IS EXPORTED:
- Timestamps (observed_at only - user-provided)
- Geometry / coordinates as submitted
- Evidence type
- Raw payload submitted by user

WHAT IS EXPLICITLY EXCLUDED (INV-D1, INV-D4):
- contributor_fingerprint (internal evaluation identifier)
- Internal server-generated UUIDs (id, client_generated_id)
- Canonical IDs (Stop IDs, Route IDs)
- Evaluation artifacts
- Moderation artifacts
- submitted_at (server-generated, not user-provided)
- device_id (internal tracking)
- context (system metadata, not user content)

INVARIANTS ENFORCED:
- INV-D1: Export must not expose system-internal identifiers
- INV-D2: Export must not enable cross-contribution linkage beyond timestamps
- INV-D3: Export must not weaken post-deletion anonymity
- INV-D4: Export must not leak contributor_fingerprint

CANONICAL READ HARDENING (Phase-2 Sprint-2):
- Explicit field whitelist (not blacklist)
- No field can be added without explicit review
- Serializer validates output schema
"""

from rest_framework import serializers


# BLOCKED FIELDS - These must NEVER appear in export output
# Phase-2 Sprint-2: Explicit documentation of forbidden fields
BLOCKED_EXPORT_FIELDS = frozenset([
    "id",                       # Server-generated UUID
    "client_generated_id",      # Internal idempotency key
    "contributor",              # User reference (FK)
    "contributor_id",           # User ID
    "contributor_fingerprint",  # Evaluation identity (INV-D4)
    "device_id",                # Internal tracking
    "context",                  # System metadata
    "submitted_at",             # Server timestamp
    "created_at",               # Model timestamp
    "updated_at",               # Model timestamp
])


class ContributionExportSerializer(serializers.Serializer):
    """
    Dedicated serializer for exporting user contributions.

    This serializer explicitly whitelists only user-supplied fields.
    It is intentionally NOT a ModelSerializer to prevent accidental
    inclusion of internal fields.

    CRITICAL: This serializer must NEVER include:
    - contributor_fingerprint
    - id (server-generated)
    - client_generated_id (internal idempotency key)
    - device_id (internal tracking)
    - context (system metadata)
    - submitted_at (server timestamp)

    Only fields the user explicitly provided are exported.
    """

    # === User-Provided Fields Only ===

    observed_at = serializers.DateTimeField(
        help_text="When the user observed this (user-provided timestamp)."
    )

    contribution_type = serializers.CharField(
        help_text="Type of observation submitted."
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

        This method explicitly extracts only whitelisted fields.
        Any internal identifiers are intentionally omitted.
        
        Phase-2 Sprint-2: Explicit whitelist approach for canonical read hardening.
        """
        # Explicit whitelist - only these fields can be exported
        # Adding new fields requires explicit code change and review
        result = {
            "observed_at": instance.observed_at.isoformat(),
            "contribution_type": instance.contribution_type,
            "subject_ref": instance.subject_ref,
            "payload": instance.payload,
        }
        
        # Phase-2 Sprint-2: Validate no blocked fields leaked
        # This is a defense-in-depth check
        for key in result.keys():
            if key in BLOCKED_EXPORT_FIELDS:
                raise ValueError(
                    f"SECURITY: Blocked field '{key}' in export output. "
                    "This is a programming error."
                )
        
        return result


class ContributionExportListSerializer(serializers.Serializer):
    """
    Wrapper serializer for the full export response.

    Provides metadata about the export along with the contributions.
    This serializer manually builds output in to_representation()
    rather than using declared fields, to maintain explicit control
    over the export structure.
    """

    def to_representation(self, contributions):
        """
        Build the complete export response.

        Args:
            contributions: QuerySet or list of ContributionEvent objects

        Returns:
            Dictionary with export metadata and contribution list
        """
        contribution_serializer = ContributionExportSerializer(contributions, many=True)

        return {
            "export_version": "1.0",
            "contribution_count": len(contributions),
            "contributions": contribution_serializer.data,
        }
