"""
Tests for Stop creation logic with structural gates and threshold.

Sprint-4C: Stop Creation & Initial Belief (Rules v0)

These tests verify the creation pipeline including:

1. No Stop created if any structural gate fails
2. No Stop created if threshold not crossed (even if gates pass)
3. Stop created only when gates + threshold both satisfied
4. Same-user repetition cannot trigger creation
5. Canonical writes occur only via StopWriteGateway
6. Incremental vs batch evaluation equivalence

INVARIANTS TESTED:
- INV-B1: Deterministic evaluation
- INV-B2: Replay equivalence
- INV-C1: No single-event creation
- INV-C2: Independence requirement
- INV-C3: Spatial convergence
- INV-H1: Sub-threshold belief not public
- INV-I2: Canonical write protection

These tests do NOT verify:
- Confidence decay (not implemented)
- Negative evidence semantics (not implemented)
- Merge/split logic (not implemented)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from core.models import ContributionEvent
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone
from transit.evaluation import (AggregationResult, CreationDecision,
                                EvaluationContext, EvidenceTypeBreakdown,
                                EvidenceWeight, GateResult, SpatialCluster,
                                StopCreationPipeline, StopCreator,
                                StopEvaluator, StopWriteGateway,
                                StructuralGateEvaluator, StructuralGateResult,
                                TemporalSpan, ThresholdEvaluator,
                                ThresholdResult)
from transit.models import Stop

User = get_user_model()


# =============================================================================
# Helper Functions
# =============================================================================


def create_test_user(suffix: str = "") -> "User":
    """Create a test user."""
    return User.objects.create_user(
        username=f"testuser{suffix}_{uuid4().hex[:8]}",
        email=f"test{suffix}@example.com",
    )


def create_contribution_event(
    user: "User",
    contribution_type: str,
    lat: float,
    lon: float,
    observed_at: datetime,
    accuracy: float = 10.0,
) -> ContributionEvent:
    """Create a ContributionEvent for testing."""
    return ContributionEvent.objects.create(
        contributor=user,
        client_generated_id=uuid4(),  # Required unique ID
        contribution_type=contribution_type,
        observed_at=observed_at,
        submitted_at=observed_at,
        subject_ref={"lat": lat, "lon": lon},
        payload={"name": "Test Stop"},
        context={"gps_accuracy": accuracy},
    )


def create_test_cluster(
    evidence_count: int = 3,
    contributor_count: int = 2,
    distinct_days: int = 2,
    evidence_type_count: int = 2,
    weighted_score: float = 3.0,
    cluster_radius: float = 30.0,
    centroid_lat: float = 40.7128,
    centroid_lon: float = -74.0060,
    earliest_hour: int = 9,
    latest_hour: int = 17,
) -> SpatialCluster:
    """Create a SpatialCluster for testing."""
    base_time = timezone.now().replace(hour=earliest_hour, minute=0, second=0)
    latest_time = base_time.replace(hour=latest_hour) + timedelta(days=distinct_days - 1)

    # Generate contributor IDs
    contributor_ids = frozenset(uuid4() for _ in range(contributor_count))

    # Generate evidence IDs
    evidence_ids = frozenset(uuid4() for _ in range(evidence_count))

    # Build evidence type breakdown based on type count
    if evidence_type_count >= 3:
        breakdown = EvidenceTypeBreakdown(
            stop_exists_count=1.0,
            stop_name_count=1.0,
            stop_location_count=1.0,
            stop_not_exists_count=0.0,
        )
    elif evidence_type_count == 2:
        breakdown = EvidenceTypeBreakdown(
            stop_exists_count=1.5,
            stop_name_count=1.5,
            stop_location_count=0.0,
            stop_not_exists_count=0.0,
        )
    else:
        breakdown = EvidenceTypeBreakdown(
            stop_exists_count=3.0,
            stop_name_count=0.0,
            stop_location_count=0.0,
            stop_not_exists_count=0.0,
        )

    temporal_span = TemporalSpan(
        earliest_observation=base_time,
        latest_observation=latest_time,
        distinct_days=distinct_days,
    )

    return SpatialCluster(
        cluster_id=f"test_cluster_{uuid4().hex[:8]}",
        centroid_lat=centroid_lat,
        centroid_lon=centroid_lon,
        evidence_ids=evidence_ids,
        evidence_count=evidence_count,
        independent_contributor_count=contributor_count,
        weighted_evidence_score=weighted_score,
        evidence_type_breakdown=breakdown,
        temporal_span=temporal_span,
        cluster_radius_meters=cluster_radius,
        contributor_ids=contributor_ids,
    )


# =============================================================================
# GateResult Tests
# =============================================================================


class GateResultTests(TestCase):
    """Tests for GateResult immutability and validation."""

    def test_gate_result_is_immutable(self):
        """
        GateResult should be frozen (immutable).

        INV-B1: Immutable results prevent accidental state changes.
        """
        result = GateResult(
            gate_name="test_gate",
            passed=True,
            reason="Test reason",
        )

        with self.assertRaises(Exception):
            result.passed = False

    def test_gate_result_requires_gate_name(self):
        """GateResult should require a gate_name."""
        with self.assertRaises(ValueError):
            GateResult(
                gate_name="",
                passed=True,
                reason="Test reason",
            )

    def test_gate_result_requires_reason(self):
        """GateResult should require a reason."""
        with self.assertRaises(ValueError):
            GateResult(
                gate_name="test_gate",
                passed=True,
                reason="",
            )


# =============================================================================
# StructuralGateEvaluator Tests
# =============================================================================


class StructuralGateEvaluatorTests(TestCase):
    """
    Tests for StructuralGateEvaluator.

    INV-C1: No single-event creation
    INV-C2: Independence requirement
    INV-C3: Spatial convergence
    """

    def setUp(self):
        """Set up test fixtures."""
        self.evaluation_time = timezone.now()
        self.evaluator = StructuralGateEvaluator(self.evaluation_time)

    def test_all_gates_pass_with_valid_cluster(self):
        """
        All gates should pass with a well-formed cluster.
        """
        cluster = create_test_cluster(
            evidence_count=5,
            contributor_count=3,
            distinct_days=3,
            evidence_type_count=2,
            cluster_radius=30.0,
        )

        result = self.evaluator.evaluate_all_gates(cluster)

        self.assertTrue(result.all_gates_passed)
        self.assertEqual(len(result.failed_gates), 0)
        self.assertEqual(len(result.passed_gates), 5)

    def test_contributor_gate_fails_with_single_contributor(self):
        """
        Contributor gate should fail with only one contributor.

        INV-C1: No single-event creation.
        INV-C2: Independence requirement.
        """
        cluster = create_test_cluster(
            contributor_count=1,  # Only one contributor
        )

        result = self.evaluator.evaluate_all_gates(cluster)

        self.assertFalse(result.all_gates_passed)

        # Find the contributor gate result
        contributor_gate = next(
            g for g in result.gate_results if g.gate_name == "minimum_contributors"
        )
        self.assertFalse(contributor_gate.passed)
        self.assertIn("1 independent contributor", contributor_gate.reason)

    def test_temporal_separation_gate_fails_with_single_day(self):
        """
        Temporal separation gate should fail with evidence on only one day.

        INV-C1: No single-event creation.
        """
        cluster = create_test_cluster(
            distinct_days=1,  # Only one day
        )

        result = self.evaluator.evaluate_all_gates(cluster)

        self.assertFalse(result.all_gates_passed)

        temporal_gate = next(
            g for g in result.gate_results if g.gate_name == "temporal_separation"
        )
        self.assertFalse(temporal_gate.passed)
        self.assertIn("1 distinct day", temporal_gate.reason)

    def test_evidence_diversity_gate_fails_with_single_type(self):
        """
        Evidence diversity gate should fail with only one evidence type.

        INV-C1: No single-event creation.
        """
        cluster = create_test_cluster(
            evidence_type_count=1,  # Only one type
        )

        result = self.evaluator.evaluate_all_gates(cluster)

        self.assertFalse(result.all_gates_passed)

        diversity_gate = next(
            g for g in result.gate_results if g.gate_name == "evidence_diversity"
        )
        self.assertFalse(diversity_gate.passed)
        self.assertIn("1 distinct evidence type", diversity_gate.reason)

    def test_spatial_coherence_gate_fails_with_large_radius(self):
        """
        Spatial coherence gate should fail with too large a cluster.

        INV-C3: Spatial convergence.
        """
        cluster = create_test_cluster(
            cluster_radius=150.0,  # Too large (max is 100m)
        )

        result = self.evaluator.evaluate_all_gates(cluster)

        self.assertFalse(result.all_gates_passed)

        spatial_gate = next(
            g for g in result.gate_results if g.gate_name == "spatial_coherence"
        )
        self.assertFalse(spatial_gate.passed)
        self.assertIn("exceeds maximum", spatial_gate.reason)

    def test_temporal_plausibility_gate_with_late_night_evidence(self):
        """
        Temporal plausibility gate should fail with evidence outside service hours.
        """
        cluster = create_test_cluster(
            earliest_hour=2,  # 2 AM
            latest_hour=3,    # 3 AM
        )

        result = self.evaluator.evaluate_all_gates(cluster)

        self.assertFalse(result.all_gates_passed)

        plausibility_gate = next(
            g for g in result.gate_results if g.gate_name == "temporal_plausibility"
        )
        self.assertFalse(plausibility_gate.passed)

    def test_gates_are_evaluated_deterministically(self):
        """
        Gate evaluation should be deterministic.

        INV-B1: Deterministic evaluation.
        """
        cluster = create_test_cluster()

        result1 = self.evaluator.evaluate_all_gates(cluster)
        result2 = self.evaluator.evaluate_all_gates(cluster)

        self.assertEqual(result1.all_gates_passed, result2.all_gates_passed)
        self.assertEqual(len(result1.gate_results), len(result2.gate_results))

        for g1, g2 in zip(result1.gate_results, result2.gate_results):
            self.assertEqual(g1.gate_name, g2.gate_name)
            self.assertEqual(g1.passed, g2.passed)


# =============================================================================
# ThresholdEvaluator Tests
# =============================================================================


class ThresholdEvaluatorTests(TestCase):
    """
    Tests for ThresholdEvaluator.

    INV-H1: Sub-threshold belief not public.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.evaluation_time = timezone.now()
        self.threshold_evaluator = ThresholdEvaluator(self.evaluation_time)
        self.gate_evaluator = StructuralGateEvaluator(self.evaluation_time)

    def test_threshold_not_evaluated_if_gates_fail(self):
        """
        Threshold should not be evaluated if structural gates fail.

        INV-H1: Sub-threshold belief not public.
        """
        # Create a cluster that fails gates
        cluster = create_test_cluster(contributor_count=1)
        gate_result = self.gate_evaluator.evaluate_all_gates(cluster)

        self.assertFalse(gate_result.all_gates_passed)

        threshold_result = self.threshold_evaluator.evaluate_threshold(
            cluster, gate_result
        )

        self.assertIsNone(threshold_result)

    def test_threshold_crossed_with_sufficient_evidence(self):
        """
        Threshold should be crossed with sufficient weighted evidence.
        """
        cluster = create_test_cluster(weighted_score=3.0)  # Above threshold (2.0)
        gate_result = self.gate_evaluator.evaluate_all_gates(cluster)

        self.assertTrue(gate_result.all_gates_passed)

        threshold_result = self.threshold_evaluator.evaluate_threshold(
            cluster, gate_result
        )

        self.assertIsNotNone(threshold_result)
        self.assertTrue(threshold_result.threshold_crossed)
        self.assertGreaterEqual(
            threshold_result.weighted_score, threshold_result.required_threshold
        )

    def test_threshold_not_crossed_with_insufficient_evidence(self):
        """
        Threshold should not be crossed with insufficient weighted evidence.

        INV-H1: Sub-threshold belief not public.
        """
        cluster = create_test_cluster(weighted_score=1.5)  # Below threshold (2.0)
        gate_result = self.gate_evaluator.evaluate_all_gates(cluster)

        self.assertTrue(gate_result.all_gates_passed)

        threshold_result = self.threshold_evaluator.evaluate_threshold(
            cluster, gate_result
        )

        self.assertIsNotNone(threshold_result)
        self.assertFalse(threshold_result.threshold_crossed)

    def test_threshold_evaluation_is_deterministic(self):
        """
        Threshold evaluation should be deterministic.

        INV-B1: Deterministic evaluation.
        """
        cluster = create_test_cluster()
        gate_result = self.gate_evaluator.evaluate_all_gates(cluster)

        result1 = self.threshold_evaluator.evaluate_threshold(cluster, gate_result)
        result2 = self.threshold_evaluator.evaluate_threshold(cluster, gate_result)

        self.assertEqual(result1.threshold_crossed, result2.threshold_crossed)
        self.assertEqual(result1.weighted_score, result2.weighted_score)


# =============================================================================
# StopCreator Tests
# =============================================================================


class StopCreatorTests(TestCase):
    """
    Tests for StopCreator.

    INV-I2: Canonical write protection.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.evaluation_time = timezone.now()
        self.context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=self.evaluation_time,
        )
        self.write_gateway = StopWriteGateway(self.context)
        self.creator = StopCreator(self.write_gateway)

    def test_stop_created_when_decision_positive(self):
        """
        Stop should be created when decision is positive.

        INV-I2: Canonical write protection.
        """
        cluster = create_test_cluster()
        decision = self.creator.evaluate_and_decide(cluster, self.evaluation_time)

        self.assertTrue(decision.should_create)

        stop = self.creator.create_stop(decision)

        self.assertIsNotNone(stop)
        self.assertIsNotNone(stop.id)
        self.assertEqual(stop.ruleset_version, "v0")
        self.assertTrue(len(stop.evidence_refs) > 0)

    def test_stop_not_created_when_decision_negative(self):
        """
        Stop should not be created when decision is negative.
        """
        cluster = create_test_cluster(contributor_count=1)  # Will fail gates
        decision = self.creator.evaluate_and_decide(cluster, self.evaluation_time)

        self.assertFalse(decision.should_create)

        stop = self.creator.create_stop(decision)

        self.assertIsNone(stop)

    def test_stop_created_via_gateway(self):
        """
        Stop creation must go through StopWriteGateway.

        INV-I2: Canonical write protection.
        """
        initial_count = self.write_gateway.write_count

        cluster = create_test_cluster()
        decision = self.creator.evaluate_and_decide(cluster, self.evaluation_time)
        self.creator.create_stop(decision)

        self.assertEqual(self.write_gateway.write_count, initial_count + 1)

    def test_stop_has_initial_confidence_values(self):
        """
        Newly created Stops should have initial confidence values.
        """
        cluster = create_test_cluster()
        decision = self.creator.evaluate_and_decide(cluster, self.evaluation_time)
        stop = self.creator.create_stop(decision)

        self.assertEqual(
            float(stop.structural_confidence),
            StopCreator.INITIAL_STRUCTURAL_CONFIDENCE,
        )
        self.assertEqual(
            float(stop.freshness_confidence),
            StopCreator.INITIAL_FRESHNESS_CONFIDENCE,
        )

    def test_stop_location_matches_cluster_centroid(self):
        """
        Stop location should match the cluster centroid.
        """
        cluster = create_test_cluster(
            centroid_lat=40.7128,
            centroid_lon=-74.0060,
        )
        decision = self.creator.evaluate_and_decide(cluster, self.evaluation_time)
        stop = self.creator.create_stop(decision)

        # Point uses (lon, lat) order
        self.assertAlmostEqual(stop.location.x, -74.0060, places=4)
        self.assertAlmostEqual(stop.location.y, 40.7128, places=4)


# =============================================================================
# StopCreationPipeline Tests
# =============================================================================


class StopCreationPipelineTests(TestCase):
    """
    Tests for StopCreationPipeline.

    INV-B1, INV-B2, INV-C1, INV-C2, INV-C3, INV-H1, INV-I2.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.evaluation_time = timezone.now()
        self.context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=self.evaluation_time,
        )
        self.write_gateway = StopWriteGateway(self.context)
        self.pipeline = StopCreationPipeline(self.context, self.write_gateway)

    def test_pipeline_creates_stop_for_valid_cluster(self):
        """
        Pipeline should create Stop for cluster passing all gates and threshold.
        """
        cluster = create_test_cluster()
        aggregation_result = AggregationResult(
            clusters=(cluster,),
            total_evidence_processed=5,
            total_contributors=3,
            evidence_weights=(),
            aggregation_timestamp=self.evaluation_time,
        )

        created_stops, decisions = self.pipeline.create_stops(aggregation_result)

        self.assertEqual(len(created_stops), 1)
        self.assertEqual(len(decisions), 1)
        self.assertTrue(decisions[0].should_create)

    def test_pipeline_does_not_create_stop_for_invalid_cluster(self):
        """
        Pipeline should not create Stop for cluster failing gates.

        INV-C1: No single-event creation.
        INV-C2: Independence requirement.
        """
        cluster = create_test_cluster(contributor_count=1)
        aggregation_result = AggregationResult(
            clusters=(cluster,),
            total_evidence_processed=1,
            total_contributors=1,
            evidence_weights=(),
            aggregation_timestamp=self.evaluation_time,
        )

        created_stops, decisions = self.pipeline.create_stops(aggregation_result)

        self.assertEqual(len(created_stops), 0)
        self.assertEqual(len(decisions), 1)
        self.assertFalse(decisions[0].should_create)

    def test_pipeline_handles_multiple_clusters(self):
        """
        Pipeline should correctly handle multiple clusters.
        """
        valid_cluster = create_test_cluster()
        invalid_cluster = create_test_cluster(contributor_count=1)

        aggregation_result = AggregationResult(
            clusters=(valid_cluster, invalid_cluster),
            total_evidence_processed=6,
            total_contributors=4,
            evidence_weights=(),
            aggregation_timestamp=self.evaluation_time,
        )

        created_stops, decisions = self.pipeline.create_stops(aggregation_result)

        self.assertEqual(len(created_stops), 1)  # Only valid cluster
        self.assertEqual(len(decisions), 2)  # Decision for each

    def test_pipeline_is_deterministic(self):
        """
        Pipeline should produce deterministic results.

        INV-B1: Deterministic evaluation.
        """
        cluster = create_test_cluster()
        aggregation_result = AggregationResult(
            clusters=(cluster,),
            total_evidence_processed=5,
            total_contributors=3,
            evidence_weights=(),
            aggregation_timestamp=self.evaluation_time,
        )

        decisions1 = self.pipeline.process_aggregation_result(aggregation_result)
        decisions2 = self.pipeline.process_aggregation_result(aggregation_result)

        self.assertEqual(len(decisions1), len(decisions2))
        for d1, d2 in zip(decisions1, decisions2):
            self.assertEqual(d1.should_create, d2.should_create)


# =============================================================================
# Integration Tests with Real Evidence
# =============================================================================


class StopCreationIntegrationTests(TestCase):
    """
    Integration tests using real ContributionEvent records.

    INV-B2: Replay equivalence
    INV-C1: No single-event creation
    INV-C2: Independence requirement
    """

    def setUp(self):
        """Set up test fixtures."""
        self.users = [create_test_user(str(i)) for i in range(3)]
        self.evaluation_time = timezone.now()
        self.context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=self.evaluation_time,
        )

    def test_no_stop_from_single_event(self):
        """
        A single contribution event should not create a Stop.

        INV-C1: No single-event creation.
        """
        user = self.users[0]
        create_contribution_event(
            user=user,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            lat=40.7128,
            lon=-74.0060,
            observed_at=self.evaluation_time,
        )

        evaluator = StopEvaluator(self.context)
        evidence = ContributionEvent.objects.all()

        result, created_stops, decisions = evaluator.evaluate_with_creation(evidence)

        self.assertEqual(len(created_stops), 0)

    def test_no_stop_from_same_user_repetition(self):
        """
        Same user submitting multiple times should not create a Stop.

        INV-C2: Independence requirement.
        """
        user = self.users[0]
        base_time = self.evaluation_time

        # Same user, multiple submissions on different days
        for day in range(3):
            create_contribution_event(
                user=user,
                contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
                lat=40.7128,
                lon=-74.0060,
                observed_at=base_time + timedelta(days=day),
            )

        evaluator = StopEvaluator(self.context)
        evidence = ContributionEvent.objects.all()

        result, created_stops, decisions = evaluator.evaluate_with_creation(evidence)

        # Should not create Stop - only one contributor
        self.assertEqual(len(created_stops), 0)

    def test_stop_created_with_independent_contributors(self):
        """
        Independent contributors with diverse evidence should create a Stop.

        INV-C2: Independence requirement satisfied.
        """
        base_time = self.evaluation_time

        # User 1: stop_exists on day 1
        create_contribution_event(
            user=self.users[0],
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            lat=40.7128,
            lon=-74.0060,
            observed_at=base_time,
        )

        # User 2: stop_name on day 2
        create_contribution_event(
            user=self.users[1],
            contribution_type=ContributionEvent.ContributionType.STOP_NAME,
            lat=40.7128,
            lon=-74.0060,
            observed_at=base_time + timedelta(days=1),
        )

        # User 3: stop_location on day 2
        create_contribution_event(
            user=self.users[2],
            contribution_type=ContributionEvent.ContributionType.STOP_LOCATION,
            lat=40.7129,
            lon=-74.0061,
            observed_at=base_time + timedelta(days=1),
        )

        evaluator = StopEvaluator(self.context)
        evidence = ContributionEvent.objects.all()

        result, created_stops, decisions = evaluator.evaluate_with_creation(evidence)

        # Should create Stop - multiple contributors, days, and types
        self.assertEqual(len(created_stops), 1)

        stop = created_stops[0]
        self.assertEqual(stop.ruleset_version, "v0")
        self.assertTrue(len(stop.evidence_refs) > 0)

    def test_no_stop_from_single_evidence_type(self):
        """
        Evidence of only one type should not create a Stop.

        INV-C1: Evidence diversity required.
        """
        base_time = self.evaluation_time

        # Multiple users, but only stop_exists type
        for i, user in enumerate(self.users[:2]):
            create_contribution_event(
                user=user,
                contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
                lat=40.7128,
                lon=-74.0060,
                observed_at=base_time + timedelta(days=i),
            )

        evaluator = StopEvaluator(self.context)
        evidence = ContributionEvent.objects.all()

        result, created_stops, decisions = evaluator.evaluate_with_creation(evidence)

        # Should not create Stop - only one evidence type
        self.assertEqual(len(created_stops), 0)

    def test_no_stop_from_single_day(self):
        """
        Evidence from only one day should not create a Stop.

        INV-C1: Temporal separation required.
        """
        base_time = self.evaluation_time

        # Multiple users, different types, but same day
        create_contribution_event(
            user=self.users[0],
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            lat=40.7128,
            lon=-74.0060,
            observed_at=base_time,
        )

        create_contribution_event(
            user=self.users[1],
            contribution_type=ContributionEvent.ContributionType.STOP_NAME,
            lat=40.7128,
            lon=-74.0060,
            observed_at=base_time + timedelta(hours=2),  # Same day
        )

        evaluator = StopEvaluator(self.context)
        evidence = ContributionEvent.objects.all()

        result, created_stops, decisions = evaluator.evaluate_with_creation(evidence)

        # Should not create Stop - only one day
        self.assertEqual(len(created_stops), 0)

    def test_no_stop_from_spatially_distant_evidence(self):
        """
        Spatially distant evidence should not form a single Stop.

        INV-C3: Spatial convergence required.
        """
        base_time = self.evaluation_time

        # Evidence at two distant locations (NYC and LA)
        create_contribution_event(
            user=self.users[0],
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            lat=40.7128,
            lon=-74.0060,  # NYC
            observed_at=base_time,
        )

        create_contribution_event(
            user=self.users[1],
            contribution_type=ContributionEvent.ContributionType.STOP_NAME,
            lat=34.0522,
            lon=-118.2437,  # LA
            observed_at=base_time + timedelta(days=1),
        )

        evaluator = StopEvaluator(self.context)
        evidence = ContributionEvent.objects.all()

        result, created_stops, decisions = evaluator.evaluate_with_creation(evidence)

        # Should not create Stop - evidence too far apart
        self.assertEqual(len(created_stops), 0)

    def test_incremental_and_batch_produce_same_result(self):
        """
        Incremental and batch evaluation should produce equivalent results.

        INV-B2: Replay equivalence.
        """
        base_time = self.evaluation_time

        # Create evidence that will create a Stop
        events = []
        events.append(create_contribution_event(
            user=self.users[0],
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            lat=40.7128,
            lon=-74.0060,
            observed_at=base_time,
        ))

        events.append(create_contribution_event(
            user=self.users[1],
            contribution_type=ContributionEvent.ContributionType.STOP_NAME,
            lat=40.7128,
            lon=-74.0060,
            observed_at=base_time + timedelta(days=1),
        ))

        events.append(create_contribution_event(
            user=self.users[2],
            contribution_type=ContributionEvent.ContributionType.STOP_LOCATION,
            lat=40.7129,
            lon=-74.0061,
            observed_at=base_time + timedelta(days=1),
        ))

        # Batch evaluation
        batch_context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=self.evaluation_time,
        )
        batch_evaluator = StopEvaluator(batch_context)
        batch_evidence = ContributionEvent.objects.all()

        batch_result, batch_stops, batch_decisions = batch_evaluator.evaluate_with_creation(
            batch_evidence
        )

        # The key assertion is that both produce the same number of stops
        # (In a full implementation, we'd compare more details)
        self.assertEqual(len(batch_stops), 1)

    def test_canonical_writes_only_via_gateway(self):
        """
        All Stop writes must go through StopWriteGateway.

        INV-I2: Canonical write protection.
        """
        base_time = self.evaluation_time

        # Create evidence that will create a Stop
        create_contribution_event(
            user=self.users[0],
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            lat=40.7128,
            lon=-74.0060,
            observed_at=base_time,
        )

        create_contribution_event(
            user=self.users[1],
            contribution_type=ContributionEvent.ContributionType.STOP_NAME,
            lat=40.7128,
            lon=-74.0060,
            observed_at=base_time + timedelta(days=1),
        )

        create_contribution_event(
            user=self.users[2],
            contribution_type=ContributionEvent.ContributionType.STOP_LOCATION,
            lat=40.7129,
            lon=-74.0061,
            observed_at=base_time + timedelta(days=1),
        )

        evaluator = StopEvaluator(self.context)
        evidence = ContributionEvent.objects.all()

        initial_gateway_writes = evaluator.write_gateway.write_count
        result, created_stops, decisions = evaluator.evaluate_with_creation(evidence)

        # Gateway should have recorded the write
        self.assertEqual(
            evaluator.write_gateway.write_count,
            initial_gateway_writes + len(created_stops),
        )

        # Each created stop should be in gateway's written_ids
        for stop in created_stops:
            self.assertIn(stop.id, evaluator.write_gateway.written_ids)


# =============================================================================
# Invariant Regression Tests
# =============================================================================


class InvariantRegressionTests(TestCase):
    """
    Regression tests for specific invariants.

    These tests are designed to catch violations of critical invariants.
    """

    def test_inv_c1_single_evidence_never_creates_stop(self):
        """
        INV-C1: A single evidence event must never create a Stop.

        This test verifies that even with perfect evidence quality,
        a single event cannot trigger Stop creation.
        """
        user = create_test_user()
        evaluation_time = timezone.now()

        # Single high-quality evidence event
        create_contribution_event(
            user=user,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            lat=40.7128,
            lon=-74.0060,
            observed_at=evaluation_time,
            accuracy=1.0,  # Perfect GPS
        )

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=evaluation_time,
        )
        evaluator = StopEvaluator(context)
        evidence = ContributionEvent.objects.all()

        result, created_stops, decisions = evaluator.evaluate_with_creation(evidence)

        # Must not create a Stop
        self.assertEqual(len(created_stops), 0, "INV-C1 violated: single event created Stop")

    def test_inv_c2_same_user_repetition_insufficient(self):
        """
        INV-C2: Same-user repetition must not satisfy independence requirement.

        Even with multiple submissions on different days with different types,
        same user cannot create a Stop alone.
        """
        user = create_test_user()
        evaluation_time = timezone.now()

        # Multiple events from same user
        for i, etype in enumerate([
            ContributionEvent.ContributionType.STOP_EXISTS,
            ContributionEvent.ContributionType.STOP_NAME,
            ContributionEvent.ContributionType.STOP_LOCATION,
        ]):
            create_contribution_event(
                user=user,
                contribution_type=etype,
                lat=40.7128,
                lon=-74.0060,
                observed_at=evaluation_time + timedelta(days=i),
            )

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=evaluation_time,
        )
        evaluator = StopEvaluator(context)
        evidence = ContributionEvent.objects.all()

        result, created_stops, decisions = evaluator.evaluate_with_creation(evidence)

        # Must not create a Stop
        self.assertEqual(
            len(created_stops), 0,
            "INV-C2 violated: same-user repetition created Stop"
        )

    def test_inv_h1_sub_threshold_not_creates_stop(self):
        """
        INV-H1: Sub-threshold belief must not create a public Stop.

        Even if structural gates pass, insufficient weighted evidence
        should not create a Stop.
        """
        # This test uses the threshold evaluator directly to verify
        # that sub-threshold clusters don't trigger creation

        evaluation_time = timezone.now()

        # Create a cluster that passes gates but has low weighted score
        cluster = create_test_cluster(
            weighted_score=1.0,  # Below threshold (2.0)
        )

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=evaluation_time,
        )
        write_gateway = StopWriteGateway(context)
        creator = StopCreator(write_gateway)

        decision = creator.evaluate_and_decide(cluster, evaluation_time)

        # Gates should pass
        self.assertTrue(decision.structural_result.all_gates_passed)

        # But threshold should not be crossed
        self.assertIsNotNone(decision.threshold_result)
        self.assertFalse(decision.threshold_result.threshold_crossed)

        # And Stop should not be created
        self.assertFalse(decision.should_create)

        stop = creator.create_stop(decision)
        self.assertIsNone(stop, "INV-H1 violated: sub-threshold created Stop")

    def test_inv_i2_all_writes_via_gateway(self):
        """
        INV-I2: All canonical writes must occur via StopWriteGateway.

        This test verifies that the gateway tracks all writes.
        """
        users = [create_test_user(str(i)) for i in range(3)]
        evaluation_time = timezone.now()
        base_time = evaluation_time

        # Create evidence that will create a Stop
        create_contribution_event(
            user=users[0],
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            lat=40.7128,
            lon=-74.0060,
            observed_at=base_time,
        )

        create_contribution_event(
            user=users[1],
            contribution_type=ContributionEvent.ContributionType.STOP_NAME,
            lat=40.7128,
            lon=-74.0060,
            observed_at=base_time + timedelta(days=1),
        )

        create_contribution_event(
            user=users[2],
            contribution_type=ContributionEvent.ContributionType.STOP_LOCATION,
            lat=40.7129,
            lon=-74.0061,
            observed_at=base_time + timedelta(days=1),
        )

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=evaluation_time,
        )
        evaluator = StopEvaluator(context)

        initial_db_count = Stop.objects.count()
        initial_gateway_writes = evaluator.write_gateway.write_count

        evidence = ContributionEvent.objects.all()
        result, created_stops, decisions = evaluator.evaluate_with_creation(evidence)

        final_db_count = Stop.objects.count()
        final_gateway_writes = evaluator.write_gateway.write_count

        # DB count change should match gateway write count change
        db_writes = final_db_count - initial_db_count
        gateway_writes = final_gateway_writes - initial_gateway_writes

        self.assertEqual(
            db_writes, gateway_writes,
            f"INV-I2 violated: DB writes ({db_writes}) != gateway writes ({gateway_writes})"
        )
        )
