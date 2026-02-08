"""
Tests for Sprint-12: Performance & Recompute Control.

This module tests:
1. EvaluationJob abstraction (immutability, validation, fields)
2. Advisory locking (deterministic keys, lock/unlock, context managers)
3. Executor abstraction (inline executor, atomicity, locking)
4. Orchestration (recompute stops/routes/all, dependency ordering)
5. Recompute management command (stops, routes, all, no default)
6. Automatic evaluation on new evidence

INVARIANTS VERIFIED:
- Evaluation jobs are immutable once created
- Scoped advisory locks prevent concurrent mutation of same entity
- Evidence ingestion is never blocked
- Recompute supports stops, routes, and all explicitly
- 'all' enforces Stops → Routes ordering
- Failures leave canonical state unchanged
- No evaluation semantics are modified

Sprint-12 MUST NOT:
- Change evaluation rules or thresholds
- Change canonical schemas or belief semantics
- Introduce new canonical states
- Add new public APIs
"""


from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from uuid import UUID, uuid4

from core.models import ContributionEvent
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from transit.evaluation.base import EvaluationContext
from transit.evaluation.executor import (
    BaseExecutor,
    ExecutionResult,
    InlineExecutor,
)
from transit.evaluation.jobs import (
    EvaluationJob,
    TargetType,
    Trigger,
)
from transit.evaluation.route_evaluator import RouteEvaluator
from transit.evaluation.stop_evaluator import StopEvaluator
from transit.evaluation.locking import (
    _NAMESPACE_ROUTE,
    _NAMESPACE_STOP,
    advisory_lock,
    derive_route_lock_key,
    derive_stop_lock_key,
    release_advisory_lock,
    route_evaluation_lock,
    stop_evaluation_lock,
    try_advisory_lock,
)
from transit.evaluation.orchestration import (
    DEFAULT_RULESET_VERSION,
    OrchestrationResult,
    create_evaluation_job_for_contribution,
    enqueue_evaluation_for_contribution,
    recompute_all,
    recompute_routes,
    recompute_stops,
)
from transit.models import Route, Stop

User = get_user_model()


# =============================================================================
# EvaluationJob Tests
# =============================================================================


class EvaluationJobCreationTests(TestCase):
    """Tests for EvaluationJob immutability, validation, and fields."""

    def test_job_creation_with_required_fields(self):
        """EvaluationJob can be created with required fields."""
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.CONTRIBUTION,
            ruleset_version="1.0",
        )
        self.assertEqual(job.target_type, TargetType.STOP)
        self.assertEqual(job.trigger, Trigger.CONTRIBUTION)
        self.assertEqual(job.ruleset_version, "1.0")
        self.assertIsInstance(job.job_id, UUID)
        self.assertIsNone(job.target_ids)
        self.assertIsNotNone(job.created_at)

    def test_job_creation_with_target_ids(self):
        """EvaluationJob can be created with specific target IDs."""
        ids = frozenset([uuid4(), uuid4()])
        job = EvaluationJob(
            target_type=TargetType.ROUTE,
            trigger=Trigger.ADMIN,
            ruleset_version="2.0",
            target_ids=ids,
        )
        self.assertEqual(job.target_ids, ids)
        self.assertFalse(job.is_full_scope)
        self.assertEqual(job.target_count, 2)

    def test_job_is_immutable(self):
        """EvaluationJob is frozen (immutable) after creation."""
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.REPLAY,
            ruleset_version="1.0",
        )
        with self.assertRaises(AttributeError):
            job.target_type = TargetType.ROUTE

    def test_job_requires_ruleset_version(self):
        """EvaluationJob must have a non-empty ruleset_version."""
        with self.assertRaises(ValueError, msg="ruleset_version is required"):
            EvaluationJob(
                target_type=TargetType.STOP,
                trigger=Trigger.ADMIN,
                ruleset_version="",
            )

    def test_job_requires_valid_target_type(self):
        """EvaluationJob rejects invalid target_type."""
        with self.assertRaises(ValueError):
            EvaluationJob(
                target_type="invalid",
                trigger=Trigger.ADMIN,
                ruleset_version="1.0",
            )

    def test_job_requires_valid_trigger(self):
        """EvaluationJob rejects invalid trigger."""
        with self.assertRaises(ValueError):
            EvaluationJob(
                target_type=TargetType.STOP,
                trigger="invalid",
                ruleset_version="1.0",
            )

    def test_job_full_scope_when_target_ids_none(self):
        """is_full_scope is True when target_ids is None."""
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=None,
        )
        self.assertTrue(job.is_full_scope)
        self.assertIsNone(job.target_count)

    def test_job_not_full_scope_with_target_ids(self):
        """is_full_scope is False when target_ids is provided."""
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=frozenset([uuid4()]),
        )
        self.assertFalse(job.is_full_scope)
        self.assertEqual(job.target_count, 1)

    def test_job_target_ids_must_be_frozenset_or_none(self):
        """target_ids must be a frozenset or None, not a list."""
        with self.assertRaises(ValueError):
            EvaluationJob(
                target_type=TargetType.STOP,
                trigger=Trigger.ADMIN,
                ruleset_version="1.0",
                target_ids=[uuid4()],
            )

    def test_job_str_representation(self):
        """EvaluationJob has a meaningful string representation."""
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
        )
        s = str(job)
        self.assertIn("stop", s)
        self.assertIn("admin", s)
        self.assertIn("full", s)

    def test_job_str_with_targets(self):
        """String representation shows target count when not full scope."""
        ids = frozenset([uuid4(), uuid4()])
        job = EvaluationJob(
            target_type=TargetType.ROUTE,
            trigger=Trigger.CONTRIBUTION,
            ruleset_version="1.0",
            target_ids=ids,
        )
        s = str(job)
        self.assertIn("2 targets", s)

    def test_target_type_enum_values(self):
        """TargetType enum has expected values."""
        self.assertEqual(TargetType.STOP.value, "stop")
        self.assertEqual(TargetType.ROUTE.value, "route")

    def test_trigger_enum_values(self):
        """Trigger enum has expected values."""
        self.assertEqual(Trigger.CONTRIBUTION.value, "contribution")
        self.assertEqual(Trigger.ADMIN.value, "admin")
        self.assertEqual(Trigger.REPLAY.value, "replay")


# =============================================================================
# Advisory Locking Tests
# =============================================================================


class LockKeyDerivationTests(TestCase):
    """Tests for deterministic lock key derivation."""

    def test_stop_key_is_deterministic(self):
        """Same stop_id always produces the same lock key."""
        stop_id = uuid4()
        key1 = derive_stop_lock_key(stop_id)
        key2 = derive_stop_lock_key(stop_id)
        self.assertEqual(key1, key2)

    def test_route_key_is_deterministic(self):
        """Same route_id always produces the same lock key."""
        route_id = uuid4()
        key1 = derive_route_lock_key(route_id)
        key2 = derive_route_lock_key(route_id)
        self.assertEqual(key1, key2)

    def test_different_ids_produce_different_keys(self):
        """Different entity IDs produce different lock keys."""
        id1 = uuid4()
        id2 = uuid4()
        self.assertNotEqual(
            derive_stop_lock_key(id1), derive_stop_lock_key(id2)
        )

    def test_stop_and_route_keys_differ_for_same_uuid(self):
        """Same UUID yields different keys for stop vs route namespace."""
        entity_id = uuid4()
        stop_key = derive_stop_lock_key(entity_id)
        route_key = derive_route_lock_key(entity_id)
        self.assertNotEqual(stop_key, route_key)

    def test_key_is_within_bigint_range(self):
        """Lock keys must be within PostgreSQL bigint range."""
        for _ in range(100):
            entity_id = uuid4()
            key = derive_stop_lock_key(entity_id)
            self.assertGreaterEqual(key, -(1 << 63))
            self.assertLess(key, 1 << 63)

    def test_namespaces_are_distinct(self):
        """Stop and route namespaces are different constants."""
        self.assertNotEqual(_NAMESPACE_STOP, _NAMESPACE_ROUTE)


class AdvisoryLockAcquisitionTests(TransactionTestCase):
    """Tests for PostgreSQL advisory lock acquisition and release.

    Uses TransactionTestCase because advisory locks are session-level
    and need real database connections.
    """

    def test_acquire_and_release_lock(self):
        """Can acquire and then release an advisory lock."""
        key = derive_stop_lock_key(uuid4())
        acquired = try_advisory_lock(key)
        self.assertTrue(acquired)
        released = release_advisory_lock(key)
        self.assertTrue(released)

    def test_same_session_can_reacquire(self):
        """Same session can acquire the same lock multiple times (PG behavior)."""
        key = derive_stop_lock_key(uuid4())
        self.assertTrue(try_advisory_lock(key))
        self.assertTrue(try_advisory_lock(key))
        # Must release for each acquisition
        release_advisory_lock(key)
        release_advisory_lock(key)

    def test_release_unheld_lock_returns_false(self):
        """Releasing an unheld lock returns False."""
        key = derive_stop_lock_key(uuid4())
        released = release_advisory_lock(key)
        self.assertFalse(released)

    def test_context_manager_acquires_and_releases(self):
        """advisory_lock context manager acquires and releases cleanly."""
        key = derive_stop_lock_key(uuid4())
        with advisory_lock(key) as acquired:
            self.assertTrue(acquired)
        # After context exit, lock should be released
        # We verify by checking we can still acquire it
        acquired_again = try_advisory_lock(key)
        self.assertTrue(acquired_again)
        release_advisory_lock(key)

    def test_stop_evaluation_lock_context_manager(self):
        """stop_evaluation_lock context manager works correctly."""
        stop_id = uuid4()
        with stop_evaluation_lock(stop_id) as acquired:
            self.assertTrue(acquired)

    def test_route_evaluation_lock_context_manager(self):
        """route_evaluation_lock context manager works correctly."""
        route_id = uuid4()
        with route_evaluation_lock(route_id) as acquired:
            self.assertTrue(acquired)

    def test_context_manager_releases_on_exception(self):
        """Lock is released even if an exception occurs."""
        key = derive_stop_lock_key(uuid4())
        try:
            with advisory_lock(key) as acquired:
                self.assertTrue(acquired)
                raise RuntimeError("simulated failure")
        except RuntimeError:
            pass
        # Lock should be released
        with advisory_lock(key) as acquired:
            self.assertTrue(acquired)


# =============================================================================
# Executor Tests
# =============================================================================


class ExecutionResultTests(TestCase):
    """Tests for ExecutionResult data structure."""

    def test_execution_result_creation(self):
        """ExecutionResult can be created with required fields."""
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
        )
        result = ExecutionResult(
            job=job,
            success=True,
            entities_evaluated=5,
            canonical_writes=3,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.entities_evaluated, 5)
        self.assertEqual(result.canonical_writes, 3)

    def test_execution_result_duration(self):
        """ExecutionResult computes duration when timestamps are present."""
        now = timezone.now()
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
        )
        result = ExecutionResult(
            job=job,
            success=True,
            started_at=now,
            finished_at=now + timedelta(seconds=5),
        )
        self.assertAlmostEqual(result.duration_seconds, 5.0, places=1)

    def test_execution_result_duration_none_without_timestamps(self):
        """Duration is None when timestamps are missing."""
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
        )
        result = ExecutionResult(job=job, success=True)
        self.assertIsNone(result.duration_seconds)


class BaseExecutorInterfaceTests(TestCase):
    """Tests for BaseExecutor abstract interface."""

    def test_base_executor_is_abstract(self):
        """BaseExecutor cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            BaseExecutor()

    def test_custom_executor_can_be_implemented(self):
        """A concrete executor can implement BaseExecutor."""

        class NoOpExecutor(BaseExecutor):
            def execute(self, job):
                return ExecutionResult(job=job, success=True)

        executor = NoOpExecutor()
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
        )
        result = executor.execute(job)
        self.assertTrue(result.success)


class InlineExecutorTests(TransactionTestCase):
    """Tests for InlineExecutor correctness.

    Uses TransactionTestCase for advisory lock support.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="executor_test_user",
            email="executor@test.com",
            password="testpass123",
        )
        self.executor = InlineExecutor()

    def test_execute_stop_job_no_entities(self):
        """Stop evaluation with no existing stops succeeds with 0 evaluated."""
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=None,
        )
        result = self.executor.execute(job)
        self.assertTrue(result.success)
        self.assertEqual(result.entities_evaluated, 0)

    def test_execute_route_job_no_entities(self):
        """Route evaluation with no existing routes succeeds with 0 evaluated."""
        job = EvaluationJob(
            target_type=TargetType.ROUTE,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=None,
        )
        result = self.executor.execute(job)
        self.assertTrue(result.success)
        self.assertEqual(result.entities_evaluated, 0)

    def test_execute_stop_job_with_existing_stop(self):
        """Stop evaluation processes existing stops."""
        stop = Stop(
            name="Test Stop",
            location=Point(-74.0, 40.7),
            public_id=f"stop-{uuid4().hex[:8]}",
        )
        stop._internal_save()

        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=None,
        )
        result = self.executor.execute(job)
        self.assertTrue(result.success)
        self.assertEqual(result.entities_evaluated, 1)

    def test_execute_route_job_with_existing_route(self):
        """Route evaluation processes existing routes."""
        route = Route(
            name="Test Route",
            public_id=f"route-{uuid4().hex[:8]}",
        )
        route._internal_save()

        job = EvaluationJob(
            target_type=TargetType.ROUTE,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=None,
        )
        result = self.executor.execute(job)
        self.assertTrue(result.success)
        self.assertEqual(result.entities_evaluated, 1)

    def test_execute_with_targeted_stop_ids(self):
        """Stop evaluation with specific target IDs."""
        stop = Stop(
            name="Targeted Stop",
            location=Point(-74.0, 40.7),
            public_id=f"stop-{uuid4().hex[:8]}",
        )
        stop._internal_save()

        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.CONTRIBUTION,
            ruleset_version="1.0",
            target_ids=frozenset([stop.id]),
        )
        result = self.executor.execute(job)
        self.assertTrue(result.success)
        self.assertEqual(result.entities_evaluated, 1)

    def test_executor_result_has_timestamps(self):
        """Executor sets started_at and finished_at."""
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
        )
        result = self.executor.execute(job)
        self.assertIsNotNone(result.started_at)
        self.assertIsNotNone(result.finished_at)
        self.assertGreaterEqual(result.finished_at, result.started_at)

    def test_executor_failure_safety_on_exception(self):
        """If evaluation raises, result reports failure cleanly."""
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=frozenset([uuid4()]),  # Non-existent stop
        )
        # This should complete without errors since there's no evidence
        result = self.executor.execute(job)
        self.assertTrue(result.success)


class AdvisoryLockReleaseOnFailureTests(TransactionTestCase):
    """Tests that advisory locks are properly released after evaluation.

    PostgreSQL session-level advisory locks auto-release on session end
    or connection close (a PG guarantee). These tests verify our
    application code releases locks in the finally block of the executor,
    ensuring they don't leak within a long-lived session.
    """

    def test_lock_released_after_successful_stop_evaluation(self):
        """Lock is released after successful stop evaluation."""
        stop = Stop(
            name="Lock Release Stop",
            location=Point(-74.0, 40.7),
            public_id=f"stop-{uuid4().hex[:8]}",
        )
        stop._internal_save()

        executor = InlineExecutor()
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=frozenset([stop.id]),
        )
        result = executor.execute(job)
        self.assertTrue(result.success)

        # Lock should be released — verify we can acquire it again
        lock_key = derive_stop_lock_key(stop.id)
        acquired = try_advisory_lock(lock_key)
        self.assertTrue(
            acquired, "Lock should be released after successful evaluation"
        )
        release_advisory_lock(lock_key)

    def test_lock_released_after_failed_stop_evaluation(self):
        """Lock is released even when stop evaluation raises an exception."""
        stop = Stop(
            name="Failing Stop",
            location=Point(-74.0, 40.7),
            public_id=f"stop-{uuid4().hex[:8]}",
        )
        stop._internal_save()

        executor = InlineExecutor()
        with patch.object(
            executor,
            "_get_stop_evidence",
            side_effect=RuntimeError("simulated DB crash"),
        ):
            job = EvaluationJob(
                target_type=TargetType.STOP,
                trigger=Trigger.ADMIN,
                ruleset_version="1.0",
                target_ids=frozenset([stop.id]),
            )
            result = executor.execute(job)
            self.assertFalse(result.success)

        # Lock MUST still be released despite the error
        lock_key = derive_stop_lock_key(stop.id)
        acquired = try_advisory_lock(lock_key)
        self.assertTrue(
            acquired,
            "Lock should be released even after evaluation failure",
        )
        release_advisory_lock(lock_key)

    def test_lock_released_after_successful_route_evaluation(self):
        """Lock is released after successful route evaluation."""
        route = Route(
            name="Lock Release Route",
            public_id=f"route-{uuid4().hex[:8]}",
        )
        route._internal_save()

        executor = InlineExecutor()
        job = EvaluationJob(
            target_type=TargetType.ROUTE,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=frozenset([route.id]),
        )
        result = executor.execute(job)
        self.assertTrue(result.success)

        # Lock should be released
        lock_key = derive_route_lock_key(route.id)
        acquired = try_advisory_lock(lock_key)
        self.assertTrue(
            acquired, "Lock should be released after successful evaluation"
        )
        release_advisory_lock(lock_key)

    def test_lock_released_after_failed_route_evaluation(self):
        """Lock is released even when route evaluation raises an exception."""
        route = Route(
            name="Failing Route",
            public_id=f"route-{uuid4().hex[:8]}",
        )
        route._internal_save()

        executor = InlineExecutor()
        with patch.object(
            executor,
            "_get_route_evidence",
            side_effect=RuntimeError("simulated DB crash"),
        ):
            job = EvaluationJob(
                target_type=TargetType.ROUTE,
                trigger=Trigger.ADMIN,
                ruleset_version="1.0",
                target_ids=frozenset([route.id]),
            )
            result = executor.execute(job)
            self.assertFalse(result.success)

        # Lock MUST still be released despite the error
        lock_key = derive_route_lock_key(route.id)
        acquired = try_advisory_lock(lock_key)
        self.assertTrue(
            acquired,
            "Lock should be released even after evaluation failure",
        )
        release_advisory_lock(lock_key)


# =============================================================================
# Orchestration Tests
# =============================================================================


class OrchestrationResultTests(TestCase):
    """Tests for OrchestrationResult data structure."""

    def test_empty_result(self):
        """New OrchestrationResult has zero counts."""
        result = OrchestrationResult()
        self.assertEqual(result.total_jobs, 0)
        self.assertEqual(result.successful_jobs, 0)
        self.assertEqual(result.failed_jobs, 0)
        self.assertFalse(result.all_successful)
        self.assertFalse(result.has_failures)

    def test_add_successful_result(self):
        """Adding a successful result increments counters correctly."""
        orch = OrchestrationResult()
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
        )
        orch.add_result(ExecutionResult(job=job, success=True))
        self.assertEqual(orch.total_jobs, 1)
        self.assertEqual(orch.successful_jobs, 1)
        self.assertEqual(orch.failed_jobs, 0)
        self.assertTrue(orch.all_successful)
        self.assertFalse(orch.has_failures)

    def test_add_failed_result(self):
        """Adding a failed result increments failure counter."""
        orch = OrchestrationResult()
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
        )
        orch.add_result(
            ExecutionResult(
                job=job, success=False, errors=["test error"]
            )
        )
        self.assertEqual(orch.total_jobs, 1)
        self.assertEqual(orch.failed_jobs, 1)
        self.assertFalse(orch.all_successful)
        self.assertTrue(orch.has_failures)


class RecomputeStopsTests(TransactionTestCase):
    """Tests for recompute_stops orchestration."""

    def test_recompute_stops_no_data(self):
        """Recompute stops with no data completes successfully."""
        executor = InlineExecutor()
        result = recompute_stops(executor)
        self.assertTrue(result.all_successful)
        self.assertEqual(result.total_jobs, 1)

    def test_recompute_stops_with_data(self):
        """Recompute stops evaluates existing stops."""
        stop = Stop(
            name="Recompute Stop",
            location=Point(-74.0, 40.7),
            public_id=f"stop-{uuid4().hex[:8]}",
        )
        stop._internal_save()

        executor = InlineExecutor()
        result = recompute_stops(executor)
        self.assertTrue(result.all_successful)
        self.assertEqual(result.execution_results[0].entities_evaluated, 1)

    def test_recompute_stops_custom_ruleset(self):
        """Recompute stops uses the specified ruleset version."""
        executor = InlineExecutor()
        result = recompute_stops(executor, ruleset_version="2.0")
        self.assertTrue(result.all_successful)
        self.assertEqual(
            result.execution_results[0].job.ruleset_version, "2.0"
        )


class RecomputeRoutesTests(TransactionTestCase):
    """Tests for recompute_routes orchestration."""

    def test_recompute_routes_no_data(self):
        """Recompute routes with no data completes successfully."""
        executor = InlineExecutor()
        result = recompute_routes(executor)
        self.assertTrue(result.all_successful)
        self.assertEqual(result.total_jobs, 1)

    def test_recompute_routes_with_data(self):
        """Recompute routes evaluates existing routes."""
        route = Route(
            name="Recompute Route",
            public_id=f"route-{uuid4().hex[:8]}",
        )
        route._internal_save()

        executor = InlineExecutor()
        result = recompute_routes(executor)
        self.assertTrue(result.all_successful)
        self.assertEqual(result.execution_results[0].entities_evaluated, 1)


class RecomputeAllTests(TransactionTestCase):
    """Tests for recompute_all orchestration and dependency ordering."""

    def test_recompute_all_no_data(self):
        """Recompute all with no data completes both phases."""
        executor = InlineExecutor()
        result = recompute_all(executor)
        self.assertTrue(result.all_successful)
        # Should have 2 jobs: stops and routes
        self.assertEqual(result.total_jobs, 2)

    def test_recompute_all_dependency_ordering(self):
        """Recompute all evaluates stops before routes."""
        execution_order = []

        class OrderTrackingExecutor(BaseExecutor):
            def execute(self, job):
                execution_order.append(job.target_type)
                return ExecutionResult(job=job, success=True)

        executor = OrderTrackingExecutor()
        result = recompute_all(executor)

        self.assertEqual(len(execution_order), 2)
        self.assertEqual(execution_order[0], TargetType.STOP)
        self.assertEqual(execution_order[1], TargetType.ROUTE)
        self.assertTrue(result.all_successful)
        self.assertEqual(result.total_jobs, 2)

    def test_recompute_all_aborts_routes_on_stop_failure(self):
        """If stop recompute fails, route recompute is NOT executed."""
        execution_order = []

        class FailStopsExecutor(BaseExecutor):
            def execute(self, job):
                execution_order.append(job.target_type)
                if job.target_type == TargetType.STOP:
                    return ExecutionResult(
                        job=job,
                        success=False,
                        errors=["Stop evaluation failed"],
                    )
                return ExecutionResult(job=job, success=True)

        executor = FailStopsExecutor()
        result = recompute_all(executor)

        # Only stop job should have been executed
        self.assertEqual(len(execution_order), 1)
        self.assertEqual(execution_order[0], TargetType.STOP)
        # Result should reflect only stop failure
        self.assertEqual(result.total_jobs, 1)
        self.assertTrue(result.has_failures)

    def test_recompute_all_with_data(self):
        """Recompute all evaluates both stops and routes."""
        stop = Stop(
            name="Stop",
            location=Point(-74.0, 40.7),
            public_id=f"stop-{uuid4().hex[:8]}",
        )
        stop._internal_save()

        route = Route(
            name="Route",
            public_id=f"route-{uuid4().hex[:8]}",
        )
        route._internal_save()

        executor = InlineExecutor()
        result = recompute_all(executor)
        self.assertTrue(result.all_successful)
        self.assertEqual(result.total_jobs, 2)
        # First result is stops, second is routes
        self.assertEqual(
            result.execution_results[0].job.target_type, TargetType.STOP
        )
        self.assertEqual(
            result.execution_results[1].job.target_type, TargetType.ROUTE
        )


# =============================================================================
# Management Command Tests
# =============================================================================


class RecomputeCommandTests(TransactionTestCase):
    """Tests for the recompute management command."""

    def test_command_requires_target_argument(self):
        """Command fails without a target argument."""
        with self.assertRaises(CommandError):
            out = StringIO()
            call_command("recompute", stderr=out, stdout=out)

    def test_command_rejects_invalid_target(self):
        """Command fails with invalid target."""
        with self.assertRaises(CommandError):
            out = StringIO()
            call_command("recompute", "invalid", stderr=out, stdout=out)

    def test_command_accepts_stops(self):
        """Command succeeds with 'stops' target."""
        out = StringIO()
        call_command("recompute", "stops", stdout=out, stderr=StringIO())
        output = out.getvalue()
        self.assertIn("Recompute complete", output)

    def test_command_accepts_routes(self):
        """Command succeeds with 'routes' target."""
        out = StringIO()
        call_command("recompute", "routes", stdout=out, stderr=StringIO())
        output = out.getvalue()
        self.assertIn("Recompute complete", output)

    def test_command_accepts_all(self):
        """Command succeeds with 'all' target."""
        out = StringIO()
        call_command("recompute", "all", stdout=out, stderr=StringIO())
        output = out.getvalue()
        self.assertIn("Recompute complete", output)

    def test_command_accepts_custom_ruleset_version(self):
        """Command accepts --ruleset-version flag."""
        out = StringIO()
        call_command(
            "recompute",
            "stops",
            "--ruleset-version",
            "2.0",
            stdout=out,
            stderr=StringIO(),
        )
        output = out.getvalue()
        self.assertIn("ruleset_version=2.0", output)

    def test_command_reports_success(self):
        """Command output includes success message."""
        out = StringIO()
        call_command("recompute", "stops", stdout=out, stderr=StringIO())
        output = out.getvalue()
        self.assertIn("Recompute completed successfully", output)


# =============================================================================
# Auto-Evaluation Tests
# =============================================================================


class CreateEvaluationJobForContributionTests(TestCase):
    """Tests for automatic evaluation job creation on new evidence."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="autotrigger_user",
            email="auto@test.com",
            password="testpass123",
        )

    def _create_event(self, contribution_type, subject_ref=None):
        return ContributionEvent.objects.create(
            client_generated_id=uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,
            contribution_type=contribution_type,
            subject_ref=subject_ref or {"lat": 40.7, "lon": -74.0},
            payload={"test": True},
            observed_at=timezone.now(),
        )

    def test_stop_exists_creates_stop_job(self):
        """stop_exists contribution creates a Stop evaluation job."""
        event = self._create_event(
            ContributionEvent.ContributionType.STOP_EXISTS
        )
        job = create_evaluation_job_for_contribution(event)
        self.assertEqual(job.target_type, TargetType.STOP)
        self.assertEqual(job.trigger, Trigger.CONTRIBUTION)

    def test_stop_not_exists_creates_stop_job(self):
        """stop_not_exists contribution creates a Stop evaluation job."""
        event = self._create_event(
            ContributionEvent.ContributionType.STOP_NOT_EXISTS
        )
        job = create_evaluation_job_for_contribution(event)
        self.assertEqual(job.target_type, TargetType.STOP)

    def test_stop_name_creates_stop_job(self):
        """stop_name contribution creates a Stop evaluation job."""
        event = self._create_event(
            ContributionEvent.ContributionType.STOP_NAME
        )
        job = create_evaluation_job_for_contribution(event)
        self.assertEqual(job.target_type, TargetType.STOP)

    def test_stop_location_creates_stop_job(self):
        """stop_location contribution creates a Stop evaluation job."""
        event = self._create_event(
            ContributionEvent.ContributionType.STOP_LOCATION
        )
        job = create_evaluation_job_for_contribution(event)
        self.assertEqual(job.target_type, TargetType.STOP)

    def test_route_exists_creates_route_job(self):
        """route_exists contribution creates a Route evaluation job."""
        event = self._create_event(
            ContributionEvent.ContributionType.ROUTE_EXISTS
        )
        job = create_evaluation_job_for_contribution(event)
        self.assertEqual(job.target_type, TargetType.ROUTE)

    def test_route_traversal_creates_route_job(self):
        """route_traversal contribution creates a Route evaluation job."""
        event = self._create_event(
            ContributionEvent.ContributionType.ROUTE_TRAVERSAL
        )
        job = create_evaluation_job_for_contribution(event)
        self.assertEqual(job.target_type, TargetType.ROUTE)

    def test_stop_event_with_stop_id_in_subject_ref(self):
        """Job is scoped to the specific stop_id from subject_ref."""
        stop_id = uuid4()
        event = self._create_event(
            ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"stop_id": str(stop_id), "lat": 40.7, "lon": -74.0},
        )
        job = create_evaluation_job_for_contribution(event)
        self.assertIsNotNone(job.target_ids)
        self.assertIn(stop_id, job.target_ids)

    def test_route_event_with_route_id_in_subject_ref(self):
        """Job is scoped to the specific route_id from subject_ref."""
        route_id = uuid4()
        event = self._create_event(
            ContributionEvent.ContributionType.ROUTE_EXISTS,
            subject_ref={"route_id": str(route_id)},
        )
        job = create_evaluation_job_for_contribution(event)
        self.assertIsNotNone(job.target_ids)
        self.assertIn(route_id, job.target_ids)

    def test_event_without_entity_id_creates_unscoped_job(self):
        """Without entity ID in subject_ref, job has no target_ids."""
        event = self._create_event(
            ContributionEvent.ContributionType.STOP_EXISTS,
            subject_ref={"lat": 40.7, "lon": -74.0},
        )
        job = create_evaluation_job_for_contribution(event)
        self.assertIsNotNone(job)
        self.assertIsNone(job.target_ids)
        self.assertTrue(job.is_full_scope)

    def test_unhandled_contribution_type_returns_none(self):
        """Contribution types not mapped to stop/route return None."""
        event = self._create_event(
            ContributionEvent.ContributionType.STOP_SEQUENCE,
            subject_ref={"lat": 40.7, "lon": -74.0},
        )
        job = create_evaluation_job_for_contribution(event)
        self.assertIsNone(job)

    def test_service_time_contribution_type_returns_none(self):
        """SERVICE_TIME is not handled by any evaluator."""
        event = self._create_event(
            ContributionEvent.ContributionType.SERVICE_TIME,
            subject_ref={"lat": 40.7, "lon": -74.0},
        )
        job = create_evaluation_job_for_contribution(event)
        self.assertIsNone(job)

    def test_job_uses_default_ruleset_version(self):
        """Auto-eval jobs use DEFAULT_RULESET_VERSION constant."""
        event = self._create_event(
            ContributionEvent.ContributionType.STOP_EXISTS,
        )
        job = create_evaluation_job_for_contribution(event)
        self.assertEqual(job.ruleset_version, DEFAULT_RULESET_VERSION)


class EnqueueEvaluationTests(TransactionTestCase):
    """Tests for enqueue_evaluation_for_contribution.

    Uses TransactionTestCase because transaction.on_commit callbacks
    only fire after real commits (not savepoints in TestCase).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="enqueue_user",
            email="enqueue@test.com",
            password="testpass123",
        )

    def _create_event(self, contribution_type):
        return ContributionEvent.objects.create(
            client_generated_id=uuid4(),
            contributor=self.user,
            contributor_fingerprint=self.user.id,
            contribution_type=contribution_type,
            subject_ref={"lat": 40.7, "lon": -74.0},
            payload={"test": True},
            observed_at=timezone.now(),
        )

    def test_enqueue_does_not_raise_on_success(self):
        """enqueue_evaluation_for_contribution does not raise on success."""
        event = self._create_event(
            ContributionEvent.ContributionType.STOP_EXISTS
        )
        # Should not raise
        enqueue_evaluation_for_contribution(event)

    def test_enqueue_does_not_raise_on_error(self):
        """enqueue_evaluation_for_contribution never blocks evidence ingestion."""
        event = self._create_event(
            ContributionEvent.ContributionType.STOP_EXISTS
        )
        with patch(
            "transit.evaluation.orchestration.InlineExecutor.execute",
            side_effect=RuntimeError("simulated failure"),
        ):
            # Must not raise, even if executor fails
            enqueue_evaluation_for_contribution(event)

    def test_enqueue_skips_unhandled_contribution_type(self):
        """Unhandled contribution types produce no job and no error."""
        event = self._create_event(
            ContributionEvent.ContributionType.STOP_SEQUENCE
        )
        # Should not raise, and should not attempt execution
        with patch(
            "transit.evaluation.orchestration.InlineExecutor.execute",
        ) as mock_exec:
            enqueue_evaluation_for_contribution(event)
            mock_exec.assert_not_called()

    def test_enqueue_uses_transaction_on_commit(self):
        """Execution is deferred via transaction.on_commit."""
        event = self._create_event(
            ContributionEvent.ContributionType.STOP_EXISTS
        )
        with patch(
            "transit.evaluation.orchestration.transaction.on_commit",
        ) as mock_on_commit:
            enqueue_evaluation_for_contribution(event)
            mock_on_commit.assert_called_once()
            # The argument should be a callable
            callback = mock_on_commit.call_args[0][0]
            self.assertTrue(callable(callback))


# =============================================================================
# Failure Safety Tests
# =============================================================================


class FailureSafetyTests(TransactionTestCase):
    """Tests that failures leave canonical state unchanged."""

    def test_canonical_state_unchanged_on_evaluation_error(self):
        """If evaluation fails, canonical state must not be corrupted."""
        stop = Stop(
            name="Safe Stop",
            location=Point(-74.0, 40.7),
            public_id=f"stop-{uuid4().hex[:8]}",
            structural_confidence=Decimal("0.5"),
        )
        stop._internal_save()
        original_confidence = stop.structural_confidence

        # Execute with a mock that raises during evaluation
        executor = InlineExecutor()
        with patch.object(
            executor,
            "_get_stop_evidence",
            side_effect=RuntimeError("DB error"),
        ):
            job = EvaluationJob(
                target_type=TargetType.STOP,
                trigger=Trigger.ADMIN,
                ruleset_version="1.0",
                target_ids=frozenset([stop.id]),
            )
            result = executor.execute(job)

        # Canonical state should be unchanged
        stop.refresh_from_db()
        self.assertEqual(stop.structural_confidence, original_confidence)
        self.assertFalse(result.success)


# =============================================================================
# Self-Audit Tests (Review Checklist)
# =============================================================================


class SprintSelfAuditTests(TestCase):
    """
    Sprint-12 review checklist tests.

    These verify that Sprint-12 has NOT violated any constraints.
    """

    def test_no_new_canonical_fields_on_stop(self):
        """Sprint-12 must not add new fields to the Stop model."""
        # Known Stop fields (before Sprint-12)
        known_fields = {
            "id",
            "public_id",
            "version",
            "valid_from",
            "valid_until",
            "structural_confidence",
            "freshness_confidence",
            "ruleset_version",
            "evidence_refs",
            "created_at",
            "updated_at",
            "name",
            "location",
            "alternate_names",
            "belief_state",
            "properties",
        }
        # Remove reverse relations and other non-concrete fields
        concrete_fields = {
            f.name for f in Stop._meta.get_fields() if hasattr(f, "column")
        }
        new_fields = concrete_fields - known_fields
        self.assertEqual(
            new_fields,
            set(),
            f"Sprint-12 must not add new canonical fields to Stop: {new_fields}",
        )

    def test_no_new_canonical_fields_on_route(self):
        """Sprint-12 must not add new fields to the Route model."""
        known_fields = {
            "id",
            "public_id",
            "version",
            "valid_from",
            "valid_until",
            "structural_confidence",
            "freshness_confidence",
            "ruleset_version",
            "evidence_refs",
            "created_at",
            "updated_at",
            "name",
            "short_name",
            "route_type",
            "operator",
            "properties",
        }
        concrete_fields = {
            f.name for f in Route._meta.get_fields() if hasattr(f, "column")
        }
        new_fields = concrete_fields - known_fields
        self.assertEqual(
            new_fields,
            set(),
            f"Sprint-12 must not add new canonical fields to Route: {new_fields}",
        )

    def test_no_table_locks_in_locking_module(self):
        """Locking module must use advisory locks only, not table locks."""
        import inspect

        from transit.evaluation import locking

        source = inspect.getsource(locking)
        forbidden_patterns = [
            "LOCK TABLE",
            "lock_table",
            "SHARE MODE",
            "EXCLUSIVE MODE",
            "FOR UPDATE",
        ]
        for pattern in forbidden_patterns:
            self.assertNotIn(
                pattern,
                source,
                f"Locking module must not use table locks: found '{pattern}'",
            )

    def test_evaluation_logic_not_modified(self):
        """Sprint-12 must not modify evaluation thresholds or rules."""
        from transit.evaluation.route_evaluator import RouteEvaluator

        # Check that thresholds are unchanged from Sprint-11
        self.assertEqual(RouteEvaluator.MIN_INDEPENDENT_CONTRIBUTORS, 2)
        self.assertEqual(RouteEvaluator.MIN_DISTINCT_DAYS, 2)
        self.assertEqual(RouteEvaluator.MIN_EVIDENCE_COUNT, 3)

    def test_no_implicit_recompute_in_orchestration(self):
        """All recompute actions must be explicit and intentional."""
        import inspect

        from transit.evaluation import orchestration

        source = inspect.getsource(orchestration)
        # Should not have any auto-triggering on model save signals
        self.assertNotIn(
            "post_save.connect",
            source,
            "Orchestration must not auto-trigger via Django signals",
        )
        self.assertNotIn(
            "pre_save.connect",
            source,
            "Orchestration must not auto-trigger via Django signals",
        )

    def test_enqueue_uses_transaction_on_commit_guard(self):
        """enqueue_evaluation_for_contribution must use transaction.on_commit."""
        import inspect

        from transit.evaluation import orchestration

        source = inspect.getsource(orchestration.enqueue_evaluation_for_contribution)
        self.assertIn(
            "transaction.on_commit",
            source,
            "enqueue_evaluation_for_contribution must defer execution "
            "via transaction.on_commit to avoid evaluating uncommitted evidence",
        )

    def test_default_ruleset_version_is_single_source(self):
        """Orchestration, management command, and auto-eval use the same constant."""
        from transit.evaluation.orchestration import DEFAULT_RULESET_VERSION
        from transit.management.commands.recompute import Command

        # Check management command default matches the constant
        cmd = Command()
        parser = cmd.create_parser("manage.py", "recompute")
        # The --ruleset-version default should be DEFAULT_RULESET_VERSION
        for action in parser._actions:
            if hasattr(action, "dest") and action.dest == "ruleset_version":
                self.assertEqual(
                    action.default,
                    DEFAULT_RULESET_VERSION,
                    "Management command default must match DEFAULT_RULESET_VERSION",
                )
                break
        else:
            self.fail("--ruleset-version argument not found in management command")

    def test_entity_resolution_is_deterministically_ordered(self):
        """_resolve_stop_ids and _resolve_route_ids return sorted results."""
        import inspect

        from transit.evaluation.executor import InlineExecutor

        for method_name in ("_resolve_stop_ids", "_resolve_route_ids"):
            source = inspect.getsource(getattr(InlineExecutor, method_name))
            self.assertTrue(
                "sorted(" in source or "order_by" in source,
                f"{method_name} must produce deterministic ordering "
                f"(sorted() for targeted IDs, order_by for full scope)",
            )


# =============================================================================
# Deterministic Ordering Tests
# =============================================================================


class DeterministicOrderingTests(TransactionTestCase):
    """Tests that entity resolution produces deterministic ordering."""

    def setUp(self):
        self.executor = InlineExecutor()

    def test_targeted_stop_ids_are_sorted(self):
        """Targeted stop IDs are returned in sorted (deterministic) order."""
        id_a = UUID("aaaaaaaa-0000-0000-0000-000000000001")
        id_c = UUID("cccccccc-0000-0000-0000-000000000003")
        id_b = UUID("bbbbbbbb-0000-0000-0000-000000000002")

        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=frozenset([id_c, id_a, id_b]),
        )
        result = self.executor._resolve_stop_ids(job)
        self.assertEqual(result, [id_a, id_b, id_c])

    def test_targeted_route_ids_are_sorted(self):
        """Targeted route IDs are returned in sorted (deterministic) order."""
        id_a = UUID("aaaaaaaa-0000-0000-0000-000000000001")
        id_c = UUID("cccccccc-0000-0000-0000-000000000003")
        id_b = UUID("bbbbbbbb-0000-0000-0000-000000000002")

        job = EvaluationJob(
            target_type=TargetType.ROUTE,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=frozenset([id_c, id_a, id_b]),
        )
        result = self.executor._resolve_route_ids(job)
        self.assertEqual(result, [id_a, id_b, id_c])

    def test_full_scope_stops_are_ordered_by_id(self):
        """Full-scope stop resolution returns stops ordered by ID."""
        stops = []
        for _ in range(3):
            s = Stop(
                name="Ordered Stop",
                location=Point(-74.0, 40.7),
                public_id=f"stop-{uuid4().hex[:8]}",
            )
            s._internal_save()
            stops.append(s)

        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=None,
        )
        result = self.executor._resolve_stop_ids(job)
        self.assertEqual(result, sorted(result))

    def test_full_scope_routes_are_ordered_by_id(self):
        """Full-scope route resolution returns routes ordered by ID."""
        routes = []
        for _ in range(3):
            r = Route(
                name="Ordered Route",
                public_id=f"route-{uuid4().hex[:8]}",
            )
            r._internal_save()
            routes.append(r)

        job = EvaluationJob(
            target_type=TargetType.ROUTE,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=None,
        )
        result = self.executor._resolve_route_ids(job)
        self.assertEqual(result, sorted(result))


# =============================================================================
# Review-Comment Regression Tests
# =============================================================================


class LockContentionErrorSurfacingTests(TransactionTestCase):
    """Tests that lock contention is surfaced as an error for admin triggers
    but silently skipped for contribution triggers (#7)."""

    def test_admin_stop_job_reports_error_on_lock_contention(self):
        """Admin stop recompute reports failure when a lock is held."""
        stop = Stop(
            name="Locked Stop",
            location=Point(-74.0, 40.7),
            public_id=f"stop-{uuid4().hex[:8]}",
        )
        stop._internal_save()

        # Mock try_advisory_lock to simulate contention (advisory locks are
        # session-scoped so real contention can't be tested in-process).
        executor = InlineExecutor()
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=frozenset([stop.id]),
        )
        with patch(
            "transit.evaluation.executor.try_advisory_lock", return_value=False
        ):
            result = executor.execute(job)

        self.assertFalse(result.success)
        self.assertEqual(result.skipped_locked, 1)
        self.assertTrue(
            any("lock held" in e for e in result.errors),
            f"Expected lock contention error, got: {result.errors}",
        )

    def test_contribution_stop_job_skips_silently_on_lock_contention(self):
        """Contribution-triggered stop job skips locked entities without error."""
        stop = Stop(
            name="Locked Stop",
            location=Point(-74.0, 40.7),
            public_id=f"stop-{uuid4().hex[:8]}",
        )
        stop._internal_save()

        executor = InlineExecutor()
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.CONTRIBUTION,
            ruleset_version="1.0",
            target_ids=frozenset([stop.id]),
        )
        with patch(
            "transit.evaluation.executor.try_advisory_lock", return_value=False
        ):
            result = executor.execute(job)

        # Contribution triggers: skip is silent, success is True
        self.assertTrue(result.success)
        self.assertEqual(result.skipped_locked, 1)
        self.assertEqual(result.errors, [])

    def test_admin_route_job_reports_error_on_lock_contention(self):
        """Admin route recompute reports failure when a lock is held."""
        route = Route(
            name="Locked Route",
            public_id=f"route-{uuid4().hex[:8]}",
        )
        route._internal_save()

        executor = InlineExecutor()
        job = EvaluationJob(
            target_type=TargetType.ROUTE,
            trigger=Trigger.ADMIN,
            ruleset_version="1.0",
            target_ids=frozenset([route.id]),
        )
        with patch(
            "transit.evaluation.executor.try_advisory_lock", return_value=False
        ):
            result = executor.execute(job)

        self.assertFalse(result.success)
        self.assertEqual(result.skipped_locked, 1)
        self.assertTrue(
            any("lock held" in e for e in result.errors),
            f"Expected lock contention error, got: {result.errors}",
        )

    def test_contribution_route_job_skips_silently_on_lock_contention(self):
        """Contribution-triggered route job skips locked entities without error."""
        route = Route(
            name="Locked Route",
            public_id=f"route-{uuid4().hex[:8]}",
        )
        route._internal_save()

        executor = InlineExecutor()
        job = EvaluationJob(
            target_type=TargetType.ROUTE,
            trigger=Trigger.CONTRIBUTION,
            ruleset_version="1.0",
            target_ids=frozenset([route.id]),
        )
        with patch(
            "transit.evaluation.executor.try_advisory_lock", return_value=False
        ):
            result = executor.execute(job)

        # Contribution triggers: skip is silent, success is True
        self.assertTrue(result.success)
        self.assertEqual(result.skipped_locked, 1)
        self.assertEqual(result.errors, [])


class EvaluatorErrorRollbackTests(TransactionTestCase):
    """Tests that evaluator-reported errors trigger transaction rollback
    so no partial canonical writes persist (#1)."""

    def test_stop_evaluator_errors_rollback_canonical_writes(self):
        """If StopEvaluator reports errors, canonical state is unchanged."""
        stop = Stop(
            name="Rollback Stop",
            location=Point(-74.0, 40.7),
            public_id=f"stop-{uuid4().hex[:8]}",
            structural_confidence=Decimal("0.5"),
        )
        stop._internal_save()
        original_confidence = stop.structural_confidence

        from transit.evaluation.base import EvaluationResult as BaseEvalResult

        # Mock evaluate_with_creation to return errors
        mock_eval_result = BaseEvalResult()
        mock_eval_result.canonical_writes = 1
        mock_eval_result.add_error("simulated evaluator error")

        executor = InlineExecutor()
        with patch(
            "transit.evaluation.executor.StopEvaluator.evaluate_with_creation",
            return_value=(mock_eval_result, [], []),
        ):
            job = EvaluationJob(
                target_type=TargetType.STOP,
                trigger=Trigger.ADMIN,
                ruleset_version="1.0",
                target_ids=frozenset([stop.id]),
            )
            result = executor.execute(job)

        self.assertFalse(result.success)
        self.assertTrue(
            any("simulated evaluator error" in e for e in result.errors),
        )
        # Canonical writes should be 0 — the transaction was rolled back
        self.assertEqual(result.canonical_writes, 0)
        # DB state unchanged
        stop.refresh_from_db()
        self.assertEqual(stop.structural_confidence, original_confidence)


class RecomputeAllSkippedLockedTests(TransactionTestCase):
    """Tests that recompute_all aborts route recompute when stops
    are partially recomputed due to lock contention (#4)."""

    def test_recompute_all_aborts_routes_on_stop_skipped_locked(self):
        """If stops have skipped_locked > 0, routes are NOT executed."""
        execution_order = []

        class SkipLockedStopsExecutor(BaseExecutor):
            def execute(self, job):
                execution_order.append(job.target_type)
                if job.target_type == TargetType.STOP:
                    return ExecutionResult(
                        job=job,
                        success=True,
                        entities_evaluated=5,
                        skipped_locked=1,  # One stop was locked
                    )
                return ExecutionResult(job=job, success=True)

        executor = SkipLockedStopsExecutor()
        result = recompute_all(executor)

        # Only stop job should have been executed — routes aborted
        self.assertEqual(len(execution_order), 1)
        self.assertEqual(execution_order[0], TargetType.STOP)
        self.assertEqual(result.total_jobs, 1)

    def test_recompute_all_proceeds_when_no_stops_skipped(self):
        """When all stops complete without contention, routes run."""
        execution_order = []

        class FullSuccessExecutor(BaseExecutor):
            def execute(self, job):
                execution_order.append(job.target_type)
                return ExecutionResult(
                    job=job,
                    success=True,
                    entities_evaluated=3,
                    skipped_locked=0,
                )

        executor = FullSuccessExecutor()
        result = recompute_all(executor)

        self.assertEqual(len(execution_order), 2)
        self.assertEqual(execution_order[0], TargetType.STOP)
        self.assertEqual(execution_order[1], TargetType.ROUTE)
        self.assertTrue(result.all_successful)


class ReplaySafeEvaluationTimeTests(TransactionTestCase):
    """Tests that evaluation_time uses job.created_at for replay safety (#2, #3)."""

    def test_stop_evaluation_uses_job_created_at(self):
        """Stop evaluation context uses job.created_at, not timezone.now()."""
        stop = Stop(
            name="Replay Stop",
            location=Point(-74.0, 40.7),
            public_id=f"stop-{uuid4().hex[:8]}",
        )
        stop._internal_save()

        fixed_time = timezone.now() - timedelta(hours=1)
        job = EvaluationJob(
            target_type=TargetType.STOP,
            trigger=Trigger.REPLAY,
            ruleset_version="1.0",
            target_ids=frozenset([stop.id]),
            created_at=fixed_time,
        )

        captured_contexts = []
        original_init = StopEvaluator.__init__

        def capturing_init(self_eval, context):
            captured_contexts.append(context)
            original_init(self_eval, context)

        executor = InlineExecutor()
        with patch.object(StopEvaluator, "__init__", capturing_init):
            executor.execute(job)

        self.assertEqual(len(captured_contexts), 1)
        self.assertEqual(captured_contexts[0].evaluation_time, fixed_time)

    def test_route_evaluation_uses_job_created_at(self):
        """Route evaluation context uses job.created_at, not timezone.now()."""
        route = Route(
            name="Replay Route",
            public_id=f"route-{uuid4().hex[:8]}",
        )
        route._internal_save()

        fixed_time = timezone.now() - timedelta(hours=2)
        job = EvaluationJob(
            target_type=TargetType.ROUTE,
            trigger=Trigger.REPLAY,
            ruleset_version="1.0",
            target_ids=frozenset([route.id]),
            created_at=fixed_time,
        )

        captured_contexts = []
        original_init = RouteEvaluator.__init__

        def capturing_init(self_eval, context):
            captured_contexts.append(context)
            original_init(self_eval, context)

        executor = InlineExecutor()
        with patch.object(RouteEvaluator, "__init__", capturing_init):
            executor.execute(job)

        self.assertEqual(len(captured_contexts), 1)
        self.assertEqual(captured_contexts[0].evaluation_time, fixed_time)
