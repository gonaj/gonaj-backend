"""
Stop evaluator scaffolding and canonical write gateway.

Sprint-4A: Evaluation Scaffolding and Determinism

This module provides:
- StopWriteGateway: Controlled pathway for canonical Stop writes
- StopEvaluator: Deterministic evaluation entrypoint for Stop entities

WHAT THIS MODULE PROVIDES:
- Deterministic evidence processing for Stop-related contributions
- Single controlled pathway for Stop writes
- Incremental and full evaluation hooks

WHAT THIS MODULE DOES NOT PROVIDE (Sprint-4A):
- Stop creation logic
- Confidence calculations
- Decay logic
- Spatial clustering or thresholds
- Any semantic evaluation decisions

INVARIANTS ENFORCED:
- INV-A1: No evidence loss
- INV-A2: Evidence immutability
- INV-B1: Deterministic evaluation
- INV-B2: Replay equivalence
- INV-I2: Canonical write protection (all writes via gateway)
"""

from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from core.models import ContributionEvent
from django.db import transaction
from transit.models import Stop

from .base import BaseEvaluator, EvaluationContext, EvaluationResult


class StopWriteGateway:
    """
    Controlled gateway for canonical Stop writes.

    INV-I2: All canonical Stop writes must occur via this gateway.

    This class provides a single, controlled pathway through which
    canonical Stop records may be written. Direct .save() on Stop
    models should not be used elsewhere in the codebase.

    Sprint-4A Note:
    This gateway exists as scaffolding. It performs minimal work
    in this sprint but establishes the pattern for future
    evaluation logic to follow.

    RESPONSIBILITIES:
    - Enforce that all Stop writes go through one explicit method
    - Provide hooks for future write validation
    - Track writes for audit and result reporting

    FUTURE RESPONSIBILITIES (not in Sprint-4A):
    - Enforce invariants before writes
    - Apply confidence calculations
    - Handle version management
    CONSTRAINTS (Phase-1):
    - This gateway must not perform semantic evaluation, threshold
      checks, confidence math, or belief decisions before Sprint-4C.
    IMPORTANT:
    - No semantic decisions are permitted in this gateway until
      Sprint-4C. Any such logic is a Phase-1 violation.
    """

    def __init__(self, context: EvaluationContext):
        """
        Initialize the write gateway with evaluation context.

        Args:
            context: The evaluation context for this write session
        """
        self._context = context
        self._write_count = 0
        self._written_ids: List[UUID] = []

    @property
    def context(self) -> EvaluationContext:
        """Get the evaluation context (read-only)."""
        return self._context

    @property
    def write_count(self) -> int:
        """Get the number of writes performed through this gateway."""
        return self._write_count

    @property
    def written_ids(self) -> List[UUID]:
        """Get the IDs of entities written through this gateway."""
        return self._written_ids.copy()

    def write_stop(
        self,
        stop: Stop,
        evidence_refs: List[UUID],
    ) -> Stop:
        """
        Write a Stop entity through the controlled gateway.

        INV-I2: This is the ONLY method that should write Stop records.

        This method:
        - Ensures the ruleset_version is set correctly
        - Records evidence references
        - Uses _internal_save() to bypass the guardrail
        - Tracks the write for audit

        Sprint-4A Note:
        This method performs minimal validation. Future sprints
        will add invariant enforcement here.

        Args:
            stop: The Stop entity to write
            evidence_refs: List of ContributionEvent IDs supporting this write

        Returns:
            The saved Stop entity

        Raises:
            ValueError: If stop or evidence_refs is invalid
        """
        if stop is None:
            raise ValueError("Stop entity cannot be None")
        if not isinstance(evidence_refs, list):
            raise ValueError("evidence_refs must be a list")

        # Set evaluation metadata
        stop.ruleset_version = self._context.ruleset_version
        stop.evidence_refs = [str(ref) for ref in evidence_refs]

        # Perform the write using internal save
        stop._internal_save()

        # Track the write
        self._write_count += 1
        self._written_ids.append(stop.id)

        return stop

    def write_stop_atomic(
        self,
        stop: Stop,
        evidence_refs: List[UUID],
    ) -> Stop:
        """
        Write a Stop entity atomically within a transaction.

        This method wraps write_stop in a database transaction
        for safer writes when multiple operations may be involved.

        Args:
            stop: The Stop entity to write
            evidence_refs: List of ContributionEvent IDs supporting this write

        Returns:
            The saved Stop entity
        """
        with transaction.atomic():
            return self.write_stop(stop, evidence_refs)


class StopEvaluator(BaseEvaluator):
    """
    Deterministic evaluator for Stop entities.

    This class provides the evaluation scaffolding for Stop entities.
    It processes ContributionEvent records related to Stops and
    routes all writes through the StopWriteGateway.

    CONTRIBUTION TYPES HANDLED:
    - stop_exists: Stop existence confirmation
    - stop_not_exists: Stop non-existence report
    - stop_name: Stop name correction
    - stop_location: Stop location refinement

    DETERMINISM:
    - Evidence is sorted using explicit, stable sort keys
    - Processing order is deterministic
    - No wall-clock time is used during evaluation
    - No randomness

    INVARIANTS:
    - INV-A1: All evidence is processed (no loss)
    - INV-A2: Evidence is never mutated
    - INV-B1: Output is deterministic for identical input
    - INV-B2: Incremental and batch evaluation converge
    - INV-I2: All writes go through the gateway

    Sprint-4A Note:
    This evaluator provides scaffolding only. No semantic
    evaluation logic (stop creation, confidence, decay) is
    implemented in this sprint.
    """

    # Contribution types relevant to Stop evaluation
    STOP_CONTRIBUTION_TYPES = (
        ContributionEvent.ContributionType.STOP_EXISTS,
        ContributionEvent.ContributionType.STOP_NOT_EXISTS,
        ContributionEvent.ContributionType.STOP_NAME,
        ContributionEvent.ContributionType.STOP_LOCATION,
    )

    def __init__(self, context: EvaluationContext):
        """
        Initialize the Stop evaluator.

        Args:
            context: Immutable evaluation context
        """
        super().__init__(context)
        self._write_gateway = StopWriteGateway(context)

    @property
    def write_gateway(self) -> StopWriteGateway:
        """Get the write gateway for this evaluator."""
        return self._write_gateway

    def filter_stop_evidence(
        self, evidence: Sequence[ContributionEvent]
    ) -> List[ContributionEvent]:
        """
        Filter evidence to only Stop-related contribution types.

        This method filters the evidence stream to include only
        contribution types relevant to Stop evaluation.

        Args:
            evidence: Full evidence sequence

        Returns:
            List of Stop-related ContributionEvents
        """
        return [
            e for e in evidence if e.contribution_type in self.STOP_CONTRIBUTION_TYPES
        ]

    def evaluate(self, evidence: Sequence[ContributionEvent]) -> EvaluationResult:
        """
        Process evidence and return evaluation result.

        This is the main deterministic entrypoint for Stop evaluation.
        It:
        1. Captures original evidence IDs (for INV-A2 validation)
        2. Filters to Stop-related evidence
        3. Sorts evidence deterministically
        4. Processes each evidence event (scaffolding only)
        5. Validates evidence was not mutated

        Sprint-4A Note:
        The actual processing loop is scaffolding. No semantic
        decisions (stop creation, confidence updates) are made.

        Args:
            evidence: Collection of ContributionEvent records

        Returns:
            EvaluationResult with processed evidence tracking
        """
        # Capture original IDs for immutability validation (INV-A2)
        original_ids = self.get_evidence_ids(evidence)

        # Filter to Stop-related evidence
        stop_evidence = self.filter_stop_evidence(evidence)

        # Sort deterministically (INV-B1)
        sorted_evidence = self.sort_evidence_deterministically(stop_evidence)

        # Process each evidence event
        # Sprint-4A: This is scaffolding only - no semantic decisions
        for event in sorted_evidence:
            self._process_evidence_event(event)

        # Validate evidence immutability (INV-A2)
        if not self._validate_evidence_not_mutated(evidence, original_ids):
            self._result.add_error(
                "Evidence was mutated during evaluation - INV-A2 violation"
            )

        # Record gateway write count
        self._result.canonical_writes = self._write_gateway.write_count

        return self._result

    def evaluate_incremental(
        self, new_evidence: Sequence[ContributionEvent]
    ) -> EvaluationResult:
        """
        Process new evidence incrementally.

        INV-B2: This must converge to the same state as full evaluation.

        Incremental evaluation is the normal operational path. It
        processes newly arrived evidence and updates canonical state
        based on the existing state plus new evidence.

        Sprint-4A Note:
        Both incremental and full evaluation use the same core
        processing path to ensure convergence (INV-B2).

        Args:
            new_evidence: Newly arrived ContributionEvent records

        Returns:
            EvaluationResult with processed evidence tracking
        """
        # Use the same core path as full evaluation
        # This ensures INV-B2 (incremental == batch)
        return self._evaluate_core(new_evidence, is_incremental=True)

    def evaluate_full(
        self, all_evidence: Sequence[ContributionEvent]
    ) -> EvaluationResult:
        """
        Perform full recomputation from all evidence.

        INV-B2: This must produce the same result as applying
        all evidence incrementally.

        Full recomputation is used for:
        - Fixing bugs in evaluation logic
        - Introducing improved rules
        - Auditing system behavior

        Sprint-4A Note:
        Both incremental and full evaluation use the same core
        processing path to ensure convergence (INV-B2).

        Args:
            all_evidence: Complete history of ContributionEvent records

        Returns:
            EvaluationResult with processed evidence tracking
        """
        # Use the same core path as incremental evaluation
        # This ensures INV-B2 (incremental == batch)
        return self._evaluate_core(all_evidence, is_incremental=False)

    def _evaluate_core(
        self,
        evidence: Sequence[ContributionEvent],
        is_incremental: bool,
    ) -> EvaluationResult:
        """
        Core evaluation logic shared by incremental and full paths.

        INV-B2: Using a single core path ensures that incremental
        and batch evaluation converge to the same result.

        Args:
            evidence: ContributionEvent records to process
            is_incremental: Whether this is incremental evaluation

        Returns:
            EvaluationResult with processed evidence tracking
        """
        # Delegate to the main evaluate method
        # This ensures consistent deterministic processing
        return self.evaluate(evidence)

    def _process_evidence_event(self, event: ContributionEvent) -> None:
        """
        Process a single evidence event.

        Sprint-4A Note:
        This is scaffolding only. The method:
        - Records that the event was processed (INV-A1)
        - Does NOT make any semantic decisions
        - Does NOT create or modify Stops
        - Does NOT calculate confidence

        Future sprints will add evaluation logic here.

        Args:
            event: The ContributionEvent to process
        """
        # Record that this evidence was processed (INV-A1)
        self._result.add_processed_evidence(event.id)

        # Sprint-4A: No semantic processing
        # Future sprints will add:
        # - Spatial clustering
        # - Confidence calculation
        # - Stop creation/update logic
        # - Decay handling

    def get_stop_evidence_queryset(self):
        """
        Get a queryset for Stop-related evidence, properly ordered.

        This method provides a reusable queryset that:
        - Filters to Stop-related contribution types
        - Orders deterministically using explicit sort keys

        Returns:
            QuerySet of ContributionEvents for Stop evaluation
        """
        return ContributionEvent.objects.filter(
            contribution_type__in=self.STOP_CONTRIBUTION_TYPES
        ).order_by(*self.EVIDENCE_SORT_KEYS)
