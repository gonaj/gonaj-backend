"""
Tests for Sprint-5B: Evidence De-identification with Evaluation Safety.

These tests verify that:
1. Multiple deleted users still count as multiple independent contributors
2. Setting contributor = NULL does not change Stop creation behavior
3. Evaluation results are identical pre- and post-deletion

INVARIANTS TESTED:
- INV-E1: ContributionEvent is immutable after creation
- INV-I1: Contributor independence is counted correctly even after account deletion
- INV-I2: Account deletion must not reduce or inflate contributor counts
- PH-4: Replay determinism (evaluation before/after deletion produces identical results)
- PH-5: Independence is an event-level property (submission-time identity)

ARCHITECTURAL PRINCIPLES VERIFIED:
- PH-1: Evidence is permanent (no evidence deleted)
- PH-2: Identity is optional (user identity may disappear, evidence survives)
- PH-3: Belief is derived (canonical entities derived from evidence, not user lifecycle)
"""

import uuid
from datetime import timedelta

from accounts.services.account_deletion import AccountDeletionService
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from transit.evaluation import EvaluationContext, StopEvidenceAggregator
from transit.evaluation.stop_creation import StructuralGateEvaluator

from core.models import ContributionEvent

User = get_user_model()


class ContributorFingerprintInvariantsTests(TestCase):
    """
    Tests that contributor_fingerprint is correctly set and immutable.

    These tests verify the fundamental Sprint-5B requirement that
    contributor_fingerprint is an event-level property that survives
    user deletion.
    """

    def setUp(self):
        """Create test users."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_contributor_fingerprint_equals_contributor_id_at_creation(self):
        """
        contributor_fingerprint should equal contributor.id at creation time.

        This is the fundamental invariant that preserves identity for evaluation.
        """
        event = ContributionEvent.objects.create(
            client_generated_id=uuid.uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"lat": 40.7128, "lon": -74.0060},
            payload={"test": True},
            observed_at=timezone.now(),
        )

        self.assertEqual(event.contributor_fingerprint, self.user.id)

    def test_contributor_fingerprint_survives_contributor_nullification(self):
        """
        contributor_fingerprint remains unchanged when contributor FK is set to NULL.

        This is the core Sprint-5B guarantee: evaluation identity survives deletion.
        """
        event = ContributionEvent.objects.create(
            client_generated_id=uuid.uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"lat": 40.7128, "lon": -74.0060},
            payload={"test": True},
            observed_at=timezone.now(),
        )

        original_fingerprint = event.contributor_fingerprint

        # Simulate account deletion by setting contributor to NULL
        # (This is what SET_NULL does on user deletion)
        ContributionEvent.objects.filter(id=event.id).update(contributor=None)

        # Reload and verify fingerprint unchanged
        event.refresh_from_db()
        self.assertIsNone(event.contributor)
        self.assertEqual(event.contributor_fingerprint, original_fingerprint)

    def test_contributor_fingerprint_required_at_creation(self):
        """
        contributor_fingerprint must be explicitly provided at creation.

        Sprint-5B requirement: fingerprint is NEVER auto-derived.
        """
        with self.assertRaises(IntegrityError):
            ContributionEvent.objects.create(
                client_generated_id=uuid.uuid4(),
                contributor=self.user,
                # contributor_fingerprint intentionally omitted
                contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
                subject_ref={"lat": 40.7128, "lon": -74.0060},
                payload={"test": True},
                observed_at=timezone.now(),
            )


class IndependentContributorCountTests(TestCase):
    """
    Tests that independent contributor counts remain correct after account deletion.

    INV-I1: Contributor independence is counted correctly even after account deletion
    INV-I2: Account deletion must not reduce or inflate contributor counts
    """

    def setUp(self):
        """Create multiple test users."""
        self.users = []
        for i in range(3):
            user = User.objects.create_user(
                username=f"testuser{i}",
                email=f"test{i}@example.com",
                password="testpass123",
            )
            self.users.append(user)

        self.deletion_service = AccountDeletionService()

    def _create_contribution(self, user, lat_offset=0):
        """Helper to create a contribution from a user."""
        return ContributionEvent.objects.create(
            client_generated_id=uuid.uuid4(),
            contributor=user,
            contributor_fingerprint=user.id,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"lat": 40.7128 + lat_offset * 0.0001, "lon": -74.0060},
            payload={"test": True},
            observed_at=timezone.now() - timedelta(days=lat_offset),
            context={"gps_accuracy": 10.0},
        )

    def test_multiple_deleted_users_count_as_multiple_contributors(self):
        """
        Multiple deleted users should still count as multiple independent contributors.

        This is the PRIMARY Sprint-5B test case.
        """
        # Create contributions from 3 different users
        events = []
        for i, user in enumerate(self.users):
            event = self._create_contribution(user, lat_offset=i)
            events.append(event)

        # Aggregate before deletion
        aggregator = StopEvidenceAggregator()
        result_before = aggregator.aggregate(events, timezone.now())

        # Verify 3 independent contributors before deletion
        self.assertEqual(result_before.total_contributors, 3)
        if result_before.clusters:
            self.assertEqual(result_before.clusters[0].independent_contributor_count, 3)

        # Delete ALL users (this de-identifies their contributions)
        for user in self.users:
            self.deletion_service.delete_account(user)

        # Reload events from database
        events_after = list(
            ContributionEvent.objects.filter(id__in=[e.id for e in events])
        )

        # Verify contributor is now NULL for all
        for event in events_after:
            self.assertIsNone(event.contributor)
            # But fingerprint is preserved
            self.assertIsNotNone(event.contributor_fingerprint)

        # Aggregate AFTER deletion
        result_after = aggregator.aggregate(events_after, timezone.now())

        # CRITICAL: Still 3 independent contributors
        self.assertEqual(result_after.total_contributors, 3)
        if result_after.clusters:
            self.assertEqual(result_after.clusters[0].independent_contributor_count, 3)

    def test_single_deleted_user_contributions_not_collapsed(self):
        """
        Multiple contributions from a single deleted user should not be collapsed.

        The fingerprint ensures same-user contributions are still dampened correctly.
        """
        user = self.users[0]

        # Create multiple contributions from same user
        events = []
        for i in range(3):
            event = self._create_contribution(user, lat_offset=i)
            events.append(event)

        # Aggregate before deletion
        aggregator = StopEvidenceAggregator()
        result_before = aggregator.aggregate(events, timezone.now())

        # Only 1 contributor
        self.assertEqual(result_before.total_contributors, 1)

        # Delete user
        self.deletion_service.delete_account(user)

        # Reload events
        events_after = list(
            ContributionEvent.objects.filter(id__in=[e.id for e in events])
        )

        # Aggregate after deletion
        result_after = aggregator.aggregate(events_after, timezone.now())

        # Still only 1 contributor (not inflated)
        self.assertEqual(result_after.total_contributors, 1)


class EvaluationReplayDeterminismTests(TestCase):
    """
    Tests that evaluation produces identical results before and after account deletion.

    PH-4: Replay determinism - evaluation before and after deletion must produce
    identical canonical outcomes.
    """

    def setUp(self):
        """Create test users and contributions."""
        self.users = []
        for i in range(2):
            user = User.objects.create_user(
                username=f"evaluser{i}",
                email=f"eval{i}@example.com",
                password="testpass123",
            )
            self.users.append(user)

        self.deletion_service = AccountDeletionService()

    def _create_contribution(self, user, day_offset=0):
        """Helper to create a contribution."""
        return ContributionEvent.objects.create(
            client_generated_id=uuid.uuid4(),
            contributor=user,
            contributor_fingerprint=user.id,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"lat": 40.7128, "lon": -74.0060},
            payload={"test": True},
            observed_at=timezone.now() - timedelta(days=day_offset),
            context={"gps_accuracy": 10.0},
        )

    def test_aggregation_identical_before_and_after_deletion(self):
        """
        Aggregation results must be identical before and after user deletion.
        """
        # Create contributions
        events = []
        for i, user in enumerate(self.users):
            event = self._create_contribution(user, day_offset=i)
            events.append(event)

        # Aggregate before deletion
        aggregator = StopEvidenceAggregator()
        now = timezone.now()
        result_before = aggregator.aggregate(events, now)

        # Capture key metrics
        metrics_before = {
            "total_evidence": result_before.total_evidence_processed,
            "total_contributors": result_before.total_contributors,
            "cluster_count": result_before.cluster_count,
        }
        if result_before.clusters:
            metrics_before["cluster_0_evidence"] = result_before.clusters[
                0
            ].evidence_count
            metrics_before["cluster_0_contributors"] = result_before.clusters[
                0
            ].independent_contributor_count

        # Delete all users
        for user in self.users:
            self.deletion_service.delete_account(user)

        # Reload events
        events_after = list(
            ContributionEvent.objects.filter(id__in=[e.id for e in events])
        )

        # Aggregate after deletion with SAME timestamp
        result_after = aggregator.aggregate(events_after, now)

        # Capture metrics after
        metrics_after = {
            "total_evidence": result_after.total_evidence_processed,
            "total_contributors": result_after.total_contributors,
            "cluster_count": result_after.cluster_count,
        }
        if result_after.clusters:
            metrics_after["cluster_0_evidence"] = result_after.clusters[
                0
            ].evidence_count
            metrics_after["cluster_0_contributors"] = result_after.clusters[
                0
            ].independent_contributor_count

        # CRITICAL: Metrics must be identical
        self.assertEqual(metrics_before, metrics_after)

    def test_stop_creation_gate_unchanged_after_deletion(self):
        """
        Stop creation structural gates must produce same result after deletion.

        The independence gate (MIN_INDEPENDENT_CONTRIBUTORS) must not be affected.
        """
        # Create contributions from 2 users on different days
        events = []
        for i, user in enumerate(self.users):
            # Create multiple events per user on different days
            for day in range(2):
                event = ContributionEvent.objects.create(
                    client_generated_id=uuid.uuid4(),
                    contributor=user,
                    contributor_fingerprint=user.id,
                    contribution_type=(
                        ContributionEvent.ContributionType.STOP_EXISTS
                        if day == 0
                        else ContributionEvent.ContributionType.STOP_NAME
                    ),
                    subject_ref={"lat": 40.7128, "lon": -74.0060},
                    payload={"test": True},
                    observed_at=timezone.now() - timedelta(days=day + i * 2),
                    context={"gps_accuracy": 10.0},
                )
                events.append(event)

        # Aggregate before deletion
        aggregator = StopEvidenceAggregator()
        now = timezone.now()
        agg_result_before = aggregator.aggregate(events, now)

        gate_result_before = None
        if agg_result_before.clusters:
            gate_evaluator = StructuralGateEvaluator(evaluation_time=now)
            structural_result_before = gate_evaluator.evaluate_all_gates(
                agg_result_before.clusters[0]
            )
            gate_result_before = structural_result_before.all_gates_passed

        # Delete all users (this de-identifies their contributions)
        for user in self.users:
            self.deletion_service.delete_account(user)

        # Reload events
        events_after = list(
            ContributionEvent.objects.filter(id__in=[e.id for e in events])
        )

        # Re-aggregate
        agg_result_after = aggregator.aggregate(events_after, now)

        gate_result_after = None
        if agg_result_after.clusters:
            gate_evaluator_after = StructuralGateEvaluator(evaluation_time=now)
            structural_result_after = gate_evaluator_after.evaluate_all_gates(
                agg_result_after.clusters[0]
            )
            gate_result_after = structural_result_after.all_gates_passed

        # Gate result must be unchanged
        self.assertIsNotNone(gate_result_before)
        self.assertIsNotNone(gate_result_after)
        self.assertEqual(gate_result_before, gate_result_after)


class EvidencePreservationTests(TestCase):
    """
    Tests that evidence is preserved exactly as submitted, per PH-1.

    INV-E1: ContributionEvent is immutable after creation
    """

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username="preserveuser",
            email="preserve@example.com",
            password="testpass123",
        )
        self.deletion_service = AccountDeletionService()

    def test_evidence_payload_unchanged_after_deletion(self):
        """
        Evidence payload must remain byte-identical after account deletion.
        """
        original_payload = {
            "confidence": "high",
            "notes": "Saw the bus stop clearly",
            "extra": [1, 2, 3],
        }
        original_subject_ref = {"lat": 40.7128, "lon": -74.0060}
        original_observed_at = timezone.now() - timedelta(hours=2)

        event = ContributionEvent.objects.create(
            client_generated_id=uuid.uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,
            contribution_type=ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref=original_subject_ref,
            payload=original_payload,
            observed_at=original_observed_at,
            context={"gps_accuracy": 5.0},
        )

        event_id = event.id

        # Delete user
        self.deletion_service.delete_account(self.user)

        # Reload event
        event = ContributionEvent.objects.get(id=event_id)

        # All evidence fields must be unchanged
        self.assertEqual(event.payload, original_payload)
        self.assertEqual(event.subject_ref, original_subject_ref)
        self.assertEqual(event.observed_at, original_observed_at)
        self.assertEqual(
            event.contribution_type, ContributionEvent.ContributionType.STOP_EXISTS
        )

        # Only contributor should be NULL
        self.assertIsNone(event.contributor)
        # But fingerprint is preserved
        self.assertIsNotNone(event.contributor_fingerprint)
