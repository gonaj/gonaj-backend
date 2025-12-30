# GitHub Copilot Agent Prompt — Phase-1 / Sprint-5B (REWRITTEN, STRICT)

> **Sprint Name:** Phase-1 Sprint-5B — Evidence De‑identification with Evaluation Safety
>
> **Project:** Gonaj Backend (Django)
>
> **Status:** This prompt **supersedes any previous Sprint‑5B prompt**. Follow this version only.

This prompt must be provided **as‑is** to the GitHub Copilot Agent.

---

## 0. Non‑Negotiable Instruction (Read First)

You must **analyze the existing codebase before writing or modifying any code**.

Before implementing anything, you must:

1. Identify **all places where contributor identity is used** (directly or indirectly)
2. Identify **all evaluation logic that depends on contributor counts or independence**
3. Explicitly reason about **how de‑identification affects those paths**

If you change a model or field that influences evaluation semantics **without accounting for downstream logic**, the sprint is considered failed.

---

## 1. Core Architectural Philosophy (Authoritative)

The following principles are **hard laws** of the backend. They override convenience, refactors, or local correctness.

### PH‑1: Evidence is permanent

* No evidence row may be deleted or mutated in a way that alters payload, geometry, or timestamps

### PH‑2: Identity is optional

* User identity may disappear
* Evidence and belief must survive unchanged

### PH‑3: Belief is derived

* Canonical entities (Stops, Routes, etc.) are derived from evidence
* User lifecycle events must not affect belief outcomes

### PH‑4: Replay determinism

* Evaluation before and after account deletion must produce identical results

### PH‑5: Independence is an event‑level property

* "Independent contributors" refers to **submission‑time identity**, not live user records
* Evaluation must **never** depend on nullable foreign keys

Any implementation violating these principles is invalid.

---

## 2. Phase‑1 Invariants You Must Preserve

The following invariants are already locked by Rules v0 and test invariants. Your changes must preserve all of them:

* INV‑E1: ContributionEvent is immutable after creation
* INV‑E2: Evidence payload is replay‑stable
* INV‑I1: Contributor independence is counted correctly even after account deletion
* INV‑I2: Account deletion must not reduce or inflate contributor counts
* INV‑C1: Canonical Stop creation thresholds must not change
* INV‑C2: Structural gates (independence, diversity) must remain correct

You must explicitly verify that your changes do **not** violate any invariant.

---

## 3. Why Sprint‑5B Exists (Problem Statement)

Account deletion (Sprint‑5A) removes user identity.

Therefore:

* `ContributionEvent.contributor` **cannot remain PROTECT + non‑nullable**
* Identity must be removed **without breaking evaluation semantics**

The mistake to avoid:

> Treating contributor identity as a live FK used by evaluation logic

This sprint exists to **remove identity while preserving independence semantics**.

---

## 4. Required Design (Authoritative)

### 4.1 Contributor Identity Separation

You must enforce a **strict separation** between:

* **Identity for evaluation** (immutable, event‑level)
* **Identity for ownership** (user FK, removable)

Concretely:

1. Introduce a **non‑PII, non‑nullable, immutable field** on `ContributionEvent` that represents contributor identity *at submission time* (e.g. `contributor_fingerprint`).

2. This field must:

   * Be populated **explicitly at creation time**
   * Never be derived in `save()`
   * Never be nullable
   * Never change

3. The existing `contributor` FK:

   * Must become nullable
   * Must use `on_delete=SET_NULL`
   * Must NOT be used by evaluation logic

---

## 5. Mandatory Impact Analysis (Do Not Skip)

You must review and reason about the following areas, **even if you do not change them directly**:

### 5.1 Stop Evaluation & Aggregation

Files to inspect:

* `transit/evaluation/stop_aggregation.py`
* `transit/evaluation/stop_creation.py`
* `transit/evaluation/stop_evaluator.py`

Questions you must answer in code or comments:

* How are unique contributors counted?
* What happens if `contributor_id` is NULL?
* Does deletion collapse contributor counts?

If any logic uses `contributor_id`, it must be corrected.

---

### 5.2 Structural Gates for Stop Creation

Rules v0 require:

* Minimum independent contributors
* Evidence diversity

You must ensure:

* De‑identified evidence still satisfies these gates
* Account deletion does not retroactively block Stop creation

---

### 5.3 Replay Safety

You must ensure:

* Running evaluation before deletion
* Running evaluation after deletion

Produces identical canonical outcomes.

---

## 6. Migration Plan (Required)

You must implement migrations in a **safe, monotonic order**:

1. Add the new event‑level contributor identity field (nullable initially)
2. Backfill existing rows deterministically
3. Enforce NOT NULL
4. Make `contributor` nullable and change `on_delete` to `SET_NULL`

At no point may data be lost or belief change.

---

## 7. What You Must NOT Do

You must NOT:

* ❌ Use `contributor_id` in evaluation logic
* ❌ Derive identity in `save()`
* ❌ Delete or rewrite ContributionEvent rows
* ❌ Recompute belief as part of deletion
* ❌ Add shortcuts like "if contributor is NULL"

Any of the above is a hard failure.

---

## 8. Tests (Mandatory)

Add or update tests to prove:

* Multiple deleted users still count as multiple independent contributors
* Setting `contributor = NULL` does not change Stop creation behavior
* Evaluation results are identical pre‑ and post‑deletion

These tests are **not optional**.

---

## 9. Definition of Done

Sprint‑5B is complete only when:

* Identity is removable without breaking evaluation
* Contributor independence remains correct
* Canonical Stop logic is unaffected
* All invariants listed above hold
* Tests explicitly prove safety

---

## 10. Completion Document

Create:

```
docs/05_execution_history/phase_1/sprint_5b_complete.md
```

The document must include:

* What changed
* What was intentionally not changed
* Impact analysis on evaluation & Stop creation
* Invariants verified
* Tests added
* Implementation metadata (LLM used, dates)

---

## Canonical Reminder

> **Sprint‑5B is not a schema change sprint.**
> It is an **evaluation safety sprint**.

If contributor identity changes break Stop creation, the sprint has failed.
