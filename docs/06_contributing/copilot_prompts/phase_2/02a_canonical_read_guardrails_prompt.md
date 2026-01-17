# Phase-2 Sprint-2A — Canonical Read Guardrails (Preparation Only)

> **IMPORTANT**
>
>This sprint does **NOT** implement any public canonical read APIs (Stops, Routes, etc.).
>
>This sprint exists **only** to establish guardrails, patterns, and constraints that all future canonical read APIs **must** follow.
>
>Assume that no canonical public read endpoints exist today.

---

## 1. Context (Read Carefully)

The Gonaj backend follows an evidence-driven architecture:

- Evidence is mutable only by accumulation, never by overwrite
- Canonical truth is derived conservatively
- Public read APIs must **never** expose evidence, diagnostics, or internal reasoning

As of now:

- There are **no** public canonical read endpoints for Stops, Routes, or other transit entities
- Existing read endpoints are limited to:
  - User self-data (`/api/auth/me`)
  - User data exports (`/api/me/contributions/export`)

This sprint prepares the system so that when canonical read APIs are introduced later, they are **forced** to comply with strict safety and visibility rules.

---

## 2. Explicit Non-Goals (Do NOT Do These)

The following are **out of scope** and must **NOT** be done:

- Do NOT add new public endpoints for Stops, Routes, or any canonical entity
- Do NOT expose any transit data publicly
- Do NOT modify evaluation logic
- Do NOT modify models or add migrations
- Do NOT change write or contribution behavior
- Do NOT assume how future canonical endpoints will be queried

This sprint is **guardrails only**.

---

## 3. What Exists Today

You must work only with what already exists:

- `backend/api/permissions.py`
- `backend/api/serializers/`
- `backend/api/views/`
- `backend/api/tests/`

There is **no** canonical read serializer for Stops or Routes yet.

---

## 4. Objective of This Sprint

Establish **enforceable constraints** so that future canonical read APIs:

- Cannot accidentally leak evidence data
- Cannot expose contributor identity or fingerprints
- Cannot expose internal IDs or diagnostics
- Are bounded against scraping or DoS
- Are safe for anonymous access by default

These constraints must be testable **now**, even though the APIs do not yet exist.

---

## 5. Required Guardrails to Implement

### 5.1 Canonical Read Permission Pattern

Define or document a permission pattern that:

- Allows GET and HEAD only
- Explicitly denies all mutation methods
- Is safe for anonymous users
- Is clearly documented as intended **only** for canonical data

No endpoint should be added using this yet — only the pattern.

---

### 5.2 Canonical Read Serializer Contract (Abstract)

Define a **base serializer contract** (abstract or documented pattern) that future canonical serializers must follow:

Rules:

- Whitelist-only fields
- Explicitly documented blocked fields
- No internal identifiers
- No contributor references
- No evidence counts or confidence scores

You may:

- Create an abstract base serializer
- Or create a documented example serializer not wired to any endpoint

Do NOT serialize real Stop or Route models yet.

---

### 5.3 Pagination & Bounding Utilities

Define shared utilities or constants for read bounding:

- Default page size
- Maximum page size
- Safe handling of malformed parameters

These must be reusable by future canonical read endpoints.

---

### 5.4 Defensive Tests (Future-Facing)

Write tests that assert:

- Canonical read permission rejects write methods
- Canonical read serializers cannot include blocked fields
- Pagination bounds are enforced
- Malformed parameters do not crash or leak details

These tests may target:

- Abstract serializers
- Dummy views created **only for testing purposes**

Tests must clearly state they are guarding future APIs.

---

## 6. Documentation Requirement

Add a short document under:

`docs/05_execution_history/phase_2/`

Suggested filename:

`phase2-sprint2a-canonical-read-guardrails.md`

The document must clearly state:

- No canonical public read APIs exist yet
- This sprint establishes mandatory guardrails
- All future canonical read APIs must comply

---

## 7. Safety & Style Constraints

- Do NOT use emojis or special characters in code, comments, or strings
- Do NOT modify unrelated files
- Do NOT refactor existing logic
- Keep changes minimal and explicit

---

## 8. Definition of Done

This sprint is complete when:

- Guardrail patterns exist and are documented
- Tests enforce future-facing constraints
- No new endpoints are exposed
- No models or migrations are changed
- Documentation clearly explains intent and scope

---

## 9. Final Reminder

This sprint is about **preventing future mistakes**, not delivering features.

Treat every change as something that future developers and agents will rely on to avoid breaking core invariants.

