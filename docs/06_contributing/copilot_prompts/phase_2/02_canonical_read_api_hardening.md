# Phase-2 Sprint-2 — Canonical Read API Hardening

## Purpose

This sprint hardens **canonical read APIs** so they are safe for anonymous access, leak no internal state, and remain stable under hostile or malformed usage.

This sprint is strictly **read-only** in scope. No evaluation, contribution, or domain semantics may be altered.

---

## Absolute Constraints (Non-Negotiable)

- Do NOT modify:
  - Any model in `backend/core/models`
  - Any evaluation logic in `backend/transit/evaluation`
  - Any migration files
  - Any write / contribution endpoint behavior
  - Any serializer used for write paths

- Do NOT add new endpoints.
- Do NOT change request shapes.
- Do NOT introduce new permissions beyond read-safety enforcement.

- Do NOT use emojis or special characters anywhere in code, comments, logs, or strings.

- All work MUST be done on a **new feature branch** named:
  `phase2-sprint2-canonical-read-hardening`

---

## Architectural Invariants to Respect

You must respect these invariants at all times:

- Canonical data is the only data exposed to anonymous users.
- Evidence data must never be inferable from read APIs.
- Absence of data must not be interpreted as falseness.
- Backend remains sole authority on truth.
- UI modes affect visibility only, not semantics.

Refer to:
- `docs/01_architecture/backend_philosophy.md`
- `docs/01_architecture/ui_constitution_v1.md`
- `docs/02_phase_1/rules_v0.md`

---

## Scope of This Sprint

### 1. Harden Public Canonical Read Endpoints

Target modules:

- `backend/api/views/contributions.py` (read paths only)
- `backend/api/views/export.py` (read-only behavior confirmation)
- `backend/api/views/me.py` (read-only endpoints only)

Required changes:

- Explicitly enforce read-only behavior using:
  - HTTP method allow-lists
  - Safe permission classes (`ReadOnlyPublic` or equivalent)

- Ensure unsupported HTTP verbs return HTTP 405 consistently.

---

### 2. Canonical Serializer Lockdown

Target modules:

- `backend/api/serializers/contributions.py`
- Any serializer used for canonical read responses

Required changes:

- Ensure serializers:
  - Expose only canonical fields
  - Do NOT include:
    - contributor identifiers
    - fingerprints
    - internal IDs
    - evaluation diagnostics
    - confidence internals

- Validate output schemas strictly.
- Remove or block accidental field leakage.

---

### 3. Anonymous Safety Guarantees

Target modules:

- `backend/api/tests/`

Add tests to assert:

- Anonymous users:
  - Can access canonical read endpoints
  - Cannot infer evidence existence
  - Cannot access user-scoped data

- Responses:
  - Are stable under malformed parameters
  - Do not leak stack traces or debug info

---

### 4. Pagination and Bounding Enforcement

Target modules:

- Canonical read views only

Required behavior:

- Enforce reasonable pagination defaults
- Enforce hard upper bounds
- Reject unbounded queries explicitly

This prevents scraping and accidental DoS.

---

### 5. Documentation Update

Target file:

- `docs/05_execution_history/phase_2/phase2-sprint2-canonical-read-hardening.md`

Document:

- Which endpoints are canonical-read
- What guarantees they provide
- What they explicitly do NOT provide

Do NOT restate Phase-1 philosophy. Reference it instead.

---

## Testing Requirements

You MUST add or update tests to cover:

- HTTP 405 for unsupported verbs
- Anonymous access safety
- No evidence leakage through serializers
- Pagination bounds enforcement
- Output schema stability

Tests must be deterministic and isolated.

---

## Explicit Out of Scope

- No evaluation changes
- No contribution logic changes
- No moderation tooling
- No performance optimizations
- No third-party app integration

---

## Definition of Done

This sprint is complete only if:

- All canonical read endpoints are safe for anonymous access
- No internal or evidence data can be inferred
- Unsupported methods are rejected cleanly
- All new tests pass
- Existing tests remain unchanged

Any deviation is a failure.

---

## Final Instruction to Copilot

Treat this sprint as **surgical hardening**, not feature development.

If you believe a change is required outside this scope:
- STOP
- Do NOT implement it
- Leave a comment explaining why

Do not refactor unrelated code.
Do not improve code style.
Do not optimize.

Only enforce safety, boundaries, and correctness.

