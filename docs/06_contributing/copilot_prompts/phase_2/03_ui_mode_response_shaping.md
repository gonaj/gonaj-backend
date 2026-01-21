# Phase-2 Sprint-3 — UI Mode–Aware Response Shaping

## Context (Must Read First)

This repository implements **Gonaj**, an evidence-based backend where:
- The backend is the sole authority on truth
- Evidence is immutable
- Canonical entities are derived conservatively
- UI concerns must never affect evaluation, belief, or canonical state

**Important**:
- As of this sprint, there are **NO public canonical read endpoints yet** for Stops, Routes, or other transit entities.
- Phase-2 Sprint-2A established *guardrails only* for future canonical read APIs.
- This sprint must operate strictly at the **response shaping layer**, without creating new canonical endpoints.

Refer to these documents for architectural context:
- `docs/01_architecture/backend_philosophy.md`
- `docs/01_architecture/ui_constitution_v1.md`
- `docs/02_phases/phase_1/rules_v0.md`
- `docs/02_phases/phase_1/test_invariants_v0.md`
- `docs/05_execution_history/phase_2/phase2-sprint2a-canonical-read-guardrails.md`

This agent must **not assume any prior discussion** beyond what is written here.

---

## Applicable Phase-2 Invariants (Must Be Preserved)

This sprint MUST preserve the following Phase-2 invariants:

- **P2-INV-1 — Backend Truth Authority**: UI mode must never influence belief, evaluation, or canonical state.
- **P2-INV-2 — Visibility-Only UI Modes**: UI modes may only affect response visibility, not semantics.
- **P2-INV-3 — Canonical Read Safety**: No evidence, contributor identity, or evaluation artifacts may leak.
- **P2-INV-6 — Deterministic Evaluation**: Mode changes must not affect replay or evaluation determinism.
- **P2-INV-9 — No Silent Scope Expansion**: No new capabilities or data exposure without explicit definition.

Violation of any of these invariants constitutes a hard failure of this sprint.

---

## Primary Goal

Allow UI modes to control **visibility only**, never truth or evaluation.

UI mode must affect:
- Which fields are visible in responses

UI mode must NOT affect:
- Evidence ingestion
- Evaluation
- Belief accumulation
- Canonical state
- Thresholds
- Confidence

---

## What This Sprint Achieves

- Introduces an explicit **UI mode concept**: `read`, `contributor`, `admin`
- Applies **mode-aware response filtering**
- Ensures filtering is:
  - Non-destructive
  - Reversible
  - Presentation-only
- Proves via tests that:
  - All modes operate on identical underlying data
  - Canonical truth is unchanged regardless of mode
  - No evidence becomes canonical due to UI mode

---

## Explicit Non-Goals (Do NOT Do These)

The agent must NOT:
- Add new canonical read endpoints
- Modify any models
- Add or change migrations
- Change evaluation logic
- Touch evidence aggregation
- Change thresholds or confidence scoring
- Introduce mode-based branching inside evaluation code
- Alter write or contribution APIs

Any such change is considered a hard failure of this sprint.

---

## Key Work Items

### 1. Define UI Mode Representation

Introduce a **UI mode flag** that can be supplied with requests.

Constraints:
- Mode must be explicit
- Mode must default to `read`
- Mode must be validated against allowed values
- Invalid modes must fail safely

Allowed modes:
- `read`
- `contributor`
- `admin`

**Where to implement**:
- Request parsing layer (e.g., request context, headers, or query params)
- Must NOT be stored in database
- Must NOT be persisted

Document the chosen mechanism clearly in code comments.

---

### 2. Implement Mode-Aware Response Filtering

Implement a **response-layer filtering mechanism** that:
- Receives raw response data
- Applies field visibility rules based on UI mode
- Returns a filtered representation

Constraints:
- Filtering must happen AFTER data retrieval
- Filtering must NOT mutate source objects
- Filtering must NOT affect serialization logic used for canonical exports

Recommended location:
- New utility module under `backend/api/` (e.g., `visibility.py`)

Example conceptual structure (illustrative only):
- `apply_visibility(data, mode)`

Do NOT:
- Put mode checks inside serializers
- Put mode checks inside models
- Put mode checks inside evaluation logic

---

### 3. Define Visibility Rules (Explicit and Minimal)

Define clear visibility differences:

- `read` mode:
  - Canonical-safe fields only
  - No diagnostics
  - No evidence metadata

- `contributor` mode:
  - Canonical fields
  - Limited, explicitly allowed candidate metadata
  - Still no contributor identities

- `admin` mode:
  - Canonical fields
  - Diagnostics and evaluation metadata
  - Still no mutation capability

These rules must be:
- Centralized
- Explicit
- Easy to audit

Do NOT infer rules implicitly from serializers.

---

### 4. Tests (Mandatory)

Add tests proving the following invariants:

1. **Visibility-Only Invariant**
   - Same request, same underlying data, different modes
   - Only response fields differ

2. **Truth Invariance**
   - Evaluation results unchanged regardless of mode

3. **Non-Canonical Safety**
   - No evidence promoted due to mode

4. **Reversibility**
   - Switching modes does not permanently remove data

5. **Default Safety**
   - Missing or invalid mode behaves as `read`

6. **Contributor Threshold Secrecy (New Invariant)**
   - Contributor mode MUST NOT expose:
     - Numeric thresholds
     - Confidence scores
     - Required counts
     - Distance-to-threshold indicators
   - Tests must assert that:
     - No numeric fields related to evaluation thresholds are present
     - No values allow a contributor to infer how close a candidate is to promotion
     - Contributor-visible metadata remains boolean, categorical, or coarse-grained only

Tests must:
- Live under `backend/api/tests/`
- Use dummy views or fixtures if necessary
- Avoid touching evaluation or contribution pipelines

---

## Files That MAY Be Modified

- `backend/api/` (new utility modules)
- `backend/api/tests/` (new test files)
- Minimal wiring in views to pass mode to response layer

## Files That MUST NOT Be Modified

- `backend/transit/evaluation/*`
- `backend/core/models/*`
- Any migrations
- Contribution creation logic
- Stop or Route evaluators

---

## Definition of Done

This sprint is complete when:

- UI mode exists and is validated
- Responses differ by mode without affecting truth
- No canonical or evaluation logic is modified
- Tests clearly prove visibility-only behavior
- Code is minimal, explicit, and well-documented
- No emojis or special characters appear in code, comments, or strings

---

## Philosophy Reminder (Non-Negotiable)

UI modes control **what is shown**, never **what is true**.

If a change could influence belief, evaluation, or canonical state,
it does not belong in this sprint.

