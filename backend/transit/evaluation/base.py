"""
Base classes for evaluation scaffolding.

Sprint-4A: Evaluation Scaffolding and Determinism

This module provides the foundational classes for evaluation:
- EvaluationContext: Immutable context for evaluation runs
- EvaluationResult: Container for evaluation outcomes
- BaseEvaluator: Abstract base class for entity evaluators

DETERMINISM REQUIREMENTS (Non-Negotiable):
- Evidence ordering must be deterministic (explicit sort keys)
- No reliance on database default ordering
- No use of wall-clock time during evaluation
- No randomness

Given identical inputs, outputs must be byte-identical.

INVARIANTS SUPPORTED:
- INV-A1: No evidence loss (all evidence must be processed)
- INV-A2: Evidence immutability (no writes to evidence tables)
- INV-B1: Deterministic evaluation
- INV-B2: Replay equivalence
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional, Sequence
from uuid import UUID

from core.models import ContributionEvent


@dataclass(frozen=True)
class EvaluationContext:
    """
    Immutable context for an evaluation run.

    This context captures everything needed to make evaluation deterministic
    and reproducible. It is frozen (immutable) to prevent accidental mutation.

    Attributes:
        ruleset_version: Version of evaluation rules being applied
        evaluation_time: Fixed timestamp for this evaluation run
                        (NOT wall-clock time - passed explicitly)
        is_incremental: Whether this is an incremental or full evaluation
        batch_id: Optional identifier for this evaluation batch

    DETERMINISM:
    - evaluation_time is passed in, not generated from wall-clock
    - This allows replay with identical timestamps
    """

    ruleset_version: str
    evaluation_time: datetime
    is_incremental: bool = True
    batch_id: Optional[str] = None

    def __post_init__(self):
        """Validate context parameters."""
        if not self.ruleset_version:
            raise ValueError("ruleset_version is required")
        if not self.evaluation_time:
            raise ValueError("evaluation_time is required")


@dataclass
class EvaluationResult:
    """
    Container for evaluation outcomes.

    This class captures the result of an evaluation run without
    making any semantic decisions. It provides:
    - List of evidence processed
    - Metadata about the evaluation run
    - Hooks for future evaluation logic

    Sprint-4A Note:
    This is scaffolding only. No actual evaluation outcomes
    are computed in this sprint.

    Attributes:
        evidence_processed: List of ContributionEvent IDs that were processed
        evidence_count: Total count of evidence processed
        context: The evaluation context used
        canonical_writes: Count of canonical entity writes performed
        errors: List of any errors encountered during evaluation
    """

    evidence_processed: List[UUID] = field(default_factory=list)
    evidence_count: int = 0
    context: Optional[EvaluationContext] = None
    canonical_writes: int = 0
    errors: List[str] = field(default_factory=list)

    def add_processed_evidence(self, event_id: UUID) -> None:
        """
        Record that an evidence event was processed.

        INV-A1: This ensures no evidence is lost by tracking
        all processed events.
        """
        self.evidence_processed.append(event_id)
        self.evidence_count = len(self.evidence_processed)

    def add_error(self, error_message: str) -> None:
        """Record an error encountered during evaluation."""
        self.errors.append(error_message)

    def has_errors(self) -> bool:
        """Check if any errors occurred during evaluation."""
        return len(self.errors) > 0

    def increment_canonical_writes(self) -> None:
        """Record that a canonical entity was written."""
        self.canonical_writes += 1


class BaseEvaluator(ABC):
    """
    Abstract base class for entity evaluators.

    This class defines the contract for all evaluators in the system.
    Concrete implementations must:
    - Process evidence deterministically
    - Never mutate evidence records
    - Write canonical entities only through the designated gateway

    DETERMINISM:
    Evidence is sorted using explicit, stable sort keys before processing.
    The sort order is:
    1. observed_at (when the observation occurred)
    2. submitted_at (when it was received by the server)
    3. id (UUID as tiebreaker for absolute stability)

    This ensures that given identical evidence sets, evaluation
    will always process events in the same order.

    INVARIANTS:
    - INV-A1: All evidence in the input must be processed
    - INV-A2: No writes to evidence tables
    - INV-B1: Deterministic output for identical input
    - INV-B2: Incremental and batch evaluation must converge
    """

    # Sort keys for deterministic evidence ordering
    # These are explicit and must not be changed without careful consideration
    EVIDENCE_SORT_KEYS = ("observed_at", "submitted_at", "id")

    def __init__(self, context: EvaluationContext):
        """
        Initialize the evaluator with an evaluation context.

        Args:
            context: Immutable evaluation context
        """
        self._context = context
        self._result = EvaluationResult(context=context)

    @property
    def context(self) -> EvaluationContext:
        """Get the evaluation context (read-only)."""
        return self._context

    @property
    def result(self) -> EvaluationResult:
        """Get the evaluation result."""
        return self._result

    def sort_evidence_deterministically(
        self, evidence: Sequence[ContributionEvent]
    ) -> List[ContributionEvent]:
        """
        Sort evidence using deterministic, explicit sort keys.

        INV-B1: This method ensures deterministic ordering regardless
        of how evidence was retrieved from the database.

        Sort order:
        1. observed_at (ascending) - when the observation occurred
        2. submitted_at (ascending) - when it was received
        3. id (ascending) - UUID as absolute tiebreaker

        Args:
            evidence: Sequence of ContributionEvent records

        Returns:
            List of ContributionEvents sorted deterministically
        """
        return sorted(
            evidence,
            key=lambda e: (e.observed_at, e.submitted_at, str(e.id)),
        )

    def get_evidence_ids(self, evidence: Sequence[ContributionEvent]) -> List[UUID]:
        """
        Extract IDs from evidence for tracking.

        This is used to record which evidence was processed
        without storing references to the full objects.
        """
        return [e.id for e in evidence]

    @abstractmethod
    def evaluate(self, evidence: Sequence[ContributionEvent]) -> EvaluationResult:
        """
        Process evidence and return evaluation result.

        This is the main entry point for evaluation. Implementations
        must:
        - Sort evidence deterministically
        - Process all evidence (INV-A1)
        - Not mutate evidence (INV-A2)
        - Produce deterministic output (INV-B1)

        Args:
            evidence: Collection of ContributionEvent records to evaluate

        Returns:
            EvaluationResult containing processed evidence and outcomes
        """
        pass

    @abstractmethod
    def evaluate_incremental(
        self, new_evidence: Sequence[ContributionEvent]
    ) -> EvaluationResult:
        """
        Process new evidence incrementally.

        INV-B2: The result of incremental evaluation must converge
        to the same state as full recomputation.

        Args:
            new_evidence: Newly arrived ContributionEvent records

        Returns:
            EvaluationResult containing processed evidence and outcomes
        """
        pass

    @abstractmethod
    def evaluate_full(
        self, all_evidence: Sequence[ContributionEvent]
    ) -> EvaluationResult:
        """
        Perform full recomputation from all evidence.

        This method processes all historical evidence to derive
        canonical state from scratch. Used for:
        - Fixing bugs in evaluation logic
        - Introducing improved rules
        - Auditing system behavior

        INV-B2: The result must be identical to applying all
        evidence incrementally.

        Args:
            all_evidence: Complete history of ContributionEvent records

        Returns:
            EvaluationResult containing processed evidence and outcomes
        """
        pass

    def _validate_evidence_not_mutated(
        self,
        evidence: Sequence[ContributionEvent],
        original_ids: List[UUID],
    ) -> bool:
        """
        Verify that evidence was not mutated during evaluation.

        INV-A2: This helper validates that evidence IDs remain
        unchanged after processing.

        Args:
            evidence: Evidence after processing
            original_ids: IDs captured before processing

        Returns:
            True if evidence is unchanged, False otherwise
        """
        current_ids = self.get_evidence_ids(evidence)
        return current_ids == original_ids
