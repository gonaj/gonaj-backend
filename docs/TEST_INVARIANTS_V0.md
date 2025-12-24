# TEST_INVARIANTS_V0

> **Status:** Locked for Phase-1 (Rules v0)
> **Applies to:** Sprint-4 and all subsequent Phase-1 implementation
> **Purpose:** Define non-negotiable test invariants derived from Evaluation Rules v0

---

## 1. Purpose of This Document

This document defines **test invariants** for Gonaj’s Phase-1 backend.

Test invariants are **properties that must always hold true**, regardless of:

* implementation details
* refactors
* performance optimizations
* incremental vs batch evaluation

If any invariant in this document is violated, the implementation is **architecturally incorrect**, even if individual tests pass.

---

## 2. Scope & Constraints

These invariants:

* Apply **only to Phase-1**
* Are derived directly from **Evaluation Rules v0**
* Are intentionally conservative

They explicitly do **not** cover:

* UX behavior
* Performance guarantees
* Regional or operator-specific rules
* Reputation or trust systems
* ML-based inference

---

## 3. Core Principles (Do Not Reinterpret)

The following principles are foundational and must not be redefined:

1. Evidence is **immutable** and **append-only**
2. Canonical data is **derived belief**, not edited truth
3. All decisions must be **replayable and deterministic**
4. Confidence and uncertainty are **first-class**
5. The system must be **safe to be wrong**

Every invariant below exists to protect one or more of these principles.

---

## 4. Evidence Preservation Invariants

### INV-A1 — No Evidence Loss

**Statement:**
No evaluation step may discard, ignore, or permanently exclude any `ContributionEvent`.

**Rationale:**
Dropped evidence breaks replay and auditability.

**Test Expectation:**

* All submitted evidence is visible to evaluation logic
* Low-quality or conflicting evidence still participates with reduced weight

---

### INV-A2 — Evidence Immutability

**Statement:**
Evaluation must never mutate or annotate `ContributionEvent` records.

**Test Expectation:**

* No database writes occur on evidence tables during evaluation
* Evidence rows remain byte-identical before and after evaluation

---

## 5. Determinism & Replay Invariants

### INV-B1 — Deterministic Evaluation

**Statement:**
Given the same set of `ContributionEvent`s and the same ruleset version, canonical Stop output must be identical.

**Test Expectation:**

* Re-running evaluation produces identical canonical rows
* Input ordering does not affect results

---

### INV-B2 — Replay Equivalence

**Statement:**
Incremental evaluation and full recomputation must converge to the same canonical state.

**Test Expectation:**

* Batch evaluation == incremental evaluation
* No hidden state influences outcomes

---

## 6. Stop Creation Invariants

### INV-C1 — No Single-Event Creation

**Statement:**
No single evidence event may create a canonical Stop.

**Test Expectation:**

* One `stop_exists` → no Stop
* One traversal observation → no Stop

---

### INV-C2 — Independence Requirement

**Statement:**
Stop creation requires evidence from multiple independent contributors.

**Test Expectation:**

* Repeated submissions from the same user are down-weighted
* Independence is required to cross creation threshold

---

### INV-C3 — Spatial Convergence

**Statement:**
Stop creation requires spatially convergent evidence.

**Test Expectation:**

* Distant clusters do not form a Stop
* Canonical Stop location represents a cluster centroid

---

## 7. GPS Accuracy Invariants

### INV-D1 — Accuracy Is a Weight, Not a Gate

**Statement:**
GPS accuracy reduces evidence influence but never rejects evidence.

**Test Expectation:**

* Poor accuracy evidence contributes non-zero weight
* Evidence is never dropped solely due to accuracy

---

### INV-D2 — Accuracy Cannot Dominate Alone

**Statement:**
A single high-accuracy observation cannot create a Stop.

**Test Expectation:**

* Independence and corroboration remain mandatory

---

## 8. Negative Evidence Invariants

### INV-E1 — No Deletion via Negative Evidence

**Statement:**
Negative evidence can never delete a canonical Stop.

**Test Expectation:**

* Stop confidence decreases
* Stop transitions to Dormant or Contested
* Stop record remains present

---

### INV-E2 — Negative Evidence Is Weaker Than Aggregated Positive Evidence

**Statement:**
Single negative reports cannot override multiple strong positive confirmations.

**Test Expectation:**

* Strong positive evidence maintains Stop belief

---

### INV-E3 — Negative Evidence Modulates Thresholds Only

**Statement:**
Negative evidence may raise creation thresholds or accelerate decay but cannot block future creation.

---

## 9. Confidence & Decay Invariants

### INV-F1 — Confidence Changes Are Evidence-Driven

**Statement:**
Confidence increases only with positive evidence and decreases only via decay or negative evidence.

---

### INV-F2 — Asymmetric Decay

**Statement:**
New or weak Stops decay faster than long-established Stops.

---

### INV-F3 — Dormant Is Not Deleted

**Statement:**
Dormant Stops remain recoverable by future evidence.

---

## 10. Conflict Handling Invariants

### INV-G1 — Name Conflicts Do Not Fork Stops

**Statement:**
Conflicting names do not create multiple Stops.

---

### INV-G2 — Conservative Spatial Merging

**Statement:**
Spatial clusters are merged only with strong evidence; under-merging is preferred.

---

## 11. Visibility & API Invariants

### INV-H1 — Sub-threshold Belief Is Not Public

**Statement:**
Stops below creation threshold must not appear in public read APIs.

---

### INV-H2 — Public APIs Hide Mechanics

**Statement:**
Public APIs must not expose:

* raw confidence values
* evidence counts
* contributor identities

---

## 12. Phase Discipline Invariants

### INV-I1 — Ruleset Isolation

**Statement:**
Rules v0 must not reference reputation, moderation authority, ML models, or regional overrides.

---

### INV-I2 — Canonical Write Protection

**Statement:**
All canonical Stop writes must occur via evaluation logic only.

---

## 13. Meta-Invariant

### INV-J1 — Safe to Be Wrong

**Statement:**
For any incorrect Stop belief, the system must be able to recover automatically via future evidence.

If this invariant is violated, the design is incorrect regardless of test coverage.

---

## 14. How to Use These Invariants

* Reference invariant IDs in tests and comments
* Treat violations as **blocking defects**
* Do not weaken invariants to accommodate implementation shortcuts

---

## 15. Final Note

These invariants are more important than individual test cases.

Tests may change.
Implementations may change.

**These invariants must not.**
