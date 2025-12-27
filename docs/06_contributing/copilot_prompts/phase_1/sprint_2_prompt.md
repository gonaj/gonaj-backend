# GitHub Copilot Agent Prompt — Phase-1 / Sprint-2

> **Sprint Name:** Phase-1 Sprint-2 — Write APIs (Evidence Ingestion)
> **Project:** Gonaj Backend (Django)
> **Sprint Scope:** Strictly limited to items defined below

This document is intended to be provided **as-is** to the GitHub Copilot Agent inside VS Code.

---

## 📚 Reference Documents (Provided to the Agent)

The following documents must be considered authoritative:

* `backend_philosophy.md`
* `discussion_summary.md`
* `phase_1_backend_plan.md`

If there is any conflict, `docs/02_phase_1/phase_1_backend_plan.md` takes precedence.

---

## 🧭 Context & Non-Negotiable Rules

You are implementing **Sprint-2 of Phase-1**, as defined in `docs/02_phase_1/phase_1_backend_plan.md`.

This sprint corresponds to **Phase-1 Implementation Order step 3**:

3. **Write APIs (evidence ingestion)**

⚠️ **DO NOT implement anything beyond this step.**

---

## 📁 Project Structure (Authoritative — SAME AS SPRINT-1)

You **must respect the existing Django project layout**. Do not invent new top-level folders.

Relevant structure:

* `backend/core/` → Domain models & evidence layer (already implemented)
* `backend/api/` → **DRF APIs (USE THIS APP FOR SPRINT-2)**
* `backend/accounts/` → Auth & identity (DO NOT modify)
* `backend/transit/` → Canonical transit models (DO NOT touch)

### Placement rules for Sprint-2

* DRF views, serializers, and URLs for contributions **must live in**:

  * `backend/api/views/contributions.py`
  * `backend/api/serializers/contributions.py`
  * `backend/api/urls.py` (extend, do not rewrite)

* Business logic **must not** live in views; keep logic thin and defer to models/services

* Tests **must live in**:

  * `backend/api/tests/test_contributions_api.py`

⚠️ Do **not** place API code in `core/` or `transit/`.

---

## 🚫 Absolute Restrictions

* ❌ **DO NOT modify Sprint-1 implementations** (`ImmutableModel`, `ContributionEvent`, guardrails)
* ❌ **DO NOT create or modify canonical transit entities**
* ❌ **DO NOT implement evaluation, promotion, decay, or moderation logic**
* ❌ **DO NOT expose read APIs for canonical data**
* ❌ **DO NOT allow anonymous writes**
* ❌ **DO NOT update or delete ContributionEvent records**

Any violation is a sprint failure.

---

## ✅ Sprint-2 Objectives

### Objective A — Authenticated Contribution Write API

Implement **authenticated write-only APIs** for submitting evidence as `ContributionEvent` records.

#### API Requirements

* Endpoint base path: `/v1/contributions/`
* HTTP method: `POST`
* Authentication: **required** (reuse existing auth system)
* Authorization: any authenticated user may contribute

The API must:

* Accept client-generated UUID for idempotency
* Validate payload shape minimally (structure, not truth)
* Create `ContributionEvent` using **existing model methods only**
* Return existing event on idempotent retry

---

### Objective B — Supported Contribution Types (Phase-1 Only)

The API must support **only** the following contribution types:

1. `stop_name`
2. `stop_exists`
3. `stop_not_exists`
4. `stop_location`
5. `route_exists`
6. `route_traversal`
7. `stop_sequence`
8. `service_time`

Reject all other types with a clear error.

---

### Objective C — Input Validation (Evidence Quality, Not Truth)

Implement **lightweight validation only**:

* Required fields present
* `observed_at` not in the future
* `payload`, `subject_ref`, and `context` are valid JSON objects
* Contribution type matches allowed list

⚠️ Do **not** infer correctness or truth.

---

### Objective D — Idempotency Handling

* Honor `client_generated_id` for idempotency
* Duplicate submissions must:

  * Return HTTP 200/201 with existing event
  * Never create duplicates

---

## 🧪 Tests & Validation

Add API tests covering:

* Auth required (401 if unauthenticated)
* Successful creation for each contribution type
* Idempotent retry behavior
* Invalid payload rejection
* Future `observed_at` rejection

Tests must **not** assert anything about canonical truth.

---

## 🗂 Expected Deliverables

By the end of Sprint-2, the codebase must include:

* Write-only contribution API endpoint
* DRF serializers for evidence submission
* URL routing under `/v1/contributions/`
* API tests validating correctness & safety
* No canonical reads or writes

---

## 🧠 Architectural Reminders

* This sprint **only ingests evidence**
* No belief, truth, or evaluation exists yet
* ContributionEvent remains immutable
* The API is write-only by design

---

## 🛑 Definition of Done

Sprint-2 is complete **only when**:

* Authenticated users can submit evidence
* Evidence is stored immutably as ContributionEvent
* Idempotency is enforced
* No Phase-2 or later concepts appear
* All tests pass

### 📝 Completion Document Requirements

### 📌 Required Metadata in Completion Document

The completion document **must include a dedicated section titled `Implementation Metadata`** containing at least the following information:

* **LLM / Coding Assistant Used** (e.g., GitHub Copilot, Copilot Chat, model name if visible)
* **IDE / Tooling Context** (e.g., VS Code, extensions used if relevant)
* **Human vs AI Contribution Split** (brief qualitative note: e.g., “AI-generated initial drafts, human-reviewed and edited”)
* **Date Range of Implementation**

This metadata is required for future auditability, reproducibility, and architectural forensics.

---

## 📎 Final Instruction to the Agent

After completing implementation:

1. **Create a completion document** at:

   * `docs/05_execution_history/phase_1/sprint_2_complete.md`

2. The document must include:

   * Summary of objectives
   * Files created/modified
   * Tests added and results
   * Confirmation of invariant compliance
   * Explicit statement that no out-of-scope features were implemented

> If any requested change conflicts with `docs/01_architecture/backend_philosophy.md` or violates an invariant from `docs/02_phase_1/phase_1_backend_plan.md`, **do not implement it**.
> Instead, explain why the change would be unsafe.
