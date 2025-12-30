# DATA_RIGHTS_V1 — User Data Rights & Evidence Retention

> **Status:** Frozen for Phase‑1
>
> **Scope:** This document defines how Gonaj handles user data, identity deletion, and historical evidence retention. It is a constitutional document and must not be violated by implementation details, UX shortcuts, or operational convenience.

---

## 1. Purpose

Gonaj is a civic knowledge system designed to transform human observations into reliable transit knowledge over time.

This document exists to guarantee that:

* Users retain control over their **identity and personal data**
* The system preserves **historical truth and replayability**
* Trust is maintained even when users leave the platform

The principles here are as fundamental as the backend philosophy and evaluation rules.

---

## 2. Core Principle

> **Identity is optional. Evidence is permanent. Belief is derived.**

From this principle, all rules below follow.

---

## 3. Data Categories

Gonaj explicitly distinguishes between three categories of data. Each category has different deletion semantics.

### 3.1 Identity & Access Data

Examples:

* Email address
* Authentication credentials
* OAuth / social login links
* Sessions and refresh tokens
* Registered devices

**Policy:**

* Must be fully deleted or irreversibly anonymized upon user request
* Must not be recoverable
* Must not be retained for convenience or analytics

---

### 3.2 Profile & Preference Data

Examples:

* Display name
* Profile metadata
* User preferences
* UI or notification settings

**Policy:**

* Must be fully deleted upon user request
* Must not remain accessible internally or externally

---

### 3.3 Contribution & Observation Data

Examples:

* Observations submitted by users
* Contribution events (e.g. “bus observed”, “stop inactive”)
* Timestamps, locations, and observation content

**Policy:**

* Must **not** be deleted
* Must be **permanently de‑identified** upon user deletion
* Must remain part of the immutable evidence log

**Rationale:**
Removing historical observations would:

* Break replayability
* Corrupt derived belief
* Make past system behavior irreproducible

Instead, Gonaj preserves shared reality **without ownership**.

---

## 4. User Rights (Phase‑1 Guaranteed)

### 4.1 Right to Account Deletion

Users have the right to:

* Permanently delete their account
* Remove all identity and profile data
* Invalidate all active sessions and tokens

Deletion must be:

* User‑initiated
* Immediate
* Final

---

### 4.2 Right to Contribution Download

Before deletion, users may:

* Download a copy of **their own observations**

Export characteristics:

* Human‑readable (JSON or CSV)
* One record per observation
* Contains only user‑submitted data

The export **must not** include:

* Canonical belief
* Internal confidence or scoring
* Other users’ data
* Moderation annotations

---

### 4.3 Right to Leave Without Social Exposure

* Account deletion is silent
* Other users are not notified
* Moderators are not notified
* Only aggregated internal metrics may record deletion counts

Leaving the system must never feel observed or judged.

---

## 5. Deletion Semantics (Authoritative)

When a user deletes their account:

1. Identity & access data are removed
2. All sessions and tokens are revoked immediately
3. Profile data is deleted
4. Contributions are **de‑identified**, not removed
5. Canonical belief remains unchanged

After deletion:

* No system component may re‑identify the user
* No API may resolve the former identity
* Past observations remain usable as anonymous evidence

---

## 6. What Deletion Does NOT Mean

Deletion does **not** mean:

* Removal of shared historical facts
* Rewriting system history
* Recomputing belief solely due to exit
* Erasing locations, times, or events observed

Gonaj preserves **what happened**, not **who left**.

---

## 7. Backend Guarantees (Phase‑1)

The backend must guarantee:

* **Synchronous deletion** of identity data
* Immediate token revocation
* Cache invalidation for all user‑scoped data
* Irreversible de‑identification of contributions
* Stable canonical belief after deletion

A successful deletion response must indicate finality.

---

## 8. UX Commitments

The user interface must:

* Clearly explain what is deleted and what is retained
* Avoid legalistic or defensive language
* Never discourage deletion
* Never guilt or pressure the user to stay

Deletion UX is a **trust gesture**, not a retention mechanism.

---

## 9. Audit & Governance

The system may internally record:

* That a deletion occurred
* When it occurred
* That it was user‑initiated

Audit records must:

* Contain no personal identifiers
* Never re‑enable re‑identification
* Be used only for governance and safety

---

## 10. Non‑Goals (Explicit)

Phase‑1 does **not** include:

* Deletion of historical observations
* Legal workflow automation
* Public deletion logs
* Contributor reputation cleanup
* Derived data portability

These may be considered only in later phases.

---

## 11. Final Statement

> **People may leave the system completely, but shared reality remains — without ownership, attribution, or memory of who they were.**

This rule protects users, preserves truth, and keeps Gonaj safe to evolve.

---

**End of DATA_RIGHTS_V1 (Phase‑1, Frozen)**
