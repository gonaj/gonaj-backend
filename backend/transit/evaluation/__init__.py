"""
Evaluation package for canonical transit entities.

Sprint-4A: Evaluation Scaffolding and Determinism
Sprint-4B: Positive Evidence Aggregation (No Creation)

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

WHAT THIS PACKAGE PROVIDES:
- Deterministic evidence ordering and processing
- Controlled pathway for canonical writes
- Support for both incremental and batch evaluation
- Pure aggregation of evidence into weighted clusters

WHAT THIS PACKAGE DOES NOT PROVIDE (Sprint-4A/4B):
- Stop creation logic
- Confidence calculations
- Decay logic
- Threshold decisions
- Any semantic evaluation decisions

INVARIANTS ENFORCED:
- INV-A1: No evidence loss
- INV-A2: Evidence immutability
- INV-B1: Deterministic evaluation
- INV-B2: Replay equivalence
- INV-C2: Independence handling (same-user dampening)
- INV-C3: Spatial convergence (clustering)
- INV-D1: Accuracy as weight, not gate
- INV-D2: Accuracy cannot dominate alone
- INV-I2: Canonical write protection

All evaluation logic must route through this package to ensure
these invariants are preserved.
"""

from .base import BaseEvaluator, EvaluationContext, EvaluationResult
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
from .stop_evaluator import StopEvaluator, StopWriteGateway

__all__ = [
    # Sprint-4A: Evaluation scaffolding
    "BaseEvaluator",
    "EvaluationContext",
    "EvaluationResult",
    "StopEvaluator",
    "StopWriteGateway",
    # Sprint-4B: Aggregation
    "AggregationResult",
    "EvidenceTypeBreakdown",
    "EvidenceWeight",
    "SpatialCluster",
    "SpatialClusterer",
    "StopEvidenceAggregator",
    "TemporalSpan",
    "WeightCalculator",
]
