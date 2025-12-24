# Phase-1 Sprint-4A Completion Report

## Sprint Name
Phase-1 Sprint-4A: Evaluation Scaffolding and Determinism

## Status
COMPLETE

---

## Summary of Objectives

Sprint-4A established the evaluation infrastructure for the Gonaj backend without implementing any semantic evaluation logic. The sprint delivered:

1. **Deterministic Evaluation Entrypoint** - A single, deterministic entry point for Stop evaluation that processes ContributionEvent records in a consistent, reproducible order.

2. **Canonical Write Gateway** - A controlled pathway (`StopWriteGateway`) through which all canonical Stop writes must occur, enforcing write protection invariants.

3. **Replay and Incremental Hooks** - Explicit methods for both incremental evaluation (normal operation) and full recomputation (safety mechanism), both routing through the same deterministic core.

---

## Files Created

### New Package: `backend/transit/evaluation/`

| File | Purpose |
|------|---------|
| `__init__.py` | Package initialization, exports public API |
| `base.py` | Base classes: `EvaluationContext`, `EvaluationResult`, `BaseEvaluator` |
| `stop_evaluator.py` | `StopEvaluator` class and `StopWriteGateway` for Stop entities |

### New Test File

| File | Purpose |
|------|---------|
| `backend/transit/tests/test_evaluation_scaffolding.py` | Invariant-focused tests (26 tests) |

---

## Files Modified

None. Sprint-4A created new code only and did not modify any existing Sprint-1, Sprint-2, or Sprint-3 logic.

---

## Tests Added and Results

### Test Classes and Coverage

| Test Class | Tests | Focus |
|------------|-------|-------|
| `EvaluationContextTests` | 3 | Context immutability and validation |
| `EvaluationResultTests` | 2 | Result tracking for evidence and writes |
| `DeterministicOrderingTests` | 3 | INV-B1: Deterministic evidence ordering |
| `NoEvidenceLossTests` | 2 | INV-A1: All evidence processed |
| `EvidenceImmutabilityTests` | 3 | INV-A2: Evidence not mutated |
| `ReplayEquivalenceTests` | 2 | INV-B2: Incremental == batch |
| `CanonicalWriteProtectionTests` | 7 | INV-I2: Gateway-only writes |
| `EvaluatorIntegrationTests` | 4 | End-to-end scaffolding tests |

**Total: 26 new tests**

### Test Execution Results

```
Ran 26 tests in 2.956s
OK
```

All tests pass. Full transit test suite (72 tests) also passes with no regressions.

---

## Invariants Satisfied

### INV-A1: No Evidence Loss

**Statement:** No evaluation step may discard, ignore, or permanently exclude any ContributionEvent.

**Implementation:**
- `StopEvaluator` processes all Stop-related evidence
- `EvaluationResult.add_processed_evidence()` tracks every processed event
- Tests verify all submitted evidence appears in result

**Tests:** `NoEvidenceLossTests`

---

### INV-A2: Evidence Immutability

**Statement:** Evaluation must never mutate or annotate ContributionEvent records.

**Implementation:**
- `BaseEvaluator._validate_evidence_not_mutated()` checks IDs before/after
- Evaluation only reads evidence, never writes
- Tests verify payload, observed_at, and IDs unchanged

**Tests:** `EvidenceImmutabilityTests`

---

### INV-B1: Deterministic Evaluation

**Statement:** Given the same set of ContributionEvents and ruleset version, canonical Stop output must be identical.

**Implementation:**
- Explicit sort keys: `(observed_at, submitted_at, id)`
- `BaseEvaluator.sort_evidence_deterministically()` enforces ordering
- `EvaluationContext` is frozen (immutable)
- No wall-clock time during evaluation
- No randomness

**Tests:** `DeterministicOrderingTests`

---

### INV-B2: Replay Equivalence

**Statement:** Incremental evaluation and full recomputation must converge to the same canonical state.

**Implementation:**
- `evaluate_incremental()` and `evaluate_full()` share `_evaluate_core()`
- Same deterministic processing path for both
- Tests verify identical evidence processing order

**Tests:** `ReplayEquivalenceTests`

---

### INV-I2: Canonical Write Protection

**Statement:** All canonical Stop writes must occur via evaluation logic only.

**Implementation:**
- `Stop.save()` raises `NotImplementedError` (existing guardrail)
- `StopWriteGateway.write_stop()` is the only write pathway
- Gateway sets `ruleset_version` and `evidence_refs` automatically
- Gateway tracks all writes for audit

**Tests:** `CanonicalWriteProtectionTests`

---

## Scope Compliance

### Explicitly NOT Implemented (as required)

- Stop creation logic
- Confidence calculations
- Decay logic
- Negative evidence handling
- Spatial clustering or thresholds
- GTFS, OSM, moderation, or reputation logic
- Public API modifications

### Confirmation

**No semantic Stop evaluation logic exists in this sprint.** The implementation provides scaffolding only:

- Evidence is sorted deterministically
- Evidence is tracked as processed
- Write gateway exists but performs no semantic decisions
- `_process_evidence_event()` records evidence IDs without evaluation

---

## Architecture Decisions

### 1. Shared Core Path for Incremental/Batch

Both `evaluate_incremental()` and `evaluate_full()` delegate to `_evaluate_core()` which calls `evaluate()`. This ensures INV-B2 (replay equivalence) by construction.

### 2. Frozen Evaluation Context

`EvaluationContext` is a frozen dataclass. The evaluation timestamp is passed in explicitly (not wall-clock), enabling deterministic replay.

### 3. Gateway Write Tracking

`StopWriteGateway` tracks all writes (`write_count`, `written_ids`) for audit purposes. This prepares for future observability requirements.

### 4. Evidence Sort Keys

Sort keys are defined as a class constant (`EVIDENCE_SORT_KEYS`) on `BaseEvaluator`. This makes the ordering explicit and auditable.

---

## Definition of Done Checklist

| Criterion | Status |
|-----------|--------|
| Evaluation can be run deterministically | DONE |
| Incremental and batch paths converge | DONE |
| Canonical writes are gated | DONE |
| All blocking invariants pass | DONE |
| No scope violations exist | DONE |
| Completion document created | DONE |

---

## Implementation Metadata

| Item | Value |
|------|-------|
| LLM / Coding Assistant | GitHub Copilot (Claude Opus 4.5) |
| IDE / Tooling | VS Code with GitHub Copilot Agent |
| Human vs AI Contribution | AI-generated implementation following human-authored spec |
| Date of Implementation | December 24, 2025 |

---

## Next Steps (Sprint-4B and beyond)

The scaffolding established in Sprint-4A prepares for:

1. **Stop Creation Logic** - Implementing threshold-based Stop creation
2. **Confidence Calculations** - Structural and freshness confidence
3. **Spatial Clustering** - Grouping nearby evidence
4. **Decay Logic** - Time-based confidence decay

These will be implemented in subsequent sprints, building on the deterministic foundation established here.

---

## Final Confirmation

This sprint implemented evaluation scaffolding and determinism only. **No evaluation logic was implemented.** The system can now process evidence deterministically and route all canonical writes through a controlled gateway, satisfying the required invariants for Phase-1.
