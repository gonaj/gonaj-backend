"""
Executor abstraction and minimal inline executor.

Sprint-12: Performance & Recompute Control

This module provides:
- ExecutionResult: Immutable result of job execution
- BaseExecutor: Abstract executor interface
- InlineExecutor: Minimal in-process executor with locking and atomicity

WHAT THIS MODULE PROVIDES:
- Stable executor API
- Deterministic execution semantics
- Scoped advisory locking during evaluation
- Atomic canonical writes (transaction.atomic)
- Failure-safe execution (no partial writes)

WHAT THIS MODULE DOES NOT PROVIDE:
- Celery / Redis / worker pools
- Background schedulers
- Job dashboards
- Distributed workflow engines

INVARIANTS:
- Execution is atomic (no partial canonical writes)
- Execution is idempotent and replay-safe
- Advisory locks prevent concurrent evaluation of the same entity
- Evidence ingestion is NEVER blocked
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence
from uuid import UUID

from core.models import ContributionEvent
from django.db import transaction
from django.utils import timezone
from transit.models import Route, Stop

from .base import EvaluationContext
from .jobs import EvaluationJob, TargetType
from .locking import (
    derive_route_lock_key,
    derive_stop_lock_key,
    try_advisory_lock,
    release_advisory_lock,
)
from .route_evaluator import RouteEvaluator
from .stop_evaluator import StopEvaluator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionResult:
    """
    Immutable result of a single job execution.

    Attributes:
        job: The evaluation job that was executed
        success: Whether execution completed without errors
        entities_evaluated: Number of entities evaluated
        canonical_writes: Number of canonical writes performed
        skipped_locked: Number of entities skipped due to lock contention
        errors: List of error messages (empty on success)
        started_at: When execution started
        finished_at: When execution finished
    """

    job: EvaluationJob
    success: bool
    entities_evaluated: int = 0
    canonical_writes: int = 0
    skipped_locked: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Elapsed time in seconds, or None if timestamps are missing."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class BaseExecutor(ABC):
    """
    Abstract executor interface for running evaluation jobs.

    Implementations must enforce:
    - Scoped advisory locking
    - Atomic canonical writes
    - Failure safety (no partial writes)
    """

    @abstractmethod
    def execute(self, job: EvaluationJob) -> ExecutionResult:
        """
        Execute an evaluation job.

        Implementations must:
        - Acquire scoped advisory locks per entity
        - Run evaluation inside a database transaction
        - Return an immutable ExecutionResult
        - Leave canonical state unchanged on failure

        Args:
            job: The evaluation job to execute

        Returns:
            ExecutionResult describing the outcome
        """
        pass


class InlineExecutor(BaseExecutor):
    """
    Minimal in-process executor for Sprint-12.

    This executor runs evaluation jobs synchronously in the current
    process. It exists to prove correctness, not scale.

    Execution steps for each target entity:
    1. Acquire scoped advisory lock (non-blocking)
    2. If lock not acquired, skip entity (logged)
    3. Gather evidence for entity
    4. Run evaluation inside transaction.atomic()
    5. Release advisory lock

    Failure at any step leaves canonical state unchanged.
    """

    def execute(self, job: EvaluationJob) -> ExecutionResult:
        """
        Execute an evaluation job inline (in-process).

        Args:
            job: The evaluation job to execute

        Returns:
            ExecutionResult describing the outcome
        """
        started_at = timezone.now()
        errors: list[str] = []
        entities_evaluated = 0
        canonical_writes = 0
        skipped_locked = 0

        try:
            if job.target_type == TargetType.STOP:
                result = self._execute_stop_evaluation(job)
            elif job.target_type == TargetType.ROUTE:
                result = self._execute_route_evaluation(job)
            else:
                errors.append(f"Unknown target type: {job.target_type}")
                return ExecutionResult(
                    job=job,
                    success=False,
                    errors=errors,
                    started_at=started_at,
                    finished_at=timezone.now(),
                )

            entities_evaluated = result["entities_evaluated"]
            canonical_writes = result["canonical_writes"]
            skipped_locked = result["skipped_locked"]
            errors = result["errors"]

        except Exception as exc:
            logger.exception("Evaluation job %s failed: %s", job.job_id, exc)
            errors.append(str(exc))

        success = len(errors) == 0
        return ExecutionResult(
            job=job,
            success=success,
            entities_evaluated=entities_evaluated,
            canonical_writes=canonical_writes,
            skipped_locked=skipped_locked,
            errors=errors,
            started_at=started_at,
            finished_at=timezone.now(),
        )

    def _execute_stop_evaluation(self, job: EvaluationJob) -> dict:
        """
        Execute stop evaluation for the given job.

        If job.target_ids is None (full scope), evaluate all current stops.
        Otherwise, evaluate only the targeted stops.
        """
        entities_evaluated = 0
        canonical_writes = 0
        skipped_locked = 0
        errors: list[str] = []

        context = EvaluationContext(
            ruleset_version=job.ruleset_version,
            evaluation_time=timezone.now(),
            is_incremental=job.target_ids is not None,
        )

        stop_ids = self._resolve_stop_ids(job)

        for stop_id in stop_ids:
            lock_key = derive_stop_lock_key(stop_id)
            acquired = try_advisory_lock(lock_key)
            if not acquired:
                logger.info(
                    "Skipping stop %s - lock held by another session", stop_id
                )
                skipped_locked += 1
                continue

            try:
                evidence = self._get_stop_evidence(stop_id)
                evaluator = StopEvaluator(context)
                with transaction.atomic():
                    _result, _stops, _decisions = evaluator.evaluate_with_creation(
                        evidence
                    )
                    canonical_writes += _result.canonical_writes
                entities_evaluated += 1

                if _result.has_errors():
                    errors.extend(_result.errors)

            except Exception as exc:
                logger.exception(
                    "Stop evaluation failed for %s: %s", stop_id, exc
                )
                errors.append(f"Stop {stop_id}: {exc}")
            finally:
                release_advisory_lock(lock_key)

        return {
            "entities_evaluated": entities_evaluated,
            "canonical_writes": canonical_writes,
            "skipped_locked": skipped_locked,
            "errors": errors,
        }

    def _execute_route_evaluation(self, job: EvaluationJob) -> dict:
        """
        Execute route evaluation for the given job.

        If job.target_ids is None (full scope), evaluate all routes
        with evidence. Otherwise, evaluate only the targeted routes.
        """
        entities_evaluated = 0
        canonical_writes = 0
        skipped_locked = 0
        errors: list[str] = []

        context = EvaluationContext(
            ruleset_version=job.ruleset_version,
            evaluation_time=timezone.now(),
            is_incremental=job.target_ids is not None,
        )

        route_ids = self._resolve_route_ids(job)

        for route_id in route_ids:
            lock_key = derive_route_lock_key(route_id)
            acquired = try_advisory_lock(lock_key)
            if not acquired:
                logger.info(
                    "Skipping route %s - lock held by another session", route_id
                )
                skipped_locked += 1
                continue

            try:
                evidence = self._get_route_evidence(route_id)
                evaluator = RouteEvaluator(context)
                with transaction.atomic():
                    eval_result = evaluator.evaluate_routes(evidence)
                entities_evaluated += 1

                # Route evaluator is read-only (no canonical writes in v0).
                # When route evaluation gains write capability, reflect
                # canonical_writes here from eval_result.

                # Surface base evaluator errors if any were recorded
                base_result = evaluator.result
                if base_result and base_result.has_errors():
                    errors.extend(base_result.errors)

            except Exception as exc:
                logger.exception(
                    "Route evaluation failed for %s: %s", route_id, exc
                )
                errors.append(f"Route {route_id}: {exc}")
            finally:
                release_advisory_lock(lock_key)

        return {
            "entities_evaluated": entities_evaluated,
            "canonical_writes": canonical_writes,
            "skipped_locked": skipped_locked,
            "errors": errors,
        }

    def _resolve_stop_ids(self, job: EvaluationJob) -> list[UUID]:
        """Resolve the set of Stop IDs to evaluate."""
        if job.target_ids is not None:
            # Ensure deterministic ordering even if target_ids is a set/frozenset
            return sorted(job.target_ids)
        # Full scope: all currently valid stops, ordered deterministically by ID
        return list(
            Stop.objects.filter(valid_until__isnull=True)
            .order_by("id")
            .values_list("id", flat=True)
        )

    def _resolve_route_ids(self, job: EvaluationJob) -> list[UUID]:
        """Resolve the set of Route IDs to evaluate."""
        if job.target_ids is not None:
            # Ensure deterministic ordering even if target_ids is a set/frozenset
            return sorted(job.target_ids)
        # Full scope: all currently valid routes, ordered deterministically by ID
        return list(
            Route.objects.filter(valid_until__isnull=True)
            .order_by("id")
            .values_list("id", flat=True)
        )

    def _get_stop_evidence(
        self, stop_id: UUID
    ) -> Sequence[ContributionEvent]:
        """Gather all evidence relevant to a specific stop."""
        return list(
            ContributionEvent.objects.filter(
                contribution_type__in=(
                    ContributionEvent.ContributionType.STOP_EXISTS,
                    ContributionEvent.ContributionType.STOP_NOT_EXISTS,
                    ContributionEvent.ContributionType.STOP_NAME,
                    ContributionEvent.ContributionType.STOP_LOCATION,
                ),
                subject_ref__stop_id=str(stop_id),
            ).order_by("observed_at", "submitted_at", "id")
        )

    def _get_route_evidence(
        self, route_id: UUID
    ) -> Sequence[ContributionEvent]:
        """Gather all evidence relevant to a specific route."""
        return list(
            ContributionEvent.objects.filter(
                contribution_type__in=(
                    ContributionEvent.ContributionType.ROUTE_EXISTS,
                    ContributionEvent.ContributionType.ROUTE_TRAVERSAL,
                ),
                subject_ref__route_id=str(route_id),
            ).order_by("observed_at", "submitted_at", "id")
        )
