# Phase‑2 Sprint‑11 — Evaluation Generalization (Routes v0)

> **Status:** Authoritative implementation prompt
>
> **Audience:** Coding agents with **no prior context** of Gonaj discussions
>
> This document is a **standalone, self‑contained specification**. No external discussion context may be assumed.

---

## 1. Context

Gonaj is an evidence‑based backend where:

- Canonical truth is **derived conservatively from evidence**
- Evidence is **immutable and append‑only**
- Evaluation logic is **deterministic and replay‑safe**
- Guardrails always precede features

Up to Sprint‑10, the system has:

- A complete **Stop evaluation pipeline**
- Canonical read APIs for Stops and Routes (read‑only)
- Route **models and read endpoints**
- **No Route evaluation logic**

Sprint‑11 introduces **Route evaluation v0**.

This sprint must **extend the existing evaluation architecture** without weakening or modifying any Stop semantics.

---

## 2. Primary Goal

Extend evidence‑based truth evaluation from **Stops** to **Routes**, using the **same conservative, replay‑safe philosophy**, while respecting that Routes are **composite entities**.

This sprint is about **generalization, not innovation**.

---

## 3. Canonical Truth Semantics (Non‑Negotiable)

### 3.1 Binary Canonical Truth

Route canonical truth is **strictly binary**:

- **Canonical**
- **Not Canonical**

There are **no intermediate or partial canonical states** for Routes.

The Route evaluator MUST NOT:

- introduce intermediate truth states
- attach confidence values
- encode belief or probability
- encode partial canonical truth

Any notion of incompleteness or partial correctness **must be handled exclusively by the visibility layer**, never in evaluation or canonical storage.

---

## 4. Relationship to Stops (Authoritative Rules)

Routes are **composite, derivative entities**. Stops are **atomic, upstream authorities**.

### 4.1 Dependency Direction

Route evaluation:

- ✅ MAY read Stop canonical state
- ✅ MAY read Stop belief state
- ❌ MUST NOT modify Stop state
- ❌ MUST NOT influence Stop evaluation
- ❌ MUST NOT create feedback loops

Stop evaluation is **strictly upstream authority**.

### 4.2 Canonical Dependency Rule

If **any Stop referenced by a Route is not canonical**, the Route **MUST NOT** be canonical.

Absence of evidence is **not negative evidence**.

---

## 5. Route Belief States (Explicit Prohibition)

Routes **MUST NOT** introduce belief states in v0.

Specifically forbidden:

- Proposed / Active / Contested / Dormant analogues
- Confidence decay models
- Temporal belief transitions

**Justification**:

- Routes are composite and derivative
- Uncertainty is expressed via Stop belief and visibility suppression
- Introducing Route belief states would create semantic ambiguity

Any future belief model for Routes requires **`routes_rules_v1.md`**.

---

## 6. Evaluation Isolation Rules

The Route evaluator:

- MUST NOT read UI mode
- MUST NOT branch on visibility concerns
- MUST NOT suppress or modify data for presentation reasons
- MUST NOT import or reference visibility‑layer code

Evaluation output is **pure truth derivation** and is consumed by the visibility layer downstream.

---

## 7. Scope Definition

### 7.1 In Scope

- Route evaluation logic only
- New Route evaluator module
- Minimal Route aggregation logic
- Replay‑safe, invariant‑driven tests

### 7.2 Out of Scope (Hard Constraints)

You MUST NOT:

- change Stop evaluation logic
- modify Stop aggregation or thresholds
- add Route contribution APIs
- add Route mutation APIs
- add confidence scoring or decay
- read UI mode or visibility flags
- modify canonical read APIs
- modify serializers
- introduce new API fields
- add abuse heuristics or rate limiting
- write to the database during evaluation

Violation of any item above is a **Sprint‑11 failure**.

---

## 8. Required Architecture

### 8.1 Evaluator Structure

You MUST mirror the **Stop evaluator structure**:

- Stateless evaluation functions
- Separation of aggregation and evaluation
- Deterministic output
- No side effects

New files to create:

- `backend/transit/evaluation/route_evaluator.py`
- `backend/transit/evaluation/route_aggregation.py`

Structural similarity with Stop evaluation is **required**.

---

## 9. Mandatory Evaluation Invariants (Tests MUST Enforce)

All Route evaluation tests MUST enforce **every invariant below**:

1. **Determinism**  
   Same evidence set → identical canonical output

2. **Replay safety**  
   Re‑running evaluation produces identical results

3. **No Stop mutation**  
   Stop canonical and belief state remain unchanged

4. **Canonical dependency**  
   If any referenced Stop is not canonical → Route is not canonical

5. **No side effects**  
   Evaluation performs no database writes

Failure of any invariant is a **blocking defect**.

---

## 10. Implementation Guidance (Non‑Algorithmic)

Implement Route evaluation by:

- Mirroring Stop evaluation module boundaries
- Keeping aggregation conservative and minimal
- Treating evaluation as pure computation
- Letting visibility handle partial representation

This sprint prioritizes **correctness, determinism, and safety** over completeness.

---

## 11. Definition of Done

Sprint‑11 is complete when:

- Route evaluator exists and is deterministic
- Route aggregation logic exists
- Stop → Route dependency rules are enforced
- All mandatory invariants are tested and passing
- No forbidden files or semantics were modified

---

## 12. Change Control

Any change to Route truth semantics, belief handling, or dependencies requires:

- A new rules document (`routes_rules_v1.md`)
- New invariant tests
- Explicit Phase approval

Silent semantic evolution is forbidden.

---

**End of Sprint‑11 specification**

