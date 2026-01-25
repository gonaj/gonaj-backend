# Phase-2 Sprint-8 — Contribution Abuse Signal Collection

## Context (Read Carefully)

This repository implements **Gonaj**, an evidence-based backend.

Phase-2 principles that MUST remain intact:

- Backend is the sole authority on truth
- Evidence is immutable
- Canonical entities are derived conservatively
- Guardrails precede features
- Abuse handling in Phase-2 is **observational only**, never corrective

This sprint introduces **abuse signal observability only**.

It must NOT:
- Change canonical truth
- Influence evaluation outcomes
- Penalize contributors
- Introduce identity resolution

---

## What Already Exists (Important)

The following data and mechanisms already exist and **may be used**:

- Contribution timestamps
- Contributor fingerprint (already de-identified)
- Contribution type and subject references
- Existing audit/event logging infrastructure

The following **do NOT exist** and MUST NOT be added in this sprint:

- Raw device identifiers
- Explicit device to account linking
- New persistent identifiers
- New database tables or model fields
- Client-side metadata collection

If a signal does not already exist, it must be treated as **out of scope**.

---

## Primary Goal

Observe suspicious contribution patterns **without**:
- Blocking users
- Altering evaluation
- Biasing canonical outcomes

This sprint is about **visibility, not enforcement**.

---

## What This Sprint Achieves

- Observable abuse-related signals
- Aggregated metrics for review
- Zero impact on truth, confidence, or thresholds

---

## Explicit Non-Goals (Hard Constraints)

You must NOT:

- Modify evaluation logic
- Modify canonical models
- Introduce automated enforcement
- Introduce bans, throttles, or penalties
- Introduce identity resolution
- Store raw device identifiers
- Link contributors across accounts

Any of the above is a sprint failure.

---

## Key Work Items

### 1. Submission Velocity Signals

**Objective**

Detect unusually high submission rates that may indicate automation.

**Signals to Record**

- Contributions per contributor fingerprint per time window
- Contributions per authenticated user per time window

**Rules**

- Metrics only
- No blocking or scoring
- Time windows must be coarse (minutes or hours)

---

### 2. Repetition and Duplication Signals

**Objective**

Detect repeated identical submissions that may indicate spam.

**Signals to Record**

- Repeated submissions with identical:
  - contribution_type
  - subject reference
  - payload shape

**Rules**

- Do NOT collapse or reject submissions
- Do NOT alter idempotency behavior
- Do NOT infer intent

---

### 3. Fingerprint Correlation Signals (De-identified)

**Objective**

Observe potential automation or coordinated behavior using **existing** fingerprints.

**Signals to Record**

- Frequency of reuse of the same contributor fingerprint
- Fingerprint activity across time windows

**Critical Rules**

- Fingerprints must remain de-identified
- No account linking is allowed
- No contributor resolution is allowed
- If a signal is ambiguous, record nothing

---

## Data Handling Rules

- All signals must be stored as:
  - Aggregated counters
  - Time-windowed metrics

- Signals must be:
  - Non-blocking
  - Non-authoritative
  - Non-persistent beyond analysis needs

---

## Testing Strategy

### Approach

Strict TDD is **not required** for all parts of this sprint.

Use:
- Unit tests where logic is deterministic
- Structural and invariant tests where behavior is observational

### Required Tests

You must add tests that prove:

- Signal collection does NOT affect evaluation outcomes
- Signal collection does NOT modify canonical entities
- No enforcement behavior exists
- No new identifiers are created
- Signals are ignored by evaluation and read paths

Tests should live under:

```
backend/api/tests/
```

---

## Files You MAY Touch

- backend/api/abuse_signals.py (new)
- backend/api/tests/
- docs/05_execution_history/phase_2/

---

## Files You MUST NOT Touch

- backend/transit/evaluation/*
- backend/core/models/*
- Any migrations
- Canonical serializers
- Authorization module
- Visibility module

---

## Definition of Done

This sprint is complete when:

- Abuse-related patterns are observable via metrics
- No enforcement or blocking exists
- No truth or evaluation logic is affected
- No new identifiers are introduced
- All added code is covered by appropriate tests
- No forbidden files are modified
- No emojis or special characters exist in code or strings

---

## Philosophy Reminder

Abuse signals in Phase-2 are **smoke detectors**, not fire alarms.

They inform humans and future policy — they never act.

If removing this code changes truth, evaluation, or contributor experience,
then the implementation is wrong.

End of prompt.

