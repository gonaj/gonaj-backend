"""
Evaluation package for canonical transit entities.

Sprint-4A: Evaluation Scaffolding and Determinism
Sprint-4B: Positive Evidence Aggregation (No Creation)
Sprint-4C: Stop Creation & Initial Belief
Sprint-11: Evaluation Generalization (Routes v0)

This package provides the evaluation infrastructure for deriving canonical
transit entities from ContributionEvent evidence.

Sprint-4A establishes:
1. Deterministic evaluation entrypoint
2. Canonical write gateway
3. Replay and incremental hooks

Sprint-4B adds:
4. Pure evidence aggregation
5. GPS accuracy weighting
6. Same-user dampening
7. Spatial clustering (descriptive only)

Sprint-4C adds:
8. Structural gate evaluation (hard preconditions)
9. Belief threshold evaluation
10. Canonical Stop creation via gateway

Sprint-11 adds:
11. Route evidence aggregation
12. Route evaluator (binary canonical status)
13. Stop-Route canonical dependency checks

WHAT THIS PACKAGE PROVIDES:
- Deterministic evidence ordering and processing
- Controlled pathway for canonical writes
- Support for both incremental and batch evaluation
- Pure aggregation of evidence into weighted clusters
- Structural gates + threshold-based Stop creation
- Route canonical truth evaluation (binary: Canonical / Not Canonical)

WHAT THIS PACKAGE DOES NOT PROVIDE:
- Confidence decay logic
- Negative evidence semantics
- Merge/split logic
- Route belief states (explicitly forbidden in v0)

INVARIANTS ENFORCED:
- INV-A1: No evidence loss
- INV-A2: Evidence immutability
- INV-B1: Deterministic evaluation
- INV-B2: Replay equivalence
- INV-C1: No single-event creation
- INV-C2: Independence handling (same-user dampening)
- INV-C3: Spatial convergence (clustering)
- INV-D1: Accuracy as weight, not gate
- INV-D2: Accuracy cannot dominate alone
- INV-H1: Sub-threshold belief not public
- INV-I2: Canonical write protection
- R-TRUTH-1: Route canonical state is binary
- R-TRUTH-3: Non-canonical Stop blocks Route canonical status
- R-TRUTH-4: Route evaluation never modifies Stop state

All evaluation logic must route through this package to ensure
these invariants are preserved.
"""

from .base import BaseEvaluator, EvaluationContext, EvaluationResult
from .route_aggregation import (
    RouteAggregationResult,
    RouteEvidenceAggregator,
    RouteEvidenceCluster,
    RouteEvidenceTypeBreakdown,
    RouteEvidenceWeight,
    RouteTemporalSpan,
    RouteWeightCalculator,
)
from .route_evaluator import (
    RouteCanonicalDecision,
    RouteEvaluationResult,
    RouteEvaluator,
    check_route_stop_dependency,
    evaluate_route_canonical_status,
)
from .stop_aggregation import (
    AggregationResult,
    EvidenceTypeBreakdown,
    EvidenceWeight,
    SpatialCluster,
    SpatialClusterer,
    StopEvidenceAggregator,
    TemporalSpan,
    WeightCalculator,
)
from .stop_creation import (
    CreationDecision,
    GateResult,
    StopCreationPipeline,
    StopCreator,
    StructuralGateEvaluator,
    StructuralGateResult,
    ThresholdEvaluator,
    ThresholdResult,
)
from .stop_evaluator import StopEvaluator, StopWriteGateway

# Sprint-12: Performance & Recompute Control
from .executor import BaseExecutor, ExecutionResult, InlineExecutor
from .jobs import EvaluationJob, TargetType, Trigger
from .locking import (
    advisory_lock,
    derive_route_lock_key,
    derive_stop_lock_key,
    route_evaluation_lock,
    stop_evaluation_lock,
)
from .orchestration import (
    DEFAULT_RULESET_VERSION,
    OrchestrationResult,
    create_evaluation_job_for_contribution,
    enqueue_evaluation_for_contribution,
    recompute_all,
    recompute_routes,
    recompute_stops,
)

__all__ = [
    # Sprint-4A: Evaluation scaffolding
    "BaseEvaluator",
    "EvaluationContext",
    "EvaluationResult",
    "StopEvaluator",
    "StopWriteGateway",
    # Sprint-4B: Aggregation (Stops)
    "AggregationResult",
    "EvidenceTypeBreakdown",
    "EvidenceWeight",
    "SpatialCluster",
    "SpatialClusterer",
    "StopEvidenceAggregator",
    "TemporalSpan",
    "WeightCalculator",
    # Sprint-4C: Stop creation
    "CreationDecision",
    "GateResult",
    "StopCreationPipeline",
    "StopCreator",
    "StructuralGateEvaluator",
    "StructuralGateResult",
    "ThresholdEvaluator",
    "ThresholdResult",
    # Sprint-11: Route evaluation
    "RouteAggregationResult",
    "RouteCanonicalDecision",
    "RouteEvaluationResult",
    "RouteEvaluator",
    "RouteEvidenceAggregator",
    "RouteEvidenceCluster",
    "RouteEvidenceTypeBreakdown",
    "RouteEvidenceWeight",
    "RouteTemporalSpan",
    "RouteWeightCalculator",
    "check_route_stop_dependency",
    "evaluate_route_canonical_status",
    # Sprint-12: Performance & Recompute Control
    "EvaluationJob",
    "TargetType",
    "Trigger",
    "BaseExecutor",
    "ExecutionResult",
    "InlineExecutor",
    "advisory_lock",
    "derive_stop_lock_key",
    "derive_route_lock_key",
    "stop_evaluation_lock",
    "route_evaluation_lock",
    "OrchestrationResult",
    "DEFAULT_RULESET_VERSION",
    "recompute_stops",
    "recompute_routes",
    "recompute_all",
    "create_evaluation_job_for_contribution",
    "enqueue_evaluation_for_contribution",
]
