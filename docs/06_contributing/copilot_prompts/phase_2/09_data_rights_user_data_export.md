# Phase-2 Sprint-9 — Data Rights: User Data Export

## Context (Read Carefully)

This repository implements **Gonaj**, an evidence-based backend.

**Core architectural invariants that MUST remain intact:**

* Canonical truth is derived only from evidence
* Evidence is immutable once written
* User identity is separable from evidence
* Abuse signals are observational only
* UI modes affect visibility only
* Authorization is capability-based
* Guardrails precede features

This sprint implements **user data export only**.
It must NOT alter evaluation, truth, or abuse semantics.

---

## Primary Goal

Allow authenticated users to **export all of their own data deterministically** in a safe, privacy-preserving manner.

This is a **data rights feature**, not an analytics or reporting feature.

---

## What This Sprint Achieves

* Deterministic export of **user-owned data**
* GDPR-style “right to access”
* Stable and reproducible export format
* Explicit scoping: *only data belonging to the requesting user*

---

## Explicit Non-Goals (Hard Constraints)

You must NOT:

* Export canonical entities (Stops, Routes)
* Export derived truth or evaluation outputs
* Export abuse signals or metrics
* Export data belonging to other users
* Add new persistence models
* Modify evaluation logic
* Modify contribution creation logic
* Add admin or bulk export functionality

Any of the above is a sprint failure.

---

## Scope Definition

### Exported Data (IN SCOPE)

The export MUST include **only**:

1. **Contribution Events** created by the authenticated user

   * Source: `backend/core/models/contribution_event.py`
   * Filter: `contributor == request.user`

2. **Contribution Metadata**

   * Timestamps
   * Contribution type
   * Client-generated identifiers
   * Payload (as submitted)

3. **Account Metadata (Minimal)**

   * User id
   * Account creation date
   * Account deletion status (if applicable)

---

### Explicitly Excluded (OUT OF SCOPE)

* Canonical Stops
* Canonical Routes
* Belief states
* Evaluation scores
* Confidence thresholds
* Abuse signals (Sprint-8)
* Device or fingerprint information
* Internal IDs unrelated to the user

---

## API Surface

### Endpoint to Implement

```
GET /api/v1/me/contributions/export
```

### Properties

* Authenticated only
* Read-only
* Deterministic
* Snapshot-safe (single-query semantics)
* One user only (self-service)

---

## Export Format

### Format Requirements

* JSON only
* Schema-stable
* Versioned export envelope
* Deterministic ordering

### Required Structure

```json
{
  "export_version": "v1",
  "generated_at": "ISO-8601 timestamp",
  "user": {
    "user_id": "...",
    "created_at": "ISO-8601"
  },
  "contributions": [
    {
      "contribution_id": "...",
      "contribution_type": "...",
      "observed_at": "...",
      "submitted_at": "...",
      "payload": { ... }
    }
  ]
}
```

### Ordering Rule (Mandatory)

* Contributions MUST be ordered by `submitted_at ASC`
* No pagination in v1 (explicitly frozen)

---

## Authorization Requirements

* Endpoint MUST require authenticated user
* User can export **only their own data**
* UI mode MUST NOT affect export content
* Capability required: `contribute`

Refer to:

* `backend/api/authz.py`
* `Capability.CONTRIBUTE`

---

## Implementation Guidance

### Files You MUST Refer To

* `backend/api/views/export.py` (existing pattern)
* `backend/api/views/me.py`
* `backend/core/models/contribution_event.py`
* `backend/api/permissions.py`
* `backend/api/authz.py`

### Files You MAY Modify or Add

* `backend/api/views/export.py`
* `backend/api/serializers/export.py`
* `backend/api/tests/test_contribution_export.py`
* `docs/05_execution_history/phase_2/`

---

## Testing Strategy

### TDD Applicability

**Partial TDD required**

TDD is REQUIRED for:

* Authorization enforcement
* Ownership isolation
* Deterministic ordering
* Schema stability

TDD is NOT required for:

* Timestamp formatting
* JSON envelope structure

---

### Required Tests

You must add tests proving:

1. **Authorization**

   * Anonymous access denied
   * Authenticated access allowed

2. **Ownership Isolation**

   * User A cannot see User B’s contributions

3. **Determinism**

   * Same request returns same ordering and content

4. **Non-Leakage**

   * No canonical entities included
   * No abuse signals included
   * No evaluation metadata included

5. **UI Mode Independence**

   * UI mode query/header does not change export content

Tests must live under:

```
backend/api/tests/test_contribution_export.py
```

---

## Files You MUST NOT Touch

* `backend/transit/evaluation/*`
* `backend/api/visibility.py`
* `backend/api/abuse_signals.py`
* Canonical serializers
* Any migrations
* Any database schema

---

## Definition of Done

This sprint is complete when:

* Users can export all their own contributions
* Export is deterministic and reproducible
* No other user data is exposed
* No canonical or evaluation data is leaked
* All tests pass
* No forbidden files are modified
* No emojis or special characters exist in code or strings

---

## Philosophy Reminder

Data export is a **right**, not a privilege.

This feature must:

* Reveal ownership
* Preserve truth
* Respect privacy
* Avoid inference
* Avoid enforcement coupling

If exporting data changes system behavior, the implementation is wrong.

End of prompt.
