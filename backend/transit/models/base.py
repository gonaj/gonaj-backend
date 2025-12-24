"""
Base class for canonical transit entities in Phase-1.

PHILOSOPHY:
Canonical entities represent "what the system currently believes to be true."
They are:
- DERIVED from ContributionEvent records via evaluation logic
- MATERIALIZED and stored for efficient querying
- NEVER directly edited by users or APIs

This base class provides the required metadata fields that enable:
- Replay and recomputation from evidence
- Audit trails
- Temporal versioning
- Confidence tracking
- Rule evolution

CRITICAL INVARIANTS (from BACKEND_PHILOSOPHY.md):
- Canonical data is derived, not edited
- All decisions are reversible
- Canonical tables exist for efficiency, not authority
- Authority remains with immutable ContributionEvent records

Sprint-3 Note:
This base class provides STRUCTURE ONLY.
No evaluation, aggregation, or decay logic exists in Sprint-3.
"""

import uuid

from django.db import models
from django.utils import timezone


class CanonicalModel(models.Model):
    """
    Abstract base class for all canonical transit entities.

    WHAT THIS IS:
    - Structure for storing derived transit knowledge
    - Fields for replay, audit, and evolution
    - Base for Stop, Route, RouteVariant, StopRouteLink, ObservedServiceWindow

    WHAT THIS IS NOT:
    - A source of truth (ContributionEvent is the source)
    - A directly editable model
    - A model with business logic (in Sprint-3)

    REQUIRED FIELDS:
    All fields below are required by PHASE_1_BACKEND_PLAN.md for canonical entities:
    - id: UUID primary key
    - public_id: Stable, opaque identifier for external use
    - version: Integer version number
    - valid_from: When this version became valid
    - valid_until: When this version was superseded (NULL = current)
    - structural_confidence: Long-term stability confidence
    - freshness_confidence: Recency-based confidence
    - ruleset_version: Version of evaluation rules that created this
    - evidence_refs: Array of ContributionEvent IDs that support this
    - created_at: When this record was created
    - updated_at: When this record was last updated

    GUARDRAILS:
    - save() raises NotImplementedError by default to prevent casual updates
    - Use _internal_save() for controlled writes by evaluation logic
    - No convenience methods that mutate truth
    """

    # === Primary Identification ===

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Internal unique identifier for this canonical record.",
    )

    public_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text=(
            "Stable, opaque identifier for external use (APIs, exports). "
            "This ID should remain stable across versions of the same logical entity."
        ),
    )

    # === Versioning ===

    version = models.PositiveIntegerField(
        default=1,
        help_text=(
            "Version number of this record. "
            "Increments when evaluation logic updates the entity. "
            "Multiple versions may exist for the same logical entity."
        ),
    )

    # === Temporal Validity ===

    valid_from = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When this version became valid (inclusive).",
    )

    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "When this version was superseded (exclusive). "
            "NULL means this is the current valid version."
        ),
    )

    # === Confidence Metrics ===

    structural_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0.0,
        help_text=(
            "Long-term stability confidence (0.0 to 1.0). "
            "Represents how well-established this entity is. "
            "Higher = more evidence over time."
        ),
    )

    freshness_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0.0,
        help_text=(
            "Recency-based confidence (0.0 to 1.0). "
            "Decays over time without reinforcing evidence. "
            "Higher = recently confirmed."
        ),
    )

    # === Evaluation Metadata ===

    ruleset_version = models.CharField(
        max_length=50,
        default="1.0",
        help_text=(
            "Version identifier of the evaluation rules used to derive this record. "
            "Enables recomputation when rules change."
        ),
    )

    evidence_refs = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Array of ContributionEvent IDs that support this canonical record. "
            "Used for provenance, audit, and recomputation."
        ),
    )

    # === Timestamps ===

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this canonical record was first created.",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this canonical record was last updated by evaluation logic.",
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Prevent direct saves to canonical entities.

        ARCHITECTURAL GUARDRAIL:
        Canonical entities are derived from evidence via evaluation logic.
        Direct edits violate the "canonical data is derived, not edited" invariant.

        Use _internal_save() for controlled writes by evaluation logic.
        This method exists in base classes but should only be called by
        authorized evaluation code.
        """
        # Check for internal save flag
        if kwargs.pop("_evaluation_write", False):
            super().save(*args, **kwargs)
            return

        raise NotImplementedError(
            f"{self.__class__.__name__} is a canonical entity and cannot be "
            "directly saved. Canonical entities must be updated via evaluation logic. "
            "If you are writing evaluation logic, use _internal_save() with "
            "_evaluation_write=True."
        )

    def _internal_save(self, *args, **kwargs):
        """
        Internal save method for evaluation logic.

        This method bypasses the save() guardrail and should ONLY be called
        by evaluation/aggregation code that derives truth from evidence.

        WARNING: Do not call this from API views, serializers, or user-facing code.
        """
        kwargs["_evaluation_write"] = True
        self.save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Prevent deletion of canonical entities.

        ARCHITECTURAL GUARDRAIL:
        "Nothing is ever deleted. Data fades through decay, not deletion."

        Canonical entities should be superseded by new versions or have their
        confidence decay naturally. Direct deletion is not allowed.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} cannot be deleted. "
            "Canonical entities fade through decay or are superseded by new versions. "
            "Set valid_until to close a version."
        )

    def is_current(self):
        """Check if this is the current (active) version."""
        return self.valid_until is None

    def __str__(self):
        return f"{self.__class__.__name__} ({self.public_id}, v{self.version})"
