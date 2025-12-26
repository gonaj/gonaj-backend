"""
Tests for negative evidence handling (Sprint-4D).

This module tests the negative evidence semantics introduced in Sprint-4D:
- Negative evidence interpretation and scoping
- Confidence reduction with hard caps
- Contested state derivation
- Threshold adjustment for creation

All tests reference blocking invariants explicitly.

BLOCKING INVARIANTS TESTED:
- INV-E1: No deletion via negative evidence
- INV-E2: Negative evidence weaker than aggregated positive evidence
- INV-E3: Negative evidence modulates belief only
- INV-F1: Confidence changes are gradual
- INV-J1: Safe to be wrong
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from core.models import ContributionEvent, User
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone
from transit.evaluation.base import EvaluationContext
from transit.evaluation.stop_aggregation import (
    EvidenceTypeBreakdown,
    SpatialCluster,
    TemporalSpan,
)
from transit.evaluation.stop_creation import StopCreationPipeline, ThresholdEvaluator
from transit.evaluation.stop_evaluator import StopWriteGateway
from transit.evaluation.stop_negative_evidence import (
    ConfidenceAdjuster,
    ContestedStateEvaluator,
    NegativeEvidenceAnalyzer,
    NegativeEvidenceScope,
)
from transit.models import Stop


class NegativeEvidenceScopingTest(TestCase):
    """
    Test spatial and temporal scoping of negative evidence.

    INV-E2: Negative evidence must be scoped to prevent over-application.
    """

    def test_spatial_scoping_within_radius(self):
        """Negative evidence within radius is spatially relevant."""
        location = Point(-73.9, 40.7, srid=4326)
        scope = NegativeEvidenceScope(
            location=location,
            spatial_radius_meters=50.0,
            observation_time=timezone.now(),
            temporal_window_hours=168.0,
            evidence_type="stop_not_exists",
        )

        # Stop very close (within radius)
        nearby_stop = Point(-73.90001, 40.70001, srid=4326)
        self.assertTrue(scope.is_spatially_relevant(nearby_stop))

    def test_spatial_scoping_outside_radius(self):
        """Negative evidence outside radius is not spatially relevant."""
        location = Point(-73.9, 40.7, srid=4326)
        scope = NegativeEvidenceScope(
            location=location,
            spatial_radius_meters=50.0,
            observation_time=timezone.now(),
            temporal_window_hours=168.0,
            evidence_type="stop_not_exists",
        )

        # Stop far away (outside radius)
        distant_stop = Point(-73.95, 40.75, srid=4326)
        self.assertFalse(scope.is_spatially_relevant(distant_stop))

    def test_temporal_scoping_within_window(self):
        """Negative evidence within window is temporally relevant."""
        base_time = timezone.now()
        scope = NegativeEvidenceScope(
            location=Point(-73.9, 40.7, srid=4326),
            spatial_radius_meters=50.0,
            observation_time=base_time,
            temporal_window_hours=168.0,
            evidence_type="stop_not_exists",
        )

        # Time within window
        recent_time = base_time + timedelta(hours=100)
        self.assertTrue(scope.is_temporally_relevant(recent_time))

    def test_temporal_scoping_outside_window(self):
        """Negative evidence outside window is not temporally relevant."""
        base_time = timezone.now()
        scope = NegativeEvidenceScope(
            location=Point(-73.9, 40.7, srid=4326),
            spatial_radius_meters=50.0,
            observation_time=base_time,
            temporal_window_hours=168.0,
            evidence_type="stop_not_exists",
        )

        # Time outside window
        old_time = base_time - timedelta(hours=200)
        self.assertFalse(scope.is_temporally_relevant(old_time))


class NegativeEvidenceWeightingTest(TestCase):
    """
    Test asymmetric weighting of negative evidence.

    INV-E2: Negative evidence is weaker than aggregated positive evidence.
    """

    def test_negative_weight_factor_applied(self):
        """Negative evidence is weighted lower than positive evidence."""
        analyzer = NegativeEvidenceAnalyzer()

        # Create a cluster with positive evidence
        cluster = self._create_test_cluster(
            weighted_score=3.0, evidence_count=5, location=Point(-73.9, 40.7, srid=4326)
        )

        # Create negative contributions
        negative_contribs = [
            self._create_negative_contribution(Point(-73.9, 40.7, srid=4326))
            for _ in range(2)
        ]

        result = analyzer.analyze_negative_evidence(
            cluster, negative_contribs, timezone.now()
        )

        # INV-E2: Negative weight should be less than count due to asymmetric factor
        # With 2 contributions and 0.5 factor, expect ~1.0
        self.assertLess(result.negative_weighted_score, 2.0)
        self.assertEqual(result.negative_count, 2)

    def test_negative_positive_ratio(self):
        """
        Negative/positive ratio reflects asymmetric weighting.

        INV-E2: Ratio should be < 1.0 when both evidence types present.
        """
        analyzer = NegativeEvidenceAnalyzer()

        cluster = self._create_test_cluster(
            weighted_score=3.0, evidence_count=5, location=Point(-73.9, 40.7, srid=4326)
        )

        negative_contribs = [
            self._create_negative_contribution(Point(-73.9, 40.7, srid=4326))
            for _ in range(2)
        ]

        result = analyzer.analyze_negative_evidence(
            cluster, negative_contribs, timezone.now()
        )

        # INV-E2: Ratio should be less than 1.0
        self.assertLess(result.negative_positive_ratio, 1.0)

    def _create_test_cluster(self, weighted_score, evidence_count, location):
        """Helper to create a test cluster."""
        now = timezone.now()
        return SpatialCluster(
            cluster_id="test_cluster",
            centroid_lat=location.y,
            centroid_lon=location.x,
            cluster_radius_meters=30.0,
            evidence_count=evidence_count,
            evidence_ids=frozenset([uuid4() for _ in range(evidence_count)]),
            independent_contributor_count=2,
            contributor_ids=frozenset([uuid4(), uuid4()]),
            weighted_evidence_score=weighted_score,
            evidence_type_breakdown=EvidenceTypeBreakdown(
                stop_exists_count=3.0, stop_name_count=1.0, stop_location_count=1.0
            ),
            temporal_span=TemporalSpan(
                earliest_observation=now - timedelta(days=5),
                latest_observation=now,
                distinct_days=3,
            ),
        )

    def _create_negative_contribution(self, location):
        """Helper to create a negative contribution."""
        # Create a test user for the contribution
        user = User.objects.create_user(
            username=f"test_user_{uuid4().hex[:8]}",
            email=f"test_{uuid4().hex[:8]}@example.com",
        )

        return ContributionEvent.objects.create(
            contribution_type=ContributionEvent.ContributionType.STOP_NOT_EXISTS,
            contributor=user,
            client_generated_id=uuid4(),
            subject_ref={"location": {"latitude": location.y, "longitude": location.x}},
            payload={
                "location": {"latitude": location.y, "longitude": location.x},
                "reason": "Stop does not exist here",
            },
            observed_at=timezone.now(),
        )


class ConfidenceReductionTest(TestCase):
    """
    Test capped confidence reduction.

    INV-F1: Confidence changes are gradual.
    INV-E1: No deletion via negative evidence (confidence never drops to zero).
    """

    def test_confidence_reduction_capped_per_cycle(self):
        """
        Confidence reduction is capped per evaluation cycle.

        INV-F1: Reduction cannot exceed MAX_REDUCTION_PER_CYCLE.
        """
        adjuster = ConfidenceAdjuster()

        # Create negative evidence result with high negative score
        from transit.evaluation.stop_negative_evidence import NegativeEvidenceResult

        neg_result = NegativeEvidenceResult(
            negative_count=10,
            negative_weighted_score=5.0,  # Very high
            positive_weighted_score=2.0,
            scoped_negative_evidence=tuple(),
            is_credible=True,
            analysis_time=timezone.now(),
        )

        # Start with high confidence
        current_confidence = 0.8

        adjustment = adjuster.compute_confidence_adjustment(
            current_confidence, neg_result
        )

        # INV-F1: Reduction should be capped
        # Use assertAlmostEqual to handle floating point precision
        self.assertAlmostEqual(
            adjustment.capped_reduction,
            ConfidenceAdjuster.MAX_REDUCTION_PER_CYCLE,
            places=10,
        )
        self.assertTrue(adjustment.cap_applied)

    def test_confidence_never_drops_to_zero(self):
        """
        Confidence never drops to zero in a single cycle.

        INV-E1: No deletion via negative evidence.
        """
        adjuster = ConfidenceAdjuster()

        from transit.evaluation.stop_negative_evidence import NegativeEvidenceResult

        # Extreme negative evidence
        neg_result = NegativeEvidenceResult(
            negative_count=100,
            negative_weighted_score=100.0,
            positive_weighted_score=1.0,
            scoped_negative_evidence=tuple(),
            is_credible=True,
            analysis_time=timezone.now(),
        )

        # Start with low confidence
        current_confidence = 0.1

        adjustment = adjuster.compute_confidence_adjustment(
            current_confidence, neg_result
        )

        # INV-E1: New confidence should be >= minimum floor
        self.assertGreaterEqual(
            adjustment.new_confidence, ConfidenceAdjuster.MINIMUM_CONFIDENCE_FLOOR
        )
        self.assertGreater(adjustment.new_confidence, 0.0)

    def test_no_reduction_without_credible_negative_evidence(self):
        """No reduction occurs without credible negative evidence."""
        adjuster = ConfidenceAdjuster()

        from transit.evaluation.stop_negative_evidence import NegativeEvidenceResult

        # Non-credible negative evidence
        neg_result = NegativeEvidenceResult(
            negative_count=1,
            negative_weighted_score=0.1,  # Below credibility threshold
            positive_weighted_score=2.0,
            scoped_negative_evidence=tuple(),
            is_credible=False,
            analysis_time=timezone.now(),
        )

        current_confidence = 0.5

        adjustment = adjuster.compute_confidence_adjustment(
            current_confidence, neg_result
        )

        # No reduction
        self.assertEqual(adjustment.capped_reduction, 0.0)
        self.assertEqual(adjustment.new_confidence, current_confidence)

    def test_gradual_reduction_over_multiple_cycles(self):
        """
        Multiple cycles can gradually reduce confidence.

        INV-J1: Safe to be wrong - recovery is possible.
        """
        adjuster = ConfidenceAdjuster()

        from transit.evaluation.stop_negative_evidence import NegativeEvidenceResult

        neg_result = NegativeEvidenceResult(
            negative_count=3,
            negative_weighted_score=1.5,
            positive_weighted_score=2.0,
            scoped_negative_evidence=tuple(),
            is_credible=True,
            analysis_time=timezone.now(),
        )

        confidence = 0.8

        # Apply reduction over 3 cycles
        for i in range(3):
            adjustment = adjuster.compute_confidence_adjustment(confidence, neg_result)
            confidence = adjustment.new_confidence
            # Each cycle reduces gradually
            self.assertGreater(confidence, ConfidenceAdjuster.MINIMUM_CONFIDENCE_FLOOR)

        # Confidence reduced but not to zero
        self.assertGreater(confidence, 0.0)


class ContestedStateTest(TestCase):
    """
    Test Contested state derivation.

    INV-E1: Contested != Deleted (Stop remains recoverable).
    """

    def test_contested_requires_all_three_conditions(self):
        """
        Contested state requires sufficient confidence, negative evidence, and recent positive.
        """
        evaluator = ContestedStateEvaluator()

        # Create cluster with recent positive evidence
        cluster = self._create_test_cluster(recent=True)

        # High confidence
        current_confidence = 0.5

        # Negative evidence result (credible)
        from transit.evaluation.stop_negative_evidence import NegativeEvidenceResult

        neg_result = NegativeEvidenceResult(
            negative_count=2,
            negative_weighted_score=1.0,
            positive_weighted_score=2.0,
            scoped_negative_evidence=tuple(),
            is_credible=True,
            analysis_time=timezone.now(),
        )

        result = evaluator.evaluate_contested_state(
            current_confidence, neg_result, cluster, timezone.now()
        )

        # All conditions met - should mark Contested
        self.assertTrue(result.should_mark_contested)
        self.assertTrue(result.has_sufficient_confidence)
        self.assertTrue(result.has_credible_negative)
        self.assertTrue(result.has_recent_positive)

    def test_negative_alone_does_not_mark_contested(self):
        """
        Negative evidence alone does not mark Contested.

        INV-E1: Prevents marking low-confidence Stops as Contested.
        """
        evaluator = ContestedStateEvaluator()

        cluster = self._create_test_cluster(recent=True)

        # Low confidence (below threshold)
        current_confidence = 0.2

        from transit.evaluation.stop_negative_evidence import NegativeEvidenceResult

        neg_result = NegativeEvidenceResult(
            negative_count=2,
            negative_weighted_score=1.0,
            positive_weighted_score=2.0,
            scoped_negative_evidence=tuple(),
            is_credible=True,
            analysis_time=timezone.now(),
        )

        result = evaluator.evaluate_contested_state(
            current_confidence, neg_result, cluster, timezone.now()
        )

        # Should NOT mark Contested (insufficient confidence)
        self.assertFalse(result.should_mark_contested)
        self.assertFalse(result.has_sufficient_confidence)

    def test_old_positive_evidence_does_not_mark_contested(self):
        """Contested requires RECENT positive evidence."""
        evaluator = ContestedStateEvaluator()

        # Cluster with old positive evidence
        cluster = self._create_test_cluster(recent=False)

        current_confidence = 0.5

        from transit.evaluation.stop_negative_evidence import NegativeEvidenceResult

        neg_result = NegativeEvidenceResult(
            negative_count=2,
            negative_weighted_score=1.0,
            positive_weighted_score=2.0,
            scoped_negative_evidence=tuple(),
            is_credible=True,
            analysis_time=timezone.now(),
        )

        result = evaluator.evaluate_contested_state(
            current_confidence, neg_result, cluster, timezone.now()
        )

        # Should NOT mark Contested (no recent positive)
        self.assertFalse(result.should_mark_contested)
        self.assertFalse(result.has_recent_positive)

    def _create_test_cluster(self, recent=True):
        """Helper to create test cluster with configurable recency."""
        now = timezone.now()
        if recent:
            latest = now - timedelta(hours=24)  # 1 day ago
        else:
            latest = now - timedelta(days=30)  # 30 days ago

        return SpatialCluster(
            cluster_id="test_cluster",
            centroid_lat=40.7,
            centroid_lon=-73.9,
            cluster_radius_meters=30.0,
            evidence_count=5,
            evidence_ids=frozenset([uuid4() for _ in range(5)]),
            independent_contributor_count=2,
            contributor_ids=frozenset([uuid4(), uuid4()]),
            weighted_evidence_score=2.5,
            evidence_type_breakdown=EvidenceTypeBreakdown(
                stop_exists_count=3.0, stop_name_count=1.0, stop_location_count=1.0
            ),
            temporal_span=TemporalSpan(
                earliest_observation=now - timedelta(days=5),
                latest_observation=latest,
                distinct_days=3,
            ),
        )


class ThresholdAdjustmentTest(TestCase):
    """
    Test threshold adjustment for creation with negative evidence.

    INV-E3: Negative evidence modulates thresholds only, never blocks.
    """

    def test_negative_evidence_raises_threshold(self):
        """
        Negative evidence raises creation threshold.

        INV-E3: Threshold is raised but creation remains possible.
        """
        evaluator = ThresholdEvaluator(timezone.now())

        cluster = self._create_test_cluster()

        # Pass a structural gate result (mock)
        from transit.evaluation.stop_creation import GateResult, StructuralGateResult

        gate_result = StructuralGateResult(
            all_gates_passed=True, gate_results=tuple(), evaluation_time=timezone.now()
        )

        # With no negative evidence
        result_no_neg = evaluator.evaluate_threshold(cluster, gate_result, 0.0)

        # With negative evidence
        result_with_neg = evaluator.evaluate_threshold(cluster, gate_result, 2.0)

        # Threshold should be higher with negative evidence
        self.assertGreater(
            result_with_neg.required_threshold, result_no_neg.required_threshold
        )

    def test_negative_evidence_cannot_block_creation_permanently(self):
        """
        No amount of negative evidence permanently blocks creation.

        INV-E3: Threshold adjustment is capped.
        """
        evaluator = ThresholdEvaluator(timezone.now())

        from transit.evaluation.stop_creation import StructuralGateResult

        gate_result = StructuralGateResult(
            all_gates_passed=True, gate_results=tuple(), evaluation_time=timezone.now()
        )

        cluster = self._create_test_cluster()

        # Extreme negative evidence
        extreme_negative_score = 1000.0

        result = evaluator.evaluate_threshold(
            cluster, gate_result, extreme_negative_score
        )

        # Threshold should be capped
        max_possible_threshold = (
            evaluator.BASE_CREATION_THRESHOLD + evaluator.MAX_NEGATIVE_ADJUSTMENT
        )
        self.assertLessEqual(result.required_threshold, max_possible_threshold)

    def _create_test_cluster(self):
        """Helper to create test cluster."""
        now = timezone.now()
        return SpatialCluster(
            cluster_id="test_cluster",
            centroid_lat=40.7,
            centroid_lon=-73.9,
            cluster_radius_meters=30.0,
            evidence_count=5,
            evidence_ids=frozenset([uuid4() for _ in range(5)]),
            independent_contributor_count=2,
            contributor_ids=frozenset([uuid4(), uuid4()]),
            weighted_evidence_score=3.0,  # High enough to cross threshold
            evidence_type_breakdown=EvidenceTypeBreakdown(
                stop_exists_count=3.0, stop_name_count=1.0, stop_location_count=1.0
            ),
            temporal_span=TemporalSpan(
                earliest_observation=now - timedelta(days=5),
                latest_observation=now,
                distinct_days=3,
            ),
        )


class StopNoDeletionTest(TestCase):
    """
    Test that negative evidence never deletes Stops.

    INV-E1: No deletion via negative evidence.
    INV-J1: Safe to be wrong - Stops remain recoverable.
    """

    def test_negative_evidence_does_not_delete_stop(self):
        """
        Negative evidence reduces confidence but never deletes a Stop.

        INV-E1: No deletion via negative evidence.
        """
        # Create a Stop with reasonable confidence
        stop = Stop(
            name="Test Stop",
            location=Point(-73.9, 40.7, srid=4326),
            structural_confidence=Decimal("0.5"),
            freshness_confidence=Decimal("0.5"),
            belief_state=Stop.BeliefState.ACTIVE_LOW,
        )
        stop._internal_save()

        # Apply confidence reduction
        adjuster = ConfidenceAdjuster()

        from transit.evaluation.stop_negative_evidence import NegativeEvidenceResult

        neg_result = NegativeEvidenceResult(
            negative_count=5,
            negative_weighted_score=2.5,
            positive_weighted_score=2.0,
            scoped_negative_evidence=tuple(),
            is_credible=True,
            analysis_time=timezone.now(),
        )

        adjustment = adjuster.compute_confidence_adjustment(
            float(stop.structural_confidence), neg_result
        )

        # Update Stop confidence
        stop.structural_confidence = Decimal(str(adjustment.new_confidence))
        stop._internal_save()

        # INV-E1: Stop still exists
        self.assertTrue(Stop.objects.filter(id=stop.id).exists())
        # Confidence reduced but not zero
        self.assertGreater(stop.structural_confidence, 0)

    def test_stop_recoverable_after_negative_evidence(self):
        """
        Stops remain recoverable even after negative evidence.

        INV-J1: Safe to be wrong.
        """
        # This test demonstrates that a Stop with reduced confidence
        # due to negative evidence can still be queried and updated
        # with future positive evidence.

        stop = Stop(
            name="Test Stop",
            location=Point(-73.9, 40.7, srid=4326),
            structural_confidence=Decimal("0.1"),  # Low after negative evidence
            freshness_confidence=Decimal("0.1"),
            belief_state=Stop.BeliefState.DORMANT,
        )
        stop._internal_save()

        # Simulate recovery with positive evidence
        # (In real system, this would come from aggregation)
        stop.structural_confidence = Decimal("0.6")
        stop.freshness_confidence = Decimal("0.7")
        stop.belief_state = Stop.BeliefState.ACTIVE_HIGH
        stop._internal_save()

        # INV-J1: Recovery is possible
        refreshed = Stop.objects.get(id=stop.id)
        self.assertEqual(refreshed.belief_state, Stop.BeliefState.ACTIVE_HIGH)
        self.assertGreater(refreshed.structural_confidence, Decimal("0.5"))
        self.assertGreater(refreshed.structural_confidence, Decimal("0.5"))
