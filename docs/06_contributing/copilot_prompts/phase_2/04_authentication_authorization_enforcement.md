# Phase-2 Sprint-4 — Authentication & Authorization Enforcement

## Context (Mandatory Reading)

This repository implements **Gonaj**, an evidence-based backend system with the following non-negotiable principles:

- The backend is the sole authority on truth
- Evidence is immutable once written
- Canonical state is derived conservatively from evidence
- UI concerns must never influence evaluation or belief
- Visibility, authorization, and truth are strictly separated

### What Already Exists (Do NOT Rebuild or Reinterpret)

Before starting, understand the current state:

1. **API Surface Boundaries are locked**
   - Explicit namespaces exist:
     - `/api/auth/*`
     - `/api/me/*`
     - `/api/v1/contributions/*`
   - HTTP methods are explicitly allow-listed
   - Anonymous mutation is impossible
   - Deny-by-default permissions are in place

2. **Canonical read guardrails exist**
   - Canonical read APIs are NOT yet implemented
   - Guardrails exist only (permissions, serializer base, pagination rules)

3. **UI Mode–Aware Response Shaping exists**
   - UI modes: `read`, `contributor`, `admin`
   - UI mode controls visibility ONLY
   - UI mode is parsed from request (query param or header)
   - UI mode does NOT grant authority
   - UI mode is NOT authentication
   - UI mode is NOT persisted
   - UI mode MUST NOT be used to authorize mutations

4. **Current Authentication State**
   - Authentication exists (session / token-based)
   - Some endpoints require authentication implicitly
   - Authorization logic is fragmented and inconsistent
   - No capability-based permission system exists yet

This sprint fixes **authorization**, not UI visibility and not evaluation.

The agent must NOT assume any prior discussion beyond this document.

---

## Primary Goal

Ensure **every state-changing operation** is explicitly authorized using a **capability-based, deny-by-default authorization model**, independent of UI mode.

---

## What This Sprint Achieves

- Introduces **explicit capability scopes** (e.g. read, contribute, moderate)
- Enforces authorization on **all mutation endpoints**
- Centralizes authorization logic
- Makes it impossible for:
  - Authenticated users to mutate without capability
  - UI mode to bypass authorization
  - Silent permission escalation

---

## What This Sprint Must NOT Do

The agent must NOT:

- Add new API endpoints
- Add canonical read endpoints
- Modify serializers for visibility
- Change UI mode logic
- Modify evaluation logic
- Modify evidence aggregation
- Modify thresholds or confidence scoring
- Add rate limiting (future sprint)
- Add abuse heuristics (future sprint)
- Add third-party app support (future sprint)
- Persist UI mode or auth state to database
- Conflate UI mode with authorization

Any of the above is a hard failure.

---

## Core Design Principles (Non-Negotiable)

1. **Authorization is capability-based, not role-based**
2. **UI mode affects visibility only, never authority**
3. **Authentication ≠ Authorization**
4. **Deny-by-default everywhere**
5. **Scopes must be explicit and testable**
6. **Authorization must be centralized**

---

## Key Work Items

### 1. Define Capability Model

Introduce a **capability-based authorization model**.

Capabilities MUST be explicit strings, for example:
- `read`
- `contribute`
- `moderate`
- `admin` (if needed internally)

Rules:
- Capabilities represent *what actions are allowed*
- Capabilities are NOT UI modes
- Capabilities are NOT roles
- Capabilities must be independently checkable
- Capabilities must be future-proof for app tokens

Document the capability set clearly in code comments.

---

### 2. Central Authorization Policy Module

Create a centralized authorization layer.

**Location (recommended)**:
- `backend/api/authz.py` or similar

Responsibilities:
- Define capability checks
- Provide reusable permission helpers
- Enforce deny-by-default behavior

Example conceptual API (illustrative only):
- `require_capability(request, "contribute")`
- `has_capability(request, "moderate")`

Do NOT:
- Scatter permission logic across views
- Embed authorization inside serializers
- Use UI mode for authorization decisions

---

### 3. Enforce Authorization on All Mutation Endpoints

Audit **every endpoint that mutates state**, including but not limited to:
- Contribution submission
- Account deletion
- Any POST, PUT, PATCH, DELETE endpoints

For each mutation endpoint:
- Explicitly declare required capability
- Reject requests lacking capability with 403
- Do NOT rely on authentication alone

Important:
- Being authenticated is necessary but not sufficient
- UI mode MUST NOT grant mutation rights

---

### 4. Interaction with UI Modes (Critical)

UI modes already exist and MUST remain **purely presentational**.

Explicit rules:
- UI mode must NOT be checked in authorization logic
- UI mode must NOT grant or imply capability
- Authorization must succeed or fail regardless of UI mode
- Same request with different UI modes must have identical authorization outcome

Add tests proving:
- Contributor UI mode without capability cannot mutate
- Admin UI mode without capability cannot mutate
- Read UI mode with capability can mutate (if allowed)

---

### 5. Tests (Mandatory)

Add comprehensive tests under `backend/api/tests/`.

Tests MUST prove:

1. **Deny-by-Default**
   - Authenticated users without capability cannot mutate

2. **Capability Enforcement**
   - Each mutation endpoint enforces its required capability

3. **UI Mode Independence**
   - Changing UI mode does not change authorization outcome

4. **No Silent Escalation**
   - No endpoint becomes writable accidentally

5. **Correct Error Semantics**
   - 401 for unauthenticated
   - 403 for authenticated but unauthorized
   - No internal detail leakage

Tests may use:
- Dummy views
- Existing mutation endpoints
- Test users with and without capabilities

---

## Files That MAY Be Modified

- `backend/api/` (authorization utilities, permissions)
- `backend/api/views/*` (to wire authorization checks)
- `backend/api/tests/*` (new tests)

---

## Files That MUST NOT Be Modified

- `backend/api/visibility.py`
- `backend/api/serializers/canonical.py`
- `backend/transit/evaluation/*`
- `backend/core/models/*`
- Any migrations
- Contribution evaluation logic
- Threshold or confidence logic

---

## Definition of Done

This sprint is complete when:

- Every mutation endpoint has explicit capability enforcement
- Authorization logic is centralized and auditable
- UI modes do not affect authorization
- Deny-by-default is enforced everywhere
- Tests prove no mutation without capability
- No forbidden files are modified
- No emojis or special characters exist in code, comments, or strings

---

## Exit Condition

It is **impossible** for any client to mutate backend state unless:
1. They are authenticated
2. They possess the explicitly required capability
3. The endpoint explicitly allows the mutation

UI mode must never change this outcome.

---

## Philosophy Reminder

Visibility answers:  
**What can the client see?**

Authorization answers:  
**What is the client allowed to do?**

These must never be confused.

If a change blurs this boundary, it does not belong in this sprint.
