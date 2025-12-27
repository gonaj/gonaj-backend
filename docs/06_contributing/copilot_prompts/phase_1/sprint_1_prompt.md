# GitHub Copilot Agent Prompt — Phase-1 / Sprint-1

> **Sprint Name:** Phase-1 Sprint-1 — Architectural Guardrails + ContributionEvent Backbone
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

### 📁 Project Structure (Authoritative for This Sprint)

You **must respect the existing Django project layout**. Do not invent new top-level folders unless explicitly instructed.

Current high-level structure (relevant parts):

* `backend/core/` → **Foundational domain models & cross-cutting concerns**
* `backend/transit/` → Transit-domain models (to be used in later sprints, mostly empty now)
* `backend/api/` → DRF APIs (NOT to be used in this sprint)
* `backend/accounts/` → Auth & identity (DO NOT modify)

#### Placement rules for Sprint-1

* Architectural base classes / mixins **must live in**:

  * `backend/core/models/base.py` (create this file if it does not exist)

* The new **ContributionEvent** model **must live in**:

  * `backend/core/models/contribution_event.py`

* Update `backend/core/models/__init__.py` to export the new model

* Tests for Sprint-1 **must live in**:

  * `backend/core/tests/`

⚠️ Do **not** place Sprint-1 code in `transit/`, `api/`, or `accounts/`.

---

## 🧭 Context & Non-Negotiable Rules

You are implementing **Sprint-1 of Phase-1**, as defined in `phase_1_backend_plan.md`.

This sprint corresponds to **Phase-1 Implementation Order steps 1 and 2**:

1. Architectural guardrails
2. ContributionEvent backbone

⚠️ **DO NOT implement anything beyond these two items.**

---

## 🚫 Absolute Restrictions

* ❌ **DO NOT modify or refactor existing Sprint-0, Sprint-1, or Sprint-2 implementations**
  (authentication, user models, infra, allauth, tokens, etc.)
* ❌ **DO NOT add features from later phases**
  (no canonical transit entities, no evaluation logic, no moderation UI, no read APIs)
* ❌ **DO NOT introduce CRUD APIs on any canonical data**
* ❌ **DO NOT delete or overwrite any existing data or models**
* ❌ **DO NOT add GTFS, OSM, leaderboard, reputation, or scheduling logic**

Existing code may be touched **only if strictly required** to enforce architectural guardrails.

---

## ✅ Sprint-1 Objectives

### Objective A — Architectural Guardrails

Implement structural guardrails that make it **hard or impossible** to violate Phase-1 invariants accidentally.

#### Requirements

1. **No hard deletes**

   * Introduce a shared base model / mixin that:

     * disables or overrides hard deletes
     * enforces soft invalidation via timestamps if needed
   * Apply this base model **only where appropriate**

2. **Immutable / append-only pattern**

   * Define a reusable base class or mixin for immutable records
   * Clearly document (via code comments and docstrings) that updates are forbidden

3. **Versioning foundation**

   * Create a reusable base for versioned entities
   * Include fields such as:

     * `version`
     * `valid_from`
     * `valid_until`
   * Do **not** yet apply this to transit entities

4. **Code-level guardrails**

   * Add clear comments explaining:

     * which models are immutable
     * which patterns must never be bypassed
     * which features are deferred to later phases

---

### Objective B — ContributionEvent Backbone (Evidence Layer)

Implement the **core evidence storage mechanism** for Phase-1.

This is the **only new domain model** to be introduced in this sprint.

#### ContributionEvent Model

Create a model named **`ContributionEvent`** with the following properties:

* Immutable and append-only
* Stores evidence, not truth
* Replayable and auditable

##### Required Fields (Conceptual)

* `id` (UUID, server-generated)
* `client_generated_id` (UUID, used for idempotency)
* `contributor` (ForeignKey to User)
* `device_id` (nullable, if Device model exists)
* `contribution_type` (enum / choice field)
* `subject_ref` (opaque reference or geo hint; string or JSON)
* `payload` (JSON field, raw evidence)
* `observed_at` (timestamp from client)
* `submitted_at` (server timestamp)
* `context` (JSON: accuracy, app_version, offline flag, etc.)

##### Invariants to Enforce

* No UPDATE operations
* No DELETE operations
* Duplicate submissions (same `client_generated_id`) must be idempotent
* No canonical data writes triggered from this model

---

## 🧪 Tests & Validation

Add **minimal but meaningful tests**:

* Creating a `ContributionEvent` succeeds
* Attempting to update or delete a `ContributionEvent` fails
* Duplicate submission using the same `client_generated_id` is idempotent
* Model imports correctly and migrations apply cleanly

Do **not** add business-logic or evaluation tests yet.

---

## 🗂 Expected Deliverables

By the end of Sprint-1, the codebase must include:

* Architectural guardrail base classes / mixins
* `ContributionEvent` model and migrations
* Clear docstrings explaining evidence-first design
* Tests validating immutability and idempotency
* **No APIs exposed yet** (models and foundations only)

---

## 🧠 Architectural Reminders

* Canonical truth **does not exist yet**
* Moderation **does not exist yet**
* Evaluation logic **does not exist yet**
* ContributionEvent is never "approved" or "rejected" — it simply exists
* This sprint is about **safety**, not usefulness

---

## 🛑 Definition of Done

Sprint-1 is complete **only when**:

* Evidence can be stored immutably
* Accidental truth mutation is structurally prevented
* Future replay and evaluation are possible
* No Phase-2 concepts leaked into the codebase

---

## 📎 Final Instruction to the Agent

> If any requested change conflicts with `backend_philosophy.md` or violates an invariant from `phase_1_backend_plan.md`, **do not implement it**.
> Instead, explain why the change would be unsafe.
