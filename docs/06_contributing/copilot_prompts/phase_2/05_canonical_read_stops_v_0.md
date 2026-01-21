# Phase-2 Sprint-5 — Canonical Read Endpoints (Stops v0)

## Context (Read Carefully)

This repository implements Gonaj, an evidence-based backend.

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

1. API surface boundary lockdown
   - Explicit namespaces
   - Read vs write separation
   - 405 on unsupported methods

2. Canonical read guardrails (NO endpoints yet)
   - ReadOnlyPublic permission
   - Canonical serializer base class
   - Pagination bounds
   - Explicit blocked fields

3. UI mode visibility filtering
   - read, contributor, admin
   - Visibility-only, presentation-layer filtering

4. Authentication and authorization enforcement
   - Capability-based authorization
   - Deny-by-default model
   - UI modes do NOT affect authorization

This sprint must use these mechanisms as-is and must not modify them.

---

## Primary Goal

Expose the first canonical read APIs for Stops using existing guardrails.

This sprint introduces read-only endpoints only. It does not introduce new rules, heuristics, or evaluation logic.

---

## API Versioning Rule (Mandatory)

All canonical read endpoints MUST be versioned.

Rationale:
- Canonical schemas evolve conservatively
- Public read APIs are long-lived contracts
- Versioning prevents silent client breakage

Versioning policy:
- Path-based versioning
- Version applies to canonical read APIs only
- Version is part of the public contract

Canonical version for this sprint:

/api/v1

---

## What This Sprint Achieves

- Public, read-only canonical Stop endpoints
- Explicitly versioned API surface
- Safe for anonymous access
- Pagination-bounded
- Snapshot-safe
- Non-leaky
- Compatible with UI mode visibility filtering

---

## Explicit Non-Goals (Hard Constraints)

This sprint must NOT:
- Add or modify evaluation logic
- Add write or contribution endpoints
- Modify models or migrations
- Expose evidence, confidence, or diagnostics
- Introduce Route APIs
- Change guardrail implementations
- Add GTFS ingestion or live tracking

Any of the above constitutes a sprint failure.

---

## Canonical Definition (Critical)

A canonical Stop is:
- A backend-derived belief state
- Not raw evidence
- Not a contribution
- Not user-specific
- Stable under replay

Canonical reads must never reveal:
- Contribution counts or density
- Contributor identity
- Distance to thresholds
- Internal identifiers
- Evaluation internals

---

## Endpoints to Implement (Versioned)

### 1. List Stops

GET /api/v1/stops

Properties:
- Public
- Read-only
- Paginated
- Snapshot-safe

Required:
- ReadOnlyPublic permission
- Pagination bounds from canonical guardrails
- Canonical serializer base class
- UI mode visibility filtering applied after data retrieval

---

### 2. Stop Detail

GET /api/v1/stops/{public_id}

Properties:
- Public
- Read-only
- Deterministic
- 404-safe

---

## Public Identifier Rules

- Database primary keys must never be exposed
- A stable public identifier must be used
- If a public identifier already exists, reuse it
- If none exists:
  - Derive a deterministic, non-reversible public ID
  - Ensure stability across re-evaluation
  - Document the derivation clearly

Internal UUIDs must never appear in responses.

---

## Serialization Rules (Mandatory)

- Serializers must inherit from the canonical serializer base class
- Explicit field allow-list only
- Only canonical-safe fields may be exposed, for example:
  - name
  - geometry or coordinates
  - belief_state
  - stop_type (if applicable)

The following are strictly forbidden:
- ModelSerializer usage
- Timestamps
- Evidence counts
- Confidence values
- Contributor references

---

## Ordering Guarantees

- List responses must have a deterministic ordering
- Ordering must not depend on evaluation timing, database insertion order, or pagination cursor instability
- Ordering strategy must be explicitly documented in code and tests

---

## Pagination Rules

- Canonical pagination utilities must be used
- Default page size must be safe
- MAX_PAGE_SIZE must be enforced
- Invalid parameters must fail safely

---

## Snapshot Semantics

Snapshot-safe means:
- Each request observes a self-consistent view of canonical data
- No guarantee is made across requests
- No transactional or historical snapshot guarantees are implied

---

## Query Surface (v1 Freeze)

For v1 canonical Stop APIs:
- Only pagination parameters are allowed
- No filtering, searching, or sorting parameters are permitted
- Any unsupported query parameters must be rejected or ignored safely

This freeze prevents accidental client dependency on unstable behavior.

---

## UI Mode Integration

- UI mode affects visibility only
- UI mode must not affect query logic
- Visibility filtering must be applied after data retrieval
- Authorization must remain independent of UI mode

---

## Error Handling Guarantees

- Errors must be JSON-only
- Error shapes must be stable
- No diagnostics, stack traces, or internal identifiers may appear
- 404 responses must not leak existence or evaluation details

---

## Tests (Mandatory)

Tests must prove:
1. Anonymous access works
2. No evidence leakage
3. No contributor identity leakage
4. Pagination bounds are enforced
5. Deterministic ordering
6. UI mode changes visibility only
7. Snapshot safety per request
8. Unsupported methods return 405
9. Versioned paths are enforced

Tests must be placed under backend/api/tests.

Tests must not fabricate evaluation logic or simulate contributions.

---

## Files You May Touch

- backend/api/views/
- backend/api/serializers/
- backend/api/urls.py
- backend/api/tests/
- Documentation under docs/05_execution_history/phase_2/

---

## Files You Must Not Touch

- backend/transit/evaluation/
- backend/core/models/
- Any migrations
- Contribution creation logic
- Authorization internals
- Visibility internals

---

## Definition of Done

This sprint is complete when:
- Canonical Stop data is publicly readable via /api/v1/stops
- All reads are safe, bounded, and non-leaky
- Ordering and pagination are deterministic
- UI modes affect visibility only
- API versioning is explicit and enforced
- No truth or evaluation logic is modified
- Tests enforce all invariants
- No emojis or special characters exist in code or strings

---

## Philosophy Reminder

Canonical reads expose what the backend believes to be true, never why it believes it.

If a response allows inference about:
- contribution volume
- confidence thresholds
- contributor behavior

then the API is incorrect.

End of prompt.

