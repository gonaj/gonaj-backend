# Phase-2 Sprint-1 — API Surface Boundary Lockdown

## Purpose

This document is the **authoritative Copilot Agent prompt** for **Phase-2 Sprint-1** of the Gonaj backend.

The goal of this sprint is to **explicitly lock and formalize the API surface boundaries** so that:

- All APIs are clearly classified by access level
- No accidental mutation paths exist
- Unsupported HTTP methods are rejected consistently
- Future security, abuse defense, and third-party readiness can be layered safely

This sprint is **purely infrastructural**. It must not modify domain logic, evaluation rules, or data semantics.

---

## Non-Negotiable Constraints (Read Carefully)

The agent **MUST** obey all of the following:

1. **Do NOT modify any models** (Django models, migrations, or fields)
2. **Do NOT modify evaluation logic** (stop creation, aggregation, confidence, negative evidence, etc.)
3. **Do NOT modify serializers beyond access control wiring**
4. **Do NOT add new endpoints**
5. **Do NOT change request or response payload shapes**
6. **Do NOT refactor unrelated code for cleanliness**
7. **Do NOT change business logic**

This sprint is about **API boundaries and permissions only**.

If a change is not strictly required to enforce API surface boundaries, it must NOT be made.

---

## Scope of This Sprint

### In Scope

The agent MAY:

- Modify URL routing files
- Add or update permission classes
- Add HTTP method restrictions
- Add deny-by-default enforcement
- Add tests asserting forbidden access
- Add documentation comments explaining boundaries

### Out of Scope

The agent MUST NOT:

- Touch canonical truth derivation
- Touch evidence evaluation
- Touch contribution scoring
- Touch confidence or decay logic
- Touch data rights logic
- Touch third-party app logic

---

## Required API Classification

The backend API surface must be explicitly classified into the following groups:

### 1. Public Read APIs

Characteristics:
- Read-only
- Anonymous access allowed
- Canonical data only

### 2. User-Scoped APIs (/api/me)

Characteristics:
- Authenticated users only
- Access limited strictly to the requesting user
- No cross-user access possible

### 3. Contributor APIs

Characteristics:
- Authenticated
- Explicit contributor capability required
- Used only for evidence submission

### 4. Admin or Internal APIs

Characteristics:
- Restricted access
- Not exposed publicly
- Used for moderation or diagnostics

This classification must be **enforced in code**, not just documented.

---

## Functional Requirements

The agent must implement the following, in order:

### 1. Route Namespace Lockdown

- Clearly group routes by namespace
- Ensure mutation endpoints cannot be accessed via public routes
- Reserve future namespaces (for example, /api/apps) without enabling them

### 2. HTTP Method Allow-Lists

- Explicitly define which HTTP methods are allowed per endpoint
- Reject unsupported methods with HTTP 405
- Do not rely on default Django behavior

### 3. Deny-by-Default Permissions

- Any endpoint without an explicit permission declaration must be inaccessible
- Access must be granted explicitly, never implicitly

### 4. Mutation Safety Guarantees

- Verify that no unauthenticated request can mutate state
- Verify that read-only endpoints cannot be abused via alternate HTTP methods

---

## Security Requirements

The following security guarantees MUST hold after this sprint:

- No state-changing endpoint is accessible without authentication
- No endpoint accepts unintended HTTP methods
- No permission ambiguity exists
- Access failures do not leak internal details

Security changes must **not** alter evaluation semantics.

---

## Tests Required

The agent MUST add or update tests that prove:

- Anonymous users cannot access mutation endpoints
- Authenticated users cannot access endpoints outside their scope
- Unsupported HTTP methods return HTTP 405
- Public read endpoints are read-only

Tests must be **explicit and readable**, not implicit.

---

## Documentation Update

The agent MAY add minimal inline documentation explaining:

- API boundary intent
- Permission model rationale

Do NOT rewrite existing documentation unless strictly necessary for clarity.

---

## Definition of Done

This sprint is complete only when:

- API boundaries are explicit and enforced
- Unsupported HTTP methods are rejected consistently
- No anonymous mutation paths exist
- Tests prove boundary enforcement
- No unrelated code has been modified

---

## Reminder

This sprint **does not add features**.

It establishes **guardrails** so that future Phase-2 and Phase-3 work does not accidentally weaken the backend.

Any deviation from scope is a failure of this sprint.

