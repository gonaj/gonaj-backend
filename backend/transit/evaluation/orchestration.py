"""
Evaluation orchestration logic.

Sprint-12: Performance & Recompute Control

This module provides:
- Recompute orchestration with explicit target scoping
- Dependency ordering enforcement (Stops → Routes)
- Post-commit scheduling hook for automatic evaluation on new evidence

WHAT THIS MODULE PROVIDES:
- Explicit recompute orchestration (stops, routes, or all)
- Dependency ordering: stops always before routes for 'all'
- Automatic evaluation job creation on new evidence
- Integration with executor abstraction

WHAT THIS MODULE DOES NOT PROVIDE:
- Public APIs (admin-only management commands are the entry point)
- UI triggers
- Job dashboards
- Background schedulers

DEPENDENCY ORDERING (MANDATORY):
- Stops do NOT depend on Routes
- Routes MAY read Stop canonical state
- Routes MUST NOT evaluate against partially recomputed Stops
- If target = 'all': Stops first, wait, then Routes

INVARIANTS:
- Evidence ingestion is NEVER blocked
- Evaluation MUST NOT run inside request threads (for auto-eval)
- Multiple evidence events may enqueue multiple jobs
- Redundant jobs are acceptable; race conditions are not
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from django.db import transaction

from .executor import BaseExecutor, ExecutionResult, InlineExecutor
from .jobs import EvaluationJob, TargetType, Trigger

logger = logging.getLogger(__name__)

# Single source of truth for the current ruleset version.
# Both admin recompute (management command) and auto-eval
# use this constant so they never diverge.
DEFAULT_RULESET_VERSION = "1.0"


@dataclass
class OrchestrationResult:
    """
    Result of an orchestration run.

    Aggregates results from all executed jobs.
    """

    execution_results: List[ExecutionResult] = field(default_factory=list)
    total_jobs: int = 0
    successful_jobs: int = 0
    failed_jobs: int = 0

    def add_result(self, result: ExecutionResult) -> None:
        """Record an execution result."""
        self.execution_results.append(result)
        self.total_jobs += 1
        if result.success:
            self.successful_jobs += 1
        else:
            self.failed_jobs += 1

    @property
    def all_successful(self) -> bool:
        """Whether all jobs succeeded."""
        return self.failed_jobs == 0 and self.total_jobs > 0

    @property
    def has_failures(self) -> bool:
        """Whether any job failed."""
        return self.failed_jobs > 0


def recompute_stops(
    executor: BaseExecutor,
    ruleset_version: str = DEFAULT_RULESET_VERSION,
) -> OrchestrationResult:
    """
    Orchestrate recompute for all Stops.

    Creates a single full-scope Stop evaluation job and executes it.

    Args:
        executor: The executor to use for running the job
        ruleset_version: Version of evaluation rules to apply

    Returns:
        OrchestrationResult with execution details
    """
    orchestration = OrchestrationResult()

    job = EvaluationJob(
        target_type=TargetType.STOP,
        trigger=Trigger.ADMIN,
        ruleset_version=ruleset_version,
        target_ids=None,  # Full scope
    )

    logger.info("Starting Stop recompute: job_id=%s", job.job_id)
    result = executor.execute(job)
    orchestration.add_result(result)
    logger.info(
        "Stop recompute complete: job_id=%s success=%s entities=%d writes=%d",
        job.job_id,
        result.success,
        result.entities_evaluated,
        result.canonical_writes,
    )

    return orchestration


def recompute_routes(
    executor: BaseExecutor,
    ruleset_version: str = DEFAULT_RULESET_VERSION,
) -> OrchestrationResult:
    """
    Orchestrate recompute for all Routes.

    Creates a single full-scope Route evaluation job and executes it.

    Args:
        executor: The executor to use for running the job
        ruleset_version: Version of evaluation rules to apply

    Returns:
        OrchestrationResult with execution details
    """
    orchestration = OrchestrationResult()

    job = EvaluationJob(
        target_type=TargetType.ROUTE,
        trigger=Trigger.ADMIN,
        ruleset_version=ruleset_version,
        target_ids=None,  # Full scope
    )

    logger.info("Starting Route recompute: job_id=%s", job.job_id)
    result = executor.execute(job)
    orchestration.add_result(result)
    logger.info(
        "Route recompute complete: job_id=%s success=%s entities=%d",
        job.job_id,
        result.success,
        result.entities_evaluated,
    )

    return orchestration


def recompute_all(
    executor: BaseExecutor,
    ruleset_version: str = DEFAULT_RULESET_VERSION,
) -> OrchestrationResult:
    """
    Orchestrate recompute for all entities with dependency ordering.

    DEPENDENCY ORDERING (MANDATORY):
    1. Enqueue and execute Stop recompute jobs
    2. Wait until Stop jobs complete
    3. Enqueue and execute Route recompute jobs

    Routes MUST NOT evaluate against partially recomputed Stops.

    Args:
        executor: The executor to use for running jobs
        ruleset_version: Version of evaluation rules to apply

    Returns:
        OrchestrationResult with all execution details
    """
    orchestration = OrchestrationResult()

    # Phase 1: Stops first
    logger.info("Recompute ALL — Phase 1: Stops")
    stop_job = EvaluationJob(
        target_type=TargetType.STOP,
        trigger=Trigger.ADMIN,
        ruleset_version=ruleset_version,
        target_ids=None,
    )

    stop_result = executor.execute(stop_job)
    orchestration.add_result(stop_result)

    if not stop_result.success:
        logger.error(
            "Stop recompute failed (job_id=%s). Aborting Route recompute.",
            stop_job.job_id,
        )
        return orchestration

    logger.info(
        "Recompute ALL — Phase 1 complete: %d stops evaluated",
        stop_result.entities_evaluated,
    )

    # Phase 2: Routes after Stops complete
    logger.info("Recompute ALL — Phase 2: Routes")
    route_job = EvaluationJob(
        target_type=TargetType.ROUTE,
        trigger=Trigger.ADMIN,
        ruleset_version=ruleset_version,
        target_ids=None,
    )

    route_result = executor.execute(route_job)
    orchestration.add_result(route_result)

    logger.info(
        "Recompute ALL — Phase 2 complete: %d routes evaluated",
        route_result.entities_evaluated,
    )

    return orchestration


def create_evaluation_job_for_contribution(
    contribution_event,
) -> Optional[EvaluationJob]:
    """
    Create an evaluation job for a newly ingested ContributionEvent.

    This function determines the target type and creates an appropriately
    scoped evaluation job.

    CRITICAL RULES:
    - Evidence ingestion MUST NOT block on evaluation
    - This function only CREATES the job; execution is separate
    - Multiple evidence events may create multiple jobs
    - Redundant jobs are acceptable; race conditions are not

    Args:
        contribution_event: The newly created ContributionEvent

    Returns:
        EvaluationJob targeting the affected entity scope, or None
        if the contribution type is not handled by any evaluator.
    """
    from core.models import ContributionEvent as CE

    stop_types = {
        CE.ContributionType.STOP_EXISTS,
        CE.ContributionType.STOP_NOT_EXISTS,
        CE.ContributionType.STOP_NAME,
        CE.ContributionType.STOP_LOCATION,
    }
    route_types = {
        CE.ContributionType.ROUTE_EXISTS,
        CE.ContributionType.ROUTE_TRAVERSAL,
    }

    if contribution_event.contribution_type in stop_types:
        target_type = TargetType.STOP
    elif contribution_event.contribution_type in route_types:
        target_type = TargetType.ROUTE
    else:
        logger.warning(
            "No evaluation target for contribution type %s (event %s). "
            "Add explicit handling if this type requires evaluation.",
            contribution_event.contribution_type,
            contribution_event.id,
        )
        return None

    # Extract entity-scoped target IDs from subject_ref if available
    target_ids = None
    subject_ref = contribution_event.subject_ref or {}
    if target_type == TargetType.STOP and "stop_id" in subject_ref:
        from uuid import UUID

        try:
            target_ids = frozenset([UUID(subject_ref["stop_id"])])
        except (ValueError, TypeError):
            logger.warning(
                "Failed to parse stop_id in subject_ref for contribution event %s "
                "(type %s); value: %r",
                contribution_event.id,
                contribution_event.contribution_type,
                subject_ref.get("stop_id"),
            )
    elif target_type == TargetType.ROUTE and "route_id" in subject_ref:
        from uuid import UUID

        try:
            target_ids = frozenset([UUID(subject_ref["route_id"])])
        except (ValueError, TypeError):
            logger.warning(
                "Failed to parse route_id in subject_ref for contribution event %s "
                "(type %s); value: %r",
                contribution_event.id,
                contribution_event.contribution_type,
                subject_ref.get("route_id"),
            )

    return EvaluationJob(
        target_type=target_type,
        trigger=Trigger.CONTRIBUTION,
        ruleset_version=DEFAULT_RULESET_VERSION,
        target_ids=target_ids,
    )


def enqueue_evaluation_for_contribution(contribution_event) -> None:
    """
    Schedule evaluation for a new contribution after evidence is committed.

    Sprint-12 uses inline execution via transaction.on_commit() to ensure:
    1. Evidence is fully committed before evaluation reads it
    2. Evaluation does not run inside an uncommitted transaction
    3. If the outer transaction rolls back, no evaluation is triggered

    NOTE: The on_commit callback still runs on the calling thread.
    Sprint-12 accepts this (prove correctness, not scale). Future
    sprints should replace the callback body with a task-queue
    dispatch to move evaluation off the request thread entirely.

    CRITICAL: Evidence ingestion is NEVER blocked. The on_commit callback
    runs after the current transaction commits. If no transaction is active,
    the callback runs immediately (Django's documented behaviour).

    Args:
        contribution_event: The newly created ContributionEvent
    """
    try:
        job = create_evaluation_job_for_contribution(contribution_event)
        if job is None:
            return  # Unhandled contribution type — nothing to evaluate

        def _execute_after_commit():
            try:
                executor = InlineExecutor()
                result = executor.execute(job)

                if not result.success:
                    logger.warning(
                        "Evaluation job %s completed with errors: %s",
                        job.job_id,
                        result.errors,
                    )
            except Exception as exc:
                # Log but never block evidence ingestion
                logger.exception(
                    "Post-commit evaluation failed for job %s: %s",
                    job.job_id,
                    exc,
                )

        transaction.on_commit(_execute_after_commit)
    except Exception as exc:
        # Log but never block evidence ingestion
        logger.exception(
            "Failed to schedule evaluation for contribution %s: %s",
            contribution_event.id,
            exc,
        )
