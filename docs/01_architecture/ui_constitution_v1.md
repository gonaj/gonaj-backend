# UI_CONSTITUTION — Phase‑1

> **Status:** Frozen for Phase‑1
>
> **Scope:** Applies to all user-facing interfaces
>
> **Authority:** This document defines non‑negotiable rules for all user‑facing interfaces (web, mobile, admin, moderator) in Phase‑1.
>
> If any UI design, wireframe, mockup, component, or implementation conflicts with this document, **the UI is incorrect**, regardless of usability, aesthetics, or growth impact.

---

## 0. Purpose

This document exists to ensure that the user interface:

- Preserves backend truth guarantees
- Represents uncertainty honestly
- Prevents accidental authority inflation
- Remains safe even when the system is wrong

This is **not** a style guide, branding guide, or component library.
It is a **system‑level governance document**.

---

## 1. Core UI Philosophy (Non‑Negotiable)

All Phase‑1 UI must obey the following principles:

1. **UI represents belief, not truth**
   - The system shows what is *currently believed*, not what is *guaranteed to be true*.

2. **UI accepts observations, not edits**
   - Users never “fix” data.
   - Users only share what they observed.

3. **UI must never appear more confident than the system**
   - Silence is preferable to false precision.

4. **UI must be safe when wrong**
   - Incorrect belief must fade, not mislead.

5. **Trust outweighs engagement**
   - UX choices that improve engagement but weaken trust are invalid.

---

## 2. What UI Is Allowed to Do (Explicit Powers)

UI is allowed to:

- Display **canonical entities only**
- Communicate uncertainty using **language and visual treatment**
- Allow inspection before contribution
- Allow contribution only after explicit user intent
- Allow manual input when permissions are denied
- Allow silent exit and account deletion

Anything not listed here must be treated as **suspect**.

---

## 3. What UI Is Explicitly Forbidden to Do (Hard Red Lines)

UI must **never**:

- Provide “Edit”, “Fix”, or “Correct” actions
- Use voting, rating, or approval metaphors
- Show numeric confidence, percentages, or scores
- Gamify contributions or show reputation
- Nudge users to contribute in empty areas
- Request permissions proactively
- Auto‑prompt login without explicit intent
- Hide uncertainty to reduce friction
- Imply completeness, accuracy, or authority

Violations of this section are **blocking defects**.

---

## 4. Canonical Mental Model & Vocabulary

UI language must respect the following meanings:

- **Known** ≠ Confirmed
- **Observed** ≠ True
- **Inactive / Dormant** ≠ Removed
- **Missing** ≠ Error

Copy changes that blur these distinctions are not allowed.

---

## 5. Belief → Visual Representation Contract

Belief state must be communicated **without numbers**.

| Belief State | Visual Treatment | Language Tone |
|-------------|------------------|---------------|
| Active (High) | Normal contrast | Neutral |
| Active (Low) | Muted / softened | Cautious |
| Dormant | Faded | Explicit uncertainty |
| Absent | Empty state | Calm acknowledgement |

Rules:
- Designers may not invent new metaphors without updating this table.
- Numeric confidence is forbidden.

---

## 6. Information Hierarchy Rules

Every primary screen must respect this order:

1. Orientation (what this is)
2. Uncertainty anchor
3. Exploration
4. Inspection
5. Contribution (only after inspection)

The following must **never** be primary:
- Contribution CTAs
- Login prompts
- Permission prompts

---

## 7. Contribution UX Constraints

Contribution UX must obey:

- Contribution is **contextual**, never ambient
- Login is requested **only after explicit intent**
- Location permission is optional
- Manual alternatives are mandatory
- Submission confirms **receipt**, not **impact**

Efficient or frictionless contribution flows are a warning sign.

---

## 8. Permissions & Privacy UX Rules

UI must:

- Request permissions only after explicit action
- Treat denial as a valid, final choice
- Provide graceful manual fallbacks
- Never remind or re‑prompt permissions

Account deletion UX must:
- Clearly explain what is deleted vs retained
- Offer export before deletion
- Be silent and final

---

## 9. Empty, Error, and Degraded States

UI must clearly distinguish between:

- **System failure** (temporary)
- **Data absence** (unknown)
- **Outdated belief** (stale)

Each requires distinct:
- Language
- Visual treatment
- Recovery actions

Conflating these is a trust violation.

---

## 10. Phase‑1 Explicit Non‑Goals (Frozen)

Phase‑1 UI must not include:

- Navigation or ETA UX
- Predictions or recommendations
- Notifications or background sensing
- Reputation or profiles
- Personalization

Adding these requires a Phase‑2 constitution.

---

## 11. Review & Enforcement

- All UI‑related PRs must reference relevant sections of this document
- Design reviews must include a constitution compliance check
- Violations block merge regardless of aesthetics

---

## 12. Amendment Rules

- Phase‑1 amendments require:
  - Written rationale
  - Backend compatibility review
  - Explicit version bump

Silent evolution is forbidden.

---

## Final Statement

> This UI exists to earn trust before scale.
> If a design choice improves engagement but weakens trust, it is incorrect.

