"""
Route evidence aggregation module.

Sprint-11: Evaluation Generalization (Routes v0)

This module provides pure aggregation of Route-related evidence into
structured summaries. It performs transformation only - no decisions.

ARCHITECTURE:
Routes are COMPOSITE ENTITIES - they derive their canonical status from
both their own evidence AND the canonical status of referenced Stops.

WHAT THIS MODULE PROVIDES:
- Immutable aggregate data structures for Route evidence
- Stop reference tracking
- Deterministic aggregation functions

WHAT THIS MODULE DOES NOT PROVIDE (Sprint-11):
- Route creation logic
- Belief states for Routes (explicitly forbidden)
- Confidence decay models
- Any semantic decisions about truth

INVARIANTS ENFORCED:
- INV-B1: Deterministic aggregation
- INV-B2: Replay safety
- R-TRUTH-4: Routes may read Stop state but MUST NOT modify it

This is a PURE TRANSFORMATION module:
    Evidence -> Aggregates

No side effects. No canonical writes. No decisions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple
from uuid import UUID

from core.models import ContributionEvent


# =============================================================================
# Immutable Aggregate Data Structures
# =============================================================================


@dataclass(frozen=True)
class RouteEvidenceWeight:
    """
    Immutable container for route evidence weight breakdown.

    This structure captures how a single piece of route evidence is weighted
    without making any decisions about its sufficiency.

    All weights are in range [0.0, 1.0] where:
    - 1.0 = full weight
    - 0.0 = minimal weight (but still non-zero contribution)

    Mirrors EvidenceWeight from stop_aggregation.py for structural consistency.
    """

    evidence_id: UUID
    user_dampening: float  # Same-user repetition dampening
    temporal_weight: float  # Temporal spread weight
    combined_weight: float  # Product of all weights

    def __post_init__(self):
        """Validate weight ranges."""
        for attr in ("user_dampening", "temporal_weight"):
            value = getattr(self, attr)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{attr} must be in range [0.0, 1.0], got {value}")
        if self.combined_weight < 0.0:
            raise ValueError("combined_weight cannot be negative")


@dataclass(frozen=True)
class RouteEvidenceTypeBreakdown:
    """
    Immutable breakdown of evidence by contribution type for Routes.

    Tracks weighted counts per evidence type for route evidence.
    """

    route_exists_count: float = 0.0
    route_traversal_count: float = 0.0

    @property
    def total_weighted_count(self) -> float:
        """Total weighted evidence count across all types."""
        return self.route_exists_count + self.route_traversal_count

    @property
    def evidence_type_count(self) -> int:
        """Number of distinct evidence types present."""
        count = 0
        if self.route_exists_count > 0:
            count += 1
        if self.route_traversal_count > 0:
            count += 1
        return count


@dataclass(frozen=True)
class RouteTemporalSpan:
    """
    Immutable representation of temporal spread of route evidence.

    Captures the time range over which evidence was observed.
    Mirrors TemporalSpan from stop_aggregation.py.
    """

    earliest_observation: datetime
    latest_observation: datetime
    distinct_days: int  # Number of distinct calendar days

    @property
    def duration(self) -> timedelta:
        """Duration between earliest and latest observation."""
        return self.latest_observation - self.earliest_observation

    @property
    def duration_hours(self) -> float:
        """Duration in hours."""
        return self.duration.total_seconds() / 3600.0


@dataclass(frozen=True)
class RouteEvidenceCluster:
    """
    Immutable representation of aggregated route evidence.

    This is the primary output of route aggregation - evidence collected
    for a potential route entity with computed statistics.

    It makes NO decisions about whether this evidence represents a
    canonical route. That is the evaluator's responsibility.

    This structure differs from SpatialCluster in stop_aggregation.py
    because Routes are not primarily spatial - they are identified by
    route identity (name/short_name) rather than location.
    """

    cluster_id: str
    route_name: Optional[str]  # Aggregated route name if available
    route_short_name: Optional[str]  # Aggregated short name if available
    route_type: Optional[str]  # Most common route type observed
    evidence_ids: FrozenSet[UUID]
    evidence_count: int
    independent_contributor_count: int
    weighted_evidence_score: float
    evidence_type_breakdown: RouteEvidenceTypeBreakdown
    temporal_span: RouteTemporalSpan
    referenced_stop_ids: FrozenSet[UUID]  # Stop IDs referenced by evidence
    contributor_fingerprints: FrozenSet[UUID]  # Unique contributor fingerprints

    def __post_init__(self):
        """Validate cluster data."""
        if self.evidence_count < 0:
            raise ValueError("evidence_count cannot be negative")
        if self.independent_contributor_count < 0:
            raise ValueError("independent_contributor_count cannot be negative")


@dataclass(frozen=True)
class RouteAggregationResult:
    """
    Immutable result of route evidence aggregation.

    Contains all route evidence clusters derived from evidence,
    along with metadata about the aggregation process.

    This result makes NO decisions. It is pure data.
    """

    clusters: Tuple[RouteEvidenceCluster, ...]
    total_evidence_processed: int
    aggregation_time: datetime
    metadata: Dict = field(default_factory=dict)

    @property
    def cluster_count(self) -> int:
        """Number of clusters produced."""
        return len(self.clusters)


# =============================================================================
# Weight Calculator
# =============================================================================


class RouteWeightCalculator:
    """
    Calculator for evidence weights specific to Route aggregation.

    This mirrors the structure of WeightCalculator in stop_aggregation.py
    but is tailored for route evidence which does not have GPS accuracy.

    INVARIANTS ENFORCED:
    - INV-B1: Deterministic weight calculation
    - Evidence is weighted, never gated
    """

    # Same-user dampening parameters
    SAME_USER_FIRST_WEIGHT = 1.0
    SAME_USER_DAMPENING_FACTOR = 0.5  # Each subsequent observation is halved

    # Temporal weight parameters (observations spread over time are more valuable)
    TEMPORAL_FULL_WEIGHT_HOURS = 24.0  # Full weight if 24+ hours apart

    def calculate_user_dampening(
        self,
        contributor_fingerprint: UUID,
        contributor_counts: Dict[UUID, int],
    ) -> float:
        """
        Calculate same-user dampening weight.

        Repeated observations from the same user are progressively down-weighted.

        Args:
            contributor_fingerprint: The contributor's fingerprint
            contributor_counts: Dict tracking observation count per contributor

        Returns:
            Weight in range (0.0, 1.0]
        """
        count = contributor_counts.get(contributor_fingerprint, 0)
        if count == 0:
            return self.SAME_USER_FIRST_WEIGHT
        return self.SAME_USER_FIRST_WEIGHT * (self.SAME_USER_DAMPENING_FACTOR**count)

    def calculate_temporal_weight(
        self,
        observation_time: datetime,
        evaluation_time: datetime,
    ) -> float:
        """
        Calculate temporal weight based on observation recency.

        More recent observations get higher weight.

        Args:
            observation_time: When the observation was made
            evaluation_time: The evaluation reference time

        Returns:
            Weight in range [0.1, 1.0]
        """
        if observation_time >= evaluation_time:
            return 1.0

        hours_ago = (evaluation_time - observation_time).total_seconds() / 3600.0

        # Linear decay over 30 days, minimum weight 0.1
        max_hours = 30 * 24  # 30 days
        if hours_ago >= max_hours:
            return 0.1

        return max(0.1, 1.0 - (hours_ago / max_hours) * 0.9)

    def calculate_combined_weight(
        self,
        evidence_id: UUID,
        contributor_fingerprint: UUID,
        observation_time: datetime,
        evaluation_time: datetime,
        contributor_counts: Dict[UUID, int],
    ) -> RouteEvidenceWeight:
        """
        Calculate combined weight for a single piece of route evidence.

        Args:
            evidence_id: ID of the evidence event
            contributor_fingerprint: Contributor's fingerprint
            observation_time: When the observation was made
            evaluation_time: The evaluation reference time
            contributor_counts: Dict tracking observation count per contributor

        Returns:
            RouteEvidenceWeight with all weight components
        """
        user_dampening = self.calculate_user_dampening(
            contributor_fingerprint, contributor_counts
        )
        temporal_weight = self.calculate_temporal_weight(
            observation_time, evaluation_time
        )

        combined = user_dampening * temporal_weight

        return RouteEvidenceWeight(
            evidence_id=evidence_id,
            user_dampening=user_dampening,
            temporal_weight=temporal_weight,
            combined_weight=combined,
        )


# =============================================================================
# Route Evidence Aggregator
# =============================================================================


class RouteEvidenceAggregator:
    """
    Aggregates route-related evidence into structured summaries.

    This class performs PURE TRANSFORMATION only:
    - Collects and weighs route evidence
    - Groups evidence by route identity
    - Tracks referenced stops
    - Produces immutable aggregation results

    It does NOT:
    - Make any decisions about canonical truth
    - Modify any database state
    - Reference UI mode or visibility concerns

    INVARIANTS ENFORCED:
    - INV-B1: Deterministic aggregation
    - INV-B2: Replay safety
    - R-TRUTH-4: Read-only access to Stop references
    """

    def __init__(self):
        """Initialize the route evidence aggregator."""
        self._weight_calculator = RouteWeightCalculator()

    def aggregate(
        self,
        evidence: Sequence[ContributionEvent],
        evaluation_time: datetime,
    ) -> RouteAggregationResult:
        """
        Aggregate route evidence into clusters.

        This method:
        1. Groups evidence by route identity (from subject_ref)
        2. Calculates weights for each evidence item
        3. Collects statistics per group
        4. Returns immutable aggregation result

        Args:
            evidence: Sequence of ContributionEvent records
            evaluation_time: Reference time for evaluation

        Returns:
            RouteAggregationResult containing all clusters
        """
        if not evidence:
            return RouteAggregationResult(
                clusters=(),
                total_evidence_processed=0,
                aggregation_time=evaluation_time,
            )

        # Group evidence by route identity
        groups = self._group_by_route_identity(evidence)

        # Process each group into a cluster
        clusters = []
        for group_key, group_evidence in groups.items():
            cluster = self._process_group(
                group_key, group_evidence, evaluation_time
            )
            if cluster is not None:
                clusters.append(cluster)

        # Sort clusters deterministically by cluster_id for replay safety
        sorted_clusters = tuple(sorted(clusters, key=lambda c: c.cluster_id))

        return RouteAggregationResult(
            clusters=sorted_clusters,
            total_evidence_processed=len(evidence),
            aggregation_time=evaluation_time,
        )

    def _group_by_route_identity(
        self,
        evidence: Sequence[ContributionEvent],
    ) -> Dict[str, List[ContributionEvent]]:
        """
        Group evidence by route identity extracted from subject_ref.

        Route identity is determined from the subject_ref field which
        should contain route identification information.

        Args:
            evidence: Sequence of ContributionEvent records

        Returns:
            Dict mapping route identity keys to lists of evidence
        """
        groups: Dict[str, List[ContributionEvent]] = {}

        for event in evidence:
            route_key = self._extract_route_identity(event)
            if route_key is None:
                # Evidence without valid route identity is skipped
                continue

            if route_key not in groups:
                groups[route_key] = []
            groups[route_key].append(event)

        return groups

    def _extract_route_identity(self, event: ContributionEvent) -> Optional[str]:
        """
        Extract route identity from a contribution event's subject_ref.

        The subject_ref should contain route identification such as:
        - route_name
        - route_short_name
        - route_id (reference to existing route)

        Args:
            event: The ContributionEvent to extract identity from

        Returns:
            A string key identifying the route, or None if invalid
        """
        subject_ref = event.subject_ref
        if not isinstance(subject_ref, dict):
            return None

        # Try different identity fields in order of preference
        # Priority: explicit route_id > short_name + name > name alone
        if "route_id" in subject_ref:
            return f"id:{subject_ref['route_id']}"

        short_name = subject_ref.get("route_short_name", "").strip()
        name = subject_ref.get("route_name", "").strip()

        if short_name and name:
            return f"route:{short_name}:{name}"
        elif short_name:
            return f"route:{short_name}:_"
        elif name:
            return f"route:_:{name}"

        return None

    def _process_group(
        self,
        group_key: str,
        evidence: List[ContributionEvent],
        evaluation_time: datetime,
    ) -> Optional[RouteEvidenceCluster]:
        """
        Process a group of evidence into a RouteEvidenceCluster.

        Args:
            group_key: The route identity key for this group
            evidence: List of ContributionEvent records in this group
            evaluation_time: Reference time for evaluation

        Returns:
            RouteEvidenceCluster or None if processing fails
        """
        if not evidence:
            return None

        # Sort evidence deterministically for replay safety
        sorted_evidence = sorted(
            evidence,
            key=lambda e: (e.observed_at, str(e.id)),
        )

        # Track contributor counts for dampening
        contributor_counts: Dict[UUID, int] = {}
        contributor_fingerprints: Set[UUID] = set()
        evidence_ids: Set[UUID] = set()
        referenced_stop_ids: Set[UUID] = set()

        # Evidence type counts
        route_exists_count = 0.0
        route_traversal_count = 0.0

        # Temporal tracking
        observation_times: List[datetime] = []
        observed_days: Set[str] = set()

        # Route attribute tracking
        route_names: Dict[str, float] = {}
        route_short_names: Dict[str, float] = {}
        route_types: Dict[str, float] = {}

        total_weighted_score = 0.0

        for event in sorted_evidence:
            # Calculate weight
            weight = self._weight_calculator.calculate_combined_weight(
                evidence_id=event.id,
                contributor_fingerprint=event.contributor_fingerprint,
                observation_time=event.observed_at,
                evaluation_time=evaluation_time,
                contributor_counts=contributor_counts,
            )

            # Update contributor tracking
            contributor_fingerprints.add(event.contributor_fingerprint)
            contributor_counts[event.contributor_fingerprint] = (
                contributor_counts.get(event.contributor_fingerprint, 0) + 1
            )

            # Update evidence tracking
            evidence_ids.add(event.id)
            total_weighted_score += weight.combined_weight

            # Update temporal tracking
            observation_times.append(event.observed_at)
            observed_days.add(event.observed_at.strftime("%Y-%m-%d"))

            # Update evidence type counts
            if event.contribution_type == ContributionEvent.ContributionType.ROUTE_EXISTS:
                route_exists_count += weight.combined_weight
            elif event.contribution_type == ContributionEvent.ContributionType.ROUTE_TRAVERSAL:
                route_traversal_count += weight.combined_weight

            # Extract route attributes from payload
            payload = event.payload or {}
            subject_ref = event.subject_ref or {}

            # Track route names with weights
            name = payload.get("route_name")
            if name is None:
                name = subject_ref.get("route_name")
            if name:
                route_names[name] = route_names.get(name, 0) + weight.combined_weight

            short_name = payload.get("route_short_name")
            if short_name is None:
                short_name = subject_ref.get("route_short_name")
            if short_name:
                route_short_names[short_name] = route_short_names.get(short_name, 0) + weight.combined_weight

            if route_type := payload.get("route_type"):
                route_types[route_type] = route_types.get(route_type, 0) + weight.combined_weight

            # Extract referenced stop IDs
            self._extract_stop_references(event, referenced_stop_ids)

        # Determine best route attributes (highest weighted)
        best_name = max(route_names.keys(), key=lambda k: route_names[k]) if route_names else None
        best_short_name = max(route_short_names.keys(), key=lambda k: route_short_names[k]) if route_short_names else None
        best_route_type = max(route_types.keys(), key=lambda k: route_types[k]) if route_types else None

        # Build temporal span
        temporal_span = RouteTemporalSpan(
            earliest_observation=min(observation_times),
            latest_observation=max(observation_times),
            distinct_days=len(observed_days),
        )

        # Build evidence type breakdown
        evidence_breakdown = RouteEvidenceTypeBreakdown(
            route_exists_count=route_exists_count,
            route_traversal_count=route_traversal_count,
        )

        return RouteEvidenceCluster(
            cluster_id=group_key,
            route_name=best_name,
            route_short_name=best_short_name,
            route_type=best_route_type,
            evidence_ids=frozenset(evidence_ids),
            evidence_count=len(evidence_ids),
            independent_contributor_count=len(contributor_fingerprints),
            weighted_evidence_score=total_weighted_score,
            evidence_type_breakdown=evidence_breakdown,
            temporal_span=temporal_span,
            referenced_stop_ids=frozenset(referenced_stop_ids),
            contributor_fingerprints=frozenset(contributor_fingerprints),
        )

    def _extract_stop_references(
        self,
        event: ContributionEvent,
        stop_ids: Set[UUID],
    ) -> None:
        """
        Extract Stop references from a contribution event.

        Looks in payload for referenced stop IDs from:
        - stop_ids: List of stop UUIDs
        - stops: List of stop objects with 'id' field
        - traversal_stops: List from route traversal evidence

        Args:
            event: The ContributionEvent to extract from
            stop_ids: Set to add discovered stop IDs to
        """
        payload = event.payload or {}

        # Direct stop_ids list
        if "stop_ids" in payload:
            for stop_id in payload["stop_ids"]:
                try:
                    stop_ids.add(UUID(str(stop_id)))
                except (ValueError, TypeError):
                    pass

        # Stops list with id field
        if "stops" in payload and isinstance(payload["stops"], list):
            for stop in payload["stops"]:
                if isinstance(stop, dict) and "id" in stop:
                    try:
                        stop_ids.add(UUID(str(stop["id"])))
                    except (ValueError, TypeError):
                        pass

        # Traversal stops (from GPS trace evidence)
        if "traversal_stops" in payload and isinstance(payload["traversal_stops"], list):
            for stop in payload["traversal_stops"]:
                if isinstance(stop, dict) and "stop_id" in stop:
                    try:
                        stop_ids.add(UUID(str(stop["stop_id"])))
                    except (ValueError, TypeError):
                        pass
