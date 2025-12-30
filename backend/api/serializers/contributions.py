"""
Serializers for contribution submission (Sprint-2).

This module provides DRF serializers for accepting evidence from authenticated users.

PHILOSOPHY:
Users submit observations and evidence, not truth. The API validates structure
and basic constraints but does NOT validate correctness or truth.

SCOPE (Sprint-2):
- Write-only serializer for ContributionEvent creation
- Minimal validation (structure, not truth)
- Idempotency support via client_generated_id
"""

import uuid
from datetime import datetime

from core.models import ContributionEvent
from django.utils import timezone
from rest_framework import serializers


class ContributionSubmissionSerializer(serializers.Serializer):
    """
    Serializer for submitting contribution evidence.

    This is a write-only serializer that:
    - Accepts evidence from authenticated users
    - Validates structure (not truth)
    - Creates immutable ContributionEvent records
    - Supports idempotency via client_generated_id

    IMPORTANT:
    This serializer does NOT:
    - Evaluate truth or correctness
    - Update canonical entities
    - Return canonical data
    - Allow updates or deletes

    The contributor is set from request.user automatically in the view.
    """

    # Unique client ID for idempotency
    client_generated_id = serializers.UUIDField(
        required=True,
        help_text="Client-generated UUID for idempotency. Resubmitting with the same ID returns the existing event.",
    )

    # Optional device tracking
    device_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional device identifier for pattern analysis and abuse detection.",
    )

    # Contribution classification
    contribution_type = serializers.ChoiceField(
        choices=ContributionEvent.ContributionType.choices,
        required=True,
        help_text="Type of observation being submitted.",
    )

    # What this contribution is about (flexible structure)
    subject_ref = serializers.JSONField(
        required=True,
        help_text="Reference to what this contribution is about (e.g., location hint, entity ID, name).",
    )

    # Raw evidence payload
    payload = serializers.JSONField(
        required=True,
        help_text="Raw evidence data. Structure varies by contribution_type.",
    )

    # When the observation was made (client time)
    observed_at = serializers.DateTimeField(
        required=True,
        help_text="When the user observed this (client-reported timestamp).",
    )

    # Observation context metadata
    context = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Metadata about how this observation was made (GPS accuracy, app version, etc.).",
    )

    def validate_observed_at(self, value):
        """
        Validate that observed_at is not in the future.

        We allow past observations (for offline submissions) but reject
        future timestamps as they're likely client clock errors.
        """
        if value > timezone.now():
            raise serializers.ValidationError(
                "Observation time cannot be in the future. Check your device clock."
            )
        return value

    def validate_subject_ref(self, value):
        """
        Validate that subject_ref is a JSON object (dict), not an array or primitive.
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "subject_ref must be a JSON object, not an array or primitive value."
            )
        return value

    def validate_payload(self, value):
        """
        Validate that payload is a JSON object (dict), not an array or primitive.
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "payload must be a JSON object, not an array or primitive value."
            )
        return value

    def validate_context(self, value):
        """
        Validate that context is a JSON object (dict), not an array or primitive.
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "context must be a JSON object, not an array or primitive value."
            )
        return value

    def create(self, validated_data):
        """
        Create a ContributionEvent using idempotent creation.

        The contributor is expected to be added to validated_data by the view
        before calling this method.

        Sprint-5B: contributor_fingerprint is explicitly set from contributor.id.
        This preserves identity for evaluation even after account deletion.

        Returns:
            tuple: (ContributionEvent, created) where created is a boolean
        """
        client_generated_id = validated_data.pop("client_generated_id")

        # Sprint-5B: Explicitly set contributor_fingerprint from contributor
        # This is the submission-time identity used by evaluation logic
        contributor = validated_data.get("contributor")
        if contributor is None:
            raise serializers.ValidationError(
                {
                    "contributor": "Contributor is required to create a contribution event."
                }
            )
        validated_data["contributor_fingerprint"] = contributor.id

        # Use the model's idempotent creation method
        event, created = ContributionEvent.create_or_get_idempotent(
            client_generated_id=client_generated_id, **validated_data
        )

        # Store created flag for response
        event._was_created = created

        return event

    def to_representation(self, instance):
        """
        Return a minimal representation of the created/retrieved event.

        This is write-only API, so we return just enough to confirm:
        - The submission was accepted
        - The event ID for reference
        - Whether it was newly created or already existed
        """
        return {
            "id": str(instance.id),
            "client_generated_id": str(instance.client_generated_id),
            "contribution_type": instance.contribution_type,
            "observed_at": instance.observed_at.isoformat(),
            "submitted_at": instance.submitted_at.isoformat(),
            "created": getattr(instance, "_was_created", True),
        }
