"""
Evaluation job abstraction.

Sprint-12: Performance & Recompute Control

This module provides a formal, immutable representation of an evaluation job.

An EvaluationJob describes WHAT needs to be evaluated, not HOW.
It is purely descriptive - no evaluation logic lives here.

WHAT THIS MODULE PROVIDES:
- Immutable evaluation job descriptor
- Deterministic job identity

WHAT THIS MODULE DOES NOT PROVIDE:
- Evaluation logic
- Execution logic
- Locking logic
- Database writes

INVARIANTS:
- Jobs are immutable once created
- Jobs are purely descriptive (no logic)
- Jobs have deterministic inputs
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import FrozenSet, Optional
from uuid import UUID, uuid4

from django.utils import timezone


class TargetType(str, Enum):
    """Target entity type for evaluation."""

    STOP = "stop"
    ROUTE = "route"


class Trigger(str, Enum):
    """What triggered this evaluation job."""

    CONTRIBUTION = "contribution"
    ADMIN = "admin"
    REPLAY = "replay"


@dataclass(frozen=True)
class EvaluationJob:
    """
    Immutable representation of an evaluation job.

    This abstraction describes WHAT needs to be evaluated.
    It carries no execution logic.

    Attributes:
        job_id: Unique identifier for this job
        target_type: Whether to evaluate stops or routes
        target_ids: Specific entity UUIDs to evaluate, or None for full scope
        trigger: What triggered this job (contribution, admin, replay)
        ruleset_version: Version of evaluation rules to apply
        created_at: When this job was created
    """

    target_type: TargetType
    trigger: Trigger
    ruleset_version: str
    job_id: UUID = field(default_factory=uuid4)
    target_ids: Optional[FrozenSet[UUID]] = None
    created_at: datetime = field(default_factory=timezone.now)

    def __post_init__(self):
        """Validate job parameters."""
        if not self.ruleset_version:
            raise ValueError("ruleset_version is required")
        if not isinstance(self.target_type, TargetType):
            raise ValueError(
                f"target_type must be a TargetType enum, got {type(self.target_type)}"
            )
        if not isinstance(self.trigger, Trigger):
            raise ValueError(
                f"trigger must be a Trigger enum, got {type(self.trigger)}"
            )
        if self.target_ids is not None and not isinstance(
            self.target_ids, frozenset
        ):
            raise ValueError("target_ids must be a frozenset or None")

    @property
    def is_full_scope(self) -> bool:
        """Whether this job targets all entities of the given type."""
        return self.target_ids is None

    @property
    def target_count(self) -> Optional[int]:
        """Number of targeted entities, or None for full scope."""
        if self.target_ids is None:
            return None
        return len(self.target_ids)

    def __str__(self) -> str:
        scope = "full" if self.is_full_scope else f"{self.target_count} targets"
        return (
            f"EvaluationJob({self.job_id}: "
            f"{self.target_type.value} [{scope}], "
            f"trigger={self.trigger.value})"
        )
