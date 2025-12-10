"""
Contribution model for tracking user-submitted data.

The Contribution model is the core of the crowdsourcing system. It tracks
all data submissions from various sources (UI, API, bulk imports, external)
with complete attribution, status tracking, and idempotency guarantees.

Key features:
- UUID primary key for public API exposure
- Flexible payload storage (JSONField) for different contribution types
- Multi-source attribution (authenticated users, API developers, external users)
- Status workflow (draft → pending → approved/rejected → published)
- Idempotency key for preventing duplicate submissions
- Points system integration
"""

import uuid

from django.conf import settings
from django.db import models


class Contribution(models.Model):
    """
    Represents a single data contribution to the platform.

    Contributions can be:
    - Transit schedule updates
    - Route geometry corrections
    - Stop location edits
    - Service alerts
    - Accessibility information
    - Photos and amenities

    Attribution is flexible to support multiple submission sources:
    - Web UI (authenticated user)
    - Mobile app (authenticated user + device)
    - Developer API (developer + optional external user ID)
    - Bulk imports (developer only)
    - External integrations (external user ID only)

    Status workflow:
    1. draft - User is still editing
    2. pending - Submitted and awaiting review
    3. approved - Reviewed and approved by moderator
    4. rejected - Reviewed and rejected
    5. published - Approved and published to public GTFS feed
    6. flagged - Flagged for additional review
    """

    # Source type choices
    SOURCE_UI = "ui"
    SOURCE_API = "api"
    SOURCE_BULK = "bulk"
    SOURCE_EXTERNAL = "external"

    SOURCE_CHOICES = [
        (SOURCE_UI, "Web/Mobile UI"),
        (SOURCE_API, "Developer API"),
        (SOURCE_BULK, "Bulk Import"),
        (SOURCE_EXTERNAL, "External Integration"),
    ]

    # Status choices
    STATUS_DRAFT = "draft"
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_PUBLISHED = "published"
    STATUS_FLAGGED = "flagged"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PENDING, "Pending Review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_FLAGGED, "Flagged"),
    ]

    # UUID primary key for public API
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this contribution",
    )

    # Contribution type (e.g., 'route_update', 'stop_edit', 'schedule_change')
    type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of contribution (route_update, stop_edit, etc.)",
    )

    # Flexible payload storage for contribution data
    # Structure varies by type; validated by serializers
    payload = models.JSONField(help_text="Contribution data (structure varies by type)")

    # === Attribution Fields ===

    # Authenticated user (if contribution made by logged-in user)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contributions",
        help_text="Authenticated user who submitted this contribution",
    )

    # Developer (if contribution made via API)
    submitted_by_developer = models.ForeignKey(
        "Developer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contributions",
        help_text="Developer/API client that submitted this contribution",
    )

    # External user ID (for attributing contributions from external systems)
    external_user_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="External user identifier (from partner systems)",
    )

    # Source type
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_UI,
        db_index=True,
        help_text="Source of this contribution",
    )

    # === Idempotency & Deduplication ===

    # Idempotency key for preventing duplicate submissions
    idempotency_key = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
        help_text="Client-provided key for idempotent submission",
    )

    # Content-based fingerprint for detecting duplicates
    payload_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="SHA256 hash of payload for duplicate detection",
    )

    # === Status & Workflow ===

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        help_text="Current status in moderation workflow",
    )

    # Points awarded for this contribution (0 until approved/published)
    points_awarded = models.IntegerField(
        default=0, help_text="Points awarded to submitter for this contribution"
    )

    # === Timestamps ===

    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, help_text="When this contribution was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True, help_text="When this contribution was last updated"
    )

    class Meta:
        verbose_name = "Contribution"
        verbose_name_plural = "Contributions"
        indexes = [
            models.Index(fields=["type", "status"]),
            models.Index(fields=["submitted_by", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["idempotency_key"]),
            models.Index(fields=["payload_fingerprint"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.type} - {self.status} ({self.id})"

    @classmethod
    def create_from_request(
        cls,
        contribution_type,
        payload,
        user=None,
        developer=None,
        external_user_id=None,
        source_type=SOURCE_UI,
        idempotency_key=None,
    ):
        """
        Create a new contribution from an API or UI request.

        This is the primary entry point for creating contributions. It handles:
        - Attribution (user, developer, external user)
        - Idempotency checking (if key provided)
        - Payload fingerprinting for duplicate detection
        - Initial status assignment
        - Validation of required fields

        Args:
            contribution_type: Type of contribution (e.g., 'route_update')
            payload: JSON-serializable dict with contribution data
            user: Authenticated User instance (optional)
            developer: Developer instance (optional, for API submissions)
            external_user_id: External user identifier (optional)
            source_type: Source type (ui, api, bulk, external)
            idempotency_key: Client-provided idempotency key (optional)

        Returns:
            Tuple of (contribution, created) where created is True if new

        Raises:
            ValueError: If required attribution is missing or payload invalid

        TODO (Sprint-2):
        - Implement payload validation based on contribution_type
        - Add payload fingerprinting logic
        - Implement idempotency key checking
        - Add automatic points calculation
        - Trigger background tasks for notifications
        """
        # Validation: at least one attribution source must be provided
        if not any([user, developer, external_user_id]):
            raise ValueError(
                "At least one attribution source required: user, developer, or external_user_id"
            )

        # TODO: Check idempotency_key if provided
        # if idempotency_key:
        #     existing = cls.objects.filter(idempotency_key=idempotency_key).first()
        #     if existing:
        #         return (existing, False)

        # TODO: Compute payload fingerprint for duplicate detection
        # payload_fingerprint = compute_payload_hash(payload)

        # Create contribution
        contribution = cls.objects.create(
            type=contribution_type,
            payload=payload,
            submitted_by=user,
            submitted_by_developer=developer,
            external_user_id=external_user_id or "",
            source_type=source_type,
            idempotency_key=idempotency_key or "",
            status=cls.STATUS_PENDING,
            points_awarded=0,
        )

        return (contribution, True)

    def apply_moderation(self, action, moderator=None, reason="", metadata=None):
        """
        Apply a moderation action to this contribution.

        This method is called by moderators to approve, reject, or flag
        contributions. It updates the contribution status and creates
        a moderation log entry.

        Args:
            action: Moderation action (approve, reject, flag)
            moderator: User performing moderation (optional for automated)
            reason: Text reason for the action
            metadata: Additional metadata about the decision

        Returns:
            ModerationEntry instance

        Side effects:
            - Updates contribution status
            - Awards/revokes points
            - Updates user statistics
            - Creates moderation log entry

        TODO (Sprint-2):
        - Implement points calculation and awarding
        - Trigger notifications to submitter
        - Update user stats counters
        - Trigger background job for publishing (if approved)

        Note: Import ModerationEntry here to avoid circular import
        """
        from .moderation import ModerationEntry

        # Map moderation action to status
        action_status_map = {
            "approve": self.STATUS_APPROVED,
            "reject": self.STATUS_REJECTED,
            "flag": self.STATUS_FLAGGED,
            "publish": self.STATUS_PUBLISHED,
        }

        new_status = action_status_map.get(action)
        if not new_status:
            raise ValueError(f"Invalid moderation action: {action}")

        # Update contribution status
        old_status = self.status
        self.status = new_status

        # TODO: Award points if approved/published
        # if new_status in [self.STATUS_APPROVED, self.STATUS_PUBLISHED]:
        #     self.points_awarded = calculate_points(self.type, self.payload)

        self.save(update_fields=["status", "points_awarded", "updated_at"])

        # Create moderation log entry
        moderation_entry = ModerationEntry.objects.create(
            contribution=self,
            moderator=moderator,
            action=action,
            reason=reason,
            metadata=metadata or {},
            previous_status=old_status,
            new_status=new_status,
        )

        return moderation_entry
