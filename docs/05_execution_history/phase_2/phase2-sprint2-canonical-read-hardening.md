Phase-2 Sprint-2: Read-Only Data Surface Hardening (User-Scoped)

This document summarizes the changes made in Phase-2 Sprint-2: Read-Only Data Surface Hardening (User-Scoped) for anonymous safety, prevent data leakage, and enforce
pagination bounds.

## Purpose

This sprint hardened canonical read APIs to ensure they are:
- Safe for anonymous access (where permitted)
- Protected against evidence data leakage
- Stable under malformed or hostile parameters
- Properly bounded to prevent scraping and DoS

Refer to `docs/01_architecture/backend_philosophy.md` and 
`docs/02_phase_1/rules_v0.md` for the invariants being protected.

## Architectural Invariants Enforced

- Canonical data is the only data exposed to anonymous users
- Evidence data must never be inferable from read APIs
- Absence of data must not be interpreted as falseness
- Backend remains sole authority on truth
- UI modes affect visibility only, not semantics

## Changes Made

### 1. Enhanced Permission Classes (`backend/api/permissions.py`)

Updated permission module with:

- **Documentation**: Added canonical read hardening requirements
- **Pagination Constants**: `DEFAULT_PAGE_SIZE = 20`, `MAX_PAGE_SIZE = 100`
- **`ReadOnlyPublic`**: Enhanced documentation for canonical read safety
- **`ReadOnlyAuthenticated`**: New permission class for user-scoped read endpoints

### 2. Export Endpoint Hardening (`backend/api/views/export.py`)

Added pagination enforcement to contribution export:

- **Pagination Parameters**: `page` (default 1), `page_size` (default 20, max 100)
- **Malformed Parameter Handling**: Safe defaults for invalid values
- **Pagination Metadata**: Response includes page, total_count, has_next, has_previous
- **Bounded Queries**: Cannot retrieve more than 100 items per request

### 3. Serializer Lockdown (`backend/api/serializers/export.py`)

Enhanced export serializer with explicit field blocking:

- **Blocked Fields Set**: Explicit documentation of fields that must never appear
- **Whitelist Approach**: Only explicitly allowed fields are serialized
- **Defense-in-Depth Check**: Runtime validation that no blocked field leaks
- **Field Documentation**: Clear comments on what is and is not exported

### 4. Profile Serializer Documentation (`backend/api/serializers/auth.py`)

Enhanced `UserProfileSerializer` with:

- **Explicit Field Documentation**: Whitelist of safe-to-expose fields
- **Blocked Field Documentation**: List of fields that must never appear
- **Read-Only Enforcement**: All fields marked as read-only

### 5. Comprehensive Tests (`backend/api/tests/test_canonical_read_hardening.py`)

Added 500+ lines of hardening tests:

**Test Classes:**

1. **`AnonymousSafetyTests`**: Validates anonymous users cannot access user-scoped data
2. **`SerializerLeakageTests`**: Ensures no internal identifiers are exposed
3. **`MalformedParameterTests`**: Verifies stability under hostile input
4. **`PaginationBoundingTests`**: Confirms pagination limits are enforced
5. **`HttpMethodEnforcementTests`**: Validates 405 for unsupported methods
6. **`OutputSchemaStabilityTests`**: Ensures response schemas are stable
7. **`NoDebugLeakageTests`**: Confirms no stack traces in error responses

## Canonical Read Endpoints

The following endpoints are canonical read endpoints:

| Endpoint | Access | Purpose |
|----------|--------|---------|
| `GET /api/auth/me` | Authenticated | User profile (own data only) |
| `GET /api/me/contributions/export` | Authenticated | Export own contributions |

## What These Endpoints Provide

- User's own profile information (whitelisted fields only)
- User's own contribution data (user-supplied fields only)
- Pagination metadata for large result sets
- Stable, deterministic output schemas

## What These Endpoints Do NOT Provide

- Other users' data
- Internal identifiers (UUIDs, fingerprints)
- Evaluation artifacts (confidence scores, rules applied)
- Moderation artifacts
- Server-generated metadata (submitted_at, device_id, context)
- Canonical transit entities (Stops, Routes) - reserved for future

## Security Guarantees

After these changes:

- No internal identifiers leak through serializers
- No contributor_fingerprint is ever exposed (INV-D4)
- Anonymous users cannot access user-scoped data
- Malformed parameters default to safe values
- Pagination prevents unbounded data retrieval
- All read endpoints reject write methods with 405
- Error responses do not leak stack traces or debug info

## What Was NOT Changed

In compliance with sprint constraints:

- No model changes
- No migration changes
- No evaluation logic changes
- No contribution logic changes
- No write endpoint behavior changes
- No new endpoints added
- No request shapes changed

## Testing

Run the hardening tests:

```bash
python manage.py test api.tests.test_canonical_read_hardening --verbosity=2
```

All tests must pass for the sprint to be considered complete.
