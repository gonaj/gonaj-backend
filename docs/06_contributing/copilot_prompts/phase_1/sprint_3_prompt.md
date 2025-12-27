# GitHub Copilot Agent Prompt — Phase-1 / Sprint-3

> **Sprint Name:** Phase-1 Sprint-3 — Canonical Entity Skeletons (No Evaluation Logic)
> **Project:** Gonaj Backend (Django)
> **Sprint Scope:** Strictly limited to items defined below

This document is intended to be provided **as-is** to the GitHub Copilot Agent inside VS Code.

---

## 📚 Reference Documents (Provided to the Agent)

The following documents must be considered authoritative:

* `backend_philosophy.md`
* `discussion_summary.md`
* `phase_1_backend_plan.md`

If there is any conflict, `phase_1_backend_plan.md` takes precedence.

---

## 🧭 Context & Non-Negotiable Rules

You are implementing **Sprint-3 of Phase-1**, as defined in `phase_1_backend_plan.md`.

This sprint corresponds to **Phase-1 Implementation Order step 4**:

4. **Canonical entity skeletons**

⚠️ **DO NOT implement anything beyond this step.**

Sprint-3 is about defining **what canonical truth *can look like*** — **not** how truth is derived.

---

## 📁 Project Structure (Authoritative — SAME AS PREVIOUS SPRINTS)

You **must respect the existing Django project layout**. Do not invent new top-level folders.

Relevant structure:

* `backend/core/` → Evidence layer, guardrails, shared bases (already implemented)
* `backend/transit/` → **Canonical transit domain (USE THIS APP FOR SPRINT-3)**
* `backend/api/` → APIs (DO NOT modify in this sprint)
* `backend/accounts/` → Auth & identity (DO NOT modify)

### Placement rules for Sprint-3

* Canonical transit models **must live in**:

  * `backend/transit/models/`

* Each canonical entity should be in its **own file**, for example:

  * `stop.py`
  * `route.py`
  * `route_variant.py`
  * `stop_route_link.py`
  * `observed_service_window.py`

* Update `backend/transit/models/__init__.py` to export all canonical entities

* Migrations **must be created** for new models

* Tests **must live in**:

  * `backend/transit/tests/`

⚠️ Do **not** place canonical models in `core/` or `api/`.

---

## 🚫 Absolute Restrictions

* ❌ **DO NOT modify Sprint-1 code** (guardrails, `ImmutableModel`, `ContributionEvent`)
* ❌ **DO NOT modify Sprint-2 code** (contribution APIs, serializers, views)
* ❌ **DO NOT implement evaluation, aggregation, promotion, decay, or moderation logic**
* ❌ **DO NOT write any logic that derives truth from ContributionEvent**
* ❌ **DO NOT expose any APIs (read or write)**
* ❌ **DO NOT add GTFS, OSM, scheduling, or leaderboard concepts**

Sprint-3 defines **structure only**.

---

## ✅ Sprint-3 Objectives

### Objective A — Canonical Entity Definitions (Skeleton Only)

Define the **canonical transit entities** required for Phase-1.

You must implement **only** the following entities:

1. **Stop**
2. **Route** (logical route, not trips)
3. **RouteVariant** (directional / variant-level route)
4. **StopRouteLink** (association between stops and routes/variants)
5. **ObservedServiceWindow** (observed service-time hints)

No additional canonical entities are allowed.

---

### Objective B — Required Canonical Metadata

Each canonical entity **must include fields enabling replay, audit, and evolution**.

At minimum, every canonical model must include:

* `id` (UUID primary key)
* `public_id` (stable, opaque identifier for external use)
* `version` (integer)
* `valid_from` (timestamp)
* `valid_until` (nullable timestamp)
* `structural_confidence` (float or decimal)
* `freshness_confidence` (float or decimal)
* `ruleset_version` (string or integer)
* `evidence_refs` (array / JSON of ContributionEvent IDs)
* `created_at`
* `updated_at`

⚠️ These fields **do not imply behavior** in Sprint-3 — they exist for future sprints.

---

### Objective C — Guardrails on Canonical Models

Canonical models must:

* Be **write-protected** (no casual updates)
* Not expose convenience methods that mutate truth
* Clearly document (docstrings) that:

  * they represent *current belief*
  * they are **derived**, not directly edited

You may reuse base classes or mixins from `backend/core/models/base.py` **if appropriate**, but do not refactor them.

---

## 🧪 Tests & Validation

Add **structural tests only**:

* Models import correctly
* Migrations apply cleanly
* Required fields exist on each model
* No evaluation or business logic is present

Tests must **not**:

* Assert correctness of data
* Simulate evaluation
* Touch ContributionEvent

---

## 🗂 Expected Deliverables

By the end of Sprint-3, the codebase must include:

* Canonical transit model skeletons (no logic)
* Migrations for all canonical entities
* Clear docstrings explaining canonical vs evidence roles
* Structural tests for canonical models
* No API changes

---

## 🧠 Architectural Reminders

* Canonical data is **derived but materialized**
* Canonical tables exist for **query efficiency**, not authority
* Authority remains with immutable ContributionEvent records
* Sprint-3 defines shape, not behavior

---

## 🛑 Definition of Done

Sprint-3 is complete **only when**:

* All required canonical entities exist as skeletons
* Required metadata fields are present
* No evaluation or decay logic exists
* No APIs were added or modified
* All tests pass
* Sprint-1 and Sprint-2 code remains untouched

---

## 📎 Final Instruction to the Agent

After completing implementation:

1. **Create a completion document** at:

   * `docs/05_execution_history/phase_1/sprint_3_complete.md`

2. The document **must include**:

   * Summary of Sprint-3 objectives
   * List of canonical entities added
   * Files created/modified
   * Tests added and results
   * Confirmation that no evaluation logic exists
   * Confirmation that Sprint-1 and Sprint-2 code was not modified

### 📌 Required Metadata in Completion Document

Include a dedicated section titled **`Implementation Metadata`** containing:

* **LLM / Coding Assistant Used** (tool + model, if visible)
* **IDE / Tooling Context**
* **Human vs AI Contribution Split**
* **Date Range of Implementation**

> If any requested change conflicts with `docs/01_architecture/backend_philosophy.md` or violates an invariant from `docs/02_phase_1/phase_1_backend_plan.md`, **do not implement it**.
> Instead, explain why the change would be unsafe.
