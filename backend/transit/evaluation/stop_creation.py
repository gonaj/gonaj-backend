"""
Stop creation logic with structural gates and belief threshold.

Sprint-4C: Stop Creation & Initial Belief (Rules v0)
Sprint-4D: Negative Evidence & Conflict Handling (Rules v0)

This module provides:
- StructuralGateResult: Immutable result of gate evaluation
- StructuralGateEvaluator: Hard precondition checks for Stop creation
- ThresholdEvaluator: Belief threshold evaluation (gated by structural checks)
- StopCreator: Canonical Stop creation via gateway
- Negative evidence threshold adjustment (Sprint-4D)

ARCHITECTURE:

    STRUCTURAL GATES (hard)
            |
            v
    BELIEF THRESHOLD (gated, adjusted for negative evidence)
            |
            v
    CANONICAL STOP (created)

Both stages are required. Neither alone is sufficient.

Sprint-4D Extension:
- Negative evidence may RAISE threshold (never blocks creation)
- Threshold adjustment is capped and conservative
- No amount of negative evidence permanently vetoes creation

WHAT THIS MODULE PROVIDES:
- Deterministic structural gate evaluation
- Threshold-based belief evaluation
- Canonical Stop creation via StopWriteGateway
- Negative evidence threshold adjustment (Sprint-4D)

WHAT THIS MODULE DOES NOT PROVIDE:
- Confidence decay logic
- Merge/split logic
- Threshold tuning per region/operator
- Stop deletion logic

INVARIANTS ENFORCED:
- INV-B1: Deterministic evaluation
- INV-B2: Replay equivalence
- INV-C1: No single-event creation
- INV-C2: Independence requirement
- INV-C3: Spatial convergence
- INV-H1: Sub-threshold belief not public
- INV-I2: Canonical write protection
- INV-E3: Negative evidence modulates thresholds only (Sprint-4D)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from core.models import ContributionEvent
from django.contrib.gis.geos import Point
from transit.models import Stop

from .base import EvaluationContext
from .stop_aggregation import AggregationResult, SpatialCluster
from .stop_evaluator import StopWriteGateway

# =============================================================================
# Structural Gate Results (Immutable)
# =============================================================================


@dataclass(frozen=True)
class GateResult:
    """
    Immutable result of a single structural gate evaluation.

    Each gate is a hard boolean check that must pass for Stop creation
    to be eligible. Gates are NOT tunable weights.
    """

    gate_name: str
    passed: bool
    reason: str
    details: Optional[Dict] = None

    def __post_init__(self):
        """Validate gate result."""
        if not self.gate_name:
            raise ValueError("gate_name cannot be empty")
        if not self.reason:
            raise ValueError("reason cannot be empty")


@dataclass(frozen=True)
class StructuralGateResult:
    """
    Immutable aggregate result of all structural gate evaluations.

    All gates must pass for Stop creation to be eligible.
    If any gate fails, Stop creation MUST NOT occur.

    INV-C1, INV-C2, INV-C3: These invariants are enforced via gates.
    """

    all_gates_passed: bool
    gate_results: Tuple[GateResult, ...]
    evaluation_time: datetime

    @property
    def failed_gates(self) -> Tuple[GateResult, ...]:
        """Return only the gates that failed."""
        return tuple(g for g in self.gate_results if not g.passed)

    @property
    def passed_gates(self) -> Tuple[GateResult, ...]:
        """Return only the gates that passed."""
        return tuple(g for g in self.gate_results if g.passed)


@dataclass(frozen=True)
class ThresholdResult:
    """
    Immutable result of belief threshold evaluation.

    Threshold evaluation occurs ONLY after all structural gates pass.
    This result indicates whether accumulated belief crosses the
    creation threshold.

    INV-H1: Sub-threshold belief is not public.
    """

    threshold_crossed: bool
    weighted_score: float
    required_threshold: float
    reason: str
    evaluation_time: datetime


@dataclass(frozen=True)
class CreationDecision:
    """
    Immutable decision about whether to create a canonical Stop.

    Encapsulates the complete decision chain:
    - Structural gate evaluation
    - Threshold evaluation (if gates passed)
    - Final creation decision

    This is the primary output of the creation evaluation pipeline.
    """

    should_create: bool
    structural_result: StructuralGateResult
    threshold_result: Optional[ThresholdResult]  # None if gates failed
    cluster: SpatialCluster
    reason: str


# =============================================================================
# Structural Gate Evaluator
# =============================================================================


class StructuralGateEvaluator:
    """
    Evaluates hard structural gates for Stop creation eligibility.

    Structural gates are boolean preconditions that MUST ALL pass
    before Stop creation can be considered. They are NOT tunable
    weights - they are hard requirements derived from Rules v0.

    GATES EVALUATED (ALL mandatory):
    1. Minimum independent contributors (>= 2)
    2. Temporal separation (different calendar days)
    3. Evidence diversity (>= 2 distinct types)
    4. Spatial coherence (cluster within plausible radius)
    5. Temporal plausibility (observations within service windows)

    INVARIANTS ENFORCED:
    - INV-C1: No single-event creation
    - INV-C2: Independence requirement
    - INV-C3: Spatial convergence
    - INV-B1: Deterministic evaluation
    """

    # Gate thresholds (Rules v0)
    MIN_INDEPENDENT_CONTRIBUTORS = 2
    MIN_DISTINCT_DAYS = 2
    MIN_EVIDENCE_TYPES = 2
    MAX_CLUSTER_RADIUS_METERS = 100.0  # Spatial coherence limit

    # Service window bounds (generous for v0)
    MIN_PLAUSIBLE_HOUR = 4  # 4 AM
    MAX_PLAUSIBLE_HOUR = 24  # Midnight (end of service)

    def __init__(self, evaluation_time: datetime):
        """
        Initialize the gate evaluator.

        Args:
            evaluation_time: Timestamp for this evaluation (for audit)
        """
        self._evaluation_time = evaluation_time

    def evaluate_all_gates(self, cluster: SpatialCluster) -> StructuralGateResult:
        """
        Evaluate all structural gates for a cluster.

        INV-B1: Evaluation is deterministic.

        Args:
            cluster: Spatial cluster to evaluate

        Returns:
            Immutable StructuralGateResult with all gate outcomes
        """
        gate_results = []

        # Gate 1: Minimum independent contributors
        gate_results.append(self._evaluate_contributor_gate(cluster))

        # Gate 2: Temporal separation
        gate_results.append(self._evaluate_temporal_separation_gate(cluster))

        # Gate 3: Evidence diversity
        gate_results.append(self._evaluate_evidence_diversity_gate(cluster))

        # Gate 4: Spatial coherence
        gate_results.append(self._evaluate_spatial_coherence_gate(cluster))

        # Gate 5: Temporal plausibility
        gate_results.append(self._evaluate_temporal_plausibility_gate(cluster))

        all_passed = all(g.passed for g in gate_results)

        return StructuralGateResult(
            all_gates_passed=all_passed,
            gate_results=tuple(gate_results),
            evaluation_time=self._evaluation_time,
        )

    def _evaluate_contributor_gate(self, cluster: SpatialCluster) -> GateResult:
        """
        Gate 1: Minimum independent contributors.

        INV-C1: No single-event creation.
        INV-C2: Independence requirement.

        Requires at least MIN_INDEPENDENT_CONTRIBUTORS unique contributors.
        Same-user repetition does not satisfy this gate.
        """
        contributor_count = cluster.independent_contributor_count
        passed = contributor_count >= self.MIN_INDEPENDENT_CONTRIBUTORS

        if passed:
            reason = (
                f"Gate passed: {contributor_count} independent contributors "
                f"(required: {self.MIN_INDEPENDENT_CONTRIBUTORS})"
            )
        else:
            reason = (
                f"Gate failed: only {contributor_count} independent contributor(s) "
                f"(required: {self.MIN_INDEPENDENT_CONTRIBUTORS})"
            )

        return GateResult(
            gate_name="minimum_contributors",
            passed=passed,
            reason=reason,
            details={
                "contributor_count": contributor_count,
                "required": self.MIN_INDEPENDENT_CONTRIBUTORS,
            },
        )

    def _evaluate_temporal_separation_gate(self, cluster: SpatialCluster) -> GateResult:
        """
        Gate 2: Temporal separation.

        INV-C1: No single-event creation.

        Contributions must occur on at least MIN_DISTINCT_DAYS different
        calendar days. This prevents same-session spam from triggering
        creation.
        """
        distinct_days = cluster.temporal_span.distinct_days
        passed = distinct_days >= self.MIN_DISTINCT_DAYS

        if passed:
            reason = (
                f"Gate passed: evidence spans {distinct_days} distinct days "
                f"(required: {self.MIN_DISTINCT_DAYS})"
            )
        else:
            reason = (
                f"Gate failed: evidence spans only {distinct_days} distinct day(s) "
                f"(required: {self.MIN_DISTINCT_DAYS})"
            )

        return GateResult(
            gate_name="temporal_separation",
            passed=passed,
            reason=reason,
            details={
                "distinct_days": distinct_days,
                "required": self.MIN_DISTINCT_DAYS,
                "earliest": cluster.temporal_span.earliest_observation.isoformat(),
                "latest": cluster.temporal_span.latest_observation.isoformat(),
            },
        )

    def _evaluate_evidence_diversity_gate(self, cluster: SpatialCluster) -> GateResult:
        """
        Gate 3: Evidence diversity.

        INV-C1: No single-event creation.

        Requires at least MIN_EVIDENCE_TYPES distinct evidence types.
        Example: assertion + traversal, or stop_exists + stop_name.
        """
        type_count = cluster.evidence_type_breakdown.evidence_type_count
        passed = type_count >= self.MIN_EVIDENCE_TYPES

        if passed:
            reason = (
                f"Gate passed: {type_count} distinct evidence types "
                f"(required: {self.MIN_EVIDENCE_TYPES})"
            )
        else:
            reason = (
                f"Gate failed: only {type_count} distinct evidence type(s) "
                f"(required: {self.MIN_EVIDENCE_TYPES})"
            )

        return GateResult(
            gate_name="evidence_diversity",
            passed=passed,
            reason=reason,
            details={
                "evidence_type_count": type_count,
                "required": self.MIN_EVIDENCE_TYPES,
                "stop_exists": cluster.evidence_type_breakdown.stop_exists_count,
                "stop_name": cluster.evidence_type_breakdown.stop_name_count,
                "stop_location": cluster.evidence_type_breakdown.stop_location_count,
            },
        )

    def _evaluate_spatial_coherence_gate(self, cluster: SpatialCluster) -> GateResult:
        """
        Gate 4: Spatial coherence.

        INV-C3: Spatial convergence.

        Evidence must be spatially coherent - cluster radius must be
        within MAX_CLUSTER_RADIUS_METERS. This prevents distant,
        unrelated observations from forming a Stop.
        """
        radius = cluster.cluster_radius_meters
        passed = radius <= self.MAX_CLUSTER_RADIUS_METERS

        if passed:
            reason = (
                f"Gate passed: cluster radius {radius:.1f}m "
                f"(max allowed: {self.MAX_CLUSTER_RADIUS_METERS}m)"
            )
        else:
            reason = (
                f"Gate failed: cluster radius {radius:.1f}m exceeds "
                f"maximum {self.MAX_CLUSTER_RADIUS_METERS}m"
            )

        return GateResult(
            gate_name="spatial_coherence",
            passed=passed,
            reason=reason,
            details={
                "cluster_radius_meters": radius,
                "max_allowed": self.MAX_CLUSTER_RADIUS_METERS,
            },
        )

    def _evaluate_temporal_plausibility_gate(
        self, cluster: SpatialCluster
    ) -> GateResult:
        """
        Gate 5: Temporal plausibility.

        Observations must fall within plausible transit service windows.
        This is a basic sanity check - contributions at 3 AM may indicate
        data quality issues (though we still keep the evidence per INV-A1).

        For v0, this gate is generous and checks that at least some
        observations fall within service hours.
        """
        # For v0, we check if earliest or latest observation is within
        # plausible hours. This is intentionally permissive.
        earliest_hour = cluster.temporal_span.earliest_observation.hour
        latest_hour = cluster.temporal_span.latest_observation.hour

        # At least one observation should be within service hours
        earliest_plausible = (
            self.MIN_PLAUSIBLE_HOUR <= earliest_hour < self.MAX_PLAUSIBLE_HOUR
        )
        latest_plausible = (
            self.MIN_PLAUSIBLE_HOUR <= latest_hour < self.MAX_PLAUSIBLE_HOUR
        )

        passed = earliest_plausible or latest_plausible

        if passed:
            reason = "Gate passed: observations within plausible service hours"
        else:
            reason = (
                f"Gate failed: observations outside service hours "
                f"(earliest: {earliest_hour}:00, latest: {latest_hour}:00)"
            )

        return GateResult(
            gate_name="temporal_plausibility",
            passed=passed,
            reason=reason,
            details={
                "earliest_hour": earliest_hour,
                "latest_hour": latest_hour,
                "min_plausible": self.MIN_PLAUSIBLE_HOUR,
                "max_plausible": self.MAX_PLAUSIBLE_HOUR,
            },
        )


# =============================================================================
# Threshold Evaluator
# =============================================================================


class ThresholdEvaluator:
    """
    Evaluates belief threshold for Stop creation.

    Threshold evaluation occurs ONLY after all structural gates pass.
    This ensures that threshold alone cannot bypass structural requirements.

    The threshold represents accumulated weighted belief. It is:
    - Evaluated after gates (never before)
    - Deterministic
    - Conservative (biased toward false negatives)
    - Adjusted upward when negative evidence exists (Sprint-4D)

    Sprint-4D Extension:
    Negative evidence may raise the threshold, making creation harder
    but never impossible. This ensures INV-E3: negative evidence
    modulates thresholds only, never blocks creation permanently.

    INVARIANTS ENFORCED:
    - INV-H1: Sub-threshold belief not public
    - INV-B1: Deterministic evaluation
    - INV-E3: Negative evidence modulates thresholds only (Sprint-4D)
    """

    # Base threshold for Stop creation (Rules v0)
    # This is conservative - requires substantial weighted evidence
    BASE_CREATION_THRESHOLD = 2.0

    # Maximum threshold adjustment from negative evidence (Sprint-4D)
    # Negative evidence can raise threshold by at most this amount
    MAX_NEGATIVE_ADJUSTMENT = 1.0

    # Negative evidence adjustment factor (Sprint-4D)
    # Applied to negative evidence score to compute adjustment
    NEGATIVE_ADJUSTMENT_FACTOR = 0.5

    def __init__(self, evaluation_time: datetime):
        """
        Initialize the threshold evaluator.

        Args:
            evaluation_time: Timestamp for this evaluation (for audit)
        """
        self._evaluation_time = evaluation_time

    def evaluate_threshold(
        self,
        cluster: SpatialCluster,
        gate_result: StructuralGateResult,
        negative_weighted_score: float = 0.0,
    ) -> Optional[ThresholdResult]:
        """
        Evaluate belief threshold for a cluster.

        INV-H1: This evaluation only occurs if gates passed.
        INV-B1: Evaluation is deterministic.
        INV-E3: Negative evidence raises threshold but never blocks (Sprint-4D).

        Sprint-4D Extension:
        If negative evidence exists, the threshold is raised by a capped
        amount. This makes creation harder but not impossible.

        Args:
            cluster: Spatial cluster to evaluate
            gate_result: Result of structural gate evaluation
            negative_weighted_score: Weighted score of negative evidence (Sprint-4D)

        Returns:
            ThresholdResult if gates passed, None if gates failed
        """
        # Threshold evaluation is gated by structural checks
        if not gate_result.all_gates_passed:
            return None

        # Compute adjusted threshold (Sprint-4D)
        threshold = self._compute_adjusted_threshold(negative_weighted_score)

        weighted_score = cluster.weighted_evidence_score
        threshold_crossed = weighted_score >= threshold

        if threshold_crossed:
            reason = (
                f"Threshold crossed: weighted score {weighted_score:.2f} "
                f">= {threshold:.2f}"
            )
            if negative_weighted_score > 0:
                reason += (
                    f" (threshold raised by {threshold - self.BASE_CREATION_THRESHOLD:.2f} "
                    f"due to negative evidence)"
                )
        else:
            reason = (
                f"Threshold not crossed: weighted score {weighted_score:.2f} "
                f"< {threshold:.2f}"
            )
            if negative_weighted_score > 0:
                reason += (
                    f" (threshold raised by {threshold - self.BASE_CREATION_THRESHOLD:.2f} "
                    f"due to negative evidence)"
                )

        return ThresholdResult(
            threshold_crossed=threshold_crossed,
            weighted_score=weighted_score,
            required_threshold=threshold,
            reason=reason,
            evaluation_time=self._evaluation_time,
        )

    def _compute_adjusted_threshold(self, negative_weighted_score: float) -> float:
        """
        Compute threshold adjusted for negative evidence.

        Sprint-4D: Negative evidence raises the threshold, making
        creation harder but not impossible.

        INV-E3: This adjustment is capped. No amount of negative
        evidence can raise threshold infinitely.

        Args:
            negative_weighted_score: Weighted score of negative evidence

        Returns:
            Adjusted threshold (always >= BASE_CREATION_THRESHOLD)
        """
        if negative_weighted_score <= 0:
            return self.BASE_CREATION_THRESHOLD

        # Compute adjustment (capped)
        adjustment = min(
            negative_weighted_score * self.NEGATIVE_ADJUSTMENT_FACTOR,
            self.MAX_NEGATIVE_ADJUSTMENT,
        )

        return self.BASE_CREATION_THRESHOLD + adjustment


# =============================================================================
# Stop Creator
# =============================================================================


class StopCreator:
    """
    Creates canonical Stops via StopWriteGateway.

    This class is the final step in the creation pipeline:
    1. Structural gates evaluated (by StructuralGateEvaluator)
    2. Threshold evaluated (by ThresholdEvaluator)
    3. Stop created (by StopCreator, via gateway)

    All writes go through StopWriteGateway (INV-I2).

    INVARIANTS ENFORCED:
    - INV-I2: Canonical write protection
    - INV-B1: Deterministic creation
    """

    # Initial confidence for newly created Stops (Rules v0)
    # Starts low because creation is just the beginning of belief
    INITIAL_STRUCTURAL_CONFIDENCE = 0.3
    INITIAL_FRESHNESS_CONFIDENCE = 0.5

    def __init__(self, write_gateway: StopWriteGateway):
        """
        Initialize the Stop creator.

        Args:
            write_gateway: Gateway for canonical writes (INV-I2)
        """
        self._write_gateway = write_gateway

    def evaluate_and_decide(
        self,
        cluster: SpatialCluster,
        evaluation_time: datetime,
        negative_weighted_score: float = 0.0,
    ) -> CreationDecision:
        """
        Evaluate a cluster and decide whether to create a Stop.

        This method runs the full evaluation pipeline:
        1. Evaluate structural gates
        2. If gates pass, evaluate threshold (with negative evidence adjustment)
        3. Return decision

        Sprint-4D Extension:
        Negative evidence may raise the threshold but never blocks creation.

        No Stop is created by this method - it only returns the decision.
        Use create_stop() to actually create the Stop.

        Args:
            cluster: Spatial cluster to evaluate
            evaluation_time: Timestamp for this evaluation
            negative_weighted_score: Weighted score of negative evidence (Sprint-4D)

        Returns:
            CreationDecision with complete evaluation results
        """
        # Step 1: Evaluate structural gates
        gate_evaluator = StructuralGateEvaluator(evaluation_time)
        structural_result = gate_evaluator.evaluate_all_gates(cluster)

        # Step 2: Evaluate threshold (only if gates passed)
        # Sprint-4D: Pass negative evidence score for threshold adjustment
        threshold_evaluator = ThresholdEvaluator(evaluation_time)
        threshold_result = threshold_evaluator.evaluate_threshold(
            cluster, structural_result, negative_weighted_score
        )

        # Step 3: Determine creation decision
        if not structural_result.all_gates_passed:
            should_create = False
            reason = (
                f"Cannot create Stop: {len(structural_result.failed_gates)} "
                f"structural gate(s) failed"
            )
        elif threshold_result is None:
            # Should not happen if gate evaluation worked correctly
            should_create = False
            reason = "Cannot create Stop: threshold evaluation failed unexpectedly"
        elif not threshold_result.threshold_crossed:
            should_create = False
            reason = (
                f"Cannot create Stop: threshold not crossed ({threshold_result.reason})"
            )
        else:
            should_create = True
            reason = "Stop creation approved: all gates passed and threshold crossed"

        return CreationDecision(
            should_create=should_create,
            structural_result=structural_result,
            threshold_result=threshold_result,
            cluster=cluster,
            reason=reason,
        )

    def create_stop(
        self,
        decision: CreationDecision,
        name: str = "",
    ) -> Optional[Stop]:
        """
        Create a canonical Stop based on a creation decision.

        INV-I2: All writes go through StopWriteGateway.

        This method ONLY creates a Stop if the decision says to.
        If decision.should_create is False, returns None.

        Args:
            decision: The creation decision from evaluate_and_decide()
            name: Optional name for the Stop (derived from evidence)

        Returns:
            Created Stop if decision was positive, None otherwise
        """
        if not decision.should_create:
            return None

        cluster = decision.cluster

        # Create the Stop entity
        stop = Stop(
            name=name
            or f"Stop at {cluster.centroid_lat:.5f}, {cluster.centroid_lon:.5f}",
            location=Point(cluster.centroid_lon, cluster.centroid_lat, srid=4326),
            structural_confidence=self.INITIAL_STRUCTURAL_CONFIDENCE,
            freshness_confidence=self.INITIAL_FRESHNESS_CONFIDENCE,
            belief_state=Stop.BeliefState.PROPOSED,  # Sprint-4D: Initial belief state
            properties={
                "creation_reason": decision.reason,
                "cluster_id": cluster.cluster_id,
                "cluster_radius_meters": cluster.cluster_radius_meters,
                "evidence_count": cluster.evidence_count,
                "contributor_count": cluster.independent_contributor_count,
            },
        )

        # Write via gateway (INV-I2)
        evidence_refs = list(cluster.evidence_ids)
        saved_stop = self._write_gateway.write_stop(stop, evidence_refs)

        return saved_stop


# =============================================================================
# Integrated Creation Pipeline
# =============================================================================


class StopCreationPipeline:
    """
    Integrated pipeline for Stop creation from aggregation results.

    This class orchestrates the full creation flow:
    1. Take aggregation results
    2. Evaluate each cluster
    3. Create Stops for qualifying clusters
    4. Return creation results

    Sprint-4D Extension:
    - Analyze negative evidence for each cluster
    - Adjust threshold based on negative evidence
    - Negative evidence never blocks creation (INV-E3)

    This is the primary entry point for Stop creation logic.

    INVARIANTS ENFORCED:
    - INV-B1: Deterministic evaluation
    - INV-B2: Replay equivalence
    - INV-C1: No single-event creation
    - INV-C2: Independence requirement
    - INV-C3: Spatial convergence
    - INV-H1: Sub-threshold belief not public
    - INV-I2: Canonical write protection
    - INV-E3: Negative evidence modulates thresholds only (Sprint-4D)
    """

    def __init__(self, context: EvaluationContext, write_gateway: StopWriteGateway):
        """
        Initialize the creation pipeline.

        Args:
            context: Evaluation context (immutable)
            write_gateway: Gateway for canonical writes
        """
        self._context = context
        self._write_gateway = write_gateway
        self._stop_creator = StopCreator(write_gateway)

    def process_aggregation_result(
        self,
        aggregation_result: AggregationResult,
        negative_contributions: Optional[List[ContributionEvent]] = None,
    ) -> List[CreationDecision]:
        """
        Process aggregation results and decide on Stop creation.

        This method:
        1. Evaluates each cluster from the aggregation
        2. Analyzes negative evidence for each cluster (Sprint-4D)
        3. Returns creation decisions for all clusters

        Does NOT create Stops - use create_stops() for that.

        INV-B1: Processing is deterministic.
        INV-E3: Negative evidence adjusts threshold, never blocks (Sprint-4D).

        Args:
            aggregation_result: Result from StopEvidenceAggregator
            negative_contributions: List of negative evidence (Sprint-4D)

        Returns:
            List of CreationDecision for each cluster
        """
        # Import here to avoid circular imports
        from .stop_negative_evidence import NegativeEvidenceAnalyzer

        decisions = []
        negative_contributions = negative_contributions or []

        # Initialize negative evidence analyzer if needed
        analyzer = None
        if negative_contributions:
            analyzer = NegativeEvidenceAnalyzer()

        for cluster in aggregation_result.clusters:
            # Analyze negative evidence for this cluster (Sprint-4D)
            negative_weighted_score = 0.0
            if analyzer:
                neg_result = analyzer.analyze_negative_evidence(
                    cluster,
                    negative_contributions,
                    self._context.evaluation_time,
                )
                negative_weighted_score = neg_result.negative_weighted_score

            # Evaluate and decide (with negative evidence adjustment)
            decision = self._stop_creator.evaluate_and_decide(
                cluster,
                self._context.evaluation_time,
                negative_weighted_score,
            )
            decisions.append(decision)

        return decisions

    def create_stops(
        self,
        aggregation_result: AggregationResult,
        negative_contributions: Optional[List[ContributionEvent]] = None,
        derive_names: bool = False,
    ) -> Tuple[List[Stop], List[CreationDecision]]:
        """
        Process aggregation results and create qualifying Stops.

        This is the main entry point for Stop creation.

        INV-I2: All writes go through StopWriteGateway.
        INV-E3: Negative evidence adjusts threshold, never blocks (Sprint-4D).

        Args:
            aggregation_result: Result from StopEvidenceAggregator
            negative_contributions: List of negative evidence (Sprint-4D)
            derive_names: Whether to derive names from evidence (placeholder)

        Returns:
            Tuple of (created_stops, all_decisions)
        """
        decisions = self.process_aggregation_result(
            aggregation_result, negative_contributions
        )
        created_stops = []

        for decision in decisions:
            if decision.should_create:
                # For now, use a generic name. Name derivation is a future enhancement.
                stop = self._stop_creator.create_stop(decision)
                if stop is not None:
                    created_stops.append(stop)

        return created_stops, decisions
