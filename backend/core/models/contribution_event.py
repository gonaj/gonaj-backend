"""
ContributionEvent model - The evidence layer for Phase-1.

PHILOSOPHY:
"Users never edit truth. They submit what they saw, where they were, when it happened.
The backend decides what it means."

ContributionEvent is the foundational model for Phase-1. It stores:
- Raw user observations (evidence, not truth)
- Context about how the observation was made
- Metadata for idempotency and replay

CRITICAL PROPERTIES:
1. Immutable - Once created, never modified
2. Append-only - Only INSERT operations allowed
3. Idempotent - Duplicate submissions with same client_generated_id are ignored
4. Replayable - Contains everything needed to re-evaluate later

This is the ONLY model that directly accepts user input in Phase-1.
All canonical truth is derived from these events.

WHAT THIS IS:
- Evidence storage
- Audit trail
- Source of truth for recomputation

WHAT THIS IS NOT:
- Canonical transit data
- Evaluated/approved contributions
- Truth claims
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .base import ImmutableModel


class ContributionEvent(ImmutableModel):
    """
    Immutable record of a user's observation or contribution.

    This model represents raw evidence submitted by users. It is:
    - Never updated after creation
    - Never deleted (except for GDPR compliance)
    - Used as the source for deriving canonical knowledge

    IDEMPOTENCY:
    Multiple submissions with the same client_generated_id are treated
    as duplicates and result in the same stored event (get_or_create).

    EVALUATION:
    ContributionEvents are NOT evaluated at submission time.
    They are stored as-is and evaluated later by background processes.

    MODERATION:
    Moderators cannot edit or delete ContributionEvents.
    Moderation flags are stored separately and processed as evidence.

    Fields correspond to Sprint-1 requirements:
    - id: Server-generated UUID (pk)
    - client_generated_id: Client UUID for idempotency
    - contributor: Who submitted this
    - device_id: What device (if tracked)
    - contribution_type: Category of observation
    - subject_ref: What entity this refers to (opaque/flexible)
    - payload: Raw evidence data (JSON)
    - observed_at: When user says it happened (client time)
    - submitted_at: When server received it (server time)
    - context: How it was observed (accuracy, app version, etc.)
    """

    # Contribution type choices
    # These are the ONLY contribution types allowed in Phase-1
    # Explicitly limited per phase_1_backend_plan.md
    class ContributionType(models.TextChoices):
        STOP_NAME = "stop_name", "Stop Name Correction"
        STOP_EXISTS = "stop_exists", "Stop Existence Confirmation"
        STOP_NOT_EXISTS = "stop_not_exists", "Stop Non-Existence Report"
        STOP_LOCATION = "stop_location", "Stop Location Refinement"
        ROUTE_EXISTS = "route_exists", "Route Existence Claim"
        ROUTE_TRAVERSAL = "route_traversal", "Route Traversal (GPS Trace)"
        STOP_SEQUENCE = "stop_sequence", "Stop Sequence Confirmation"
        SERVICE_TIME = "service_time", "Service Time Observation"

    # === Primary Identification ===

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Server-generated unique identifier for this contribution event.",
    )

    client_generated_id = models.UUIDField(
        unique=True,
        db_index=True,
        help_text=(
            "Client-generated UUID for idempotency. "
            "Duplicate submissions with the same ID are ignored."
        ),
    )

    # === Attribution ===

    contributor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # Never cascade delete contributions
        related_name="contribution_events",
        help_text="User who submitted this observation.",
    )

    device_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Optional device identifier. "
            "Useful for detecting patterns, abuse, or GPS accuracy issues."
        ),
    )

    # === Contribution Classification ===

    contribution_type = models.CharField(
        max_length=50,
        choices=ContributionType.choices,
        db_index=True,
        help_text="Type of observation submitted.",
    )

    # === Subject Reference (What is this about?) ===

    subject_ref = models.JSONField(
        help_text=(
            "Opaque reference to what this contribution is about. "
            "May contain: "
            "- Canonical entity ID (if updating existing) "
            "- Geographic hint (lat/lon) "
            "- Name or description "
            "Structure varies by contribution_type."
        ),
    )

    # === Evidence Payload ===

    payload = models.JSONField(
        help_text=(
            "Raw evidence data submitted by the user. "
            "Structure varies by contribution_type. "
            "Examples: "
            "- Stop name: {'name': 'Main Street Station'} "
            "- GPS trace: {'points': [{'lat': ..., 'lon': ..., 'timestamp': ...}]} "
            "- Service time: {'time': '18:40', 'direction': 'inbound'} "
            "This is NOT validated at submission - evaluation happens later."
        ),
    )

    # === Temporal Context ===

    observed_at = models.DateTimeField(
        db_index=True,
        help_text=(
            "When the user observed this (client-reported timestamp). "
            "May be in the past if submitted offline. "
            "Used for temporal reasoning about transit service."
        ),
    )

    submitted_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the server received this contribution (server time).",
    )

    # === Observation Context ===

    context = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Metadata about how this observation was made. "
            "Examples: "
            "- gps_accuracy: float (meters) "
            "- app_version: string "
            "- was_offline: boolean "
            "- network_type: string "
            "- battery_level: int "
            "Used to assess confidence and reliability."
        ),
    )

    # === Inherited from ImmutableModel ===
    # created_at: auto-populated timestamp

    class Meta:
        verbose_name = "Contribution Event"
        verbose_name_plural = "Contribution Events"
        ordering = ["-submitted_at"]
        indexes = [
            # Fast lookups for evaluation pipeline
            models.Index(fields=["contribution_type", "submitted_at"]),
            # Support contributor history queries
            models.Index(fields=["contributor", "submitted_at"]),
            # Device pattern analysis
            models.Index(fields=["device_id", "submitted_at"]),
            # Temporal queries for evaluation
            models.Index(fields=["observed_at", "contribution_type"]),
        ]

    def __str__(self):
        return (
            f"{self.get_contribution_type_display()} "
            f"by {self.contributor.username} "
            f"at {self.observed_at}"
        )

    def clean(self):
        """
        Validate the contribution event before saving.

        Validation rules:
        - observed_at cannot be in the future
        - subject_ref must be a dict/object (not null, not array)
        - payload must be a dict/object
        - context must be a dict/object

        Note: We do NOT validate payload structure here.
        Structure validation happens during evaluation, not submission.
        """
        super().clean()

        # Prevent future observations
        from django.utils import timezone

        if self.observed_at and self.observed_at > timezone.now():
            raise ValidationError(
                {"observed_at": "Observation time cannot be in the future."}
            )

        # Ensure JSON fields are dictionaries
        if not isinstance(self.subject_ref, dict):
            raise ValidationError(
                {"subject_ref": "subject_ref must be a JSON object (dict)."}
            )

        if not isinstance(self.payload, dict):
            raise ValidationError({"payload": "payload must be a JSON object (dict)."})

        if not isinstance(self.context, dict):
            raise ValidationError({"context": "context must be a JSON object (dict)."})

    @classmethod
    def create_or_get_idempotent(cls, client_generated_id, **kwargs):
        """
        Idempotent creation of a ContributionEvent.

        If a ContributionEvent with the same client_generated_id already exists,
        return the existing one. Otherwise, create a new one.

        This enables safe retry behavior for offline/unstable clients.

        Args:
            client_generated_id: UUID generated by client
            **kwargs: Other fields for ContributionEvent

        Returns:
            (contribution_event, created): Tuple of (instance, was_created)

        Example:
            event, created = ContributionEvent.create_or_get_idempotent(
                client_generated_id=uuid.uuid4(),
                contributor=user,
                contribution_type='stop_exists',
                subject_ref={'lat': 40.7, 'lon': -74.0},
                payload={'confidence': 'high'},
                observed_at=timezone.now(),
            )
        """
        return cls.objects.get_or_create(
            client_generated_id=client_generated_id, defaults=kwargs
        )
