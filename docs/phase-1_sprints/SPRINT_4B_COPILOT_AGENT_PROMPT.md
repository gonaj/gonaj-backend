# GitHub Copilot Agent Prompt — Phase-1 / Sprint-4B

> **Sprint Name:** Phase-1 Sprint-4B — Positive Evidence Aggregation (No Creation)
>
> **Project:** Gonaj Backend (Django)
>
> **Sprint Scope:** Pure evidence aggregation only — no belief, no creation, no canonical writes

This document is intended to be provided **as-is** to the GitHub Copilot Agent inside VS Code.

---

## 📚 Reference Documents (Authoritative)

The following documents must be loaded into context and treated as authoritative:

* `BACKEND_PHILOSOPHY.md`
* `PHASE_1_BACKEND_PLAN.md`
* `RULES_V_0_CONTEXT.md`
* `TEST_INVARIANTS_V0.md`
* `SPRINT_4A_COPILOT_AGENT_PROMPT.md` (for boundary reference)

If there is any conflict, **Rules v0 and test invariants take precedence over implementation convenience**.

---

## 🧭 Context & Purpose

You are implementing **Sprint-4B of Phase-1**.

Sprint-4B corresponds to the second part of **Phase-1 Step 5: Minimal Evaluation Pipeline**.

> Sprint-4B introduces **aggregation**, not **decision**.

Aggregation converts raw evidence into **structured summaries** that can later be evaluated — but makes **no judgments**.

---

## 🚫 Absolute Scope Restrictions (Non‑Negotiable)

You must NOT:

* ❌ Create or update canonical `Stop` records
* ❌ Call `StopWriteGateway`
* ❌ Compute or assign confidence values
* ❌ Apply creation thresholds
* ❌ Handle negative evidence semantics
* ❌ Perform decay or time-based belief changes
* ❌ Read existing canonical Stops (even read-only)
* ❌ Add or modify public APIs

Any violation automatically fails the sprint.

---

## 📁 Project Structure (Authoritative)

You must respect the existing Django project layout.

### Aggregation code must live in:

```
backend/transit/evaluation/
```

You may create **one new module**:

* `stop_aggregation.py`

Do NOT create new apps or move existing code.

---

## 🎯 Sprint-4B Objectives

### Objective A — Evidence-Only Aggregation

Implement a **pure aggregation component** that:

* Reads `ContributionEvent` evidence relevant to Stops
* Produces **immutable aggregate summaries**
* Has no side effects

Aggregation must be a pure transformation:

```
Evidence → Aggregates
```

---

### Objective B — Weighting Without Decision

Aggregation **may apply weights**, but must not apply thresholds.

Allowed weights:

* GPS accuracy weighting
* Same-user dampening
* Temporal spread weighting

Forbidden:

* “Enough evidence” checks
* Boolean decisions
* Confidence assignment

---

### Objective C — Spatial Clustering (Descriptive Only)

Aggregation may:

* Cluster evidence spatially
* Compute centroids
* Track cluster dispersion

Aggregation must not:

* Merge clusters aggressively
* Decide clusters represent real Stops

Under-merge is preferred to over-merge.

---

## 🧠 Determinism Contract

Aggregation must guarantee:

* Deterministic ordering of input evidence
* Deterministic cluster formation
* Deterministic aggregate output

The same input evidence set must always yield identical aggregates.

---

## 🧾 Aggregate Output Contract

Aggregation output must be:

* Pure Python data structures (dataclasses or frozen objects)
* Immutable once created
* Serializable

Each aggregate should include (at minimum):

* `cluster_id`
* `centroid_location`
* `evidence_count`
* `independent_contributor_count`
* `weighted_evidence_score`
* `evidence_type_breakdown`
* `temporal_span`

No methods that mutate state are allowed.

---

## 🧪 Blocking Test Invariants

Your implementation must satisfy **all** of the following invariants:

* INV-A1 — No evidence loss
* INV-B1 — Deterministic evaluation
* INV-C2 — Independence handling
* INV-C3 — Spatial convergence
* INV-D1 — Accuracy as weight, not gate
* INV-D2 — Accuracy cannot dominate alone

Tests must reference invariant IDs explicitly in comments.

---

## 🧪 Tests to Implement

Add tests under:

```
backend/transit/tests/
```

Tests must verify:

1. Aggregation is deterministic regardless of evidence order
2. Same-user evidence is dampened
3. Low-accuracy evidence contributes non-zero weight
4. Spatially distant evidence forms separate aggregates
5. No canonical writes occur during aggregation

Do NOT test Stop creation or confidence transitions.

---

## 🗂 Expected Deliverables

By the end of Sprint-4B, the codebase must include:

* Pure aggregation module for Stop evidence
* Immutable aggregate data structures
* Deterministic clustering and weighting
* Invariant-driven tests

No canonical data must be created or modified.

---

## 🛑 Definition of Done

Sprint-4B is complete **only when**:

* Aggregation produces deterministic summaries
* No semantic decisions are made
* No canonical writes occur
* All blocking invariants pass
* Sprint-4A behavior remains unchanged

---

## 📎 Final Instruction to the Agent

After completing implementation:

1. Create a completion document at:

   * `docs/phase-1_sprints/PHASE_1_SPRINT_4B_COMPLETE.md`

2. The document must include:

   * Summary of objectives
   * Files created or modified
   * Tests added and results
   * List of invariants satisfied
   * Explicit confirmation that **no Stop creation or confidence logic exists**

### 📌 Required Metadata in Completion Document

Include a section titled **`Implementation Metadata`** with:

* LLM / Coding Assistant used (tool + model if visible)
* IDE / tooling context
* Human vs AI contribution split
* Date range of implementation

> If any requested change conflicts with Rules v0 or `TEST_INVARIANTS_V0.md`, do NOT implement it.
> Explain why it would be unsafe instead.
