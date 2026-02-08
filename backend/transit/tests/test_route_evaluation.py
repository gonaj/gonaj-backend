"""
Tests for Route evaluation and canonical truth derivation.

Sprint-11: Evaluation Generalization (Routes v0)

These tests enforce ALL mandatory invariants from the Sprint-11 specification:

MANDATORY EVALUATION INVARIANTS (Section 9):
1. Determinism: Same evidence set → identical canonical output
2. Replay safety: Re-running evaluation produces identical results
3. No Stop mutation: Stop canonical and belief state remain unchanged
4. Canonical dependency: If any referenced Stop is not canonical → Route is not canonical
5. No side effects: Evaluation performs no database writes

ADDITIONAL INVARIANTS FROM routes_rules_v_0.md:
- R-TRUTH-1: Binary canonical state only (Canonical / Not Canonical)
- R-TRUTH-2: Evidence-derived truth only
- R-TRUTH-3: Composite truth strictness (non-canonical Stop blocks Route)
- R-TRUTH-4: Stop–Route dependency direction (one-way, read-only)

EXPLICITLY FORBIDDEN (Sprint-11):
- Route belief states (Sprint-11 Section 5)
- Confidence decay models
- Database writes during evaluation
- UI mode reading
- Visibility concerns in evaluation

SCHEMA INVARIANTS (Sprint-11 Section 5):
- Route model MUST NOT have belief_state field
- Route model MUST NOT have BeliefState enum
- Binary canonical truth via RouteCanonicalDecision.is_canonical attribute
"""

from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from uuid import uuid4

from core.models import ContributionEvent
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone

from transit.evaluation import (
    EvaluationContext,
    RouteEvaluator,
    RouteEvidenceAggregator,
    check_route_stop_dependency,
    evaluate_route_canonical_status,
)
from transit.models import Route, Stop


User = get_user_model()


# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


class RouteEvaluationTestBase(TestCase):
    """Base class with common setup for Route evaluation tests."""

    def setUp(self):
        """Set up test users and base context."""
        self.user1 = User.objects.create_user(
            username="contributor1",
            email="contrib1@example.com",
            password="testpass123",
        )
        self.user2 = User.objects.create_user(
            username="contributor2",
            email="contrib2@example.com",
            password="testpass123",
        )
        self.user3 = User.objects.create_user(
            username="contributor3",
            email="contrib3@example.com",
            password="testpass123",
        )
        self.evaluation_time = timezone.now()
        self.context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=self.evaluation_time,
        )

    def create_route_exists_event(
        self,
        contributor,
        route_name="Test Route",
        route_short_name="TR",
        route_type="bus",
        observed_at=None,
        stop_ids=None,
    ):
        """Helper to create a route_exists contribution event."""
        if observed_at is None:
            observed_at = timezone.now()

        payload = {
            "route_name": route_name,
            "route_short_name": route_short_name,
            "route_type": route_type,
        }
        if stop_ids:
            payload["stop_ids"] = [str(sid) for sid in stop_ids]

        return ContributionEvent.objects.create(
            client_generated_id=uuid4(),
            contributor=contributor,
            contributor_fingerprint=contributor.id,
            contribution_type=ContributionEvent.ContributionType.ROUTE_EXISTS,
            subject_ref={
                "route_name": route_name,
                "route_short_name": route_short_name,
            },
            payload=payload,
            observed_at=observed_at,
        )

    def create_route_traversal_event(
        self,
        contributor,
        route_name="Test Route",
        route_short_name="TR",
        observed_at=None,
        traversal_stops=None,
    ):
        """Helper to create a route_traversal contribution event."""
        if observed_at is None:
            observed_at = timezone.now()

        payload = {
            "route_name": route_name,
            "route_short_name": route_short_name,
        }
        if traversal_stops:
            payload["traversal_stops"] = traversal_stops

        return ContributionEvent.objects.create(
            client_generated_id=uuid4(),
            contributor=contributor,
            contributor_fingerprint=contributor.id,
            contribution_type=ContributionEvent.ContributionType.ROUTE_TRAVERSAL,
            subject_ref={
                "route_name": route_name,
                "route_short_name": route_short_name,
            },
            payload=payload,
            observed_at=observed_at,
        )

    def create_canonical_stop(self, name="Test Stop", confidence=0.8):
        """
        Helper to create a canonical Stop for testing.

        A Stop is canonical if it exists in the DB and is currently valid
        (valid_until is NULL). Confidence is not a canonical status threshold.

        Uses _internal_save to bypass the guardrail.
        """
        stop = Stop(
            public_id=f"stop_{uuid4().hex[:8]}",
            name=name,
            location=Point(-74.0, 40.7, srid=4326),
            structural_confidence=Decimal(str(confidence)),
            freshness_confidence=Decimal(str(confidence)),
            valid_until=None,  # Currently valid = canonical
        )
        stop._internal_save()
        return stop

    def create_non_canonical_stop(self, name="Non-Canonical Stop"):
        """
        Helper to create a non-canonical Stop for testing.

        A Stop is non-canonical if it doesn't exist OR is no longer valid
        (has valid_until set). This simulates a retired/superseded Stop.
        """
        stop = Stop(
            public_id=f"stop_{uuid4().hex[:8]}",
            name=name,
            location=Point(-74.0, 40.7, srid=4326),
            structural_confidence=Decimal("0.8"),
            freshness_confidence=Decimal("0.8"),
            valid_until=datetime(2000, 1, 1, tzinfo=dt_timezone.utc),  # Fixed past date = non-canonical
        )
        stop._internal_save()
        return stop


# =============================================================================
# Invariant 1: Determinism Tests
# =============================================================================


class DeterminismInvariantTests(RouteEvaluationTestBase):
    """
    Tests for INVARIANT 1: Determinism

    Same evidence set → identical canonical output

    This is a MANDATORY invariant from Sprint-11 Section 9.
    """

    def test_same_evidence_produces_identical_output(self):
        """
        INV-B1: Same evidence must produce identical canonical output.

        Running evaluation twice with identical evidence must produce
        byte-identical results.
        """
        now = self.evaluation_time
        day1 = now - timedelta(days=2)
        day2 = now - timedelta(days=1)

        # Create evidence that meets canonical threshold
        events = [
            self.create_route_exists_event(self.user1, observed_at=day1),
            self.create_route_exists_event(self.user2, observed_at=day2),
            self.create_route_traversal_event(self.user3, observed_at=day2),
        ]

        # Run evaluation twice
        result1 = evaluate_route_canonical_status(events, self.context)
        result2 = evaluate_route_canonical_status(events, self.context)

        # Results must be identical
        self.assertEqual(len(result1.decisions), len(result2.decisions))
        self.assertEqual(
            result1.canonical_route_count, result2.canonical_route_count
        )
        self.assertEqual(
            result1.non_canonical_route_count, result2.non_canonical_route_count
        )

        # Each decision must match
        for d1, d2 in zip(result1.decisions, result2.decisions):
            self.assertEqual(d1.route_identity, d2.route_identity)
            self.assertEqual(d1.is_canonical, d2.is_canonical)
            self.assertEqual(d1.evidence_threshold_met, d2.evidence_threshold_met)
            self.assertEqual(d1.all_stops_canonical, d2.all_stops_canonical)

    def test_evidence_order_does_not_affect_output(self):
        """
        INV-B1: Evidence order must not affect canonical output.

        Shuffling evidence order must produce identical results.
        """
        now = self.evaluation_time
        day1 = now - timedelta(days=2)
        day2 = now - timedelta(days=1)

        # Create evidence
        event1 = self.create_route_exists_event(self.user1, observed_at=day1)
        event2 = self.create_route_exists_event(self.user2, observed_at=day2)
        event3 = self.create_route_traversal_event(self.user3, observed_at=day2)

        # Different orderings
        order1 = [event1, event2, event3]
        order2 = [event3, event1, event2]
        order3 = [event2, event3, event1]

        result1 = evaluate_route_canonical_status(order1, self.context)
        result2 = evaluate_route_canonical_status(order2, self.context)
        result3 = evaluate_route_canonical_status(order3, self.context)

        # All results must be identical
        self.assertEqual(len(result1.decisions), len(result2.decisions))
        self.assertEqual(len(result1.decisions), len(result3.decisions))

        for d1, d2, d3 in zip(result1.decisions, result2.decisions, result3.decisions):
            self.assertEqual(d1.is_canonical, d2.is_canonical)
            self.assertEqual(d1.is_canonical, d3.is_canonical)


# =============================================================================
# Invariant 2: Replay Safety Tests
# =============================================================================


class ReplaySafetyInvariantTests(RouteEvaluationTestBase):
    """
    Tests for INVARIANT 2: Replay Safety

    Re-running evaluation produces identical results.

    This is a MANDATORY invariant from Sprint-11 Section 9.
    """

    def test_replay_produces_identical_results(self):
        """
        INV-B2: Re-running evaluation must produce identical results.
        """
        now = self.evaluation_time
        day1 = now - timedelta(days=3)
        day2 = now - timedelta(days=2)
        day3 = now - timedelta(days=1)

        events = [
            self.create_route_exists_event(self.user1, observed_at=day1),
            self.create_route_exists_event(self.user2, observed_at=day2),
            self.create_route_traversal_event(self.user1, observed_at=day3),
            self.create_route_traversal_event(self.user3, observed_at=day3),
        ]

        # Run evaluation multiple times
        results = []
        for _ in range(5):
            result = evaluate_route_canonical_status(events, self.context)
            results.append(result)

        # All results must be identical
        first_result = results[0]
        for result in results[1:]:
            self.assertEqual(
                len(first_result.decisions), len(result.decisions)
            )
            for d1, d2 in zip(first_result.decisions, result.decisions):
                self.assertEqual(d1.is_canonical, d2.is_canonical)
                self.assertEqual(d1.reason, d2.reason)

    def test_aggregation_is_replay_safe(self):
        """
        Aggregation must produce identical results on replay.
        """
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=1)
            ),
            self.create_route_exists_event(
                self.user2, observed_at=now - timedelta(days=2)
            ),
        ]

        aggregator = RouteEvidenceAggregator()

        # Run aggregation multiple times
        result1 = aggregator.aggregate(events, now)
        result2 = aggregator.aggregate(events, now)
        result3 = aggregator.aggregate(events, now)

        # Results must be identical
        self.assertEqual(result1.cluster_count, result2.cluster_count)
        self.assertEqual(result1.cluster_count, result3.cluster_count)

        for c1, c2, c3 in zip(result1.clusters, result2.clusters, result3.clusters):
            self.assertEqual(c1.cluster_id, c2.cluster_id)
            self.assertEqual(c1.cluster_id, c3.cluster_id)
            self.assertEqual(c1.weighted_evidence_score, c2.weighted_evidence_score)
            self.assertEqual(c1.weighted_evidence_score, c3.weighted_evidence_score)


# =============================================================================
# Invariant 3: No Stop Mutation Tests
# =============================================================================


class NoStopMutationInvariantTests(RouteEvaluationTestBase):
    """
    Tests for INVARIANT 3: No Stop Mutation

    Stop canonical and belief state remain unchanged after Route evaluation.

    This is a MANDATORY invariant from Sprint-11 Section 9.
    R-TRUTH-4: Route evaluation MUST NOT modify Stop state.
    """

    def test_stop_state_unchanged_after_route_evaluation(self):
        """
        R-TRUTH-4: Route evaluation must not modify Stop state.

        Stop confidence, belief state, and canonical status must be
        identical before and after Route evaluation.
        """
        # Create canonical stops
        stop1 = self.create_canonical_stop("Stop A", confidence=0.9)
        stop2 = self.create_canonical_stop("Stop B", confidence=0.85)

        # Record initial state
        stop1_initial = {
            "structural_confidence": stop1.structural_confidence,
            "freshness_confidence": stop1.freshness_confidence,
            "belief_state": stop1.belief_state,
            "valid_until": stop1.valid_until,
        }
        stop2_initial = {
            "structural_confidence": stop2.structural_confidence,
            "freshness_confidence": stop2.freshness_confidence,
            "belief_state": stop2.belief_state,
            "valid_until": stop2.valid_until,
        }

        # Create route evidence referencing these stops
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1,
                observed_at=now - timedelta(days=2),
                stop_ids=[stop1.id, stop2.id],
            ),
            self.create_route_exists_event(
                self.user2,
                observed_at=now - timedelta(days=1),
                stop_ids=[stop1.id, stop2.id],
            ),
            self.create_route_traversal_event(
                self.user3,
                observed_at=now,
                traversal_stops=[
                    {"stop_id": str(stop1.id)},
                    {"stop_id": str(stop2.id)},
                ],
            ),
        ]

        # Run Route evaluation
        evaluator = RouteEvaluator(self.context)
        _result = evaluator.evaluate_routes(events)  # Result unused; testing side effects

        # Verify stops are unchanged
        stop1.refresh_from_db()
        stop2.refresh_from_db()

        self.assertEqual(
            stop1.structural_confidence, stop1_initial["structural_confidence"]
        )
        self.assertEqual(
            stop1.freshness_confidence, stop1_initial["freshness_confidence"]
        )
        self.assertEqual(stop1.belief_state, stop1_initial["belief_state"])
        self.assertEqual(stop1.valid_until, stop1_initial["valid_until"])

        self.assertEqual(
            stop2.structural_confidence, stop2_initial["structural_confidence"]
        )
        self.assertEqual(
            stop2.freshness_confidence, stop2_initial["freshness_confidence"]
        )
        self.assertEqual(stop2.belief_state, stop2_initial["belief_state"])
        self.assertEqual(stop2.valid_until, stop2_initial["valid_until"])

    def test_non_canonical_stop_unchanged_after_evaluation(self):
        """
        Non-canonical Stop state must not change during Route evaluation.

        Even when a Route is blocked by a non-canonical Stop, the Stop
        must not be modified in any way.
        """
        # Create non-canonical stop
        non_canonical_stop = self.create_non_canonical_stop("Weak Stop")

        initial_confidence = non_canonical_stop.structural_confidence

        # Create route evidence
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1,
                observed_at=now - timedelta(days=2),
                stop_ids=[non_canonical_stop.id],
            ),
            self.create_route_exists_event(
                self.user2,
                observed_at=now - timedelta(days=1),
                stop_ids=[non_canonical_stop.id],
            ),
            self.create_route_traversal_event(
                self.user3,
                observed_at=now,
                traversal_stops=[{"stop_id": str(non_canonical_stop.id)}],
            ),
        ]

        # Run evaluation (should NOT make route canonical due to stop)
        _result = evaluate_route_canonical_status(events, self.context)  # Result unused; testing side effects

        # Verify stop is unchanged
        non_canonical_stop.refresh_from_db()
        self.assertEqual(
            non_canonical_stop.structural_confidence, initial_confidence
        )


# =============================================================================
# Invariant 4: Canonical Dependency Tests
# =============================================================================


class CanonicalDependencyInvariantTests(RouteEvaluationTestBase):
    """
    Tests for INVARIANT 4: Canonical Dependency

    If any referenced Stop is not canonical → Route is not canonical.

    This is a MANDATORY invariant from Sprint-11 Section 9.
    R-TRUTH-3: Composite truth strictness.
    """

    def test_non_canonical_stop_blocks_route_canonical_status(self):
        """
        R-TRUTH-3: Non-canonical Stop MUST block Route canonical status.

        Even if route evidence meets all thresholds, a single non-canonical
        Stop prevents the Route from being canonical.
        """
        # Create one canonical and one non-canonical stop
        canonical_stop = self.create_canonical_stop("Good Stop", confidence=0.9)
        non_canonical_stop = self.create_non_canonical_stop("Weak Stop")

        # Create route evidence that meets ALL evidence thresholds
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1,
                observed_at=now - timedelta(days=3),
                stop_ids=[canonical_stop.id, non_canonical_stop.id],
            ),
            self.create_route_exists_event(
                self.user2,
                observed_at=now - timedelta(days=2),
                stop_ids=[canonical_stop.id, non_canonical_stop.id],
            ),
            self.create_route_traversal_event(
                self.user3,
                observed_at=now - timedelta(days=1),
                traversal_stops=[
                    {"stop_id": str(canonical_stop.id)},
                    {"stop_id": str(non_canonical_stop.id)},
                ],
            ),
        ]

        result = evaluate_route_canonical_status(events, self.context)

        # Route must NOT be canonical despite meeting evidence threshold
        self.assertEqual(len(result.decisions), 1)
        decision = result.decisions[0]

        self.assertFalse(decision.is_canonical)
        self.assertTrue(decision.evidence_threshold_met)  # Evidence IS sufficient
        self.assertFalse(decision.all_stops_canonical)  # But stops are not
        self.assertIn(non_canonical_stop.id, decision.non_canonical_stop_ids)

    def test_all_canonical_stops_allows_route_canonical(self):
        """
        Route CAN be canonical when all referenced Stops are canonical.
        """
        # Create canonical stops
        stop1 = self.create_canonical_stop("Stop A", confidence=0.9)
        stop2 = self.create_canonical_stop("Stop B", confidence=0.85)

        # Create route evidence that meets thresholds
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1,
                observed_at=now - timedelta(days=3),
                stop_ids=[stop1.id, stop2.id],
            ),
            self.create_route_exists_event(
                self.user2,
                observed_at=now - timedelta(days=2),
                stop_ids=[stop1.id, stop2.id],
            ),
            self.create_route_traversal_event(
                self.user3,
                observed_at=now - timedelta(days=1),
                traversal_stops=[
                    {"stop_id": str(stop1.id)},
                    {"stop_id": str(stop2.id)},
                ],
            ),
        ]

        result = evaluate_route_canonical_status(events, self.context)

        self.assertEqual(len(result.decisions), 1)
        decision = result.decisions[0]

        self.assertTrue(decision.is_canonical)
        self.assertTrue(decision.evidence_threshold_met)
        self.assertTrue(decision.all_stops_canonical)

    def test_route_without_stops_can_be_canonical(self):
        """
        Route without stop references can be canonical based on evidence alone.

        Pure route existence claims without stop associations should
        be able to become canonical if evidence threshold is met.
        """
        now = self.evaluation_time

        # Create route evidence WITHOUT stop references
        events = [
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=3)
            ),
            self.create_route_exists_event(
                self.user2, observed_at=now - timedelta(days=2)
            ),
            self.create_route_traversal_event(
                self.user3, observed_at=now - timedelta(days=1)
            ),
        ]

        result = evaluate_route_canonical_status(events, self.context)

        self.assertEqual(len(result.decisions), 1)
        decision = result.decisions[0]

        # Should be canonical - no stops to block it
        self.assertTrue(decision.is_canonical)
        self.assertTrue(decision.all_stops_canonical)  # Vacuously true
        self.assertEqual(decision.referenced_stop_count, 0)

    def test_check_route_stop_dependency_function(self):
        """
        Test the pure check_route_stop_dependency function.
        """
        stop1_id = uuid4()
        stop2_id = uuid4()
        stop3_id = uuid4()

        # All canonical
        status_all_canonical = {stop1_id: True, stop2_id: True, stop3_id: True}
        self.assertTrue(
            check_route_stop_dependency(
                frozenset([stop1_id, stop2_id, stop3_id]), status_all_canonical
            )
        )

        # One non-canonical
        status_one_bad = {stop1_id: True, stop2_id: False, stop3_id: True}
        self.assertFalse(
            check_route_stop_dependency(
                frozenset([stop1_id, stop2_id, stop3_id]), status_one_bad
            )
        )

        # Empty stops (vacuously true)
        self.assertTrue(check_route_stop_dependency(frozenset(), {}))

    def test_low_confidence_stop_is_still_canonical(self):
        """
        Stop canonical status is determined by existence + validity, NOT confidence.

        A Stop with very low structural_confidence (e.g., 0.1) but valid_until=NULL
        MUST be treated as canonical. Confidence is a creation gate, not a
        canonical status threshold. The canonical read API (canonical.py) exposes
        all Stops with valid_until=NULL without confidence filtering.

        This test permanently locks the Stop canonical definition used by
        Route dependency checks.
        """
        # Create a Stop with minimal confidence but currently valid
        low_confidence_stop = Stop(
            public_id=f"stop_{uuid4().hex[:8]}",
            name="Low Confidence Stop",
            location=Point(-74.0, 40.7, srid=4326),
            structural_confidence=Decimal("0.1"),
            freshness_confidence=Decimal("0.1"),
            valid_until=None,  # Currently valid = canonical regardless of confidence
        )
        low_confidence_stop._internal_save()

        # Create route evidence referencing only this low-confidence stop
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1,
                observed_at=now - timedelta(days=3),
                stop_ids=[low_confidence_stop.id],
            ),
            self.create_route_exists_event(
                self.user2,
                observed_at=now - timedelta(days=2),
                stop_ids=[low_confidence_stop.id],
            ),
            self.create_route_traversal_event(
                self.user3,
                observed_at=now - timedelta(days=1),
                traversal_stops=[{"stop_id": str(low_confidence_stop.id)}],
            ),
        ]

        result = evaluate_route_canonical_status(events, self.context)

        self.assertEqual(len(result.decisions), 1)
        decision = result.decisions[0]

        # The low-confidence Stop MUST NOT block Route canonical status
        self.assertTrue(
            decision.all_stops_canonical,
            "Stop with valid_until=NULL must be canonical regardless of confidence value",
        )
        self.assertTrue(
            decision.is_canonical,
            "Route must be canonical when all referenced Stops exist and are currently valid",
        )


# =============================================================================
# Invariant 5: No Side Effects Tests
# =============================================================================


class NoSideEffectsInvariantTests(RouteEvaluationTestBase):
    """
    Tests for INVARIANT 5: No Side Effects

    Evaluation performs no database writes.

    This is a MANDATORY invariant from Sprint-11 Section 9.
    """

    def test_no_route_created_during_evaluation(self):
        """
        Route evaluation must NOT create Route entities.

        Sprint-11 provides evaluation only, not creation.
        """
        initial_route_count = Route.objects.count()

        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=2)
            ),
            self.create_route_exists_event(
                self.user2, observed_at=now - timedelta(days=1)
            ),
            self.create_route_traversal_event(self.user3, observed_at=now),
        ]

        # Run evaluation
        _result = evaluate_route_canonical_status(events, self.context)  # Result unused; testing side effects

        # No Routes should be created
        final_route_count = Route.objects.count()
        self.assertEqual(initial_route_count, final_route_count)

    def test_no_database_writes_during_aggregation(self):
        """
        Aggregation must perform no database writes.
        """
        initial_stop_count = Stop.objects.count()
        initial_route_count = Route.objects.count()

        events = [
            self.create_route_exists_event(
                self.user1, observed_at=self.evaluation_time - timedelta(days=1)
            ),
        ]

        aggregator = RouteEvidenceAggregator()
        _result = aggregator.aggregate(events, self.evaluation_time)  # Result unused; testing side effects

        # No database changes
        self.assertEqual(Stop.objects.count(), initial_stop_count)
        self.assertEqual(Route.objects.count(), initial_route_count)

    def test_evaluation_result_is_pure_computation(self):
        """
        Evaluation result should be pure computation with no side effects.
        """
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=2)
            ),
            self.create_route_exists_event(
                self.user2, observed_at=now - timedelta(days=1)
            ),
            self.create_route_traversal_event(self.user3, observed_at=now),
        ]

        # Count all objects before
        stop_count_before = Stop.objects.count()
        route_count_before = Route.objects.count()
        event_count_before = ContributionEvent.objects.count()

        # Run evaluation
        evaluator = RouteEvaluator(self.context)
        _result = evaluator.evaluate_routes(events)  # Result unused; testing side effects

        # Count all objects after - must be unchanged
        self.assertEqual(Stop.objects.count(), stop_count_before)
        self.assertEqual(Route.objects.count(), route_count_before)
        self.assertEqual(ContributionEvent.objects.count(), event_count_before)


# =============================================================================
# Binary Canonical Truth Tests (R-TRUTH-1)
# =============================================================================


class BinaryCanonicalTruthTests(RouteEvaluationTestBase):
    """
    Tests for R-TRUTH-1: Binary Canonical State

    Route canonical truth is strictly binary: Canonical or Not Canonical.
    There are NO intermediate states.
    """

    def test_canonical_decision_is_boolean(self):
        """
        RouteCanonicalDecision.is_canonical must be a boolean.
        """
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=2)
            ),
            self.create_route_exists_event(
                self.user2, observed_at=now - timedelta(days=1)
            ),
            self.create_route_traversal_event(self.user3, observed_at=now),
        ]

        result = evaluate_route_canonical_status(events, self.context)

        for decision in result.decisions:
            self.assertIsInstance(decision.is_canonical, bool)

    def test_no_partial_canonical_state(self):
        """
        There must be no partial or intermediate canonical states.

        The decision must be strictly True or False.
        """
        # Test case where evidence is insufficient
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=1)
            ),
        ]

        result = evaluate_route_canonical_status(events, self.context)

        for decision in result.decisions:
            # Must be exactly True or False, not any other value
            self.assertIn(decision.is_canonical, [True, False])

    def test_no_confidence_values_in_decision(self):
        """
        RouteCanonicalDecision must not contain confidence values.

        R-TRUTH-1 forbids confidence scoring for routes in v0.
        """
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=2)
            ),
            self.create_route_exists_event(
                self.user2, observed_at=now - timedelta(days=1)
            ),
            self.create_route_traversal_event(self.user3, observed_at=now),
        ]

        result = evaluate_route_canonical_status(events, self.context)

        for decision in result.decisions:
            # Decision should not have confidence attributes
            self.assertFalse(hasattr(decision, "confidence"))
            self.assertFalse(hasattr(decision, "confidence_score"))
            self.assertFalse(hasattr(decision, "probability"))


# =============================================================================
# Evidence Threshold Tests
# =============================================================================


class EvidenceThresholdTests(RouteEvaluationTestBase):
    """
    Tests for evidence threshold requirements.

    Conservative thresholds for v0:
    - MIN_INDEPENDENT_CONTRIBUTORS = 2
    - MIN_DISTINCT_DAYS = 2
    - MIN_EVIDENCE_COUNT = 3
    """

    def test_single_contributor_not_canonical(self):
        """
        Route with evidence from single contributor cannot be canonical.
        """
        now = self.evaluation_time
        # Multiple observations from same user on different days
        events = [
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=3)
            ),
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=2)
            ),
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=1)
            ),
        ]

        result = evaluate_route_canonical_status(events, self.context)

        self.assertEqual(len(result.decisions), 1)
        self.assertFalse(result.decisions[0].is_canonical)
        self.assertFalse(result.decisions[0].evidence_threshold_met)

    def test_single_day_not_canonical(self):
        """
        Route with evidence from single day cannot be canonical.
        """
        now = self.evaluation_time
        # Multiple contributors but all on same day
        events = [
            self.create_route_exists_event(self.user1, observed_at=now),
            self.create_route_exists_event(self.user2, observed_at=now),
            self.create_route_traversal_event(self.user3, observed_at=now),
        ]

        result = evaluate_route_canonical_status(events, self.context)

        self.assertEqual(len(result.decisions), 1)
        self.assertFalse(result.decisions[0].is_canonical)
        self.assertFalse(result.decisions[0].evidence_threshold_met)

    def test_insufficient_evidence_count(self):
        """
        Route with fewer than MIN_EVIDENCE_COUNT items cannot be canonical.
        """
        now = self.evaluation_time
        # Only 2 pieces of evidence
        events = [
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=2)
            ),
            self.create_route_exists_event(
                self.user2, observed_at=now - timedelta(days=1)
            ),
        ]

        result = evaluate_route_canonical_status(events, self.context)

        self.assertEqual(len(result.decisions), 1)
        self.assertFalse(result.decisions[0].is_canonical)

    def test_meeting_all_thresholds_is_canonical(self):
        """
        Route meeting all thresholds can be canonical (if stops are canonical).
        """
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=3)
            ),
            self.create_route_exists_event(
                self.user2, observed_at=now - timedelta(days=2)
            ),
            self.create_route_traversal_event(
                self.user3, observed_at=now - timedelta(days=1)
            ),
        ]

        result = evaluate_route_canonical_status(events, self.context)

        self.assertEqual(len(result.decisions), 1)
        decision = result.decisions[0]
        self.assertTrue(decision.evidence_threshold_met)
        self.assertTrue(decision.is_canonical)  # No stops to block it


# =============================================================================
# Aggregation Tests
# =============================================================================


class RouteAggregationTests(RouteEvaluationTestBase):
    """
    Tests for route evidence aggregation.
    """

    def test_groups_evidence_by_route_identity(self):
        """
        Evidence should be grouped by route identity (name + short_name).
        """
        now = self.evaluation_time

        # Evidence for Route A
        route_a_events = [
            self.create_route_exists_event(
                self.user1,
                route_name="Route A",
                route_short_name="A",
                observed_at=now - timedelta(days=1),
            ),
            self.create_route_exists_event(
                self.user2,
                route_name="Route A",
                route_short_name="A",
                observed_at=now,
            ),
        ]

        # Evidence for Route B
        route_b_events = [
            self.create_route_exists_event(
                self.user1,
                route_name="Route B",
                route_short_name="B",
                observed_at=now - timedelta(days=1),
            ),
        ]

        all_events = route_a_events + route_b_events

        aggregator = RouteEvidenceAggregator()
        result = aggregator.aggregate(all_events, now)

        # Should have 2 clusters
        self.assertEqual(result.cluster_count, 2)

        cluster_ids = {c.cluster_id for c in result.clusters}
        self.assertIn("route:A:Route A", cluster_ids)
        self.assertIn("route:B:Route B", cluster_ids)

    def test_empty_evidence_produces_empty_result(self):
        """
        Empty evidence should produce empty aggregation result.
        """
        aggregator = RouteEvidenceAggregator()
        result = aggregator.aggregate([], self.evaluation_time)

        self.assertEqual(result.cluster_count, 0)
        self.assertEqual(result.total_evidence_processed, 0)

    def test_tracks_referenced_stops(self):
        """
        Aggregation should track all referenced stop IDs.
        """
        stop_id_1 = uuid4()
        stop_id_2 = uuid4()

        events = [
            self.create_route_exists_event(
                self.user1,
                observed_at=self.evaluation_time - timedelta(days=1),
                stop_ids=[stop_id_1, stop_id_2],
            ),
        ]

        aggregator = RouteEvidenceAggregator()
        result = aggregator.aggregate(events, self.evaluation_time)

        self.assertEqual(result.cluster_count, 1)
        cluster = result.clusters[0]

        self.assertIn(stop_id_1, cluster.referenced_stop_ids)
        self.assertIn(stop_id_2, cluster.referenced_stop_ids)


# =============================================================================
# Route Belief State Prohibition Tests
# =============================================================================


class RouteBeliefStateProhibitionTests(RouteEvaluationTestBase):
    """
    Tests that Route belief states are NOT introduced in v0.

    Sprint-11 Section 5 explicitly forbids:
    - Proposed / Active / Contested / Dormant analogues
    - Confidence decay models
    - Temporal belief transitions
    """

    def test_route_evaluator_has_no_belief_state_logic(self):
        """
        RouteEvaluator must not have belief state methods or attributes.
        """
        evaluator = RouteEvaluator(self.context)

        # Should not have belief state methods
        self.assertFalse(hasattr(evaluator, "calculate_belief_state"))
        self.assertFalse(hasattr(evaluator, "get_belief_state"))
        self.assertFalse(hasattr(evaluator, "update_belief_state"))

    def test_route_decision_has_no_belief_state(self):
        """
        RouteCanonicalDecision must not contain belief state.
        """
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=2)
            ),
            self.create_route_exists_event(
                self.user2, observed_at=now - timedelta(days=1)
            ),
            self.create_route_traversal_event(self.user3, observed_at=now),
        ]

        result = evaluate_route_canonical_status(events, self.context)

        for decision in result.decisions:
            self.assertFalse(hasattr(decision, "belief_state"))
            self.assertFalse(hasattr(decision, "proposed"))
            self.assertFalse(hasattr(decision, "active"))
            self.assertFalse(hasattr(decision, "contested"))
            self.assertFalse(hasattr(decision, "dormant"))


# =============================================================================
# Schema Invariant Tests (Sprint-11 Section 5)
# =============================================================================


class SchemaInvariantTests(TestCase):
    """
    Tests for Sprint-11 Section 5 schema constraints.

    Sprint-11 explicitly forbids Route belief states:
    - "Routes MUST NOT introduce belief states in v0"
    - "No Proposed / Active / Contested / Dormant analogues"
    - "Any future belief model requires routes_rules_v1.md"

    These tests prevent regression to pre-Sprint-11 schema.
    """

    def test_route_model_has_no_belief_state_field(self):
        """
        Route model MUST NOT have belief_state field (Sprint-11 Section 5).

        This prevents regression to the pre-Sprint-11 schema that had:
        - BeliefState enum (PROPOSED, ACTIVE_LOW, ACTIVE_HIGH, CONTESTED, DORMANT)
        - belief_state CharField with default=PROPOSED
        - Metadata claiming "Phase-2 Sprint-6"

        Sprint-11 explicitly forbids these constructs.
        """
        self.assertFalse(
            hasattr(Route, "belief_state"),
            "Route model must not have belief_state field (Sprint-11 Section 5)",
        )

    def test_route_model_has_no_belief_state_enum(self):
        """
        Route model MUST NOT have BeliefState enum (Sprint-11 Section 5).
        """
        self.assertFalse(
            hasattr(Route, "BeliefState"),
            "Route model must not have BeliefState enum (Sprint-11 Section 5)",
        )


# =============================================================================
# Evaluation Isolation Tests
# =============================================================================


class EvaluationIsolationTests(RouteEvaluationTestBase):
    """
    Tests for evaluation isolation (Section 6).

    Route evaluator:
    - MUST NOT read UI mode
    - MUST NOT branch on visibility concerns
    - MUST NOT import visibility-layer code
    """

    def test_evaluator_has_no_ui_mode_reference(self):
        """
        RouteEvaluator must not reference UI mode.
        """
        evaluator = RouteEvaluator(self.context)

        self.assertFalse(hasattr(evaluator, "ui_mode"))
        self.assertFalse(hasattr(evaluator, "get_ui_mode"))
        self.assertFalse(hasattr(evaluator, "_ui_mode"))

    def test_evaluation_ignores_request_context(self):
        """
        Evaluation must not depend on request context.
        """
        now = self.evaluation_time
        events = [
            self.create_route_exists_event(
                self.user1, observed_at=now - timedelta(days=2)
            ),
            self.create_route_exists_event(
                self.user2, observed_at=now - timedelta(days=1)
            ),
            self.create_route_traversal_event(self.user3, observed_at=now),
        ]

        # Create multiple contexts (simulating different request contexts)
        context1 = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=now,
        )
        context2 = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=now,
        )

        result1 = evaluate_route_canonical_status(events, context1)
        result2 = evaluate_route_canonical_status(events, context2)

        # Results must be identical
        self.assertEqual(len(result1.decisions), len(result2.decisions))
        for d1, d2 in zip(result1.decisions, result2.decisions):
            self.assertEqual(d1.is_canonical, d2.is_canonical)
