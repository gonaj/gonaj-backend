# Phase-1 Data Rights Checklist (Authoritative)

> **Project:** Gonaj Backend
>
> **Scope:** DATA_RIGHTS_V1 implementation as part of Phase-1 (not Phase-2)
>
> **Purpose:** Verify that user data rights are fully respected without compromising belief integrity, replay safety, or canonical correctness.

This checklist is **parallel to** `PHASE_1_FREEZE_CHECKLIST.md` and must be satisfied **before Phase-1 can be declared complete**.

---

## 1. Core Data Rights Principles (Must Hold)

* [ ] **DR-I1 — Identity is optional**: Belief formation and canonical data do not depend on persistent user identity.
* [ ] **DR-I2 — Evidence is permanent**: User-contributed evidence is never deleted as part of account deletion.
* [ ] **DR-I3 — Belief is derived**: Canonical belief remains stable across user deletion.

If any principle is violated, Phase-1 must not be frozen.

---

## 2. Account Deletion (Right to Erasure)

### 2.1 Deletion Capability

* [ ] Authenticated users can request irreversible account deletion.
* [ ] Deletion endpoint is explicit, intentional, and idempotent.
* [ ] Deletion does not require moderator or admin involvement.

### 2.2 Identity Removal

* [ ] User profile data is permanently deleted or irreversibly anonymized.
* [ ] Authentication credentials are removed.
* [ ] No personal identifiers remain linkable to the deleted user.

### 2.3 Token & Session Revocation

* [ ] All active access tokens are invalidated immediately.
* [ ] All refresh tokens are revoked.
* [ ] Deleted users cannot authenticate again.

---

## 3. Contribution & Observation Handling

### 3.1 Evidence Retention

* [ ] All `ContributionEvent`s remain stored after user deletion.
* [ ] Evidence payloads remain intact for replay and audit.

### 3.2 De-identification

* [ ] Evidence authored by a deleted user is irreversibly de-identified.
* [ ] De-identification preserves timestamps, geometry, and payload.
* [ ] De-identification does not alter belief outcomes.

---

## 4. Canonical Stability Guarantees

* [ ] Deleting a user does not trigger belief recomputation.
* [ ] Canonical Stops remain unchanged post-deletion.
* [ ] Replay before and after deletion yields identical results.

---

## 5. Right to Data Access (Contribution Export)

### 5.1 Export Capability

* [ ] Users can download their own contributions.
* [ ] Export is scoped strictly to the requesting user.
* [ ] Export is available prior to deletion.

### 5.2 Export Content Rules

Export includes:

* [ ] Timestamps
* [ ] Geometry / location
* [ ] Raw evidence payload

Export excludes:

* [ ] Canonical belief
* [ ] Confidence values
* [ ] Moderation history
* [ ] Other users’ data

---

## 6. Silent Deletion & Non-Exposure

* [ ] Account deletion triggers no public notifications.
* [ ] No moderator or contributor alerts are emitted.
* [ ] Other users cannot infer deletion events.

---

## 7. Audit & Governance Safety

* [ ] Audit logs record deletion events without personal identifiers.
* [ ] Audit logs cannot be used to re-identify deleted users.
* [ ] Audit entries preserve only event type, timestamp, and reason.

---

## 8. API & Permission Enforcement

* [ ] Deletion and export endpoints require authentication.
* [ ] Rate limiting is applied to export endpoints.
* [ ] No admin override exists to reverse deletion.

---

## 9. Testing & Verification

* [ ] Tests verify deletion revokes authentication immediately.
* [ ] Tests verify evidence persists after deletion.
* [ ] Tests verify belief stability post-deletion.
* [ ] Tests verify export contains only the user’s data.

All tests must be deterministic and replay-safe.

---

## 10. Explicit Non-Goals (Confirmed Absent)

The following must **not** exist in Phase-1:

* [ ] Soft-delete or reversible deletion
* [ ] Evidence removal as part of user deletion
* [ ] User-controlled belief or confidence edits
* [ ] Public-facing deletion indicators

---

## Phase-1 Data Rights Sign-off

Phase-1 may be declared **DATA-RIGHTS COMPLIANT** only when:

* All checklist items above are satisfied
* No TODOs affect deletion or export semantics
* Data rights do not weaken belief invariants

### Sign-off

* **Reviewed by:** ______________________
* **Date:** ______________________
* **Git tag / commit:** ______________________

---

## Canonical Statement (Safe to Quote)

> *Phase-1 guarantees that users may leave the system without harming shared truth, while shared truth remains auditable, replayable, and safe.*
