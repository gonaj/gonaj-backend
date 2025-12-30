"""
Tests for evaluation scaffolding and determinism.

Sprint-4A: Evaluation Scaffolding and Determinism

These tests verify the evaluation infrastructure without testing
any semantic evaluation logic. They ensure:

1. Deterministic ordering of evidence
2. Incremental vs batch entrypoint convergence
3. Canonical writes only occur via gateway
4. No evidence mutation occurs

INVARIANTS TESTED:
- INV-A1: No evidence loss
- INV-A2: Evidence immutability
- INV-B1: Deterministic evaluation
- INV-B2: Replay equivalence
- INV-I2: Canonical write protection

These tests do NOT verify:
- Stop creation logic (not implemented)
- Confidence calculations (not implemented)
- Decay logic (not implemented)
- Spatial clustering (not implemented)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from core.models import ContributionEvent
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone

from transit.evaluation import (
    BaseEvaluator,
    EvaluationContext,
    EvaluationResult,
    StopEvaluator,
    StopWriteGateway,
)
from transit.models import Stop

User = get_user_model()


class EvaluationContextTests(TestCase):
    """Tests for EvaluationContext immutability and validation."""

    def test_context_is_immutable(self):
        """EvaluationContext should be frozen (immutable)."""
        # INV-B1: Immutable context prevents accidental state changes
        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )

        with self.assertRaises(Exception):
            # Attempting to modify a frozen dataclass should fail
            context.ruleset_version = "v1"

    def test_context_requires_ruleset_version(self):
        """EvaluationContext should require ruleset_version."""
        with self.assertRaises(ValueError):
            EvaluationContext(
                ruleset_version="",
                evaluation_time=timezone.now(),
            )

    def test_context_requires_evaluation_time(self):
        """EvaluationContext should require evaluation_time."""
        with self.assertRaises(ValueError):
            EvaluationContext(
                ruleset_version="v0",
                evaluation_time=None,
            )


class EvaluationResultTests(TestCase):
    """Tests for EvaluationResult tracking."""

    def test_result_tracks_processed_evidence(self):
        """
        EvaluationResult should track all processed evidence IDs.

        INV-A1: No evidence loss - tracking ensures all evidence is recorded.
        """
        result = EvaluationResult()

        event_id_1 = uuid4()
        event_id_2 = uuid4()

        result.add_processed_evidence(event_id_1)
        result.add_processed_evidence(event_id_2)

        self.assertEqual(result.evidence_count, 2)
        self.assertIn(event_id_1, result.evidence_processed)
        self.assertIn(event_id_2, result.evidence_processed)

    def test_result_tracks_canonical_writes(self):
        """EvaluationResult should track canonical write count."""
        result = EvaluationResult()

        self.assertEqual(result.canonical_writes, 0)

        result.increment_canonical_writes()
        result.increment_canonical_writes()

        self.assertEqual(result.canonical_writes, 2)


class DeterministicOrderingTests(TestCase):
    """
    Tests for deterministic evidence ordering.

    INV-B1: Deterministic evaluation requires explicit, stable sort keys.
    """

    def setUp(self):
        """Set up test user for contributions."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def create_contribution_event(
        self,
        contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
        observed_at=None,
        submitted_at=None,
        client_generated_id=None,
    ):
        """Helper to create a ContributionEvent for testing."""
        if observed_at is None:
            observed_at = timezone.now()

        return ContributionEvent.objects.create(
            client_generated_id=client_generated_id or uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,  # Sprint-5B
            contribution_type=contribution_type,
            subject_ref={"lat": 40.7, "lon": -74.0},
            payload={"test": True},
            observed_at=observed_at,
        )

    def test_sort_by_observed_at_ascending(self):
        """
        Evidence should be sorted by observed_at ascending.

        INV-B1: Deterministic ordering requires explicit sort keys.
        """
        now = timezone.now()

        event1 = self.create_contribution_event(
            observed_at=now - timedelta(hours=2),
        )
        event2 = self.create_contribution_event(
            observed_at=now - timedelta(hours=1),
        )
        event3 = self.create_contribution_event(
            observed_at=now,
        )

        # Create evaluator and sort
        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=now,
        )
        evaluator = StopEvaluator(context)

        # Input in random order
        evidence = [event3, event1, event2]
        sorted_evidence = evaluator.sort_evidence_deterministically(evidence)

        # Should be sorted by observed_at ascending
        self.assertEqual(sorted_evidence[0].id, event1.id)
        self.assertEqual(sorted_evidence[1].id, event2.id)
        self.assertEqual(sorted_evidence[2].id, event3.id)

    def test_sort_tiebreaker_submitted_at(self):
        """
        When observed_at is equal, should sort by submitted_at.

        INV-B1: Multiple sort keys ensure deterministic ordering.
        """
        now = timezone.now()
        same_observed_time = now - timedelta(hours=1)

        # Create events with same observed_at but we cant control submitted_at
        # So we test that the sort is stable and uses id as final tiebreaker
        event1 = self.create_contribution_event(
            observed_at=same_observed_time,
        )
        event2 = self.create_contribution_event(
            observed_at=same_observed_time,
        )

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=now,
        )
        evaluator = StopEvaluator(context)

        # Sort both orders and verify consistency
        evidence_a = [event1, event2]
        evidence_b = [event2, event1]

        sorted_a = evaluator.sort_evidence_deterministically(evidence_a)
        sorted_b = evaluator.sort_evidence_deterministically(evidence_b)

        # Both should produce the same order
        self.assertEqual(
            [e.id for e in sorted_a],
            [e.id for e in sorted_b],
        )

    def test_sort_is_deterministic_across_runs(self):
        """
        Sorting the same evidence multiple times produces identical results.

        INV-B1: Given identical inputs, outputs must be byte-identical.
        """
        now = timezone.now()

        events = [
            self.create_contribution_event(
                observed_at=now - timedelta(minutes=i * 10),
            )
            for i in range(5)
        ]

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=now,
        )
        evaluator = StopEvaluator(context)

        # Sort multiple times
        sorted_1 = evaluator.sort_evidence_deterministically(events)
        sorted_2 = evaluator.sort_evidence_deterministically(events)
        sorted_3 = evaluator.sort_evidence_deterministically(events)

        # All should be identical
        ids_1 = [e.id for e in sorted_1]
        ids_2 = [e.id for e in sorted_2]
        ids_3 = [e.id for e in sorted_3]

        self.assertEqual(ids_1, ids_2)
        self.assertEqual(ids_2, ids_3)


class NoEvidenceLossTests(TestCase):
    """
    Tests for INV-A1: No evidence loss.

    No evaluation step may discard, ignore, or permanently exclude
    any ContributionEvent.
    """

    def setUp(self):
        """Set up test user for contributions."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def create_contribution_event(
        self,
        contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
    ):
        """Helper to create a ContributionEvent for testing."""
        return ContributionEvent.objects.create(
            client_generated_id=uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,  # Sprint-5B
            contribution_type=contribution_type,
            subject_ref={"lat": 40.7, "lon": -74.0},
            payload={"test": True},
            observed_at=timezone.now(),
        )

    def test_all_stop_evidence_is_processed(self):
        """
        All Stop-related evidence must be processed.

        INV-A1: No evidence loss - all submitted evidence is visible
        to evaluation logic.
        """
        # Create multiple Stop-related events
        events = [
            self.create_contribution_event(
                contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            ),
            self.create_contribution_event(
                contribution_type=ContributionEvent.ContributionType.STOP_NAME,
            ),
            self.create_contribution_event(
                contribution_type=ContributionEvent.ContributionType.STOP_LOCATION,
            ),
        ]

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        evaluator = StopEvaluator(context)

        result = evaluator.evaluate(events)

        # All events should be recorded as processed
        self.assertEqual(result.evidence_count, 3)
        for event in events:
            self.assertIn(
                event.id,
                result.evidence_processed,
                f"Evidence {event.id} was not processed - INV-A1 violation",
            )

    def test_negative_evidence_is_processed(self):
        """
        Negative evidence (stop_not_exists) must also be processed.

        INV-A1: Low-quality or conflicting evidence still participates.
        """
        event = self.create_contribution_event(
            contribution_type=ContributionEvent.ContributionType.STOP_NOT_EXISTS,
        )

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        evaluator = StopEvaluator(context)

        result = evaluator.evaluate([event])

        # Negative evidence should be processed
        self.assertEqual(result.evidence_count, 1)
        self.assertIn(event.id, result.evidence_processed)


class EvidenceImmutabilityTests(TestCase):
    """
    Tests for INV-A2: Evidence immutability.

    Evaluation must never mutate or annotate ContributionEvent records.
    """

    def setUp(self):
        """Set up test user for contributions."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def create_contribution_event(self):
        """Helper to create a ContributionEvent for testing."""
        return ContributionEvent.objects.create(
            client_generated_id=uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,  # Sprint-5B
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"lat": 40.7, "lon": -74.0},
            payload={"original": True},
            observed_at=timezone.now(),
        )

    def test_evidence_ids_unchanged_after_evaluation(self):
        """
        Evidence IDs must remain unchanged after evaluation.

        INV-A2: Evidence rows remain byte-identical before and after.
        """
        events = [self.create_contribution_event() for _ in range(3)]
        original_ids = [e.id for e in events]

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        evaluator = StopEvaluator(context)

        # Run evaluation
        evaluator.evaluate(events)

        # IDs should be unchanged
        current_ids = [e.id for e in events]
        self.assertEqual(original_ids, current_ids)

    def test_evidence_payload_unchanged_after_evaluation(self):
        """
        Evidence payload must remain unchanged after evaluation.

        INV-A2: No database writes occur on evidence tables during evaluation.
        """
        event = self.create_contribution_event()
        original_payload = event.payload.copy()

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        evaluator = StopEvaluator(context)

        # Run evaluation
        evaluator.evaluate([event])

        # Refresh from database
        event.refresh_from_db()

        # Payload should be unchanged
        self.assertEqual(event.payload, original_payload)

    def test_evidence_observed_at_unchanged_after_evaluation(self):
        """
        Evidence observed_at must remain unchanged after evaluation.

        INV-A2: Evidence immutability.
        """
        event = self.create_contribution_event()
        original_observed_at = event.observed_at

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        evaluator = StopEvaluator(context)

        # Run evaluation
        evaluator.evaluate([event])

        # Refresh from database
        event.refresh_from_db()

        # observed_at should be unchanged
        self.assertEqual(event.observed_at, original_observed_at)


class ReplayEquivalenceTests(TestCase):
    """
    Tests for INV-B2: Replay equivalence.

    Incremental evaluation and full recomputation must converge
    to the same canonical state.
    """

    def setUp(self):
        """Set up test user for contributions."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def create_contribution_event(self, observed_offset_minutes=0):
        """Helper to create a ContributionEvent for testing."""
        return ContributionEvent.objects.create(
            client_generated_id=uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,  # Sprint-5B
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"lat": 40.7, "lon": -74.0},
            payload={"test": True},
            observed_at=timezone.now() - timedelta(minutes=observed_offset_minutes),
        )

    def test_incremental_and_batch_process_same_evidence(self):
        """
        Incremental and batch evaluation must process the same evidence.

        INV-B2: Batch evaluation == incremental evaluation.
        """
        events = [
            self.create_contribution_event(observed_offset_minutes=i * 10)
            for i in range(5)
        ]

        now = timezone.now()

        # Run incremental evaluation
        context_inc = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=now,
            is_incremental=True,
        )
        evaluator_inc = StopEvaluator(context_inc)
        result_inc = evaluator_inc.evaluate_incremental(events)

        # Run full evaluation
        context_full = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=now,
            is_incremental=False,
        )
        evaluator_full = StopEvaluator(context_full)
        result_full = evaluator_full.evaluate_full(events)

        # Both should have processed the same evidence
        self.assertEqual(result_inc.evidence_count, result_full.evidence_count)
        self.assertEqual(
            set(result_inc.evidence_processed),
            set(result_full.evidence_processed),
        )

    def test_incremental_and_batch_produce_same_order(self):
        """
        Incremental and batch evaluation must process evidence in same order.

        INV-B2: No hidden state influences outcomes.
        """
        events = [
            self.create_contribution_event(observed_offset_minutes=i * 10)
            for i in range(5)
        ]

        now = timezone.now()

        # Run incremental evaluation
        context_inc = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=now,
            is_incremental=True,
        )
        evaluator_inc = StopEvaluator(context_inc)
        result_inc = evaluator_inc.evaluate_incremental(events)

        # Run full evaluation
        context_full = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=now,
            is_incremental=False,
        )
        evaluator_full = StopEvaluator(context_full)
        result_full = evaluator_full.evaluate_full(events)

        # The processing order should be identical
        self.assertEqual(
            result_inc.evidence_processed,
            result_full.evidence_processed,
        )


class CanonicalWriteProtectionTests(TestCase):
    """
    Tests for INV-I2: Canonical write protection.

    All canonical Stop writes must occur via the StopWriteGateway.
    """

    def test_direct_stop_save_raises_error(self):
        """
        Direct Stop.save() should raise NotImplementedError.

        INV-I2: Canonical entities cannot be directly saved.
        """
        stop = Stop(
            public_id="test-direct-save",
            name="Test Stop",
            location=Point(-74.0, 40.7),
        )

        with self.assertRaises(NotImplementedError) as context:
            stop.save()

        self.assertIn("canonical entity", str(context.exception).lower())

    def test_gateway_write_succeeds(self):
        """
        Writing through StopWriteGateway should succeed.

        INV-I2: Gateway is the controlled pathway for canonical writes.
        """
        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        gateway = StopWriteGateway(context)

        stop = Stop(
            public_id="test-gateway-write",
            name="Test Stop",
            location=Point(-74.0, 40.7),
            structural_confidence=Decimal("0.5"),
            freshness_confidence=Decimal("0.5"),
        )

        evidence_refs = [uuid4(), uuid4()]

        # Write through gateway
        saved_stop = gateway.write_stop(stop, evidence_refs)

        # Should have been saved
        self.assertIsNotNone(saved_stop.pk)
        self.assertEqual(saved_stop.name, "Test Stop")

    def test_gateway_sets_ruleset_version(self):
        """
        Gateway should set ruleset_version from context.

        INV-I2: Gateway controls all write metadata.
        """
        context = EvaluationContext(
            ruleset_version="v0.test",
            evaluation_time=timezone.now(),
        )
        gateway = StopWriteGateway(context)

        stop = Stop(
            public_id="test-ruleset-version",
            name="Test Stop",
            location=Point(-74.0, 40.7),
            structural_confidence=Decimal("0.5"),
            freshness_confidence=Decimal("0.5"),
        )

        saved_stop = gateway.write_stop(stop, [uuid4()])

        # Ruleset version should match context
        self.assertEqual(saved_stop.ruleset_version, "v0.test")

    def test_gateway_sets_evidence_refs(self):
        """
        Gateway should set evidence_refs from provided list.

        INV-I2: Gateway enforces provenance tracking.
        """
        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        gateway = StopWriteGateway(context)

        stop = Stop(
            public_id="test-evidence-refs",
            name="Test Stop",
            location=Point(-74.0, 40.7),
            structural_confidence=Decimal("0.5"),
            freshness_confidence=Decimal("0.5"),
        )

        evidence_refs = [uuid4(), uuid4()]

        saved_stop = gateway.write_stop(stop, evidence_refs)

        # Evidence refs should be set
        self.assertEqual(len(saved_stop.evidence_refs), 2)
        self.assertIn(str(evidence_refs[0]), saved_stop.evidence_refs)
        self.assertIn(str(evidence_refs[1]), saved_stop.evidence_refs)

    def test_gateway_tracks_write_count(self):
        """
        Gateway should track the number of writes performed.
        """
        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        gateway = StopWriteGateway(context)

        self.assertEqual(gateway.write_count, 0)

        # Write first stop
        stop1 = Stop(
            public_id="test-count-1",
            name="Test Stop 1",
            location=Point(-74.0, 40.7),
            structural_confidence=Decimal("0.5"),
            freshness_confidence=Decimal("0.5"),
        )
        gateway.write_stop(stop1, [uuid4()])

        self.assertEqual(gateway.write_count, 1)

        # Write second stop
        stop2 = Stop(
            public_id="test-count-2",
            name="Test Stop 2",
            location=Point(-74.1, 40.8),
            structural_confidence=Decimal("0.5"),
            freshness_confidence=Decimal("0.5"),
        )
        gateway.write_stop(stop2, [uuid4()])

        self.assertEqual(gateway.write_count, 2)

    def test_gateway_validates_stop_not_none(self):
        """
        Gateway should reject None stop.
        """
        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        gateway = StopWriteGateway(context)

        with self.assertRaises(ValueError) as ctx:
            gateway.write_stop(None, [uuid4()])

        self.assertIn("cannot be None", str(ctx.exception))

    def test_gateway_validates_evidence_refs_is_list(self):
        """
        Gateway should require evidence_refs to be a list.
        """
        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        gateway = StopWriteGateway(context)

        stop = Stop(
            public_id="test-invalid-refs",
            name="Test Stop",
            location=Point(-74.0, 40.7),
            structural_confidence=Decimal("0.5"),
            freshness_confidence=Decimal("0.5"),
        )

        with self.assertRaises(ValueError) as ctx:
            gateway.write_stop(stop, "not-a-list")

        self.assertIn("must be a list", str(ctx.exception))


class EvaluatorIntegrationTests(TestCase):
    """
    Integration tests for the full evaluation pipeline.

    These tests verify that the evaluator correctly integrates
    with the write gateway and produces consistent results.
    """

    def setUp(self):
        """Set up test user for contributions."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def create_contribution_event(
        self,
        contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
    ):
        """Helper to create a ContributionEvent for testing."""
        return ContributionEvent.objects.create(
            client_generated_id=uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,  # Sprint-5B
            contribution_type=contribution_type,
            subject_ref={"lat": 40.7, "lon": -74.0},
            payload={"test": True},
            observed_at=timezone.now(),
        )

    def test_evaluator_filters_stop_evidence(self):
        """
        Evaluator should only process Stop-related evidence types.
        """
        stop_event = self.create_contribution_event(
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
        )
        route_event = self.create_contribution_event(
            contribution_type=ContributionEvent.ContributionType.ROUTE_EXISTS,
        )

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        evaluator = StopEvaluator(context)

        result = evaluator.evaluate([stop_event, route_event])

        # Only Stop evidence should be processed
        self.assertEqual(result.evidence_count, 1)
        self.assertIn(stop_event.id, result.evidence_processed)
        self.assertNotIn(route_event.id, result.evidence_processed)

    def test_evaluator_gateway_is_accessible(self):
        """
        Evaluator should provide access to its write gateway.
        """
        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        evaluator = StopEvaluator(context)

        gateway = evaluator.write_gateway

        self.assertIsInstance(gateway, StopWriteGateway)
        self.assertEqual(gateway.context, context)

    def test_evaluation_result_reflects_gateway_writes(self):
        """
        Evaluation result should reflect writes from gateway.

        Sprint-4A Note: No actual writes occur in scaffolding,
        but the tracking mechanism should work.
        """
        events = [self.create_contribution_event() for _ in range(3)]

        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        evaluator = StopEvaluator(context)

        result = evaluator.evaluate(events)

        # In Sprint-4A, no actual writes occur (scaffolding only)
        self.assertEqual(result.canonical_writes, 0)

    def test_no_errors_with_empty_evidence(self):
        """
        Evaluation with empty evidence should not produce errors.
        """
        context = EvaluationContext(
            ruleset_version="v0",
            evaluation_time=timezone.now(),
        )
        evaluator = StopEvaluator(context)

        result = evaluator.evaluate([])

        self.assertEqual(result.evidence_count, 0)
        self.assertFalse(result.has_errors())
