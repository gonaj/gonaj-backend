"""
Architectural base classes and mixins for the Gonaj platform.

This module defines foundational patterns that enforce Phase-1 invariants:

1. SoftDeletable - Prevents hard deletes, uses soft invalidation instead
2. ImmutableModel - Enforces append-only pattern, prevents updates
3. VersionedModel - Provides temporal versioning foundation

CRITICAL INVARIANTS (from BACKEND_PHILOSOPHY.md):
- Nothing is ever deleted (data fades through decay, not deletion)
- Contributions are append-only
- Truth is versioned and temporal
- All decisions are reversible

These base classes make it structurally difficult to violate these invariants.
"""

from django.db import models
from django.utils import timezone


class SoftDeletable(models.Model):
    """
    Base mixin that prevents hard deletes and enforces soft invalidation.

    PHILOSOPHY:
    "Nothing is ever deleted. Data fades through decay, not deletion."

    Instead of removing records from the database, this mixin marks them
    as invalid using timestamp-based soft deletion. This preserves:
    - Historical audit trails
    - Ability to replay and recompute
    - Reversibility of all decisions

    Usage:
        class MyModel(SoftDeletable):
            # ... your fields ...
            pass

    Note: Models using this mixin should never call .delete() directly.
    Use .soft_delete() instead.

    DEFERRED TO LATER PHASE:
    - Automatic query filtering (using custom managers)
    - Restoration workflows
    - Cascade behavior for related objects
    """

    # Timestamp when this record was soft-deleted/invalidated
    # NULL = active, Non-NULL = soft-deleted
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when this record was soft-deleted. NULL means active.",
    )

    class Meta:
        abstract = True

    def soft_delete(self):
        """
        Soft-delete this record by setting deleted_at timestamp.

        This method should be used instead of .delete() to maintain
        historical data and auditability.
        """
        if self.deleted_at is None:
            self.deleted_at = timezone.now()
            self.save(update_fields=["deleted_at"])

    def is_deleted(self):
        """Check if this record has been soft-deleted."""
        return self.deleted_at is not None

    def delete(self, *args, **kwargs):
        """
        Override delete() to prevent hard deletes.

        ARCHITECTURAL GUARDRAIL:
        Hard deletes violate the "nothing is ever deleted" invariant.

        If you absolutely must hard-delete (e.g., GDPR compliance),
        use .hard_delete() explicitly to signal intent.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} uses soft deletion. "
            "Use .soft_delete() instead of .delete(). "
            "If you absolutely must hard-delete, use .hard_delete()."
        )

    def hard_delete(self):
        """
        Actually delete the record from the database.

        WARNING: This should only be used in exceptional cases like:
        - GDPR data deletion requests
        - Data corruption cleanup
        - Test teardown

        This method exists to make hard deletes explicit and intentional.
        """
        super().delete()


class ImmutableModel(models.Model):
    """
    Base class for immutable, append-only models.

    PHILOSOPHY:
    "Contributions are append-only. Evidence is never overwritten or deleted."

    Models inheriting from this base enforce immutability by:
    - Raising errors on update attempts
    - Preventing deletion
    - Supporting idempotent creation via natural keys

    This pattern is critical for:
    - ContributionEvent (evidence layer)
    - Audit logs
    - Any record that must be replayable

    Usage:
        class MyImmutableModel(ImmutableModel):
            # ... your fields ...
            pass

    IMPORTANT:
    - Only INSERT operations are allowed
    - Use bulk_create for batch inserts
    - Implement get_or_create for idempotency

    DEFERRED TO LATER PHASE:
    - Event sourcing patterns
    - Snapshot/aggregation mechanisms
    """

    # Auto-populated creation timestamp
    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        db_index=True,
        help_text="When this immutable record was created (server time).",
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Override save to prevent updates while allowing creation.

        ARCHITECTURAL GUARDRAIL:
        Once created, immutable records cannot be modified.
        This ensures evidence integrity and replayability.
        """
        # Allow initial creation (force_insert=True or record not in DB yet)
        # Check if this is an insert operation
        force_insert = kwargs.get("force_insert", False)

        # If force_insert is True, this is definitely a creation
        if force_insert:
            super().save(*args, **kwargs)
            return

        # Otherwise, check if the instance exists in the database
        # If pk is set and the record exists, this is an update attempt
        if self.pk is not None:
            # Check if this record actually exists in the database
            try:
                self.__class__.objects.get(pk=self.pk)
                # If we get here, the record exists - this is an UPDATE
                raise NotImplementedError(
                    f"{self.__class__.__name__} is immutable. "
                    "UPDATE operations are not allowed. "
                    "Create a new record instead."
                )
            except self.__class__.DoesNotExist:
                # Record doesn't exist yet, this is an INSERT
                super().save(*args, **kwargs)
        else:
            # No pk set, this is definitely an INSERT
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Prevent deletion of immutable records.

        ARCHITECTURAL GUARDRAIL:
        Immutable records represent evidence or historical facts.
        They cannot be deleted without violating auditability.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} is immutable. "
            "DELETE operations are not allowed. "
            "Immutable records must be preserved for auditability."
        )


class VersionedModel(models.Model):
    """
    Base class for temporally-versioned entities.

    PHILOSOPHY:
    "Truth is versioned and temporal. There is no timeless truth in transit."

    This base provides the foundation for entities that:
    - Evolve over time
    - Have multiple valid versions
    - Support point-in-time queries

    Fields:
    - version: Sequential version number for this entity
    - valid_from: When this version became valid
    - valid_until: When this version was superseded (NULL = current)

    Usage:
        class MyVersionedEntity(VersionedModel):
            # Add your domain-specific fields
            # Include a field to link versions (e.g., logical_id)
            pass

    IMPORTANT:
    This base provides structure only. Versioning logic (creating new
    versions, closing old ones) must be implemented by evaluation rules,
    not by direct edits.

    DEFERRED TO LATER PHASE:
    - Automatic version creation logic
    - Point-in-time query helpers
    - Version conflict detection
    - Application to canonical transit entities (Stop, Route, etc.)

    Note: In Phase-1, this base is defined but not yet applied to
    canonical entities. It will be used in later phases.
    """

    # Sequential version number (scoped to a logical entity)
    version = models.PositiveIntegerField(
        default=1,
        help_text="Version number of this record. Increments with each change.",
    )

    # Temporal validity range
    valid_from = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When this version became valid (inclusive).",
    )

    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When this version was superseded (exclusive). NULL = current version.",
    )

    class Meta:
        abstract = True
        # Subclasses should add indexes like:
        # indexes = [
        #     models.Index(fields=['logical_id', 'valid_from']),
        #     models.Index(fields=['logical_id', 'valid_until']),
        # ]

    def is_current(self):
        """Check if this is the current (active) version."""
        return self.valid_until is None

    def close_version(self, closed_at=None):
        """
        Close this version by setting valid_until.

        This should only be called by evaluation logic when a new
        version supersedes this one.

        Args:
            closed_at: Timestamp when version was superseded.
                      Defaults to now.
        """
        if not self.is_current():
            raise ValueError(
                f"Cannot close version {self.version}: already closed at {self.valid_until}"
            )

        self.valid_until = closed_at or timezone.now()
        # Allow this specific update for version management
        # Override the save protection if this were immutable
        models.Model.save(self, update_fields=["valid_until"])
