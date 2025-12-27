# GitHub Copilot Agent Prompt — Phase-1 / Sprint-4A

> **Sprint Name:** Phase-1 Sprint-4A — Evaluation Scaffolding & Determinism
> **Project:** Gonaj Backend (Django)
> **Sprint Scope:** Strictly limited to evaluation plumbing (no decision logic)

This document is intended to be provided **as-is** to the GitHub Copilot Agent inside VS Code.

---

## 📚 Reference Documents (Authoritative)

The following documents must be considered authoritative and loaded into context:

* `backend_philosophy.md`
* `phase_1_backend_plan.md`
* `rules_v0_context.md`
* `test_invariants_v0.md`

If any conflict exists, **architectural invariants and Rules v0 take precedence over implementation convenience**.

---

## 🧭 Context & Purpose

You are implementing **Sprint-4A of Phase-1**.

Sprint-4A corresponds to the first part of **Phase-1 Step 5: Minimal Evaluation Pipeline**.

This sprint establishes the **evaluation spine**, not the evaluation logic.

> The goal is to make future evaluation deterministic, replayable, and safe — without deciding anything yet.

---

## 🚫 Absolute Scope Restrictions (Read Carefully)

You must NOT:

* ❌ Implement any stop creation logic
* ❌ Implement confidence calculations
* ❌ Implement decay logic
* ❌ Implement negative evidence handling
* ❌ Implement spatial clustering or thresholds
* ❌ Modify existing Sprint-1, Sprint-2, or Sprint-3 logic
* ❌ Add or modify public APIs
* ❌ Write GTFS, OSM, moderation, or reputation logic

If any of the above appears in your output, the sprint is considered failed.

---

## 📁 Project Structure (Authoritative)

You must respect the existing Django project layout.

Relevant directories:

* `backend/core/` → Evidence models (read-only in this sprint)
* `backend/transit/` → Canonical models (write only through controlled gateway)
* `backend/transit/models/` → Canonical Stop model (already exists)

### New code for Sprint-4A must live in ONE of:

* `backend/transit/evaluation/`

  * `__init__.py`
  * `base.py`
  * `stop_evaluator.py`

You may create this new package if it does not already exist.

Do NOT create new apps.

---

## 🎯 Sprint-4A Objectives

### Objective A — Deterministic Evaluation Entrypoint

Create a **single deterministic entrypoint** for Stop evaluation.

Requirements:

* Accepts a collection of `ContributionEvent` records
* Sorts and processes evidence deterministically
* Is agnostic to incremental vs batch invocation

The entrypoint must make no assumptions about thresholds or outcomes.

---

### Objective B — Canonical Write Gateway

Create a **single controlled pathway** through which canonical Stop records may be written.

Requirements:

* All writes go through one explicit method or service
* Direct `.save()` on canonical models must not be used elsewhere
* Gateway exists even if it performs minimal work in this sprint

This gateway will later enforce invariants.

---

### Objective C — Replay & Recompute Hooks

Provide explicit hooks for:

* Full recomputation (from all evidence)
* Incremental evaluation (from new evidence)

Both must route through the same deterministic core.

---

## 🧠 Determinism Requirements (Non-Negotiable)

You must ensure:

* Evidence ordering is deterministic (explicit sort keys)
* No reliance on database default ordering
* No use of wall-clock time during evaluation
* No randomness

Given identical inputs, outputs must be byte-identical.

---

## 🧪 Blocking Test Invariants (Must Hold)

Your implementation must satisfy **all** of the following invariants:

* INV-A1 — No evidence loss
* INV-A2 — Evidence immutability
* INV-B1 — Deterministic evaluation
* INV-B2 — Replay equivalence
* INV-I2 — Canonical write protection

Tests must reference invariant IDs explicitly in comments.

---

## 🧪 Tests to Implement

Add tests under:

* `backend/transit/tests/`

Tests must verify:

1. Deterministic ordering of evidence
2. Incremental vs batch entrypoint convergence
3. Canonical writes only occur via gateway
4. No evidence mutation occurs

Do NOT test stop creation or confidence values.

---

## 🗂 Expected Deliverables

By the end of Sprint-4A, the codebase must include:

* Evaluation scaffolding for Stop
* Deterministic evaluation entrypoint
* Canonical write gateway (even if minimal)
* Replay and incremental hooks
* Invariant-focused tests

No semantic Stop logic should exist yet.

---

## 🛑 Definition of Done

Sprint-4A is complete **only when**:

* Evaluation can be run deterministically
* Incremental and batch paths converge
* Canonical writes are gated
* All blocking invariants pass
* No scope violations exist

---

## 📎 Final Instruction to the Agent

After completing implementation:

1. Create a completion document at:

   * `docs/05_execution_history/phase_1/sprint_4a_complete.md`

2. The document must include:

   * Summary of objectives
   * Files created or modified
   * Tests added and results
   * List of invariants satisfied
   * Explicit confirmation that no evaluation logic was implemented

### 📌 Required Metadata in Completion Document

Include a section titled **`Implementation Metadata`** with:

* LLM / Coding Assistant used (tool + model if visible)
* IDE / tooling context
* Human vs AI contribution split
* Date range of implementation

> If any requested change conflicts with Rules v0 or `docs/02_phase_1/test_invariants_v0.md`, do NOT implement it.
> Explain why it would be unsafe instead.
