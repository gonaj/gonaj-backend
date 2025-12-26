# GitHub Copilot Agent Prompt — Phase-1 / Sprint-4D

> **Sprint Name:** Phase-1 Sprint-4D — Negative Evidence & Conflict Handling (Rules v0)
>
> **Project:** Gonaj Backend (Django)
>
> **Sprint Scope:** Conservative negative evidence handling, confidence weakening, and derived Contested state — no deletion, no veto

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
* `SPRINT_4C_COPILOT_AGENT_PROMPT.md`

If there is any conflict, **Rules v0 and test invariants take precedence over implementation convenience**.

---

## 🧭 Context & Authoritative Interpretation

You are implementing **Sprint-4D of Phase-1**.

Sprint-4D introduces **negative evidence semantics** under Rules v0.

### Authoritative Principles (Must Be Followed Exactly)

* Negative evidence may **weaken belief**, never negate truth
* Negative evidence may **reduce confidence gradually**, never abruptly
* Negative evidence may **raise creation thresholds**, never veto creation
* Negative evidence may **derive Contested state**, never delete Stops
* No amount of negative evidence may create an unrecoverable state

This sprint operationalizes these principles.

---

## 🚫 Absolute Scope Restrictions (Non-Negotiable)

You must NOT:

* ❌ Delete canonical Stops
* ❌ Block future Stop creation permanently
* ❌ Override structural gates
* ❌ Implement permanent removal semantics
* ❌ Implement regional or operator-specific logic
* ❌ Modify public read APIs
* ❌ Implement moderation or voting systems

Any violation automatically fails the sprint.

---

## 📁 Project Structure (Authoritative)

You must respect the existing Django project layout.

### Sprint-4D code must live in:

```
backend/transit/evaluation/
```

You may:

* Extend `stop_evaluator.py`
* Extend `stop_creation.py`
* Add helper modules (e.g. `stop_negative_evidence.py`)

Do NOT create new apps or move existing files.

---

## 🎯 Sprint-4D Objectives

### Objective A — Negative Evidence Interpretation

Support the following negative evidence types:

* `stop_not_exists`
* `stop_inactive` (semantic subtype)

Negative evidence must be:

* spatially scoped
* temporally scoped
* treated asymmetrically vs positive evidence

---

### Objective B — Confidence Reduction (Capped)

Negative evidence may reduce Stop confidence subject to a **per-evaluation-cycle hard cap**.

Requirements:

* Confidence must not drop to zero in a single cycle
* Cap must be deterministic and replay-safe
* Cap applies regardless of number of negative reports

---

### Objective C — Derived Contested State

A Stop may be marked **Contested** if and only if:

* Existing Stop confidence is above a minimal established threshold
* Credible negative evidence is present
* Credible positive evidence exists in the recent window

Negative evidence alone must **not** mark Contested.

---

### Objective D — Creation Interaction

If negative evidence exists prior to creation:

* Creation remains possible
* Belief threshold is raised
* Structural gates remain unchanged

Negative evidence must never veto creation.

---

## 🧠 Determinism & Safety Requirements

You must ensure:

* Negative evidence handling is deterministic
* Order of evidence does not change outcomes
* Replay produces identical results
* Future positive evidence can always recover belief

---

## 🧪 Blocking Test Invariants

Your implementation must satisfy **all** of the following invariants:

* INV-E1 — No deletion via negative evidence
* INV-E2 — Negative evidence weaker than aggregated positive evidence
* INV-E3 — Negative evidence modulates belief only
* INV-F1 — Confidence changes are gradual
* INV-J1 — Safe to be wrong

Tests must reference invariant IDs explicitly in comments.

---

## 🧪 Tests to Implement

Add tests under:

```
backend/transit/tests/
```

Tests must verify:

1. Negative evidence reduces confidence but never deletes a Stop
2. Confidence reduction per cycle is capped
3. Negative evidence alone does not mark Contested
4. Mixed positive + negative evidence may mark Contested
5. Future positive evidence can restore confidence
6. Negative evidence cannot permanently block creation

---

## 🗂 Expected Deliverables

By the end of Sprint-4D, the codebase must include:

* Negative evidence handling logic
* Confidence reduction with hard caps
* Contested state derivation
* Deterministic, replay-safe behavior
* Invariant-driven tests

No deletion or permanent removal logic should exist.

---

## 🛑 Definition of Done

Sprint-4D is complete **only when**:

* Negative evidence weakens belief conservatively
* No Stop is deleted or permanently disabled
* Contested state is derived correctly
* All blocking invariants pass
* Sprint-4A / 4B / 4C behavior remains unchanged

---

## 📎 Final Instruction to the Agent

After completing implementation:

1. Create a completion document at:

   * `docs/phase-1_sprints/PHASE_1_SPRINT_4D_COMPLETE.md`

2. The document must include:

   * Summary of objectives
   * Files created or modified
   * Tests added and results
   * List of invariants satisfied
   * Explicit confirmation that no deletion or veto logic exists

### 📌 Required Metadata in Completion Document

Include a section titled **`Implementation Metadata`** with:

* LLM / Coding Assistant used (tool + model if visible)
* IDE / tooling context
* Human vs AI contribution split
* Date range of implementation

> If any requested change conflicts with Rules v0 or `TEST_INVARIANTS_V0.md`, do NOT implement it.
> Explain why it would be unsafe instead.
