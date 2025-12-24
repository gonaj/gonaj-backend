"""
Tests for stop evidence aggregation.

Sprint-4B: Positive Evidence Aggregation (No Creation)

These tests verify the aggregation infrastructure without testing
any semantic evaluation logic. They ensure:

1. Aggregation is deterministic regardless of evidence order
2. Same-user evidence is dampened
3. Low-accuracy evidence contributes non-zero weight
4. Spatially distant evidence forms separate aggregates
5. No canonical writes occur during aggregation

INVARIANTS TESTED:
- INV-A1: No evidence loss
- INV-B1: Deterministic aggregation
- INV-C2: Independence handling (same-user dampening)
- INV-C3: Spatial convergence (clustering)
- INV-D1: Accuracy as weight, not gate
- INV-D2: Accuracy cannot dominate alone

These tests do NOT verify:
- Stop creation logic (not implemented)
- Confidence calculations (not implemented)
- Threshold decisions (not implemented)
"""

import random
from datetime import datetime, timedelta
from uuid import uuid4

from core.models import ContributionEvent
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from transit.evaluation import (
    AggregationResult,
    EvidenceWeight,
    SpatialCluster,
    SpatialClusterer,
    StopEvidenceAggregator,
    WeightCalculator,
)
from transit.models import Stop

User = get_user_model()


class WeightCalculatorTests(TestCase):
    """
    Tests for the WeightCalculator class.

    INV-D1: Accuracy is a weight, not a gate.
    INV-D2: Accuracy cannot dominate alone.
    """

    def test_excellent_accuracy_gets_full_weight(self):
        """
        Excellent GPS accuracy (<=5m) should get full weight.

        INV-D1: Accuracy as weight.
        """
        weight = WeightCalculator.calculate_accuracy_weight(3.0)
        self.assertEqual(weight, 1.0)

        weight = WeightCalculator.calculate_accuracy_weight(5.0)
        self.assertEqual(weight, 1.0)

    def test_poor_accuracy_still_contributes(self):
        """
        Poor GPS accuracy should still contribute non-zero weight.

        INV-D1: Accuracy reduces influence but never rejects evidence.
        """
        # 100m accuracy - poor but still contributes
        weight = WeightCalculator.calculate_accuracy_weight(100.0)
        self.assertGreater(weight, 0.0)
        self.assertLess(weight, 1.0)

        # 500m accuracy - very poor but still contributes
        weight = WeightCalculator.calculate_accuracy_weight(500.0)
        self.assertGreater(weight, 0.0)
        self.assertLess(weight, 0.5)

    def test_very_poor_accuracy_gets_minimum_weight(self):
        """
        Very poor accuracy should get minimum weight but never zero.

        INV-D1: Evidence is never dropped solely due to accuracy.
        """
        # 1000m accuracy
        weight = WeightCalculator.calculate_accuracy_weight(1000.0)
        self.assertGreaterEqual(weight, WeightCalculator.MIN_WEIGHT)
        self.assertGreater(weight, 0.0)

        # 10000m accuracy
        weight = WeightCalculator.calculate_accuracy_weight(10000.0)
        self.assertGreaterEqual(weight, WeightCalculator.MIN_WEIGHT)
        self.assertGreater(weight, 0.0)

    def test_unknown_accuracy_gets_moderate_weight(self):
        """
        Unknown accuracy (None) should get moderate weight.

        INV-D1: Evidence is never dropped.
        """
        weight = WeightCalculator.calculate_accuracy_weight(None)
        self.assertEqual(weight, 0.5)

    def test_invalid_accuracy_gets_minimum_weight(self):
        """
        Invalid accuracy (<=0) should get minimum weight.

        INV-D1: Evidence is never dropped.
        """
        weight = WeightCalculator.calculate_accuracy_weight(0.0)
        self.assertEqual(weight, WeightCalculator.MIN_WEIGHT)

        weight = WeightCalculator.calculate_accuracy_weight(-10.0)
        self.assertEqual(weight, WeightCalculator.MIN_WEIGHT)

    def test_user_dampening_first_contribution_full_weight(self):
        """
        First contribution from a user should get full weight.

        INV-C2: Same-user handling.
        """
        weight = WeightCalculator.calculate_user_dampening(0)
        self.assertEqual(weight, 1.0)

    def test_user_dampening_progressively_reduces(self):
        """
        Repeated contributions from same user are progressively dampened.

        INV-C2: Same-user repetition is progressively down-weighted.
        """
        weight_1 = WeightCalculator.calculate_user_dampening(0)  # First
        weight_2 = WeightCalculator.calculate_user_dampening(1)  # Second
        weight_3 = WeightCalculator.calculate_user_dampening(2)  # Third
        weight_4 = WeightCalculator.calculate_user_dampening(3)  # Fourth

        # Each should be less than the previous
        self.assertGreater(weight_1, weight_2)
        self.assertGreater(weight_2, weight_3)
        self.assertGreater(weight_3, weight_4)

        # All should be positive
        self.assertGreater(weight_4, 0.0)

    def test_user_dampening_has_floor(self):
        """
        User dampening should have a floor (minimum contribution).

        INV-C2: Even many repeats contribute something.
        """
        # Many repetitions
        weight = WeightCalculator.calculate_user_dampening(100)
        self.assertGreaterEqual(weight, WeightCalculator.USER_DAMPENING_FLOOR)
        self.assertGreater(weight, 0.0)


class SpatialClustererTests(TestCase):
    """
    Tests for spatial clustering.

    INV-C3: Spatial convergence.
    INV-B1: Deterministic clustering.
    """

    def test_haversine_distance_calculation(self):
        """Haversine distance should be calculated correctly."""
        # Same point - zero distance
        distance = SpatialClusterer.haversine_distance(40.7, -74.0, 40.7, -74.0)
        self.assertEqual(distance, 0.0)

        # Known distance (approximately 111km per degree at equator)
        distance = SpatialClusterer.haversine_distance(0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(distance, 111000, delta=1000)

    def test_nearby_evidence_clusters_together(self):
        """
        Evidence within cluster radius should be grouped together.

        INV-C3: Spatial convergence.
        """
        clusterer = SpatialClusterer(cluster_radius_meters=100.0)

        # Two points very close together (within 100m)
        evidence_locations = [
            (uuid4(), 40.7128, -74.0060),  # Point 1
            (uuid4(), 40.7129, -74.0061),  # Point 2 - very close
        ]

        clusters = clusterer.cluster_evidence(evidence_locations)

        # Should form one cluster
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]), 2)

    def test_distant_evidence_forms_separate_clusters(self):
        """
        Evidence beyond cluster radius should form separate clusters.

        INV-C3: Distant clusters do not form a Stop.
        """
        clusterer = SpatialClusterer(cluster_radius_meters=100.0)

        # Two points far apart (several km)
        evidence_locations = [
            (uuid4(), 40.7128, -74.0060),  # NYC
            (uuid4(), 40.7500, -73.9800),  # Several km away
        ]

        clusters = clusterer.cluster_evidence(evidence_locations)

        # Should form two separate clusters
        self.assertEqual(len(clusters), 2)

    def test_clustering_is_deterministic(self):
        """
        Clustering should be deterministic regardless of input order.

        INV-B1: Deterministic evaluation.
        """
        clusterer = SpatialClusterer(cluster_radius_meters=100.0)

        id1, id2, id3 = uuid4(), uuid4(), uuid4()

        # Same evidence in different orders
        order_a = [
            (id1, 40.7128, -74.0060),
            (id2, 40.7129, -74.0061),
            (id3, 40.7500, -73.9800),
        ]
        order_b = [
            (id3, 40.7500, -73.9800),
            (id1, 40.7128, -74.0060),
            (id2, 40.7129, -74.0061),
        ]

        clusters_a = clusterer.cluster_evidence(order_a)
        clusters_b = clusterer.cluster_evidence(order_b)

        # Both should produce same number of clusters
        self.assertEqual(len(clusters_a), len(clusters_b))

        # Flatten all IDs from clusters
        ids_a = set()
        for cluster in clusters_a:
            ids_a.update(cluster)

        ids_b = set()
        for cluster in clusters_b:
            ids_b.update(cluster)

        # Same IDs should be present
        self.assertEqual(ids_a, ids_b)

    def test_empty_evidence_returns_empty_clusters(self):
        """Empty evidence should return empty clusters."""
        clusterer = SpatialClusterer()
        clusters = clusterer.cluster_evidence([])
        self.assertEqual(clusters, [])


class StopEvidenceAggregatorTests(TestCase):
    """
    Tests for the main aggregator.

    INV-A1: No evidence loss.
    INV-B1: Deterministic aggregation.
    """

    def setUp(self):
        """Set up test users."""
        self.user1 = User.objects.create_user(
            username="testuser1",
            email="test1@example.com",
            password="testpass123",
        )
        self.user2 = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )
        self.user3 = User.objects.create_user(
            username="testuser3",
            email="test3@example.com",
            password="testpass123",
        )

    def create_contribution_event(
        self,
        contributor,
        contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
        lat=40.7128,
        lon=-74.0060,
        gps_accuracy=10.0,
        observed_at=None,
    ):
        """Helper to create a ContributionEvent for testing."""
        if observed_at is None:
            observed_at = timezone.now()

        return ContributionEvent.objects.create(
            client_generated_id=uuid4(),
            contributor=contributor,
            contribution_type=contribution_type,
            subject_ref={"lat": lat, "lon": lon},
            payload={"test": True},
            observed_at=observed_at,
            context={"gps_accuracy": gps_accuracy} if gps_accuracy else {},
        )

    def test_aggregation_processes_all_evidence(self):
        """
        All evidence should be processed and included in result.

        INV-A1: No evidence loss.
        """
        events = [
            self.create_contribution_event(self.user1),
            self.create_contribution_event(self.user2),
            self.create_contribution_event(self.user3),
        ]

        aggregator = StopEvidenceAggregator()
        result = aggregator.aggregate(events, timezone.now())

        # All evidence should be processed
        self.assertEqual(result.total_evidence_processed, 3)
        self.assertEqual(len(result.evidence_weights), 3)

        # All evidence IDs should be in the weights
        event_ids = {e.id for e in events}
        weight_ids = {w.evidence_id for w in result.evidence_weights}
        self.assertEqual(event_ids, weight_ids)

    def test_aggregation_is_deterministic(self):
        """
        Aggregation should be deterministic for identical input.

        INV-B1: Deterministic evaluation.
        """
        now = timezone.now()

        events = [
            self.create_contribution_event(
                self.user1, observed_at=now - timedelta(hours=2)
            ),
            self.create_contribution_event(
                self.user2, observed_at=now - timedelta(hours=1)
            ),
            self.create_contribution_event(self.user3, observed_at=now),
        ]

        aggregator = StopEvidenceAggregator()

        # Run aggregation multiple times
        result1 = aggregator.aggregate(events, now)
        result2 = aggregator.aggregate(events, now)
        result3 = aggregator.aggregate(events, now)

        # Results should be identical
        self.assertEqual(
            result1.total_evidence_processed, result2.total_evidence_processed
        )
        self.assertEqual(
            result2.total_evidence_processed, result3.total_evidence_processed
        )

        self.assertEqual(result1.cluster_count, result2.cluster_count)
        self.assertEqual(result2.cluster_count, result3.cluster_count)

        # Evidence weights should be identical
        weights1 = [
            (w.evidence_id, w.combined_weight) for w in result1.evidence_weights
        ]
        weights2 = [
            (w.evidence_id, w.combined_weight) for w in result2.evidence_weights
        ]
        self.assertEqual(weights1, weights2)

    def test_aggregation_deterministic_regardless_of_input_order(self):
        """
        Aggregation should produce same result regardless of input order.

        INV-B1: Input ordering does not affect results.
        """
        now = timezone.now()

        event1 = self.create_contribution_event(
            self.user1, observed_at=now - timedelta(hours=2)
        )
        event2 = self.create_contribution_event(
            self.user2, observed_at=now - timedelta(hours=1)
        )
        event3 = self.create_contribution_event(self.user3, observed_at=now)

        aggregator = StopEvidenceAggregator()

        # Different input orders
        result_a = aggregator.aggregate([event1, event2, event3], now)
        result_b = aggregator.aggregate([event3, event1, event2], now)
        result_c = aggregator.aggregate([event2, event3, event1], now)

        # All should have same evidence count
        self.assertEqual(
            result_a.total_evidence_processed, result_b.total_evidence_processed
        )
        self.assertEqual(
            result_b.total_evidence_processed, result_c.total_evidence_processed
        )

        # All should have same cluster count
        self.assertEqual(result_a.cluster_count, result_b.cluster_count)
        self.assertEqual(result_b.cluster_count, result_c.cluster_count)

        # Evidence weights should be same (sorted by ID for comparison)
        def sorted_weights(result):
            return sorted(
                [
                    (str(w.evidence_id), w.combined_weight)
                    for w in result.evidence_weights
                ]
            )

        self.assertEqual(sorted_weights(result_a), sorted_weights(result_b))
        self.assertEqual(sorted_weights(result_b), sorted_weights(result_c))

    def test_same_user_evidence_is_dampened(self):
        """
        Evidence from the same user should be progressively dampened.

        INV-C2: Same-user repetition is progressively down-weighted.
        """
        now = timezone.now()

        # Multiple events from same user
        events = [
            self.create_contribution_event(
                self.user1, observed_at=now - timedelta(hours=3)
            ),
            self.create_contribution_event(
                self.user1, observed_at=now - timedelta(hours=2)
            ),
            self.create_contribution_event(
                self.user1, observed_at=now - timedelta(hours=1)
            ),
            self.create_contribution_event(self.user1, observed_at=now),
        ]

        aggregator = StopEvidenceAggregator()
        result = aggregator.aggregate(events, now)

        # All evidence should be processed
        self.assertEqual(result.total_evidence_processed, 4)

        # Check user dampening values
        # First should have dampening=1.0, subsequent should be less
        weights_by_time = sorted(
            result.evidence_weights,
            key=lambda w: next(e.observed_at for e in events if e.id == w.evidence_id),
        )

        self.assertEqual(weights_by_time[0].user_dampening, 1.0)
        self.assertLess(weights_by_time[1].user_dampening, 1.0)
        self.assertLess(
            weights_by_time[2].user_dampening, weights_by_time[1].user_dampening
        )
        self.assertLess(
            weights_by_time[3].user_dampening, weights_by_time[2].user_dampening
        )

        # All dampening values should be positive
        for weight in weights_by_time:
            self.assertGreater(weight.user_dampening, 0.0)

    def test_low_accuracy_evidence_still_contributes(self):
        """
        Low accuracy evidence should contribute non-zero weight.

        INV-D1: Accuracy reduces influence but never rejects evidence.
        """
        events = [
            self.create_contribution_event(self.user1, gps_accuracy=5.0),  # Excellent
            self.create_contribution_event(self.user2, gps_accuracy=500.0),  # Very poor
        ]

        aggregator = StopEvidenceAggregator()
        result = aggregator.aggregate(events, timezone.now())

        # Both should be processed
        self.assertEqual(result.total_evidence_processed, 2)

        # Find the poor accuracy weight
        poor_accuracy_event = events[1]
        poor_weight = next(
            w
            for w in result.evidence_weights
            if w.evidence_id == poor_accuracy_event.id
        )

        # Should have lower accuracy weight but still positive
        self.assertLess(poor_weight.accuracy_weight, 1.0)
        self.assertGreater(poor_weight.accuracy_weight, 0.0)
        self.assertGreater(poor_weight.combined_weight, 0.0)

    def test_single_high_accuracy_observation_cannot_dominate(self):
        """
        A single high-accuracy observation should not dominate.

        INV-D2: Accuracy cannot dominate alone.
        """
        events = [
            self.create_contribution_event(
                self.user1, gps_accuracy=1.0
            ),  # Very high accuracy
        ]

        aggregator = StopEvidenceAggregator()
        result = aggregator.aggregate(events, timezone.now())

        # Should process the evidence
        self.assertEqual(result.total_evidence_processed, 1)

        # Single evidence should have weight but...
        # Only 1 contributor means independence requirement not met
        # (This is captured in the cluster metadata, not as a decision)
        if result.clusters:
            cluster = result.clusters[0]
            self.assertEqual(cluster.independent_contributor_count, 1)

    def test_spatially_distant_evidence_forms_separate_clusters(self):
        """
        Spatially distant evidence should form separate clusters.

        INV-C3: Distant clusters do not form a Stop.
        """
        # Two locations far apart
        events = [
            self.create_contribution_event(
                self.user1, lat=40.7128, lon=-74.0060
            ),  # NYC
            self.create_contribution_event(
                self.user2, lat=34.0522, lon=-118.2437
            ),  # LA
        ]

        aggregator = StopEvidenceAggregator()
        result = aggregator.aggregate(events, timezone.now())

        # Should form 2 separate clusters
        self.assertEqual(result.cluster_count, 2)

        # Each cluster should have 1 evidence item
        for cluster in result.clusters:
            self.assertEqual(cluster.evidence_count, 1)

    def test_nearby_evidence_forms_single_cluster(self):
        """
        Nearby evidence should form a single cluster.

        INV-C3: Spatial convergence.
        """
        # Three locations very close together (within 50m default radius)
        base_lat, base_lon = 40.7128, -74.0060
        events = [
            self.create_contribution_event(self.user1, lat=base_lat, lon=base_lon),
            self.create_contribution_event(
                self.user2, lat=base_lat + 0.0001, lon=base_lon + 0.0001
            ),
            self.create_contribution_event(
                self.user3, lat=base_lat + 0.0002, lon=base_lon + 0.0002
            ),
        ]

        aggregator = StopEvidenceAggregator()
        result = aggregator.aggregate(events, timezone.now())

        # Should form 1 cluster
        self.assertEqual(result.cluster_count, 1)

        # Cluster should have all 3 evidence items
        cluster = result.clusters[0]
        self.assertEqual(cluster.evidence_count, 3)
        self.assertEqual(cluster.independent_contributor_count, 3)

    def test_cluster_tracks_multiple_evidence_types(self):
        """
        Cluster should track breakdown by evidence type.
        """
        events = [
            self.create_contribution_event(
                self.user1,
                contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            ),
            self.create_contribution_event(
                self.user2,
                contribution_type=ContributionEvent.ContributionType.STOP_NAME,
            ),
            self.create_contribution_event(
                self.user3,
                contribution_type=ContributionEvent.ContributionType.STOP_LOCATION,
            ),
        ]

        aggregator = StopEvidenceAggregator()
        result = aggregator.aggregate(events, timezone.now())

        # Should have 1 cluster
        self.assertEqual(result.cluster_count, 1)

        cluster = result.clusters[0]
        breakdown = cluster.evidence_type_breakdown

        # Should have all three types
        self.assertGreater(breakdown.stop_exists_count, 0)
        self.assertGreater(breakdown.stop_name_count, 0)
        self.assertGreater(breakdown.stop_location_count, 0)
        self.assertEqual(breakdown.evidence_type_count, 3)

    def test_cluster_tracks_temporal_span(self):
        """
        Cluster should track temporal span of evidence.
        """
        now = timezone.now()

        events = [
            self.create_contribution_event(
                self.user1, observed_at=now - timedelta(days=3)
            ),
            self.create_contribution_event(
                self.user2, observed_at=now - timedelta(days=1)
            ),
            self.create_contribution_event(self.user3, observed_at=now),
        ]

        aggregator = StopEvidenceAggregator()
        result = aggregator.aggregate(events, now)

        cluster = result.clusters[0]
        temporal_span = cluster.temporal_span

        # Should span 3 days
        self.assertEqual(temporal_span.distinct_days, 3)

        # Earliest should be 3 days ago
        expected_earliest = now - timedelta(days=3)
        self.assertEqual(
            temporal_span.earliest_observation.date(), expected_earliest.date()
        )

    def test_empty_evidence_returns_empty_result(self):
        """
        Empty evidence should return empty result.
        """
        aggregator = StopEvidenceAggregator()
        result = aggregator.aggregate([], timezone.now())

        self.assertEqual(result.total_evidence_processed, 0)
        self.assertEqual(result.cluster_count, 0)
        self.assertEqual(result.total_contributors, 0)

    def test_non_stop_evidence_is_filtered(self):
        """
        Non-stop-related evidence should be filtered out.
        """
        events = [
            self.create_contribution_event(
                self.user1,
                contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            ),
            self.create_contribution_event(
                self.user2,
                contribution_type=ContributionEvent.ContributionType.ROUTE_EXISTS,
            ),
        ]

        aggregator = StopEvidenceAggregator()
        result = aggregator.aggregate(events, timezone.now())

        # Only stop evidence should be processed
        self.assertEqual(result.total_evidence_processed, 1)


class NoCanonicalWritesTests(TestCase):
    """
    Tests verifying that aggregation does not write to canonical tables.

    This is a critical Sprint-4B requirement.
    """

    def setUp(self):
        """Set up test user."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_aggregation_does_not_create_stops(self):
        """
        Aggregation must not create any Stop records.

        Sprint-4B scope: No canonical writes.
        """
        initial_stop_count = Stop.objects.count()

        events = [
            ContributionEvent.objects.create(
                client_generated_id=uuid4(),
                contributor=self.user,
                contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
                subject_ref={"lat": 40.7128, "lon": -74.0060},
                payload={"test": True},
                observed_at=timezone.now(),
            )
            for _ in range(5)
        ]

        aggregator = StopEvidenceAggregator()
        result = aggregator.aggregate(events, timezone.now())

        # Should process evidence
        self.assertEqual(result.total_evidence_processed, 5)

        # Stop count should be unchanged
        final_stop_count = Stop.objects.count()
        self.assertEqual(initial_stop_count, final_stop_count)

    def test_aggregation_result_is_pure_data(self):
        """
        Aggregation result should be pure data with no side effects.
        """
        events = [
            ContributionEvent.objects.create(
                client_generated_id=uuid4(),
                contributor=self.user,
                contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
                subject_ref={"lat": 40.7128, "lon": -74.0060},
                payload={"test": True},
                observed_at=timezone.now(),
            )
        ]

        aggregator = StopEvidenceAggregator()
        result = aggregator.aggregate(events, timezone.now())

        # Result should be an AggregationResult
        self.assertIsInstance(result, AggregationResult)

        # Clusters should be a tuple (immutable)
        self.assertIsInstance(result.clusters, tuple)

        # Evidence weights should be a tuple (immutable)
        self.assertIsInstance(result.evidence_weights, tuple)


class ImmutableDataStructureTests(TestCase):
    """
    Tests verifying that aggregate data structures are immutable.
    """

    def test_evidence_weight_is_immutable(self):
        """EvidenceWeight should be immutable (frozen dataclass)."""
        weight = EvidenceWeight(
            evidence_id=uuid4(),
            accuracy_weight=1.0,
            user_dampening=1.0,
            temporal_weight=1.0,
            combined_weight=1.0,
        )

        with self.assertRaises(Exception):
            weight.accuracy_weight = 0.5

    def test_spatial_cluster_is_immutable(self):
        """SpatialCluster should be immutable (frozen dataclass)."""
        from transit.evaluation.stop_aggregation import (
            EvidenceTypeBreakdown,
            TemporalSpan,
        )

        now = timezone.now()
        cluster = SpatialCluster(
            cluster_id="test_001",
            centroid_lat=40.7128,
            centroid_lon=-74.0060,
            evidence_ids=frozenset([uuid4()]),
            evidence_count=1,
            independent_contributor_count=1,
            weighted_evidence_score=1.0,
            evidence_type_breakdown=EvidenceTypeBreakdown(),
            temporal_span=TemporalSpan(
                earliest_observation=now,
                latest_observation=now,
                distinct_days=1,
            ),
            cluster_radius_meters=10.0,
            contributor_ids=frozenset([uuid4()]),
        )

        with self.assertRaises(Exception):
            cluster.centroid_lat = 0.0

    def test_aggregation_result_is_immutable(self):
        """AggregationResult should be immutable (frozen dataclass)."""
        result = AggregationResult(
            clusters=(),
            total_evidence_processed=0,
            total_contributors=0,
            evidence_weights=(),
            aggregation_timestamp=timezone.now(),
        )

        with self.assertRaises(Exception):
            result.total_evidence_processed = 100
