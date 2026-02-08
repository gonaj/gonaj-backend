# Visibility Layer v0

## Status

Formal architectural definition for Phase-2. Frozen once Phase-2 completes.

---

## **Relationship to UI Constitution**

This document is a backend enforcement specification for 'ui_constitution_v1.md'.

The visibility layer exists to ensure that:

- The UI never receives data it is forbidden to display
- UI constraints are enforced at the API boundary
- No client can bypass UI governance by requesting raw canonical data

If there is any conflict between this document and `ui_constitution_v1.md`, the UI Constitution takes precedence.

---

## Purpose

The visibility layer defines **how already-derived backend data is presented to clients** without altering truth, belief, or evaluation semantics.

It exists to:

- Protect canonical truth from UI-driven leakage
- Allow partial or safe presentation of incomplete data
- Support different UI modes without semantic drift

**Visibility is cosmetic, not semantic.**

---

## Scope

This document applies **uniformly** to:

- Canonical Stops
- Canonical Routes

The same visibility principles apply across entity types.
Entity-specific differences are allowed **only** where explicitly justified.

---

## Inputs

The visibility layer may consume:

- Canonical entity objects (Stop, Route)
- Canonical belief state (already evaluated)
- UI mode flag (`read`, `contributor`, `admin`)
- Request context (authentication state only for visibility, not authority)

The visibility layer must assume:

- All inputs are already validated
- All truth decisions are already made

---

## Allowed Transformations

The visibility layer MAY:

- Hide or suppress fields
- Mask internal values (thresholds, counters, diagnostics)
- Omit non-canonical related entities from responses
- Add **labels** that describe completeness or uncertainty
- Shape responses differently per UI mode

Allowed transformations must be:

- Reversible
- Deterministic
- Non-persistent

---

## Forbidden Behaviors

The visibility layer MUST NOT:

- Create, modify, or infer canonical truth
- Change belief states or confidence levels
- Promote non-canonical entities to canonical
- Introduce new truth states (e.g., "partially canonical")
- Persist any derived or filtered output
- Influence evaluation or aggregation logic

Any violation is a **hard architectural failure**.

---

## Entity-Specific Examples

### Stops

Canonical Stop truth:

- Binary: Canonical or Not Canonical

Visibility MAY:

- Display belief state labels (e.g., Contested, Dormant)
- Hide internal confidence thresholds
- Suppress evidence counts

Visibility MUST NOT:

- Recompute belief
- Infer canonical truth from UI mode

---

### Routes

Canonical Route truth:

- Binary: Canonical or Not Canonical

Visibility MAY:

- Display only canonical Stops within a Route
- Hide intermediate non-canonical Stops
- Mark Route as "incomplete" or "partial display"

Visibility MUST NOT:

- Treat partially visible Routes as canonical
- Infer Route truth from partial Stop visibility
- Modify Stop or Route canonical state

---

## Cross-Entity Consistency Rule

Visibility rules must be **conceptually identical** across Stops and Routes:

- Truth remains binary
- Partial display is allowed
- Partial truth is forbidden

Any divergence requires explicit documentation and justification.

---

## Invariants

- Visibility affects presentation only
- Truth is immutable at this layer
- Evaluation is upstream
- UI modes never alter authority or belief

---

## Phase-2 Exit Condition

Visibility behavior is:

- Explicit
- Consistent
- Non-leaky
- Identical in principle for Stops and Routes

---

End of document.

