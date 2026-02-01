"""
Route evaluator scaffolding and canonical evaluation.

Sprint-11: Evaluation Generalization (Routes v0)

This module provides:
- RouteEvaluator: Deterministic evaluation entrypoint for Route entities
- Route canonical truth derivation (binary: Canonical / Not Canonical)

ARCHITECTURE:
Routes are COMPOSITE, DERIVATIVE ENTITIES. Their canonical status
depends on:
1. Route-specific evidence meeting thresholds
2. ALL referenced Stops being Canonical

This module mirrors the Stop evaluator structure for consistency.

WHAT THIS MODULE PROVIDES:
- Deterministic evidence processing for Route-related contributions
- Canonical truth derivation based on evidence and Stop dependencies
- Integration with route aggregation pipeline
- Replay-safe evaluation

WHAT THIS MODULE DOES NOT PROVIDE:
- Route belief states (explicitly forbidden in v0)
- Confidence decay logic
- Route creation/mutation APIs
- Any database writes during evaluation

INVARIANTS ENFORCED:
- INV-B1: Deterministic evaluation
- INV-B2: Replay equivalence
- R-TRUTH-1: Binary canonical state only
- R-TRUTH-2: Evidence-derived truth only
- R-TRUTH-3: All referenced Stops must be Canonical
- R-TRUTH-4: Route evaluation never modifies Stop state

SPRINT-11 FORBIDDEN BEHAVIORS:
- Introducing belief states for Routes
- Writing to database during evaluation
- Modifying Stop evaluation logic
- Reading UI mode or visibility flags
- Adding confidence scoring or decay
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple
from uuid import UUID

from core.models import ContributionEvent
from transit.models import Route, Stop

from .base import BaseEvaluator, EvaluationContext, EvaluationResult
from .route_aggregation import (
    RouteAggregationResult,
    RouteEvidenceAggregator,
    RouteEvidenceCluster,
)


# =============================================================================
# Route Evaluation Results (Immutable)
# =============================================================================


@dataclass(frozen=True)
class RouteCanonicalDecision:
    """
    Immutable decision about a Route's canonical status.

    CRITICAL: Route canonical truth is BINARY (R-TRUTH-1):
    - Canonical
    - Not Canonical

    There are NO intermediate states, NO confidence values,
    NO partial canonical states.

    This decision encapsulates:
    - Whether the route meets evidence thresholds
    - Whether all referenced stops are canonical
    - The final binary canonical determination
    """

    route_identity: str  # The route identity key from aggregation
    is_canonical: bool  # Binary truth: Canonical or Not Canonical
    evidence_threshold_met: bool  # Did route evidence meet threshold?
    all_stops_canonical: bool  # Are all referenced stops canonical?
    referenced_stop_count: int  # Number of stops referenced
    canonical_stop_count: int  # Number of referenced stops that are canonical
    non_canonical_stop_ids: FrozenSet[UUID]  # IDs of non-canonical stops
    reason: str  # Human-readable explanation of decision
    evidence_cluster: RouteEvidenceCluster  # The evidence this decision is based on

    def __post_init__(self):
        """Validate decision consistency."""
        # R-TRUTH-3: If any stop is not canonical, route cannot be canonical
        if self.is_canonical and not self.all_stops_canonical:
            raise ValueError(
                "INVARIANT VIOLATION: Route cannot be canonical if not all "
                "referenced stops are canonical (R-TRUTH-3)"
            )
        # Route can only be canonical if evidence threshold is met AND all stops are canonical
        if self.is_canonical and not self.evidence_threshold_met:
            raise ValueError(
                "INVARIANT VIOLATION: Route cannot be canonical if evidence "
                "threshold is not met"
            )


@dataclass(frozen=True)
class RouteEvaluationResult:
    """
    Immutable result of route evaluation.

    Contains all canonical decisions made during evaluation,
    along with metadata about the evaluation process.

    This result performs NO database writes. It is pure computation.
    """

    decisions: Tuple[RouteCanonicalDecision, ...]
    total_evidence_processed: int
    total_routes_evaluated: int
    canonical_route_count: int
    non_canonical_route_count: int
    evaluation_time: datetime
    ruleset_version: str

    @property
    def canonical_decisions(self) -> Tuple[RouteCanonicalDecision, ...]:
        """Return only decisions where route is canonical."""
        return tuple(d for d in self.decisions if d.is_canonical)

    @property
    def non_canonical_decisions(self) -> Tuple[RouteCanonicalDecision, ...]:
        """Return only decisions where route is not canonical."""
        return tuple(d for d in self.decisions if not d.is_canonical)


# =============================================================================
# Route Evaluator
# =============================================================================


class RouteEvaluator(BaseEvaluator):
    """
    Deterministic evaluator for Route entities.

    This class provides evaluation for Route entities based on:
    1. Route-specific evidence (route_exists, route_traversal)
    2. Canonical status of referenced Stops

    CANONICAL TRUTH MODEL (R-TRUTH-1):
    Route canonical truth is STRICTLY BINARY:
    - Canonical: Evidence threshold met AND all referenced Stops are Canonical
    - Not Canonical: Otherwise

    COMPOSITE ENTITY RULES:
    Routes are derivative entities. They depend on Stops.
    - Route evaluation MAY read Stop canonical state
    - Route evaluation MUST NOT modify Stop state
    - Dependency is strictly one-way (R-TRUTH-4)

    CONTRIBUTION TYPES HANDLED:
    - route_exists: Route existence confirmation
    - route_traversal: GPS trace indicating route path

    INVARIANTS:
    - INV-B1: Output is deterministic for identical input
    - INV-B2: Incremental and batch evaluation converge
    - R-TRUTH-1: Binary canonical state only
    - R-TRUTH-2: Evidence-derived truth only
    - R-TRUTH-3: Canonical dependency on Stops
    - R-TRUTH-4: No Stop mutation allowed

    EXPLICITLY FORBIDDEN:
    - Belief states for Routes
    - Database writes during evaluation
    - UI mode or visibility concerns
    - Confidence scoring or decay
    """

    # Contribution types relevant to Route evaluation
    ROUTE_CONTRIBUTION_TYPES = (
        ContributionEvent.ContributionType.ROUTE_EXISTS,
        ContributionEvent.ContributionType.ROUTE_TRAVERSAL,
    )

    # Evidence thresholds for route canonical status (conservative for v0)
    MIN_INDEPENDENT_CONTRIBUTORS = 2
    MIN_DISTINCT_DAYS = 2
    MIN_EVIDENCE_COUNT = 3
    
    # Stop canonical threshold (for dependency checks)
    STOP_CANONICAL_CONFIDENCE_THRESHOLD = 0.5  # Decimal("0.5") minimum for Stop canonical status

    def __init__(self, context: EvaluationContext):
        """
        Initialize the Route evaluator.

        Args:
            context: Immutable evaluation context
        """
        super().__init__(context)
        self._aggregator = RouteEvidenceAggregator()

    @property
    def aggregator(self) -> RouteEvidenceAggregator:
        """Get the evidence aggregator for this evaluator."""
        return self._aggregator

    def filter_route_evidence(
        self, evidence: Sequence[ContributionEvent]
    ) -> List[ContributionEvent]:
        """
        Filter evidence to only Route-related contribution types.

        This method filters the evidence stream to include only
        contribution types relevant to Route evaluation.

        Args:
            evidence: Full evidence sequence

        Returns:
            List of Route-related ContributionEvents
        """
        return [
            e for e in evidence if e.contribution_type in self.ROUTE_CONTRIBUTION_TYPES
        ]

    def evaluate(self, evidence: Sequence[ContributionEvent]) -> EvaluationResult:
        """
        Process evidence and return base evaluation result.

        This is the main deterministic entrypoint for Route evaluation.
        It mirrors the Stop evaluator's evaluate() method for consistency.

        Args:
            evidence: Collection of ContributionEvent records

        Returns:
            EvaluationResult with processed evidence tracking
        """
        # Capture original IDs for immutability validation (INV-A2)
        original_ids = self.get_evidence_ids(evidence)

        # Filter to Route-related evidence
        route_evidence = self.filter_route_evidence(evidence)

        # Sort deterministically (INV-B1)
        sorted_evidence = self.sort_evidence_deterministically(route_evidence)

        # Process each evidence event (tracking only)
        for event in sorted_evidence:
            self._result.add_processed_evidence(event.id)

        # Validate evidence immutability (INV-A2)
        if not self._validate_evidence_not_mutated(evidence, original_ids):
            self._result.add_error(
                "Evidence was mutated during evaluation - INV-A2 violation"
            )

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

        For Routes, incremental and full evaluation use the same core
        processing path to ensure convergence (INV-B2).

        Args:
            new_evidence: Newly arrived ContributionEvent records

        Returns:
            EvaluationResult with processed evidence tracking
        """
        # Use the same core path as full evaluation
        # This ensures INV-B2 (incremental == batch)
        return self.evaluate(new_evidence)

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

        For Routes, incremental and full evaluation use the same core
        processing path to ensure convergence (INV-B2).

        Args:
            all_evidence: Complete history of ContributionEvent records

        Returns:
            EvaluationResult with processed evidence tracking
        """
        # Use the same core path as incremental evaluation
        # This ensures INV-B2 (incremental == batch)
        return self.evaluate(all_evidence)

    def evaluate_routes(
        self,
        evidence: Sequence[ContributionEvent],
        stop_canonical_status: Optional[Dict[UUID, bool]] = None,
    ) -> RouteEvaluationResult:
        """
        Evaluate route evidence and determine canonical status.

        This is the main route evaluation pipeline that:
        1. Filters to route-related evidence
        2. Aggregates evidence into clusters by route identity
        3. Checks evidence thresholds for each cluster
        4. Checks Stop canonical dependencies (R-TRUTH-3)
        5. Produces binary canonical decisions

        CRITICAL INVARIANTS:
        - R-TRUTH-1: Canonical status is binary
        - R-TRUTH-3: Non-canonical Stop blocks Route canonical status
        - R-TRUTH-4: Stop state is never modified

        Args:
            evidence: Collection of ContributionEvent records
            stop_canonical_status: Optional dict mapping Stop UUIDs to canonical status.
                If not provided, will query the database for Stop canonical status.

        Returns:
            RouteEvaluationResult with all canonical decisions
        """
        # First, run the base evaluation (tracking, sorting)
        self.evaluate(evidence)

        # Filter to route evidence for aggregation
        route_evidence = self.filter_route_evidence(evidence)

        if not route_evidence:
            return RouteEvaluationResult(
                decisions=(),
                total_evidence_processed=0,
                total_routes_evaluated=0,
                canonical_route_count=0,
                non_canonical_route_count=0,
                evaluation_time=self.context.evaluation_time,
                ruleset_version=self.context.ruleset_version,
            )

        # Aggregate evidence into clusters by route identity
        aggregation_result = self._aggregator.aggregate(
            route_evidence,
            self.context.evaluation_time,
        )

        # Get Stop canonical status (read-only, R-TRUTH-4)
        if stop_canonical_status is None:
            stop_canonical_status = self._get_stop_canonical_status(
                aggregation_result
            )

        # Evaluate each cluster and produce decisions
        decisions = []
        for cluster in aggregation_result.clusters:
            decision = self._evaluate_cluster(cluster, stop_canonical_status)
            decisions.append(decision)

        # Sort decisions deterministically for replay safety
        sorted_decisions = tuple(
            sorted(decisions, key=lambda d: d.route_identity)
        )

        canonical_count = sum(1 for d in sorted_decisions if d.is_canonical)
        non_canonical_count = len(sorted_decisions) - canonical_count

        return RouteEvaluationResult(
            decisions=sorted_decisions,
            total_evidence_processed=len(route_evidence),
            total_routes_evaluated=len(sorted_decisions),
            canonical_route_count=canonical_count,
            non_canonical_route_count=non_canonical_count,
            evaluation_time=self.context.evaluation_time,
            ruleset_version=self.context.ruleset_version,
        )

    def _get_stop_canonical_status(
        self,
        aggregation_result: RouteAggregationResult,
    ) -> Dict[UUID, bool]:
        """
        Get canonical status for all Stops referenced by route evidence.

        R-TRUTH-4: This is a READ-ONLY operation. Stop state is never modified.

        A Stop is considered canonical if:
        - It exists in the database
        - Its structural_confidence is above threshold (>= 0.5 for v0)
        - It is currently valid (valid_until is NULL)

        Args:
            aggregation_result: The aggregation result containing stop references

        Returns:
            Dict mapping Stop UUIDs to canonical status (True = Canonical)
        """
        # Collect all referenced stop IDs
        all_stop_ids: Set[UUID] = set()
        for cluster in aggregation_result.clusters:
            all_stop_ids.update(cluster.referenced_stop_ids)

        if not all_stop_ids:
            return {}

        # Query Stop canonical status (READ-ONLY)
        # A Stop is canonical if it exists, is currently valid, and has sufficient confidence
        canonical_stops = Stop.objects.filter(
            id__in=all_stop_ids,
            valid_until__isnull=True,  # Currently valid
            structural_confidence__gte=self.STOP_CANONICAL_CONFIDENCE_THRESHOLD,
        ).values_list("id", flat=True)

        canonical_stop_set = set(canonical_stops)

        # Build status dict - stops in set are canonical, others are not
        return {
            stop_id: stop_id in canonical_stop_set
            for stop_id in all_stop_ids
        }

    def _evaluate_cluster(
        self,
        cluster: RouteEvidenceCluster,
        stop_canonical_status: Dict[UUID, bool],
    ) -> RouteCanonicalDecision:
        """
        Evaluate a single route evidence cluster.

        This method determines the binary canonical status of a route
        based on:
        1. Evidence threshold checks
        2. Stop canonical dependency checks (R-TRUTH-3)

        Args:
            cluster: The route evidence cluster to evaluate
            stop_canonical_status: Dict mapping Stop UUIDs to canonical status

        Returns:
            RouteCanonicalDecision with binary canonical determination
        """
        # Check evidence thresholds
        evidence_threshold_met = self._check_evidence_threshold(cluster)

        # Check Stop canonical dependencies (R-TRUTH-3)
        stop_check = self._check_stop_dependencies(cluster, stop_canonical_status)

        # Determine canonical status (R-TRUTH-1: Binary)
        is_canonical = evidence_threshold_met and stop_check["all_canonical"]

        # Build human-readable reason
        reason = self._build_decision_reason(
            evidence_threshold_met,
            stop_check,
            cluster,
        )

        return RouteCanonicalDecision(
            route_identity=cluster.cluster_id,
            is_canonical=is_canonical,
            evidence_threshold_met=evidence_threshold_met,
            all_stops_canonical=stop_check["all_canonical"],
            referenced_stop_count=stop_check["total_count"],
            canonical_stop_count=stop_check["canonical_count"],
            non_canonical_stop_ids=frozenset(stop_check["non_canonical_ids"]),
            reason=reason,
            evidence_cluster=cluster,
        )

    def _check_evidence_threshold(
        self,
        cluster: RouteEvidenceCluster,
    ) -> bool:
        """
        Check if route evidence meets canonical threshold.

        Conservative thresholds for v0:
        - At least MIN_INDEPENDENT_CONTRIBUTORS independent contributors
        - Evidence on at least MIN_DISTINCT_DAYS different days
        - At least MIN_EVIDENCE_COUNT total evidence items

        Args:
            cluster: The route evidence cluster to check

        Returns:
            True if evidence threshold is met, False otherwise
        """
        # Check independent contributor count
        if cluster.independent_contributor_count < self.MIN_INDEPENDENT_CONTRIBUTORS:
            return False

        # Check temporal spread
        if cluster.temporal_span.distinct_days < self.MIN_DISTINCT_DAYS:
            return False

        # Check total evidence count
        if cluster.evidence_count < self.MIN_EVIDENCE_COUNT:
            return False

        return True

    def _check_stop_dependencies(
        self,
        cluster: RouteEvidenceCluster,
        stop_canonical_status: Dict[UUID, bool],
    ) -> Dict:
        """
        Check canonical status of all Stops referenced by the route.

        R-TRUTH-3: If ANY referenced Stop is not canonical, the Route
        MUST NOT be canonical.

        Args:
            cluster: The route evidence cluster
            stop_canonical_status: Dict mapping Stop UUIDs to canonical status

        Returns:
            Dict with:
            - all_canonical: True if all referenced stops are canonical
            - total_count: Total referenced stops
            - canonical_count: Count of canonical stops
            - non_canonical_ids: Set of non-canonical stop IDs
        """
        referenced_stops = cluster.referenced_stop_ids
        total_count = len(referenced_stops)

        if total_count == 0:
            # No stops referenced - Route can be canonical based on evidence alone
            # This handles pure route existence claims without stop associations
            return {
                "all_canonical": True,
                "total_count": 0,
                "canonical_count": 0,
                "non_canonical_ids": set(),
            }

        non_canonical_ids: Set[UUID] = set()
        canonical_count = 0

        for stop_id in referenced_stops:
            is_canonical = stop_canonical_status.get(stop_id, False)
            if is_canonical:
                canonical_count += 1
            else:
                non_canonical_ids.add(stop_id)

        return {
            "all_canonical": len(non_canonical_ids) == 0,
            "total_count": total_count,
            "canonical_count": canonical_count,
            "non_canonical_ids": non_canonical_ids,
        }

    def _build_decision_reason(
        self,
        evidence_threshold_met: bool,
        stop_check: Dict,
        cluster: RouteEvidenceCluster,
    ) -> str:
        """
        Build a human-readable reason for the canonical decision.

        Args:
            evidence_threshold_met: Whether evidence threshold was met
            stop_check: Result from _check_stop_dependencies
            cluster: The route evidence cluster

        Returns:
            Human-readable explanation string
        """
        reasons = []

        if not evidence_threshold_met:
            issues = []
            if cluster.independent_contributor_count < self.MIN_INDEPENDENT_CONTRIBUTORS:
                issues.append(
                    f"insufficient independent contributors "
                    f"({cluster.independent_contributor_count} < {self.MIN_INDEPENDENT_CONTRIBUTORS})"
                )
            if cluster.temporal_span.distinct_days < self.MIN_DISTINCT_DAYS:
                issues.append(
                    f"insufficient temporal spread "
                    f"({cluster.temporal_span.distinct_days} days < {self.MIN_DISTINCT_DAYS})"
                )
            if cluster.evidence_count < self.MIN_EVIDENCE_COUNT:
                issues.append(
                    f"insufficient evidence count "
                    f"({cluster.evidence_count} < {self.MIN_EVIDENCE_COUNT})"
                )
            reasons.append(f"Evidence threshold not met: {'; '.join(issues)}")

        if not stop_check["all_canonical"]:
            non_canonical_count = len(stop_check["non_canonical_ids"])
            reasons.append(
                f"Not all referenced Stops are canonical: "
                f"{non_canonical_count} of {stop_check['total_count']} Stops are not canonical "
                f"(R-TRUTH-3 violation)"
            )

        if not reasons:
            return "Route is canonical: evidence threshold met and all referenced Stops are canonical"

        return " | ".join(reasons)

    def get_route_evidence_queryset(self):
        """
        Get a queryset for Route-related evidence, properly ordered.

        This method provides a reusable queryset that:
        - Filters to Route-related contribution types
        - Orders deterministically using explicit sort keys

        Returns:
            QuerySet of ContributionEvents for Route evaluation
        """
        return ContributionEvent.objects.filter(
            contribution_type__in=self.ROUTE_CONTRIBUTION_TYPES
        ).order_by(*self.EVIDENCE_SORT_KEYS)


# =============================================================================
# Convenience Functions
# =============================================================================


def evaluate_route_canonical_status(
    evidence: Sequence[ContributionEvent],
    context: EvaluationContext,
    stop_canonical_status: Optional[Dict[UUID, bool]] = None,
) -> RouteEvaluationResult:
    """
    Convenience function to evaluate route canonical status.

    This is a stateless function that creates an evaluator and runs evaluation.
    It performs NO database writes - it is pure computation.

    Args:
        evidence: Collection of ContributionEvent records
        context: Immutable evaluation context
        stop_canonical_status: Optional pre-fetched Stop canonical status

    Returns:
        RouteEvaluationResult with all canonical decisions
    """
    evaluator = RouteEvaluator(context)
    return evaluator.evaluate_routes(evidence, stop_canonical_status)


def check_route_stop_dependency(
    route_stop_ids: FrozenSet[UUID],
    stop_canonical_status: Dict[UUID, bool],
) -> bool:
    """
    Check if all stops referenced by a route are canonical.

    This is a pure function for checking R-TRUTH-3 compliance.
    It performs NO database access - status must be pre-fetched.

    Args:
        route_stop_ids: Set of Stop UUIDs referenced by the route
        stop_canonical_status: Dict mapping Stop UUIDs to canonical status

    Returns:
        True if all referenced stops are canonical, False otherwise
    """
    if not route_stop_ids:
        return True

    for stop_id in route_stop_ids:
        if not stop_canonical_status.get(stop_id, False):
            return False

    return True
