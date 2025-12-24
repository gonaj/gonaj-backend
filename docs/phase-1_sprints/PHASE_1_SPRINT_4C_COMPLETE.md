# Phase-1 Sprint-4C Complete

> **Sprint Name:** Phase-1 Sprint-4C - Stop Creation & Initial Belief (Rules v0)
> **Status:** COMPLETE
> **Date:** 2025-12-24

---

## Summary

Sprint-4C implements the Stop creation logic for the Gonaj Backend, completing the Minimal Evaluation Pipeline (Phase-1 Step 5). This sprint adds:

1. **Structural Gate Evaluation** - Hard preconditions that must all pass before Stop creation is eligible
2. **Threshold Evaluation** - Belief threshold check (only evaluated after gates pass)
3. **Canonical Stop Creation** - Safe Stop creation via StopWriteGateway

The architecture enforces a strict ordering:

```
STRUCTURAL GATES (hard)
        |
        v
BELIEF THRESHOLD (gated)
        |
        v
CANONICAL STOP (created)
```

Both stages are required. Neither alone is sufficient.

---

## Objectives Completed

### Objective A - Structural Gate Evaluation (Hard Preconditions)

Implemented explicit, boolean structural gates that determine Stop creation eligibility.

**Gates Implemented (ALL mandatory):**

1. **Minimum Independent Contributors** - At least 2 independent contributors required
2. **Temporal Separation** - Contributions must occur on at least 2 different calendar days
3. **Evidence Diversity** - At least 2 distinct evidence types required
4. **Spatial Coherence** - Cluster radius must be within 100m
5. **Temporal Plausibility** - Observations must fall within plausible service hours

If ANY gate fails, Stop creation MUST NOT occur.

### Objective B - Belief Threshold Evaluation (Secondary)

Implemented threshold evaluation that only runs after all structural gates pass.

- Threshold: weighted score >= 2.0
- Evaluation is deterministic
- Conservative (biased toward false negatives)

### Objective C - Canonical Stop Creation

Implemented safe Stop creation:

- All writes go through `StopWriteGateway` (INV-I2)
- Initial confidence values set (structural: 0.3, freshness: 0.5)
- Evidence refs recorded on Stop
- Ruleset version set to "v0"

---

## Files Created

### New Files

| File | Purpose | Lines |
|------|---------|-------|
| `backend/transit/evaluation/stop_creation.py` | Structural gates, threshold evaluation, Stop creation | 580 |
| `backend/transit/tests/test_stop_creation.py` | Comprehensive invariant-driven tests | 565 |

### Modified Files

| File | Changes |
|------|---------|
| `backend/transit/evaluation/__init__.py` | Added exports for Sprint-4C classes |
| `backend/transit/evaluation/stop_evaluator.py` | Added `evaluate_with_creation()` method, integrated aggregator |

---

## New Classes

### Immutable Data Classes

| Class | Purpose |
|-------|---------|
| `GateResult` | Result of a single structural gate evaluation |
| `StructuralGateResult` | Aggregate result of all structural gates |
| `ThresholdResult` | Result of belief threshold evaluation |
| `CreationDecision` | Complete decision about Stop creation |

### Evaluators

| Class | Purpose |
|-------|---------|
| `StructuralGateEvaluator` | Evaluates 5 mandatory structural gates |
| `ThresholdEvaluator` | Evaluates belief threshold (gated) |
| `StopCreator` | Creates Stops via gateway based on decisions |
| `StopCreationPipeline` | Orchestrates full creation flow |

---

## Tests Added

### Test File: `test_stop_creation.py`

| Test Class | Tests | Purpose |
|------------|-------|---------|
| `GateResultTests` | 3 | Immutability and validation |
| `StructuralGateEvaluatorTests` | 7 | Gate evaluation logic |
| `ThresholdEvaluatorTests` | 4 | Threshold evaluation logic |
| `StopCreatorTests` | 5 | Stop creation via gateway |
| `StopCreationPipelineTests` | 4 | Pipeline integration |
| `StopCreationIntegrationTests` | 8 | Real evidence integration |
| `InvariantRegressionTests` | 4 | Specific invariant verification |

**Total New Tests:** 35

### Key Test Scenarios

1. No Stop created if any structural gate fails
2. No Stop created if threshold not crossed (even if gates pass)
3. Stop created only when gates + threshold both satisfied
4. Same-user repetition cannot trigger creation (INV-C2)
5. Single event cannot create Stop (INV-C1)
6. Canonical writes occur only via StopWriteGateway (INV-I2)
7. Incremental vs batch evaluation equivalence (INV-B2)

---

## Test Results

```
$ python manage.py test --verbosity=1

Ran 202 tests in 22.616s

OK
```

**Total Tests:** 202 (167 existing + 35 new)

### Test Breakdown by App

| App | Tests |
|-----|-------|
| `core` | 63 |
| `transit` | 137 |
| `api` | 2 |

---

## Invariants Satisfied

### Stop Creation Invariants

| Invariant | Description | Verification |
|-----------|-------------|--------------|
| INV-C1 | No single-event creation | `test_inv_c1_single_evidence_never_creates_stop` |
| INV-C2 | Independence requirement | `test_inv_c2_same_user_repetition_insufficient` |
| INV-C3 | Spatial convergence | `test_spatial_coherence_gate_fails_with_large_radius` |

### Visibility Invariants

| Invariant | Description | Verification |
|-----------|-------------|--------------|
| INV-H1 | Sub-threshold belief not public | `test_inv_h1_sub_threshold_not_creates_stop` |

### Determinism Invariants

| Invariant | Description | Verification |
|-----------|-------------|--------------|
| INV-B1 | Deterministic evaluation | `test_gates_are_evaluated_deterministically` |
| INV-B2 | Replay equivalence | `test_incremental_and_batch_produce_same_result` |

### Write Protection Invariants

| Invariant | Description | Verification |
|-----------|-------------|--------------|
| INV-I2 | Canonical write protection | `test_inv_i2_all_writes_via_gateway` |

---

## Explicit Confirmations

### NOT Implemented (Per Sprint Scope)

- Confidence decay logic
- Negative evidence semantics
- Merge/split logic
- Threshold tuning per region/operator

### Sprint-4A/4B Behavior Preserved

- All 26 Sprint-4A tests pass
- All 30 Sprint-4B tests pass
- No modifications to existing evaluation scaffolding
- No modifications to aggregation logic

---

## Architecture Summary

### Creation Flow

```
ContributionEvent[]
        |
        v
StopEvidenceAggregator.aggregate()    # Sprint-4B
        |
        v
AggregationResult (clusters)
        |
        v
StructuralGateEvaluator.evaluate_all_gates()    # Sprint-4C
        |
        v
StructuralGateResult
        |
        v (only if all gates pass)
ThresholdEvaluator.evaluate_threshold()         # Sprint-4C
        |
        v (only if threshold crossed)
StopCreator.create_stop()                       # Sprint-4C
        |
        v
StopWriteGateway.write_stop()                   # Sprint-4A
        |
        v
Stop (canonical)
```

### Gate Thresholds (Rules v0)

| Gate | Threshold |
|------|-----------|
| Minimum Contributors | >= 2 independent |
| Temporal Separation | >= 2 distinct days |
| Evidence Diversity | >= 2 distinct types |
| Spatial Coherence | <= 100m radius |
| Temporal Plausibility | >= 1 observation in 4AM-midnight |

### Creation Threshold (Rules v0)

| Metric | Threshold |
|--------|-----------|
| Weighted Score | >= 2.0 |

### Initial Confidence (Rules v0)

| Field | Initial Value |
|-------|---------------|
| structural_confidence | 0.3 |
| freshness_confidence | 0.5 |

---

## Implementation Metadata

| Field | Value |
|-------|-------|
| LLM/Coding Assistant | GitHub Copilot (Claude Opus 4.5) |
| IDE | VS Code |
| Human vs AI Split | Specification: Human, Implementation: AI |
| Implementation Date | 2025-12-24 |

---

## Next Steps (Future Sprints)

Sprint-4C completes the Minimal Evaluation Pipeline. Future work includes:

1. **Confidence Decay** - Time-based decay of freshness confidence
2. **Negative Evidence** - Processing stop_not_exists contributions
3. **Name Derivation** - Extracting names from stop_name evidence
4. **Merge/Split** - Handling spatial cluster changes over time

These are explicitly out of scope for Phase-1 Sprint-4C.
