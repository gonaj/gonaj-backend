# Phase-2 Sprint-7 — Rate Limiting & Idempotency

## Context (Read Carefully)

This repository implements **Gonaj**, an evidence-based backend.

Core principles that MUST remain intact:
- Backend is the sole authority on truth
- Evidence is immutable
- Canonical entities are derived conservatively
- Guardrails always precede features
- Rate limiting and idempotency are **operational protections**, not semantic logic

This sprint introduces **traffic safety mechanisms only**.

It must NOT alter:
- What the backend believes
- How beliefs are evaluated
- How canonical entities are derived

---

## What Already Exists (Do NOT Reimplement)

Previous Phase-2 sprints have already delivered:

1. **API Surface Boundary Lockdown**
   - Explicit read vs write separation
   - 405 on unsupported HTTP methods

2. **Canonical Read Guardrails**
   - ReadOnlyPublic permission
   - Pagination bounds
   - Explicit field allow-lists

3. **UI Mode Visibility Filtering**
   - Presentation-only filtering
   - UI modes do NOT affect authorization

4. **Authorization Enforcement**
   - Capability-based auth
   - Deny-by-default for mutations

5. **Canonical Read Endpoints (Stops v0, Routes v0)**
   - Public read-only endpoints
   - Snapshot-safe

This sprint must **layer protections on top**, not change any of the above.

---

## Primary Goal

Protect exposed APIs from:
- Flooding
- Scraping
- Replay and duplicate writes

Without affecting:
- Evaluation logic
- Canonical semantics
- Visibility rules

---

## What This Sprint Achieves

- Controlled request volume for public reads
- Controlled request volume for authenticated writes
- Safe retry semantics for mutation endpoints
- Explicit idempotency guarantees

---

## Explicit Non-Goals (Hard Constraints)

You must NOT:
- Modify evaluation logic
- Modify canonical models
- Modify serializers for semantic reasons
- Add new API endpoints
- Change existing endpoint behavior beyond rate limiting or idempotency
- Add abuse scoring or heuristics
- Persist rate-limit state in application models

Any of the above is a sprint failure.

---

## Scope Definition

### APIs In Scope

**Read APIs**
- GET /api/v1/stops
- GET /api/v1/stops/{public_id}
- GET /api/v1/routes
- GET /api/v1/routes/{public_id}

**Write APIs**
- POST /api/v1/contributions
- DELETE /api/me

---

## Key Work Items

### 1. Per-IP Rate Limiting for Reads

**Objective**
- Prevent scraping and brute-force enumeration

**Rules**
- Anonymous read requests are rate-limited by IP
- Authenticated read requests may share same limits (keep simple)
- Limits must be conservative and configurable

**Implementation Guidance**
- Use Django REST Framework throttling
- Define custom throttle classes
- Do NOT hardcode limits inside views

---

### 2. Per-User Rate Limiting for Writes

**Objective**
- Prevent write floods and accidental client loops

**Rules**
- Write endpoints must be throttled per authenticated user
- Anonymous users must never be allowed to write (already enforced)

**Implementation Guidance**
- Use DRF UserRateThrottle or custom subclass
- Throttling must be independent of UI mode

---

### 3. Idempotency Keys for Mutation Endpoints

**Objective**
- Allow safe retries without duplicate mutations

**Explicit Scope (Frozen for Phase-2)**
Idempotency applies ONLY to the following mutation endpoints:
- POST /api/v1/contributions
- DELETE /api/me

No other endpoints may implement idempotency behavior in this sprint.
Any future mutation endpoint MUST introduce idempotency via a new sprint.

**Rules**
- Idempotency applies ONLY to the mutation endpoints listed above
- Client supplies an Idempotency-Key header
- Replaying the same key with the same payload must NOT create duplicate effects
- Replaying the same key with a different payload must fail safely
- Missing Idempotency-Key behaves as non-idempotent

**Implementation Guidance**
- Idempotency must be request-scoped
- Store idempotency state in cache or equivalent
- Do NOT modify contribution or deletion logic

---

## Test-Driven Development Requirement (MANDATORY)

You must follow strict TDD:

1. Write failing tests FIRST
2. Verify tests fail
3. Implement minimal code to pass tests
4. Verify all tests pass

Do NOT write implementation before tests.

---

## Required Tests

You must add tests that prove:

### Rate Limiting
- Excessive anonymous read requests return HTTP 429
- Rate limit headers are present and stable
- Authenticated users are throttled independently
- Rate limiting does NOT affect authorization semantics

### Idempotency
- Same Idempotency-Key with same payload is safe
- Same Idempotency-Key with different payload fails
- Missing Idempotency-Key behaves as non-idempotent
- Idempotency does NOT leak internal state

### Invariants
- UI mode does NOT affect throttling
- Rate limiting does NOT affect evaluation or truth
- Throttling failures do NOT leak diagnostics

Tests must live under:
```
backend/api/tests/
```

---

## Files You MAY Touch

- backend/api/throttling.py (new)
- backend/api/views/
- backend/api/tests/
- backend/api/settings (throttle config only)
- docs/05_execution_history/phase_2/

---

## Files You MUST NOT Touch

- backend/transit/evaluation/*
- backend/core/models/*
- Any migrations
- Canonical serializers logic
- Visibility module
- Authorization module

---

## Definition of Done

This sprint is complete when:

- Public reads are rate-limited per IP
- Writes are rate-limited per user
- Mutation endpoints support idempotent retries
- HTTP 429 is returned for limit violations
- All behavior is covered by tests
- No semantic logic is altered
- No forbidden files are modified
- No emojis or special characters exist in code or strings

---

## Philosophy Reminder

Rate limiting and idempotency are **seatbelts**, not steering wheels.

They protect the system under stress but must never:
- Change truth
- Bias evaluation
- Reveal internals

If disabling throttling changes correctness, the implementation is wrong.

End of prompt.

