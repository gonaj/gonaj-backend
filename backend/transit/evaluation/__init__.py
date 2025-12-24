"""
Evaluation package for canonical transit entities.

Sprint-4A: Evaluation Scaffolding and Determinism

This package provides the evaluation infrastructure for deriving canonical
transit entities from ContributionEvent evidence. Sprint-4A establishes:

1. Deterministic evaluation entrypoint
2. Canonical write gateway
3. Replay and incremental hooks

WHAT THIS PACKAGE PROVIDES:
- Deterministic evidence ordering and processing
- Controlled pathway for canonical writes
- Support for both incremental and batch evaluation

WHAT THIS PACKAGE DOES NOT PROVIDE (Sprint-4A):
- Stop creation logic
- Confidence calculations
- Decay logic
- Spatial clustering or thresholds
- Any semantic evaluation decisions

INVARIANTS ENFORCED:
- INV-A1: No evidence loss
- INV-A2: Evidence immutability
- INV-B1: Deterministic evaluation
- INV-B2: Replay equivalence
- INV-I2: Canonical write protection

All evaluation logic must route through this package to ensure
these invariants are preserved.
"""

from .base import BaseEvaluator, EvaluationContext, EvaluationResult
from .stop_evaluator import StopEvaluator, StopWriteGateway

__all__ = [
    "BaseEvaluator",
    "EvaluationContext",
    "EvaluationResult",
    "StopEvaluator",
    "StopWriteGateway",
]
