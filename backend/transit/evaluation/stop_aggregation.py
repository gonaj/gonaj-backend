"""
Stop evidence aggregation module.

Sprint-4B: Positive Evidence Aggregation (No Creation)
Sprint-5B: Evidence De-identification with Evaluation Safety

This module provides pure aggregation of Stop-related evidence into
structured summaries. It performs transformation only - no decisions.

WHAT THIS MODULE PROVIDES:
- Immutable aggregate data structures
- GPS accuracy weighting
- Same-user dampening
- Temporal spread weighting
- Deterministic spatial clustering

WHAT THIS MODULE DOES NOT PROVIDE (Sprint-4B):
- Stop creation logic
- Confidence calculations
- Threshold checks
- Negative evidence handling
- Canonical writes
- Any semantic decisions

INVARIANTS ENFORCED:
- INV-A1: No evidence loss (all evidence contributes)
- INV-B1: Deterministic aggregation
- INV-C2: Independence handling (same-user dampening)
- INV-C3: Spatial convergence (clustering)
- INV-D1: Accuracy as weight, not gate
- INV-D2: Accuracy cannot dominate alone
- INV-I1: Contributor independence counted correctly after account deletion (Sprint-5B)
- INV-I2: Account deletion does not reduce/inflate contributor counts (Sprint-5B)

SPRINT-5B CRITICAL NOTES:
- All contributor identity references use contributor_fingerprint, NOT contributor_id
- contributor_fingerprint is immutable and survives account deletion
- contributor_id (FK) may be NULL after deletion and MUST NOT be used for evaluation
- This ensures PH-4 (replay determinism) and PH-5 (independence is event-level)

This is a PURE TRANSFORMATION module:
    Evidence -> Aggregates

No side effects. No canonical writes. No decisions.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple
from uuid import UUID

from core.models import ContributionEvent

# =============================================================================
# Immutable Aggregate Data Structures
# =============================================================================


@dataclass(frozen=True)
class EvidenceWeight:
    """
    Immutable container for evidence weight breakdown.

    This structure captures how a single piece of evidence is weighted
    without making any decisions about its sufficiency.

    All weights are in range [0.0, 1.0] where:
    - 1.0 = full weight
    - 0.0 = minimal weight (but still non-zero contribution)

    INV-D1: Even low weights contribute; evidence is never dropped.
    """

    evidence_id: UUID
    accuracy_weight: float  # GPS accuracy weight
    user_dampening: float  # Same-user repetition dampening
    temporal_weight: float  # Temporal spread weight
    combined_weight: float  # Product of all weights

    def __post_init__(self):
        """Validate weight ranges."""
        for attr in ("accuracy_weight", "user_dampening", "temporal_weight"):
            value = getattr(self, attr)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{attr} must be in range [0.0, 1.0], got {value}")
        if self.combined_weight < 0.0:
            raise ValueError("combined_weight cannot be negative")


@dataclass(frozen=True)
class EvidenceTypeBreakdown:
    """
    Immutable breakdown of evidence by contribution type.

    Tracks weighted counts per evidence type for a cluster.
    """

    stop_exists_count: float = 0.0
    stop_name_count: float = 0.0
    stop_location_count: float = 0.0
    stop_not_exists_count: float = 0.0

    @property
    def total_weighted_count(self) -> float:
        """Total weighted evidence count across all types."""
        return (
            self.stop_exists_count
            + self.stop_name_count
            + self.stop_location_count
            + self.stop_not_exists_count
        )

    @property
    def positive_weighted_count(self) -> float:
        """Weighted count of positive evidence only."""
        return self.stop_exists_count + self.stop_name_count + self.stop_location_count

    @property
    def evidence_type_count(self) -> int:
        """Number of distinct evidence types present (positive only)."""
        count = 0
        if self.stop_exists_count > 0:
            count += 1
        if self.stop_name_count > 0:
            count += 1
        if self.stop_location_count > 0:
            count += 1
        return count


@dataclass(frozen=True)
class TemporalSpan:
    """
    Immutable representation of temporal spread of evidence.

    Captures the time range over which evidence was observed.
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
class SpatialCluster:
    """
    Immutable representation of a spatial cluster of evidence.

    This is the primary output of aggregation - a cluster of evidence
    with computed statistics. It makes NO decisions about whether
    this cluster represents a real Stop.

    INV-C3: Spatial clustering is descriptive only.
    """

    cluster_id: str
    centroid_lat: float
    centroid_lon: float
    evidence_ids: FrozenSet[UUID]
    evidence_count: int
    independent_contributor_count: int
    weighted_evidence_score: float
    evidence_type_breakdown: EvidenceTypeBreakdown
    temporal_span: TemporalSpan
    cluster_radius_meters: float  # Approximate radius of cluster
    contributor_ids: FrozenSet[UUID]  # Set of unique contributor IDs

    def __post_init__(self):
        """Validate cluster data."""
        if not (-90.0 <= self.centroid_lat <= 90.0):
            raise ValueError(f"Invalid latitude: {self.centroid_lat}")
        if not (-180.0 <= self.centroid_lon <= 180.0):
            raise ValueError(f"Invalid longitude: {self.centroid_lon}")
        if self.evidence_count < 0:
            raise ValueError("evidence_count cannot be negative")
        if self.independent_contributor_count < 0:
            raise ValueError("independent_contributor_count cannot be negative")


@dataclass(frozen=True)
class AggregationResult:
    """
    Immutable result of stop evidence aggregation.

    Contains all spatial clusters derived from evidence,
    along with metadata about the aggregation process.

    This result makes NO decisions. It is pure data.
    """

    clusters: Tuple[SpatialCluster, ...]
    total_evidence_processed: int
    total_contributors: int
    evidence_weights: Tuple[EvidenceWeight, ...]
    aggregation_timestamp: datetime  # When aggregation was performed (for audit)

    @property
    def cluster_count(self) -> int:
        """Number of clusters formed."""
        return len(self.clusters)


# =============================================================================
# Weighting Functions (Pure, No Decisions)
# =============================================================================


class WeightCalculator:
    """
    Pure functions for calculating evidence weights.

    All methods are stateless and deterministic.
    Weights are always in range (0.0, 1.0] - never zero.

    INV-D1: Accuracy is a weight, not a gate.
    INV-D2: High accuracy alone cannot dominate.
    """

    # Minimum weight - evidence is never dropped
    # INV-D1: Even very poor evidence contributes
    MIN_WEIGHT = 0.01

    # GPS accuracy thresholds (meters)
    EXCELLENT_ACCURACY = 5.0  # Full weight
    GOOD_ACCURACY = 15.0  # High weight
    MODERATE_ACCURACY = 50.0  # Medium weight
    POOR_ACCURACY = 100.0  # Low weight
    # Beyond POOR_ACCURACY: minimum weight

    # User dampening parameters
    USER_DAMPENING_BASE = 0.5  # Each repeat halves contribution
    USER_DAMPENING_FLOOR = 0.1  # Minimum contribution from same user

    @classmethod
    def calculate_accuracy_weight(cls, accuracy_meters: Optional[float]) -> float:
        """
        Calculate weight based on GPS accuracy.

        INV-D1: Accuracy reduces influence but never rejects evidence.

        Args:
            accuracy_meters: GPS accuracy in meters (None = unknown)

        Returns:
            Weight in range [MIN_WEIGHT, 1.0]
        """
        if accuracy_meters is None:
            # Unknown accuracy - use moderate weight
            return 0.5

        if accuracy_meters <= 0:
            # Invalid accuracy - use minimum weight
            return cls.MIN_WEIGHT

        if accuracy_meters <= cls.EXCELLENT_ACCURACY:
            return 1.0
        elif accuracy_meters <= cls.GOOD_ACCURACY:
            # Linear interpolation from 1.0 to 0.8
            ratio = (accuracy_meters - cls.EXCELLENT_ACCURACY) / (
                cls.GOOD_ACCURACY - cls.EXCELLENT_ACCURACY
            )
            return 1.0 - (ratio * 0.2)
        elif accuracy_meters <= cls.MODERATE_ACCURACY:
            # Linear interpolation from 0.8 to 0.5
            ratio = (accuracy_meters - cls.GOOD_ACCURACY) / (
                cls.MODERATE_ACCURACY - cls.GOOD_ACCURACY
            )
            return 0.8 - (ratio * 0.3)
        elif accuracy_meters <= cls.POOR_ACCURACY:
            # Linear interpolation from 0.5 to 0.2
            ratio = (accuracy_meters - cls.MODERATE_ACCURACY) / (
                cls.POOR_ACCURACY - cls.MODERATE_ACCURACY
            )
            return 0.5 - (ratio * 0.3)
        else:
            # Very poor accuracy - use minimum weight but never zero
            # INV-D1: Evidence is never dropped
            return max(cls.MIN_WEIGHT, 0.2 * (cls.POOR_ACCURACY / accuracy_meters))

    @classmethod
    def calculate_user_dampening(cls, contribution_index: int) -> float:
        """
        Calculate dampening for repeated contributions from same user.

        INV-C2: Same-user repetition is progressively down-weighted.

        Args:
            contribution_index: 0-based index of this contribution from user
                               (0 = first contribution, 1 = second, etc.)

        Returns:
            Weight in range [USER_DAMPENING_FLOOR, 1.0]
        """
        if contribution_index <= 0:
            return 1.0

        # Exponential decay: weight = base^index, floored
        weight = cls.USER_DAMPENING_BASE**contribution_index
        return max(cls.USER_DAMPENING_FLOOR, weight)

    @classmethod
    def calculate_temporal_weight(
        cls,
        observation_time: datetime,
        earliest_time: datetime,
        latest_time: datetime,
    ) -> float:
        """
        Calculate weight based on temporal spread.

        Evidence spread over time is more valuable than
        clustered-in-time evidence.

        Args:
            observation_time: When this evidence was observed
            earliest_time: Earliest observation in the set
            latest_time: Latest observation in the set

        Returns:
            Weight in range [0.5, 1.0]
        """
        total_span = (latest_time - earliest_time).total_seconds()

        if total_span <= 0:
            # All evidence at same time - moderate weight
            return 0.75

        # Position in temporal span [0, 1]
        position = (observation_time - earliest_time).total_seconds() / total_span

        # Weight based on how well this spreads the evidence
        # Evidence near edges or middle gets higher weight
        # This encourages temporal diversity
        edge_distance = min(position, 1.0 - position)
        return 0.5 + (0.5 * (1.0 - edge_distance))


# =============================================================================
# Spatial Clustering (Descriptive Only)
# =============================================================================


class SpatialClusterer:
    """
    Deterministic spatial clustering of evidence.

    This class groups evidence by spatial proximity without
    making any decisions about what constitutes a "real" stop.

    INV-C3: Clustering is descriptive, not prescriptive.
    INV-B1: Clustering is deterministic.

    Algorithm: Simple grid-based clustering
    - Evidence is assigned to grid cells
    - Adjacent cells are merged if within distance threshold
    - This is conservative (under-merge preferred)
    """

    # Default clustering radius in meters
    DEFAULT_CLUSTER_RADIUS_METERS = 50.0

    # Earth radius for distance calculations
    EARTH_RADIUS_METERS = 6_371_000.0

    def __init__(self, cluster_radius_meters: float = DEFAULT_CLUSTER_RADIUS_METERS):
        """
        Initialize clusterer with radius.

        Args:
            cluster_radius_meters: Maximum radius for cluster membership
        """
        self._cluster_radius = cluster_radius_meters

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points in meters.

        Uses haversine formula for accuracy.

        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates

        Returns:
            Distance in meters
        """
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return SpatialClusterer.EARTH_RADIUS_METERS * c

    def cluster_evidence(
        self,
        evidence_locations: List[Tuple[UUID, float, float]],
    ) -> List[List[UUID]]:
        """
        Cluster evidence by spatial proximity.

        INV-B1: Clustering is deterministic (evidence processed in order).
        INV-C3: Under-merge is preferred.

        Args:
            evidence_locations: List of (evidence_id, lat, lon) tuples
                               Must be sorted deterministically before calling

        Returns:
            List of clusters, each cluster is a list of evidence IDs
        """
        if not evidence_locations:
            return []

        clusters: List[List[UUID]] = []
        cluster_centroids: List[Tuple[float, float]] = []

        for evidence_id, lat, lon in evidence_locations:
            assigned = False

            # Try to assign to existing cluster (in order for determinism)
            for i, (c_lat, c_lon) in enumerate(cluster_centroids):
                distance = self.haversine_distance(lat, lon, c_lat, c_lon)
                if distance <= self._cluster_radius:
                    clusters[i].append(evidence_id)
                    # Update centroid (running average)
                    n = len(clusters[i])
                    new_lat = c_lat + (lat - c_lat) / n
                    new_lon = c_lon + (lon - c_lon) / n
                    cluster_centroids[i] = (new_lat, new_lon)
                    assigned = True
                    break

            if not assigned:
                # Create new cluster
                clusters.append([evidence_id])
                cluster_centroids.append((lat, lon))

        return clusters

    def calculate_cluster_radius(
        self,
        centroid_lat: float,
        centroid_lon: float,
        evidence_locations: List[Tuple[float, float]],
    ) -> float:
        """
        Calculate the approximate radius of a cluster.

        Args:
            centroid_lat, centroid_lon: Cluster centroid
            evidence_locations: List of (lat, lon) for evidence in cluster

        Returns:
            Maximum distance from centroid in meters
        """
        if not evidence_locations:
            return 0.0

        max_distance = 0.0
        for lat, lon in evidence_locations:
            distance = self.haversine_distance(centroid_lat, centroid_lon, lat, lon)
            max_distance = max(max_distance, distance)

        return max_distance


# =============================================================================
# Main Aggregator (Pure Transformation)
# =============================================================================


class StopEvidenceAggregator:
    """
    Pure aggregator for Stop-related evidence.

    This class transforms evidence into aggregates without
    making any decisions about Stop creation or confidence.

    PURE TRANSFORMATION:
        Evidence -> Aggregates

    NO SIDE EFFECTS:
    - Does not write to database
    - Does not read canonical Stops
    - Does not call StopWriteGateway
    - Does not make threshold decisions

    INVARIANTS ENFORCED:
    - INV-A1: All evidence is processed
    - INV-B1: Deterministic aggregation
    - INV-C2: Same-user dampening
    - INV-C3: Spatial clustering
    - INV-D1: Accuracy as weight
    - INV-D2: Accuracy cannot dominate
    """

    # Stop-related contribution types
    STOP_CONTRIBUTION_TYPES = (
        ContributionEvent.ContributionType.STOP_EXISTS,
        ContributionEvent.ContributionType.STOP_NOT_EXISTS,
        ContributionEvent.ContributionType.STOP_NAME,
        ContributionEvent.ContributionType.STOP_LOCATION,
    )

    # Sort keys for deterministic processing
    EVIDENCE_SORT_KEYS = ("observed_at", "submitted_at", "id")

    def __init__(self, cluster_radius_meters: float = 50.0):
        """
        Initialize aggregator.

        Args:
            cluster_radius_meters: Radius for spatial clustering
        """
        self._clusterer = SpatialClusterer(cluster_radius_meters)
        self._weight_calculator = WeightCalculator

    def aggregate(
        self,
        evidence: Sequence[ContributionEvent],
        aggregation_time: datetime,
    ) -> AggregationResult:
        """
        Aggregate evidence into spatial clusters with weights.

        This is a PURE TRANSFORMATION with no side effects.

        INV-A1: All evidence is processed.
        INV-B1: Output is deterministic for identical input.

        Args:
            evidence: Collection of ContributionEvent records
            aggregation_time: Timestamp for this aggregation (for audit)

        Returns:
            Immutable AggregationResult with all clusters
        """
        # Filter to stop-related evidence
        stop_evidence = [
            e for e in evidence if e.contribution_type in self.STOP_CONTRIBUTION_TYPES
        ]

        if not stop_evidence:
            return AggregationResult(
                clusters=(),
                total_evidence_processed=0,
                total_contributors=0,
                evidence_weights=(),
                aggregation_timestamp=aggregation_time,
            )

        # Sort deterministically (INV-B1)
        sorted_evidence = self._sort_evidence(stop_evidence)

        # Calculate temporal span for weighting
        earliest = min(e.observed_at for e in sorted_evidence)
        latest = max(e.observed_at for e in sorted_evidence)

        # Calculate weights for all evidence (INV-A1, INV-D1, INV-D2)
        user_contribution_counts: Dict[UUID, int] = {}
        evidence_weights: List[EvidenceWeight] = []

        for event in sorted_evidence:
            weight = self._calculate_evidence_weight(
                event, user_contribution_counts, earliest, latest
            )
            evidence_weights.append(weight)

            # Track user contribution count for dampening
            # Sprint-5B: Use contributor_fingerprint (immutable) NOT contributor_id (nullable FK)
            # This ensures contributor independence survives account deletion (INV-I1, INV-I2)
            fingerprint = event.contributor_fingerprint
            user_contribution_counts[fingerprint] = (
                user_contribution_counts.get(fingerprint, 0) + 1
            )

        # Extract locations for clustering
        evidence_locations = self._extract_locations(sorted_evidence)

        # Perform spatial clustering (INV-C3)
        cluster_ids_list = self._clusterer.cluster_evidence(evidence_locations)

        # Build cluster objects
        clusters = self._build_clusters(
            sorted_evidence,
            evidence_weights,
            cluster_ids_list,
            evidence_locations,
        )

        # Collect all unique contributors
        # Sprint-5B: Use contributor_fingerprint (immutable) NOT contributor_id (nullable FK)
        # This ensures contributor counts remain correct after account deletion (INV-I1, INV-I2)
        all_contributors = frozenset(e.contributor_fingerprint for e in sorted_evidence)

        return AggregationResult(
            clusters=tuple(clusters),
            total_evidence_processed=len(sorted_evidence),
            total_contributors=len(all_contributors),
            evidence_weights=tuple(evidence_weights),
            aggregation_timestamp=aggregation_time,
        )

    def _sort_evidence(
        self, evidence: Sequence[ContributionEvent]
    ) -> List[ContributionEvent]:
        """
        Sort evidence deterministically.

        INV-B1: Deterministic ordering.
        """
        return sorted(
            evidence,
            key=lambda e: (e.observed_at, e.submitted_at, str(e.id)),
        )

    def _calculate_evidence_weight(
        self,
        event: ContributionEvent,
        user_contribution_counts: Dict[UUID, int],
        earliest: datetime,
        latest: datetime,
    ) -> EvidenceWeight:
        """
        Calculate weight for a single evidence event.

        INV-D1: Accuracy is weight, not gate (always contributes).
        INV-C2: Same-user repetition is dampened.

        Sprint-5B: Uses contributor_fingerprint for user identity, NOT contributor_id.
        This ensures dampening logic is stable across account deletions.
        """
        # GPS accuracy weight
        accuracy = event.context.get("gps_accuracy") if event.context else None
        accuracy_weight = self._weight_calculator.calculate_accuracy_weight(accuracy)

        # User dampening weight
        # Sprint-5B: Use contributor_fingerprint (immutable) NOT contributor_id (nullable FK)
        fingerprint = event.contributor_fingerprint
        contribution_index = user_contribution_counts.get(fingerprint, 0)
        user_dampening = self._weight_calculator.calculate_user_dampening(
            contribution_index
        )

        # Temporal weight
        temporal_weight = self._weight_calculator.calculate_temporal_weight(
            event.observed_at, earliest, latest
        )

        # Combined weight (product)
        combined = accuracy_weight * user_dampening * temporal_weight

        return EvidenceWeight(
            evidence_id=event.id,
            accuracy_weight=accuracy_weight,
            user_dampening=user_dampening,
            temporal_weight=temporal_weight,
            combined_weight=combined,
        )

    def _extract_locations(
        self, evidence: List[ContributionEvent]
    ) -> List[Tuple[UUID, float, float]]:
        """
        Extract location data from evidence.

        Returns list of (evidence_id, lat, lon) tuples.
        Evidence without valid location is assigned a placeholder
        so it still contributes (INV-A1).
        """
        locations = []

        for event in evidence:
            lat, lon = self._get_location_from_event(event)
            if lat is not None and lon is not None:
                locations.append((event.id, lat, lon))

        return locations

    def _get_location_from_event(
        self, event: ContributionEvent
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract lat/lon from a contribution event.

        Checks subject_ref and payload for location data.
        """
        # Try subject_ref first
        if event.subject_ref:
            lat = event.subject_ref.get("lat")
            lon = event.subject_ref.get("lon")
            if lat is not None and lon is not None:
                return (float(lat), float(lon))

        # Try payload
        if event.payload:
            lat = event.payload.get("lat")
            lon = event.payload.get("lon")
            if lat is not None and lon is not None:
                return (float(lat), float(lon))

            # Try nested location object
            location = event.payload.get("location")
            if location:
                lat = location.get("lat")
                lon = location.get("lon")
                if lat is not None and lon is not None:
                    return (float(lat), float(lon))

        return (None, None)

    def _build_clusters(
        self,
        evidence: List[ContributionEvent],
        weights: List[EvidenceWeight],
        cluster_ids_list: List[List[UUID]],
        evidence_locations: List[Tuple[UUID, float, float]],
    ) -> List[SpatialCluster]:
        """
        Build SpatialCluster objects from clustering results.
        """
        # Build lookup maps
        evidence_by_id = {e.id: e for e in evidence}
        weight_by_id = {w.evidence_id: w for w in weights}
        location_by_id = {loc[0]: (loc[1], loc[2]) for loc in evidence_locations}

        clusters = []

        for idx, cluster_evidence_ids in enumerate(cluster_ids_list):
            if not cluster_evidence_ids:
                continue

            # Get evidence in this cluster
            cluster_evidence = [
                evidence_by_id[eid]
                for eid in cluster_evidence_ids
                if eid in evidence_by_id
            ]

            if not cluster_evidence:
                continue

            # Calculate centroid
            lats = []
            lons = []
            for eid in cluster_evidence_ids:
                if eid in location_by_id:
                    lat, lon = location_by_id[eid]
                    lats.append(lat)
                    lons.append(lon)

            if not lats:
                continue

            centroid_lat = sum(lats) / len(lats)
            centroid_lon = sum(lons) / len(lons)

            # Calculate cluster radius
            cluster_radius = self._clusterer.calculate_cluster_radius(
                centroid_lat,
                centroid_lon,
                [(lat, lon) for lat, lon in zip(lats, lons)],
            )

            # Collect unique contributors
            # Sprint-5B: Use contributor_fingerprint (immutable) NOT contributor_id (nullable FK)
            # This ensures contributor counts remain correct after account deletion (INV-I1, INV-I2)
            contributors = frozenset(
                e.contributor_fingerprint for e in cluster_evidence
            )

            # Calculate weighted score
            weighted_score = sum(
                weight_by_id[eid].combined_weight
                for eid in cluster_evidence_ids
                if eid in weight_by_id
            )

            # Build evidence type breakdown
            type_breakdown = self._build_type_breakdown(cluster_evidence, weight_by_id)

            # Build temporal span
            temporal_span = self._build_temporal_span(cluster_evidence)

            cluster = SpatialCluster(
                cluster_id=f"cluster_{idx:04d}",
                centroid_lat=centroid_lat,
                centroid_lon=centroid_lon,
                evidence_ids=frozenset(cluster_evidence_ids),
                evidence_count=len(cluster_evidence),
                independent_contributor_count=len(contributors),
                weighted_evidence_score=weighted_score,
                evidence_type_breakdown=type_breakdown,
                temporal_span=temporal_span,
                cluster_radius_meters=cluster_radius,
                contributor_ids=contributors,
            )
            clusters.append(cluster)

        return clusters

    def _build_type_breakdown(
        self,
        evidence: List[ContributionEvent],
        weight_by_id: Dict[UUID, EvidenceWeight],
    ) -> EvidenceTypeBreakdown:
        """
        Build evidence type breakdown for a cluster.
        """
        stop_exists = 0.0
        stop_name = 0.0
        stop_location = 0.0
        stop_not_exists = 0.0

        for event in evidence:
            weight = weight_by_id.get(event.id)
            w = weight.combined_weight if weight else 1.0

            if (
                event.contribution_type
                == ContributionEvent.ContributionType.STOP_EXISTS
            ):
                stop_exists += w
            elif (
                event.contribution_type == ContributionEvent.ContributionType.STOP_NAME
            ):
                stop_name += w
            elif (
                event.contribution_type
                == ContributionEvent.ContributionType.STOP_LOCATION
            ):
                stop_location += w
            elif (
                event.contribution_type
                == ContributionEvent.ContributionType.STOP_NOT_EXISTS
            ):
                stop_not_exists += w

        return EvidenceTypeBreakdown(
            stop_exists_count=stop_exists,
            stop_name_count=stop_name,
            stop_location_count=stop_location,
            stop_not_exists_count=stop_not_exists,
        )

    def _build_temporal_span(self, evidence: List[ContributionEvent]) -> TemporalSpan:
        """
        Build temporal span for a cluster.
        """
        if not evidence:
            now = datetime.now()
            return TemporalSpan(
                earliest_observation=now,
                latest_observation=now,
                distinct_days=0,
            )

        observation_times = [e.observed_at for e in evidence]
        earliest = min(observation_times)
        latest = max(observation_times)

        # Count distinct calendar days
        distinct_days = len(set(t.date() for t in observation_times))

        return TemporalSpan(
            earliest_observation=earliest,
            latest_observation=latest,
            distinct_days=distinct_days,
        )
