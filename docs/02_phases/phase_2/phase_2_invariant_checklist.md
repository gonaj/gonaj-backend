# Phase-2 Backend Invariant Checklist

This document defines the **non-negotiable invariants** that govern all Phase-2 backend work. These invariants extend Phase-1 invariants and apply to every Phase-2 sprint, Copilot agent task, and code change.

Phase-2 focuses on **safety, access control, and visibility**, not on changing truth or evaluation semantics.

---

## P2-INV-1: Truth Authority Invariant

The backend remains the **sole authority on truth**.

- No API, UI mode, or client input may influence belief, evaluation, or canonical state.
- Canonical entities are derived only through evaluation logic.
- Read paths must never modify or bias truth.

---

## P2-INV-2: Visibility-Only UI Modes

UI modes affect **presentation only**.

- UI mode may hide or reveal fields.
- UI mode must never:
  - Change evaluation outcomes
  - Alter belief thresholds
  - Promote or suppress evidence
  - Affect canonical creation

---

## P2-INV-3: Canonical Read Safety

Canonical data must be safe for public consumption.

- No evidence metadata exposed
- No contributor identity exposed
- No thresholds, confidence, or evaluation diagnostics exposed
- Canonical serializers must be whitelist-only

---

## P2-INV-4: API Boundary Explicitness

Every API endpoint must have:

- Explicit namespace
- Explicit permission model
- Explicit HTTP method allow-list

No implicit behavior is allowed.

---

## P2-INV-5: Authentication Before Mutation

All mutation requires explicit authorization.

- No anonymous writes
- No optional authentication on write paths
- Capability-based authorization preferred

---

## P2-INV-6: Determinism and Replay Safety

Evaluation and derived data must be deterministic.

- Same inputs produce same outputs
- UI modes do not affect determinism
- Reads must not introduce side effects

---

## P2-INV-7: Abuse Observability Without Enforcement

Phase-2 may observe abuse but must not act on it.

- No automatic bans
- No confidence penalties
- No trust inflation
- Signals are metrics only

---

## P2-INV-8: Data Rights Preservation

User data rights must be respected without harming truth.

- Identity can be removed
- Evidence must remain
- Canonical truth must persist
- Exports must be deterministic

---

## P2-INV-9: No Silent Scope Expansion

No sprint may:

- Add new canonical endpoints implicitly
- Expose new data fields silently
- Change response semantics without tests

Every expansion must be deliberate and tested.

---

## P2-INV-10: Guardrails Before Features

Before adding any new capability:

- Guardrails must exist
- Failure modes must be tested
- Visibility and access must be bounded

---

## Usage Rules

- This checklist applies to **all Phase-2 sprints**.
- Every Sprint prompt must explicitly state which invariants apply.
- Any change violating an invariant is invalid, regardless of test status.

---

## Relationship to Phase-1

- Phase-1 invariants define **what truth is**.
- Phase-2 invariants define **who can see what, and how safely**.

Phase-2 must never weaken Phase-1 guarantees.

