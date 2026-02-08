# Route Canonical Truth Rules v0

This document defines the **canonical truth rules for Routes** in Phase-2. It mirrors the Stop truth model where applicable and explicitly documents where Routes differ, with justification.

---

## Purpose

Routes are **composite entities** derived from evidence and dependent on Stop canonical state. This document exists to:

- Prevent semantic drift in Route evaluation
- Ensure consistency with Stop truth semantics
- Provide invariant-level guarantees for evaluation, visibility, and replay

This document is **normative** for all Route evaluation logic.

---

## Relationship to Stop Rules

This document must be read alongside:

- `docs/02_phases/phase_1/rules_v0.md` (Stop rules)

Rules are intentionally aligned unless explicitly stated otherwise.

---

## Canonical Truth Model

### R-TRUTH-1: Binary Canonical State

A Route has exactly two canonical states:

- **Canonical**
- **Not Canonical**

There is **no partial canonical state** for Routes.

Justification:
- Routes are composite abstractions
- Partial correctness must not affect backend truth

---

### R-TRUTH-2: Evidence-Derived Truth Only

Route canonical state is derived **only from evidence**.

- No manual promotion
- No admin overrides
- No UI-driven truth changes

Mirrors Stop truth rules exactly.

---

### R-TRUTH-3: Composite Truth Strictness

A Route may be considered **Canonical** only if:

- All required structural evidence thresholds are met
- **All Stops referenced by the Route are Canonical Stops**

If any referenced Stop is **Not Canonical**, the Route is **Not Canonical**.

Justification:
- Prevents propagation of unstable truth
- Ensures downstream consistency

---

### R-TRUTH-4: Stop–Route Dependency Direction

- Route evaluation **may read** Stop canonical state
- Route evaluation **must never modify** Stop state

Dependency is **strictly one-way**.

---

## Belief States

Routes **do not introduce independent belief states**.

Unlike Stops (which expose belief states such as Proposed, Active, Contested), Routes expose:

- Canonical
- Not Canonical

Justification:
- Belief states are meaningful for atomic entities
- Routes are composite and derivative

Any notion of partial correctness must be handled at the **visibility layer**, not in canonical truth.

---

## Visibility Layer Interaction

The visibility layer may:

- Show partial Route representations
- Hide non-canonical Stops
- Display route fragments for UX purposes

The visibility layer must:

- Never change Route canonical state
- Never influence evaluation

Canonical truth remains binary regardless of visibility.

---

## Evaluation Constraints

Route evaluation must be:

- Deterministic
- Replay-safe
- Side-effect free

No evaluation run may:

- Write to the database
- Alter Stop evaluation
- Depend on request context or UI mode

---

## Test Invariants (Required)

Route evaluation tests MUST include:

- Determinism invariant
- Replay safety invariant
- No Stop mutation invariant
- Canonical dependency invariant (non-canonical Stop blocks Route)

These must mirror equivalent Stop evaluation tests.

---

## Non-Goals

This document explicitly does NOT define:

- Route contribution APIs
- Route mutation APIs
- Performance optimizations
- UI presentation rules

---

## Change Control

Any change to these rules requires:

- A new version of this document
- Corresponding invariant tests
- Explicit Phase planning approval

---

End of document.

