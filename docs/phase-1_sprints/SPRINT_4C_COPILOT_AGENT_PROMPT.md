# GitHub Copilot Agent Prompt — Phase-1 / Sprint-4C

> **Sprint Name:** Phase-1 Sprint-4C — Stop Creation & Initial Belief (Rules v0)
>
> **Project:** Gonaj Backend (Django)
>
> **Sprint Scope:** Canonical Stop creation using structural gates + belief threshold (no decay, no negative evidence)

This document is intended to be provided **as-is** to the GitHub Copilot Agent inside VS Code.

---

## 📚 Reference Documents (Authoritative)

The following documents must be loaded into context and treated as authoritative:

* `BACKEND_PHILOSOPHY.md`
* `PHASE_1_BACKEND_PLAN.md`
* `RULES_V_0_CONTEXT.md`
* `TEST_INVARIANTS_V0.md`
* `SPRINT_4A_COPILOT_AGENT_PROMPT.md`
* `SPRINT_4B_COPILOT_AGENT_PROMPT.md`

If there is any conflict, **Rules v0 and test invariants take precedence over implementation convenience**.

---

## 🧭 Context & Authoritative Interpretation

You are implementing **Sprint-4C of Phase-1**.

Sprint-4C corresponds to the third part of **Phase-1 Step 5: Minimal Evaluation Pipeline**.

### Authoritative Rule Interpretation (Must Be Followed Exactly)

In Rules v0, **Stop creation is threshold-based only after mandatory structural checks are satisfied**.

Both are required. Neither alone is sufficient.

Correct mental model:

```
STRUCTURAL GATES (hard)
        ↓
BELIEF THRESHOLD (gated)
        ↓
CANONICAL STOP (created)
```

This sprint implements **both stages**, in this order.

---

## 🚫 Absolute Scope Restrictions (Non-Negotiable)

You must NOT:

* ❌ Implement confidence decay
* ❌ Implement negative evidence semantics
* ❌ Merge or split existing Stops
* ❌ Override structural gates with numeric confidence
* ❌ Read or modify public APIs
* ❌ Modify aggregation logic from Sprint-4B
* ❌ Write canonical data outside `StopWriteGateway`

Any violation automatically fails the sprint.

---

## 📁 Project Structure (Authoritative)

You must respect the existing Django project layout.

### Sprint-4C code must live in:

```
backend/transit/evaluation/
```

You may:

* Extend `stop_evaluator.py`
* Add helper modules if necessary (e.g. `stop_creation.py`)

Do NOT create new apps or move existing files.

---

## 🎯 Sprint-4C Objectives

### Objective A — Structural Gate Evaluation (Hard Preconditions)

Implement **explicit, boolean structural gates** that determine whether Stop creation is *eligible*.

Structural gates (ALL mandatory):

1. **Minimum independent contributors**

   * At least two independent contributors
   * Same-user repetition never qualifies

2. **Temporal separation**

   * Contributions must occur on different calendar days

3. **Evidence diversity**

   * At least two distinct evidence types
   * Example: assertion + traversal

4. **Spatial coherence**

   * Aggregated evidence cluster within plausible radius

5. **Temporal plausibility**

   * Observations fall within plausible service windows

If **any gate fails**:

* Stop creation MUST NOT occur
* Evidence aggregation continues
* No canonical writes happen

These gates are **not tunable weights**.

---

### Objective B — Belief Threshold Evaluation (Secondary)

Only if **all structural gates pass**, evaluate belief threshold.

Threshold semantics:

* Represents accumulated belief from weighted evidence
* Is evaluated *after* gates
* Is not a single scalar shortcut

Threshold evaluation must:

* Use aggregation outputs
* Be deterministic
* Be conservative

If threshold is not crossed:

* Do nothing (no Stop)
* Preserve all evidence

---

### Objective C — Canonical Stop Creation

Only when:

* All structural gates pass
* Belief threshold is crossed

Then:

* Create canonical `Stop` via `StopWriteGateway`
* Initialize:

  * low initial confidence
  * ruleset_version
  * evidence_refs

No other writes are permitted.

---

## 🧠 Determinism & Safety Requirements

You must ensure:

* Structural gate evaluation is deterministic
* Threshold evaluation is deterministic
* Replay produces identical canonical Stops
* Incremental and batch paths converge

No wall-clock time, randomness, or DB default ordering is allowed.

---

## 🧪 Blocking Test Invariants

Your implementation must satisfy **all** of the following invariants:

* INV-B1 — Deterministic evaluation
* INV-B2 — Replay equivalence
* INV-C1 — No single-event creation
* INV-C2 — Independence requirement
* INV-C3 — Spatial convergence
* INV-H1 — Sub-threshold belief not public
* INV-I2 — Canonical write protection

Tests must reference invariant IDs explicitly in comments.

---

## 🧪 Tests to Implement

Add tests under:

```
backend/transit/tests/
```

Tests must verify:

1. No Stop created if any structural gate fails
2. No Stop created if threshold not crossed (even if gates pass)
3. Stop created only when gates + threshold both satisfied
4. Same-user repetition cannot trigger creation
5. Canonical writes occur only via `StopWriteGateway`
6. Incremental vs batch evaluation equivalence

Do NOT test decay or negative evidence.

---

## 🗂 Expected Deliverables

By the end of Sprint-4C, the codebase must include:

* Structural gate evaluation logic
* Threshold-based Stop creation logic
* Canonical Stop creation via gateway
* Deterministic, replay-safe behavior
* Invariant-driven tests

No decay or negative evidence logic should exist.

---

## 🛑 Definition of Done

Sprint-4C is complete **only when**:

* Stop creation requires BOTH structural gates and threshold
* No gate can be bypassed by confidence
* Canonical Stops are created safely and deterministically
* All blocking invariants pass
* Sprint-4A and Sprint-4B behavior remains unchanged

---

## 📎 Final Instruction to the Agent

After completing implementation:

1. Create a completion document at:

   * `docs/phase-1_sprints/PHASE_1_SPRINT_4C_COMPLETE.md`

2. The document must include:

   * Summary of objectives
   * Files created or modified
   * Tests added and results
   * List of invariants satisfied
   * Explicit confirmation that no decay or negative evidence logic exists

### 📌 Required Metadata in Completion Document

Include a section titled **`Implementation Metadata`** with:

* LLM / Coding Assistant used (tool + model if visible)
* IDE / tooling context
* Human vs AI contribution split
* Date range of implementation

> If any requested change conflicts with Rules v0 or `TEST_INVARIANTS_V0.md`, do NOT implement it.
> Explain why it would be unsafe instead.
