# Phase-2 Sprint-10 — Data Rights: Account Deletion

## Context (Read Carefully)

This repository implements **Gonaj**, an evidence-based backend with strict separation between:
- **Identity** (user accounts, authentication)
- **Evidence** (immutable contribution events)
- **Canonical truth** (derived deterministically from evidence)

**Up to Sprint-9**, the system has:
- Canonical Stop and Route read APIs
- Fully implemented authorization (Sprint-4)
- Rate limiting, idempotency, and abuse signal collection
- GDPR-style **data export** (`/api/v1/me/contributions/export`)

**User account deletion is not yet implemented.**

This sprint introduces **Data Rights: Account Deletion**, with strict guarantees that **identity removal must never erase evidence or alter canonical truth**.

---

## Primary Goal

Remove user identity while preserving all evidence and canonical truth.

---

## What This Sprint Achieves

- Deterministic, user-initiated account deletion
- De-identification of user-linked data
- Foreign key nullification or replacement where required
- Audit logging of deletion action
- Proof that evidence and canonical state remain unchanged

---

## Explicit Non-Goals (Hard Constraints)

You must NOT:

- Delete contribution events
- Modify canonical Stop or Route state
- Modify evaluation logic
- Modify abuse signals
- Modify rate limiting or idempotency
- Introduce soft-delete logic on evidence
- Reassign evidence to another user

Any of the above is a sprint failure.

---

## Scope Definition

### In Scope

- User account deletion flow
- Identity de-coupling from evidence
- Audit trail for deletion
- Tests proving invariants

### Out of Scope

- Bulk deletion
- Admin-driven deletion
- Re-identification mechanisms
- UI changes

---

## Architectural References (Must Read)

Before writing code, read and understand:

- `backend/accounts/services/account_deletion.py`
- `backend/accounts/models.py`
- `backend/core/models/contribution_event.py`
- `backend/api/views/me.py`
- `docs/02_phases/phase_1/phase_1_data_rights_checklist.md`
- `docs/02_phases/phase_2/phase_2_invariant_checklist.md`

These define the **non-negotiable data rights and identity separation rules**.

---

## Key Work Items

### 1. Account Deletion Service (Core Logic)

**Objective**

Implement a single, authoritative service responsible for account deletion.

**Files**

- `[MODIFY] backend/accounts/services/account_deletion.py`

**Requirements**

- Must:
  - Deactivate the user account
  - Remove or nullify user-identifying fields
  - Preserve all contribution events
- Must NOT:
  - Delete evidence
  - Modify contribution payloads
  - Touch canonical models

**Guidance**

- Prefer **nullification or irreversible anonymization** over deletion
- Ensure the operation is **idempotent**
- Deletion must be final and irreversible

---

### 2. Foreign Key and Identity Handling

**Objective**

Ensure all user-linked references are safely de-identified.

**Files to Review**

- `backend/core/models/contribution_event.py`
- `backend/accounts/models.py`

**Rules**

- Evidence must survive deletion
- User foreign keys must:
  - Be set to NULL, OR
  - Be replaced with a system anonymized value
- No cascade deletes allowed

---

### 3. API Endpoint Enforcement

**Objective**

Expose a safe, authorized deletion endpoint.

**Files**

- `[MODIFY] backend/api/views/me.py`

**Requirements**

- Endpoint: `DELETE /api/v1/me`
- Must require explicit capability (`Capability.CONTRIBUTE`)
- Must be idempotent
- Must not depend on UI mode

---

### 4. Audit Logging

**Objective**

Record deletion events for legal and compliance reasons.

**Files**

- `[MODIFY] backend/core/models/audit.py` (if applicable)

**Rules**

- Log:
  - Timestamp
  - Action type (ACCOUNT_DELETION)
  - Anonymized user reference
- Must NOT log PII

---

### 5. Tests (TDD REQUIRED)

This sprint **MUST follow TDD**.

**Files**

- `[NEW] backend/accounts/tests/test_account_deletion.py`
- `[MODIFY] backend/api/tests/test_account_deletion_api.py`

**Tests Required**

- User can delete own account
- Deleting twice is safe (idempotent)
- Contribution events remain intact
- Canonical state unchanged after deletion
- User identity fields are removed
- Audit log entry created

Write failing tests first, then implement minimal logic to pass.

---

## Files You MAY Touch

- backend/accounts/services/
- backend/accounts/tests/
- backend/api/views/me.py
- backend/api/tests/
- backend/core/models/audit.py

---

## Files You MUST NOT Touch

- backend/transit/evaluation/*
- backend/transit/models/*
- backend/api/visibility.py
- backend/api/serializers/canonical.py
- Any migrations unless strictly required

---

## Test Coverage (Mandatory)

All scenarios below MUST be covered by automated tests. Naming is prescriptive to prevent scope drift.

### Identity & Access
- `test_account_deletion_revokes_authentication`
- `test_deleted_user_cannot_authenticate`
- `test_deleted_user_cannot_access_me_endpoints`

### Data Integrity (Non-Destructive)
- `test_account_deletion_does_not_delete_contributions`
- `test_account_deletion_does_not_modify_canonical_stops`
- `test_account_deletion_does_not_modify_canonical_routes`
- `test_account_deletion_does_not_affect_evaluation_outputs`

### Foreign Key & De-identification
- `test_contributor_fk_is_nullified_on_deletion`
- `test_no_fk_constraint_violation_after_deletion`
- `test_contributor_fingerprint_preserved`

### Ordering & Reproducibility
- `test_export_ordering_unchanged_after_account_deletion`
- `test_canonical_read_ordering_unchanged_after_account_deletion`

### Export Semantics
- `test_export_before_deletion_succeeds`
- `test_export_after_deletion_forbidden`
- `test_previous_exports_remain_reproducible`

### Idempotency & Safety
- `test_account_deletion_is_idempotent`
- `test_repeated_deletion_requests_are_noops`

### Abuse & Metrics Continuity
- `test_abuse_signals_continue_after_account_deletion`
- `test_fingerprint_based_metrics_unaffected_by_deletion`

---

## Definition of Done

This sprint is complete only when:

- All tests above pass
- No canonical truth is modified
- No evaluation logic changes
- No ordering or indexing side effects occur
- Account deletion is provably safe, idempotent, and non-destructive

