# GitHub Copilot Agent Prompt — Phase-1 / Sprint-5C

> **Sprint Name:** Phase-1 Sprint-5C — User Contribution Export (DATA_RIGHTS_V1)
>
> **Project:** Gonaj Backend (Django)
>
> **Status:** Authoritative Sprint-5C prompt. Execute as-is.

---

## 1. Non-Negotiable Instruction (Read First)

Before writing any code, you must understand:

* Sprint-5C is about **data access**, not data mutation
* Sprint-5C must not weaken Sprint-5A or Sprint-5B guarantees
* Export is allowed **only before account deletion**

If any change enables export **after deletion**, the sprint fails.

---

## 2. Authoritative Architectural Principles

The following are **hard constraints**:

### PH-1: Evidence is permanent

* Export must not mutate or mark evidence

### PH-2: Identity is optional

* Export must not rely on `contributor` FK being present

### PH-3: Belief is derived

* Export must not include belief, confidence, or canonical state

### PH-4: Replay determinism

* Export must not affect replay or evaluation

### PH-5: Internal identifiers are confidential

* System-internal identifiers must never be exported

---

## 3. Scope of Sprint-5C (Authoritative)

Sprint-5C implements **user-initiated export of their own contributions**.

### In scope:

* Raw contributions submitted by the authenticated user
* Metadata the user directly supplied
* Deterministic, complete export

### Out of scope (explicit):

* Export after account deletion
* Export of other users’ data
* Canonical entities (Stops, Routes, etc.)
* Belief scores, confidence, moderation state
* Background jobs or async exports

---

## 4. Critical Invariants (Must Hold)

You must preserve all of the following:

* INV-D1: Export must not expose system-internal identifiers
* INV-D2: Export must not enable cross-contribution linkage beyond timestamps
* INV-D3: Export must not weaken post-deletion anonymity
* INV-D4: Export must not leak contributor_fingerprint

Violating any invariant fails the sprint.

---

## 5. Data That MUST Be EXCLUDED

The export **must NOT include**:

* `contributor_fingerprint`
* Any internal UUID not originally provided by the user
* Canonical IDs (Stop IDs, Route IDs, etc.)
* Evaluation artifacts
* Moderation artifacts

Even though `contributor_fingerprint` is non-PII, it is **strictly internal**.

---

## 6. Data That MAY Be INCLUDED

The export **may include only**:

* Contribution timestamp
* Raw payload submitted by the user
* Geometry / coordinates as submitted
* Evidence type

If a field was not explicitly provided by the user, do not export it.

---

## 7. API Design (Strict)

Implement a **read-only endpoint**:

```
GET /api/me/contributions/export
```

Requirements:

* Requires authentication
* Returns HTTP 404 or 403 if account is deleted
* Produces a deterministic export
* No side effects

Do not introduce alternative routes.

---

## 8. Serializer Requirements

Create a dedicated export serializer.

The serializer must:

* Explicitly whitelist fields
* Explicitly exclude internal fields
* Never reuse existing contribution serializers

Example (conceptual only):

```python
class ContributionExportSerializer(serializers.Serializer):
    timestamp = ...
    lat = ...
    lon = ...
    payload = ...
```

---

## 9. Tests (Mandatory)

Add tests verifying:

* User can export their own contributions
* User cannot export after deletion
* Export does not include internal identifiers
* Export is stable across repeated calls

Tests must live under:

```
backend/api/tests/test_contribution_export.py
```

---

## 10. What You Must NOT Do

You must NOT:

* ❌ Export contributor_fingerprint
* ❌ Export canonical IDs
* ❌ Trigger evaluation or recomputation
* ❌ Cache export results
* ❌ Modify evidence or belief state

---

## 11. Definition of Done

Sprint-5C is complete only when:

* Export endpoint exists and is documented
* Only user-supplied data is exported
* Export is unavailable post-deletion
* All tests pass
* No invariant is violated

---

## 12. Completion Document

Create:

```
docs/05_execution_history/phase_1/sprint_5c_complete.md
```

The document must include:

* Summary
* Endpoint implemented
* Fields included / excluded
* Invariants verified
* Tests added
* Implementation metadata

---

## Canonical Reminder

> **Sprint-5C is about user rights, not system introspection.**
>
> If the export teaches the user how the system works internally, it is wrong.
