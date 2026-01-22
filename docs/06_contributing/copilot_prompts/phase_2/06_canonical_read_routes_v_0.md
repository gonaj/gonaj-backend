# Phase-2 Sprint-6 — Canonical Read Endpoints (Routes v0)

## Context (Read Carefully)

This repository implements **Gonaj**, an evidence-based backend.

Core principles:
- The backend is the sole authority on truth
- Evidence is immutable
- Canonical entities are derived conservatively
- Guardrails precede features
- Read APIs must NEVER leak:
  - Evidence
  - Contributor identity
  - Evaluation thresholds
  - Diagnostics

### What already exists (do NOT reimplement)

Previous Phase-2 sprints have already delivered:

1. **API boundary lockdown**
   - Explicit namespaces
   - Read vs write separation
   - 405 on unsupported methods

2. **Canonical read guardrails**
   - `ReadOnlyPublic` permission
   - Canonical serializer base class
   - Pagination bounds
   - Explicit blocked fields

3. **UI mode visibility filtering**
   - `read`, `contributor`, `admin`
   - Visibility-only, presentation-layer filtering

4. **Authorization enforcement**
   - Capability-based auth
   - Deny-by-default
   - UI modes do NOT affect authorization

5. **Canonical Stop read APIs (v1)**
   - Versioned
   - Snapshot-safe
   - Deterministic

This sprint must **use these mechanisms**, not modify them.

---

## Primary Goal

Expose the **first canonical read APIs for Routes** using existing guardrails.

This sprint introduces **read-only endpoints only**. No new evaluation, no new write paths.

---

## API Versioning Rule (Critical)

All canonical read endpoints MUST be versioned.

**Canonical version for this sprint**:
```
v1
```

---

## What This Sprint Achieves

- Public, read-only canonical Route endpoints
- Versioned API surface (`/api/v1/`)
- Safe for anonymous access
- Pagination-bounded
- Snapshot-safe
- Deterministic ordering
- Non-leaky
- UI-mode compatible

---

## Explicit Non-Goals (Hard Constraints)

You must NOT:
- Add or modify evaluation logic
- Add write or contribution endpoints
- Modify models or migrations
- Expose evidence or confidence
- Introduce stop mutation logic
- Change guardrail implementations
- Add GTFS or live tracking

Any of the above is a sprint failure.

---

## Canonical Definition (Critical)

A **canonical Route** is:
- A backend-derived belief state
- Not raw evidence
- Not a contribution
- Not user-specific
- Stable under replay

Canonical reads must never reveal:
- How many contributions exist
- Who contributed
- How close a route is to thresholds
- Internal IDs or diagnostics

---

## Public Identifier Invariants (Mandatory)

Routes exposed via read APIs MUST have a **public_id** with the following invariants:

- Deterministic
- Stable across re-evaluation
- Independent of contribution volume
- Independent of database primary keys
- Never reused
- Non-reversible

These invariants must be documented at the **API layer**, not only in models.

---

## Relationship Expansion Rule (Critical)

Canonical Route endpoints **MUST NOT embed or expand related entities**.

Specifically:
- No embedded Stops
- No `?include=stops` or similar parameters
- No nested canonical entities

Relationships may only be expressed via **stable public identifiers**.

Any relationship expansion is a **future versioned change** and out of scope for this sprint.

---

## Endpoints to Implement (Versioned)

### 1. List Routes

```
GET /api/v1/routes
```

**Properties**
- Public
- Read-only
- Paginated
- Snapshot-safe
- Deterministically ordered

**Required**
- `ReadOnlyPublic` permission
- Canonical serializer base class
- Pagination bounds from canonical guardrails
- Deterministic ordering (see Ordering Rules)
- UI mode visibility filtering

---

### 2. Route Detail

```
GET /api/v1/routes/{public_id}
```

**Properties**
- Public
- Read-only
- Deterministic
- 404-safe

---

## Ordering Rules (Mandatory)

- List endpoints MUST define explicit ordering
- Ordering MUST be deterministic
- Ordering MUST NOT depend on:
  - insertion order
  - evaluation timing
  - contribution arrival

**Required ordering**:
```
order_by(public_id)
```

This guarantees stable pagination and replay safety.

---

## Serialization Rules (Mandatory)

- Serializer MUST inherit from canonical serializer base
- Explicit field allow-list only
- Use only canonical-safe fields such as:
  - name
  - route_type
  - geometry or shape
  - belief_state

DO NOT:
- Use ModelSerializer
- Include timestamps
- Include evidence counts
- Include contributor fields
- Include stop details

---

## Pagination Rules

- Must use canonical pagination utilities
- Enforce MAX_PAGE_SIZE
- Default page size must be safe
- Invalid parameters must fail safely

---

## UI Mode Integration

- UI mode affects **visibility only**
- Do NOT branch logic based on UI mode
- Apply visibility filtering AFTER data retrieval

---

## Error Response Contract (Mandatory)

All error responses MUST:
- Be JSON
- Be schema-stable
- Contain no diagnostics
- Contain no internal identifiers
- Use standard HTTP semantics only

This applies to:
- 400
- 404
- 405

---

## Cache Semantics (Explicit Disclaimer)

- Cache behavior is **undefined in v1**
- Clients MUST NOT rely on cache headers
- Snapshot safety does NOT imply cache stability

Any cache guarantees are a future, versioned change.

---

## Tests (Mandatory)

Add tests that prove:

1. Anonymous access works
2. No evidence leakage
3. No contributor identity leakage
4. Pagination bounds enforced
5. Deterministic ordering
6. UI mode changes visibility only
7. Snapshot safety
8. Unsupported methods return 405
9. Versioned paths are enforced
10. No relationship expansion

Tests must live under:
```
backend/api/tests/
```

---

## Files You MAY Touch

- `backend/api/views/`
- `backend/api/serializers/`
- `backend/api/urls.py`
- `backend/api/tests/`
- Documentation under `docs/05_execution_history/phase_2/`

---

## Files You MUST NOT Touch

- `backend/transit/evaluation/*`
- `backend/core/models/*`
- Any migrations
- Contribution creation logic
- Authorization or visibility internals

---

## Definition of Done

This sprint is complete when:

- Canonical Route data is publicly readable via `/api/v1/routes`
- All reads are safe, bounded, and non-leaky
- No relationship expansion exists
- Ordering is deterministic
- Error responses are stable and safe
- UI modes affect visibility only
- No truth or evaluation logic is modified
- Tests clearly enforce invariants
- No emojis or special characters exist in code or strings

---

## Philosophy Reminder

Canonical reads expose **what the backend believes to be true**,
not **how** it arrived there.

If an API response allows a client to infer:
- contribution volume
- confidence thresholds
- contributor behavior

then it is wrong.

End of prompt.

