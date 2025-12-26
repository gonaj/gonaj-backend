"""
Negative evidence handling for Stop evaluation.

Sprint-4D: Negative Evidence & Conflict Handling (Rules v0)

This module provides:
- NegativeEvidenceResult: Immutable result of negative evidence analysis
- NegativeEvidenceAnalyzer: Conservative negative evidence interpretation
- ConfidenceAdjuster: Gradual, capped confidence reduction
- ContestedStateEvaluator: Derived Contested state detection

ARCHITECTURE:

    NEGATIVE EVIDENCE
            |
            v
    SPATIAL/TEMPORAL SCOPING
            |
            v
    CONFIDENCE REDUCTION (CAPPED)
            |
            v
    CONTESTED STATE (DERIVED)

CRITICAL PRINCIPLES (Rules v0):
- Negative evidence may WEAKEN BELIEF, never negate truth
- Negative evidence may REDUCE CONFIDENCE GRADUALLY, never abruptly
- Negative evidence may RAISE CREATION THRESHOLDS, never veto creation
- Negative evidence may DERIVE Contested state, never delete Stops
- No amount of negative evidence creates unrecoverable state

WHAT THIS MODULE PROVIDES:
- Conservative negative evidence handling
- Gradual, capped confidence reduction
- Contested state derivation (requires mixed evidence)
- Threshold adjustment for creation

WHAT THIS MODULE DOES NOT PROVIDE:
- Stop deletion logic
- Permanent blocking of creation
- Permanent removal semantics
- Regional or operator-specific logic

INVARIANTS ENFORCED:
- INV-E1: No deletion via negative evidence
- INV-E2: Negative evidence weaker than aggregated positive evidence
- INV-E3: Negative evidence modulates belief only
- INV-F1: Confidence changes are gradual
- INV-J1: Safe to be wrong
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from core.models import ContributionEvent
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D

from .stop_aggregation import EvidenceWeight, SpatialCluster

# =============================================================================
# Negative Evidence Types & Scoping
# =============================================================================


@dataclass(frozen=True)
class NegativeEvidenceScope:
    """
    Immutable representation of negative evidence spatial/temporal scope.

    Negative evidence is scoped both spatially and temporally to prevent
    over-application. This ensures negative evidence affects only
    relevant Stops within a reasonable area and time window.
    """

    location: Point
    spatial_radius_meters: float
    observation_time: datetime
    temporal_window_hours: float
    evidence_type: str  # "stop_not_exists" or "stop_inactive"

    def __post_init__(self):
        """Validate scope parameters."""
        if self.spatial_radius_meters <= 0:
            raise ValueError("spatial_radius_meters must be positive")
        if self.temporal_window_hours <= 0:
            raise ValueError("temporal_window_hours must be positive")
        if self.evidence_type not in ("stop_not_exists", "stop_inactive"):
            raise ValueError(f"Invalid evidence_type: {self.evidence_type}")

    def is_spatially_relevant(self, stop_location: Point) -> bool:
        """
        Check if this negative evidence is spatially relevant to a Stop.

        Args:
            stop_location: Location of the Stop to check

        Returns:
            True if Stop is within spatial scope
        """
        # Calculate distance in meters
        distance_meters = (
            stop_location.distance(self.location) * 111319.9
        )  # degrees to meters approximation
        return distance_meters <= self.spatial_radius_meters

    def is_temporally_relevant(self, reference_time: datetime) -> bool:
        """
        Check if this negative evidence is temporally relevant.

        Args:
            reference_time: Time to check against

        Returns:
            True if reference_time is within temporal window
        """
        time_delta = abs(
            (reference_time - self.observation_time).total_seconds() / 3600
        )
        return time_delta <= self.temporal_window_hours


@dataclass(frozen=True)
class NegativeEvidenceResult:
    """
    Immutable result of negative evidence analysis for a Stop.

    This structure captures:
    - Count and weight of negative evidence
    - Spatial/temporal scoping
    - Whether negative evidence is credible
    - Asymmetric weighting vs positive evidence

    INV-E2: Negative evidence is weaker than aggregated positive evidence.
    """

    negative_count: int
    negative_weighted_score: float
    positive_weighted_score: float
    scoped_negative_evidence: Tuple[NegativeEvidenceScope, ...]
    is_credible: bool
    analysis_time: datetime

    @property
    def has_negative_evidence(self) -> bool:
        """Check if any negative evidence exists."""
        return self.negative_count > 0

    @property
    def negative_positive_ratio(self) -> float:
        """
        Ratio of negative to positive evidence (asymmetric).

        INV-E2: This ratio should be < 1.0 when both exist,
        reflecting that negative evidence is weaker.
        """
        if self.positive_weighted_score == 0:
            return float("inf") if self.negative_weighted_score > 0 else 0.0
        return self.negative_weighted_score / self.positive_weighted_score


# =============================================================================
# Confidence Adjustment with Hard Cap
# =============================================================================


@dataclass(frozen=True)
class ConfidenceAdjustment:
    """
    Immutable result of confidence adjustment calculation.

    INV-F1: Confidence changes are gradual.
    INV-E3: Negative evidence modulates belief only.

    This structure captures:
    - Original confidence
    - Proposed adjustment
    - Capped adjustment (never drops to zero in one cycle)
    - Reason for adjustment
    """

    original_confidence: float
    proposed_reduction: float
    capped_reduction: float
    new_confidence: float
    cap_applied: bool
    reason: str

    def __post_init__(self):
        """Validate confidence values."""
        if not (0.0 <= self.original_confidence <= 1.0):
            raise ValueError("original_confidence must be in [0.0, 1.0]")
        if not (0.0 <= self.new_confidence <= 1.0):
            raise ValueError("new_confidence must be in [0.0, 1.0]")
        if self.capped_reduction < 0:
            raise ValueError("capped_reduction cannot be negative")


@dataclass(frozen=True)
class ContestedStateResult:
    """
    Immutable result of Contested state evaluation.

    A Stop may be marked Contested if and only if:
    - Existing Stop confidence is above minimal established threshold
    - Credible negative evidence is present
    - Credible positive evidence exists in recent window

    Negative evidence alone must NOT mark Contested.

    INV-E1: No deletion via negative evidence (Contested != Deleted).
    """

    should_mark_contested: bool
    has_sufficient_confidence: bool
    has_credible_negative: bool
    has_recent_positive: bool
    reason: str
    evaluation_time: datetime


# =============================================================================
# Negative Evidence Analyzer
# =============================================================================


class NegativeEvidenceAnalyzer:
    """
    Conservative negative evidence interpretation.

    This class analyzes negative evidence (stop_not_exists, stop_inactive)
    and produces scoped, weighted results that can inform confidence
    reduction and Contested state derivation.

    SPATIAL SCOPING:
    - Negative evidence affects only Stops within spatial radius
    - Default radius: 50 meters (conservative)

    TEMPORAL SCOPING:
    - Negative evidence has limited temporal relevance
    - Default window: 168 hours (7 days)

    ASYMMETRIC WEIGHTING:
    - Negative evidence is weighted lower than positive evidence
    - Single negative report cannot override multiple confirmations

    INVARIANTS:
    - INV-E2: Negative evidence weaker than positive evidence
    - INV-E3: Negative evidence modulates belief only
    """

    # Spatial scoping (Rules v0)
    DEFAULT_SPATIAL_RADIUS_METERS = 50.0

    # Temporal scoping (Rules v0)
    DEFAULT_TEMPORAL_WINDOW_HOURS = 168.0  # 7 days

    # Asymmetric weighting factor
    # Negative evidence is weighted at 50% of positive evidence
    NEGATIVE_WEIGHT_FACTOR = 0.5

    # Credibility threshold
    # Negative evidence is credible if weighted score > threshold
    CREDIBILITY_THRESHOLD = 0.3

    def __init__(
        self,
        spatial_radius_meters: Optional[float] = None,
        temporal_window_hours: Optional[float] = None,
    ):
        """
        Initialize the negative evidence analyzer.

        Args:
            spatial_radius_meters: Override default spatial scope
            temporal_window_hours: Override default temporal scope
        """
        self._spatial_radius = (
            spatial_radius_meters or self.DEFAULT_SPATIAL_RADIUS_METERS
        )
        self._temporal_window = (
            temporal_window_hours or self.DEFAULT_TEMPORAL_WINDOW_HOURS
        )

    def analyze_negative_evidence(
        self,
        cluster: SpatialCluster,
        negative_contributions: List[ContributionEvent],
        analysis_time: datetime,
    ) -> NegativeEvidenceResult:
        """
        Analyze negative evidence for a Stop cluster.

        This method:
        1. Extracts negative evidence from contributions
        2. Applies spatial/temporal scoping
        3. Computes asymmetric weighting
        4. Determines credibility

        INV-E2: Negative evidence is weaker than positive evidence.

        Args:
            cluster: Spatial cluster of positive evidence
            negative_contributions: List of negative ContributionEvents
            analysis_time: Time of analysis

        Returns:
            Immutable NegativeEvidenceResult
        """
        # Extract and scope negative evidence
        scoped_evidence = self._scope_negative_evidence(
            cluster.centroid_lat,
            cluster.centroid_lon,
            negative_contributions,
            analysis_time,
        )

        # Compute weighted scores
        negative_weighted_score = self._compute_negative_weight(scoped_evidence)
        positive_weighted_score = cluster.weighted_evidence_score

        # Determine credibility
        is_credible = negative_weighted_score >= self.CREDIBILITY_THRESHOLD

        return NegativeEvidenceResult(
            negative_count=len(scoped_evidence),
            negative_weighted_score=negative_weighted_score,
            positive_weighted_score=positive_weighted_score,
            scoped_negative_evidence=tuple(scoped_evidence),
            is_credible=is_credible,
            analysis_time=analysis_time,
        )

    def _scope_negative_evidence(
        self,
        cluster_centroid_lat: float,
        cluster_centroid_lon: float,
        negative_contributions: List[ContributionEvent],
        analysis_time: datetime,
    ) -> List[NegativeEvidenceScope]:
        """
        Apply spatial and temporal scoping to negative evidence.

        Args:
            cluster_centroid_lat: Latitude of positive evidence cluster centroid
            cluster_centroid_lon: Longitude of positive evidence cluster centroid
            negative_contributions: List of negative ContributionEvents
            analysis_time: Time of analysis

        Returns:
            List of scoped negative evidence
        """
        scoped = []
        cluster_centroid = Point(cluster_centroid_lon, cluster_centroid_lat, srid=4326)

        for contrib in negative_contributions:
            # Extract location from contribution
            location_data = contrib.payload.get("location")
            if not location_data:
                continue

            location = Point(
                location_data.get("longitude"),
                location_data.get("latitude"),
                srid=4326,
            )

            # Determine evidence type
            if (
                contrib.contribution_type
                == ContributionEvent.ContributionType.STOP_NOT_EXISTS
            ):
                evidence_type = "stop_not_exists"
            else:
                # Treat other negative types as inactive for v0
                evidence_type = "stop_inactive"

            # Create scope
            scope = NegativeEvidenceScope(
                location=location,
                spatial_radius_meters=self._spatial_radius,
                observation_time=contrib.created_at,
                temporal_window_hours=self._temporal_window,
                evidence_type=evidence_type,
            )

            # Check spatial relevance to cluster
            if scope.is_spatially_relevant(cluster_centroid):
                # Check temporal relevance
                if scope.is_temporally_relevant(analysis_time):
                    scoped.append(scope)

        return scoped

    def _compute_negative_weight(
        self,
        scoped_evidence: List[NegativeEvidenceScope],
    ) -> float:
        """
        Compute asymmetric weight for negative evidence.

        INV-E2: Negative evidence is weighted lower than positive evidence.

        Args:
            scoped_evidence: List of scoped negative evidence

        Returns:
            Weighted score (asymmetrically reduced)
        """
        if not scoped_evidence:
            return 0.0

        # Simple count-based weighting with asymmetric factor
        # In v0, each negative report contributes equally
        base_weight = len(scoped_evidence)

        # Apply asymmetric factor (negative evidence is weaker)
        return base_weight * self.NEGATIVE_WEIGHT_FACTOR


# =============================================================================
# Confidence Adjuster
# =============================================================================


class ConfidenceAdjuster:
    """
    Gradual, capped confidence reduction based on negative evidence.

    INV-F1: Confidence changes are gradual.
    INV-E1: No deletion via negative evidence.
    INV-J1: Safe to be wrong (recovery possible).

    This class applies conservative confidence reduction with hard caps
    to ensure:
    - Confidence never drops to zero in a single cycle
    - Reduction is deterministic and replay-safe
    - Future positive evidence can always recover belief
    """

    # Per-evaluation-cycle hard cap
    # Confidence cannot drop more than this in one evaluation cycle
    MAX_REDUCTION_PER_CYCLE = 0.15  # 15% absolute reduction max

    # Minimum floor (never drop below this)
    MINIMUM_CONFIDENCE_FLOOR = 0.05  # 5% minimum

    def compute_confidence_adjustment(
        self,
        current_confidence: float,
        negative_evidence_result: NegativeEvidenceResult,
    ) -> ConfidenceAdjustment:
        """
        Compute gradual, capped confidence adjustment.

        This method:
        1. Calculates proposed reduction based on negative evidence
        2. Applies per-cycle hard cap
        3. Applies minimum floor
        4. Returns adjustment result

        INV-F1: Reduction is gradual and capped.

        Args:
            current_confidence: Current confidence value [0.0, 1.0]
            negative_evidence_result: Result of negative evidence analysis

        Returns:
            Immutable ConfidenceAdjustment
        """
        if not (0.0 <= current_confidence <= 1.0):
            raise ValueError("current_confidence must be in [0.0, 1.0]")

        # If no credible negative evidence, no reduction
        if not negative_evidence_result.is_credible:
            return ConfidenceAdjustment(
                original_confidence=current_confidence,
                proposed_reduction=0.0,
                capped_reduction=0.0,
                new_confidence=current_confidence,
                cap_applied=False,
                reason="No credible negative evidence - no reduction applied",
            )

        # Compute proposed reduction based on negative/positive ratio
        # Higher ratio = more reduction (but still capped)
        ratio = negative_evidence_result.negative_positive_ratio
        proposed_reduction = min(ratio * 0.1, 0.25)  # Max 25% proposal

        # Apply per-cycle hard cap
        capped_reduction = min(proposed_reduction, self.MAX_REDUCTION_PER_CYCLE)
        cap_applied = capped_reduction < proposed_reduction

        # Compute new confidence
        new_confidence = max(
            current_confidence - capped_reduction,
            self.MINIMUM_CONFIDENCE_FLOOR,
        )

        # Ensure we didn't drop below floor
        actual_reduction = current_confidence - new_confidence

        reason = self._generate_adjustment_reason(
            proposed_reduction,
            capped_reduction,
            cap_applied,
            new_confidence,
        )

        return ConfidenceAdjustment(
            original_confidence=current_confidence,
            proposed_reduction=proposed_reduction,
            capped_reduction=actual_reduction,
            new_confidence=new_confidence,
            cap_applied=cap_applied,
            reason=reason,
        )

    def _generate_adjustment_reason(
        self,
        proposed: float,
        capped: float,
        cap_applied: bool,
        new_confidence: float,
    ) -> str:
        """Generate human-readable reason for adjustment."""
        if cap_applied:
            return (
                f"Proposed reduction of {proposed:.2%} was capped to {capped:.2%} "
                f"(max per-cycle reduction). New confidence: {new_confidence:.2%}."
            )
        else:
            return (
                f"Confidence reduced by {capped:.2%} due to negative evidence. "
                f"New confidence: {new_confidence:.2%}."
            )


# =============================================================================
# Contested State Evaluator
# =============================================================================


class ContestedStateEvaluator:
    """
    Derived Contested state evaluation.

    A Stop may be marked Contested if and only if:
    - Existing Stop confidence is above minimal established threshold
    - Credible negative evidence is present
    - Credible positive evidence exists in recent window

    Negative evidence alone must NOT mark Contested.

    INV-E1: Contested != Deleted (Stop remains recoverable).
    """

    # Minimum confidence to be eligible for Contested state
    # Below this, Stop is just weak, not contested
    MIN_ESTABLISHED_CONFIDENCE = 0.3

    # Recent positive evidence window (hours)
    RECENT_POSITIVE_WINDOW_HOURS = 168.0  # 7 days

    # Minimum recent positive weight to qualify
    MIN_RECENT_POSITIVE_WEIGHT = 0.5

    def evaluate_contested_state(
        self,
        current_confidence: float,
        negative_evidence_result: NegativeEvidenceResult,
        cluster: SpatialCluster,
        evaluation_time: datetime,
    ) -> ContestedStateResult:
        """
        Evaluate whether a Stop should be marked Contested.

        Contested state requires ALL of:
        1. Sufficient existing confidence
        2. Credible negative evidence
        3. Recent credible positive evidence

        This ensures Contested represents genuine conflict, not just
        weak positive evidence with any negative evidence.

        Args:
            current_confidence: Current Stop confidence
            negative_evidence_result: Negative evidence analysis
            cluster: Spatial cluster of positive evidence
            evaluation_time: Time of evaluation

        Returns:
            Immutable ContestedStateResult
        """
        # Check 1: Sufficient established confidence
        has_sufficient_confidence = (
            current_confidence >= self.MIN_ESTABLISHED_CONFIDENCE
        )

        # Check 2: Credible negative evidence
        has_credible_negative = negative_evidence_result.is_credible

        # Check 3: Recent credible positive evidence
        has_recent_positive = self._has_recent_positive_evidence(
            cluster,
            evaluation_time,
        )

        # All three must be true
        should_mark_contested = (
            has_sufficient_confidence and has_credible_negative and has_recent_positive
        )

        reason = self._generate_contested_reason(
            should_mark_contested,
            has_sufficient_confidence,
            has_credible_negative,
            has_recent_positive,
        )

        return ContestedStateResult(
            should_mark_contested=should_mark_contested,
            has_sufficient_confidence=has_sufficient_confidence,
            has_credible_negative=has_credible_negative,
            has_recent_positive=has_recent_positive,
            reason=reason,
            evaluation_time=evaluation_time,
        )

    def _has_recent_positive_evidence(
        self,
        cluster: SpatialCluster,
        evaluation_time: datetime,
    ) -> bool:
        """
        Check if cluster has recent positive evidence.

        Args:
            cluster: Spatial cluster to check
            evaluation_time: Time of evaluation

        Returns:
            True if recent positive evidence exists
        """
        # Check if latest observation is within window
        time_delta_hours = (
            evaluation_time - cluster.temporal_span.latest_observation
        ).total_seconds() / 3600

        if time_delta_hours > self.RECENT_POSITIVE_WINDOW_HOURS:
            return False

        # Check if weighted score is sufficient
        return cluster.weighted_evidence_score >= self.MIN_RECENT_POSITIVE_WEIGHT

    def _generate_contested_reason(
        self,
        should_mark: bool,
        has_confidence: bool,
        has_negative: bool,
        has_positive: bool,
    ) -> str:
        """Generate human-readable reason for Contested decision."""
        if should_mark:
            return (
                "Stop marked Contested: sufficient confidence, "
                "credible negative evidence, and recent positive evidence all present."
            )

        missing = []
        if not has_confidence:
            missing.append("insufficient established confidence")
        if not has_negative:
            missing.append("no credible negative evidence")
        if not has_positive:
            missing.append("no recent positive evidence")

        return f"Stop not Contested: {', '.join(missing)}."
