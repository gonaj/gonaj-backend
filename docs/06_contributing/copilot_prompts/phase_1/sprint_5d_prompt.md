# GitHub Copilot Agent Prompt — Phase-1 / Sprint-5D (API Namespace Correction Only)

> **Sprint Name:** Phase-1 Sprint-5D — API Endpoint Namespace Fix (`/api/me/*`)
>
> **Project:** Gonaj Backend (Django)
>
> **Nature of Sprint:** **MINOR REFACTOR / ROUTING FIX ONLY**

⚠️ **READ THIS FIRST — CRITICAL CONTEXT**

This sprint is **NOT** about implementing new functionality.
This sprint is **NOT** about rewriting views, services, serializers, or business logic.

All required functionality for:

* Account deletion (Sprint-5A)
* Contribution export (Sprint-5C)

**ALREADY EXISTS AND IS CORRECT.**

Your task is ONLY to **expose the existing logic under the correct public API namespace**.

If you attempt to re‑implement models, services, serializers, or logic, **the sprint fails**.

---

## 🎯 Sprint-5D Objective (Single Sentence)

Move existing user self‑service endpoints from incorrect or mixed namespaces to the canonical `/api/me/*` namespace **without changing behavior**.

---

## 📚 Authoritative Context (Read, Do NOT Re-Implement)

You may READ these documents to understand intent:

* `docs/01_architecture/backend_philosophy.md`
* `docs/01_architecture/data_rights_v1.md`
* `docs/05_execution_history/phase_1/sprint_5a_complete.md`
* `docs/05_execution_history/phase_1/sprint_5c_complete.md`

These documents describe **logic that already exists**.

⚠️ You must **reuse existing views/services exactly as-is**.

---

## 🚫 Absolute Prohibitions (Non-Negotiable)

You MUST NOT:

* ❌ Recreate or duplicate views
* ❌ Recreate serializers
* ❌ Modify services or business logic
* ❌ Touch evaluation, aggregation, or contribution logic
* ❌ Change tests asserting behavior

Allowed changes are **routing-level only**.

---

## ✅ What You ARE Allowed To Do

You MAY:

* Add new URL routes pointing to **existing views**
* Deprecate or remove old routes (if safe)
* Update API documentation to reflect new routes
* Add routing-level tests (optional)

---

## 🧭 Canonical API Rules (Authoritative)

These rules are FINAL and must be enforced:

* `/api/auth/*` → authentication & session lifecycle ONLY
* `/api/me/*` → user self‑service & data rights ONLY

Specifically:

* Contribution export MUST be available at:

  ```
  GET /api/me/contributions/export
  ```

* Account deletion MUST be available at:

  ```
  DELETE /api/me
  ```

No other namespace is acceptable for these actions.

---

## 📁 Files You May Modify (Strict)

Likely candidates (exact paths may vary):

* `backend/api/urls.py`
* `backend/api/views/*` (IMPORT ONLY — no logic changes)

If you feel tempted to create new files — **STOP**.

---

## 🧪 Tests

If tests already exist and pass — do not rewrite them.

You MAY add **small routing tests** to confirm:

* `/api/me/contributions/export` resolves correctly
* `/api/me` resolves correctly

Behavioral tests must remain unchanged.

---

## 🛑 Definition of Done

Sprint-5D is complete ONLY when:

* Existing export logic is reachable via `/api/me/contributions/export`
* Existing deletion logic is reachable via `/api/me`
* No logic duplication exists
* No business behavior has changed
* All existing tests still pass

---

## 📎 Completion Document (Required)

Create:

```
docs/05_execution_history/phase_1/sprint_5d_complete.md
```

Include:

* What routes were changed
* Which existing views were reused
* Explicit confirmation that **no logic was rewritten**
* Confirmation of API namespace compliance
* LLM model used for the changes

---

## 🧠 Final Reminder (Read Twice)

This sprint is a **namespace correction**, not an implementation sprint.

Reuse. Route. Document.

Do **not** re‑build.
