# Phase-2 Sprint-2A — Canonical Read Guardrails

**Status**: ✅ Complete  
**Date**: 2026-01-17  
**Branch**: `phase2-sprint2-canonical-read-hardening`

---

## Critical Context

**As of Phase-2 Sprint-2A, NO canonical read endpoints exist yet.**

There are no public endpoints for Stops, Routes, or any other transit entities.

This sprint exists **only** to establish guardrails, patterns, and constraints that all future canonical read APIs **must** follow.

---

## What This Sprint Delivers

This sprint implements **guardrails only** — mandatory patterns that prevent future canonical endpoints from:

- Leaking evidence data
- Exposing contributor identity
- Revealing internal identifiers
- Enabling scraping or DoS attacks
- Accidentally breaking safety invariants

These guardrails are **enforceable now** and **testable now**, even though the endpoints they protect do not yet exist.

---

## Implementation Summary

### 1. Canonical Read Permission Pattern

**File**: `backend/api/permissions.py`

Enhanced `ReadOnlyPublic` permission class with explicit documentation:

- **Mandatory** permission for all future canonical read endpoints
- Allows GET, HEAD, OPTIONS only
- Denies POST, PUT, PATCH, DELETE
- Safe for anonymous access
- Returns HTTP 405 for unsafe methods

**Key Addition**: Clear documentation that this is the required pattern for canonical endpoints, with usage examples for future implementations.

---

### 2. Canonical Read Serializer Contract

**File**: `backend/api/serializers/canonical.py` (NEW)

Created abstract base class: `CanonicalReadSerializerBase`

**Mandatory Rules**:
- Whitelist-only fields (explicit `Meta.allowed_fields`)
- No contributor references or fingerprints
- No internal UUIDs or server IDs
- No evidence counts or confidence scores
- No evaluation diagnostics
- No contribution timestamps

**Blocked Fields** (58 total in `CANONICAL_BLOCKED_FIELDS`):
```python
CANONICAL_BLOCKED_FIELDS = frozenset([
    # Contributor identity
    "contributor", "contributor_id", "contributor_fingerprint",
    "device_id", "user", "user_id",
    
    # Internal identifiers
    "id", "uuid", "internal_id", "server_id",
    "client_generated_id",
    
    # Evidence and evaluation
    "evidence_count", "evidence", "confidence",
    "quality_score", "evaluation_result",
    
    # Timing patterns
    "created_at", "updated_at", "submitted_at",
    
    # System metadata
    "context", "metadata", "diagnostic",
    # ... and more
])
```

**Defense-in-Depth**:
- Validates `allowed_fields` declaration at init
- Runtime validation in `to_representation()`
- Raises AssertionError in DEBUG if blocked fields leak
- Silently sanitizes in production with error logging

**Future Usage** (not implemented yet):
```python
class StopSerializer(CanonicalReadSerializerBase):
    name = serializers.CharField()
    location = serializers.JSONField()
    
    class Meta:
        allowed_fields = {'name', 'location'}
```

---

### 3. Pagination & Bounding Utilities

**File**: `backend/api/serializers/canonical.py`

Created `CanonicalReadPaginationMixin`:

- Validates `page_size` parameter
- Enforces `DEFAULT_PAGE_SIZE = 20`
- Caps at `MAX_PAGE_SIZE = 100`
- Rejects malformed, negative, or zero values
- Clear error messages for invalid inputs

**Prevents**:
- Unbounded queries
- Scraping attacks
- DoS via massive page sizes

---

### 4. Defensive Tests (Future-Facing)

**File**: `backend/api/tests/test_canonical_read_guardrails.py` (NEW)

Created 35 tests across 5 test classes:

#### `CanonicalReadPermissionTests` (8 tests)
- Verifies `ReadOnlyPublic` allows GET/HEAD/OPTIONS
- Verifies POST/PUT/PATCH/DELETE denied
- Verifies authenticated users follow same rules

#### `CanonicalSerializerContractTests` (6 tests)
- Validates blocked fields defined correctly
- Ensures compliant serializers work
- Raises errors for missing `allowed_fields`
- Catches undeclared fields
- Tests DEBUG vs production sanitization

#### `CanonicalPaginationGuardTests` (8 tests)
- Default page size applied correctly
- Custom page sizes accepted within bounds
- MAX_PAGE_SIZE enforced
- Negative, zero, malformed values rejected

#### `CanonicalReadInvariantTests` (6 tests)
- Evidence fields blocked
- Contributor identity blocked
- Internal IDs blocked
- Timing patterns blocked
- Pagination constants validated
- All unsafe methods denied

**Test Philosophy**:
These tests validate **guardrails**, not features. They use dummy views and serializers created **only for testing**. They ensure the contract is correct **before** any real canonical endpoints are implemented.

---

## Files Modified

### Modified
- `backend/api/permissions.py` - Enhanced `ReadOnlyPublic` docstring with guardrails documentation

### Created
- `backend/api/serializers/canonical.py` - Abstract base serializer and pagination mixin
- `backend/api/tests/test_canonical_read_guardrails.py` - 35 defensive tests
- `docs/05_execution_history/phase_2/phase2-sprint2a-canonical-read-guardrails.md` - This document

---

## Test Results

```bash
docker compose exec web uv run python backend/manage.py test \
  api.tests.test_canonical_read_guardrails --verbosity=2
```

**Expected**: All 35 tests pass

These tests validate:
- Permission patterns enforce read-only access
- Serializer contract prevents field leakage
- Pagination bounds protect against scraping
- Invariants are enforceable before endpoints exist

---

## Key Invariants Enforced

### INV-CR1: Canonical Data is Read-Only
All canonical endpoints **must** use `ReadOnlyPublic` permission.  
**Enforcement**: Permission denies all unsafe methods.

### INV-CR2: No Evidence Exposure
Canonical serializers **cannot** include evidence counts, confidence scores, or evaluation artifacts.  
**Enforcement**: `CANONICAL_BLOCKED_FIELDS` + runtime validation.

### INV-CR3: No Contributor Identity
Canonical serializers **cannot** reference contributors, fingerprints, or user IDs.  
**Enforcement**: `CANONICAL_BLOCKED_FIELDS` + runtime validation.

### INV-CR4: Whitelist-Only Fields
Canonical serializers **must** declare explicit `allowed_fields`.  
**Enforcement**: `CanonicalReadSerializerBase.validate_allowed_fields()`.

### INV-CR5: Bounded Pagination
Canonical list endpoints **must** enforce page size limits.  
**Enforcement**: `CanonicalReadPaginationMixin` + constants.

### INV-CR6: Anonymous Safety
Canonical endpoints are public by default; no authentication bypass possible.  
**Enforcement**: `ReadOnlyPublic` allows anonymous GET/HEAD.

---

## What This Does NOT Do

This sprint explicitly **does not**:

- ❌ Add any public Stop, Route, or transit entity endpoints
- ❌ Expose any canonical data publicly
- ❌ Modify evaluation logic or models
- ❌ Add migrations
- ❌ Change write or contribution behavior
- ❌ Make assumptions about future query patterns

---

## Future Usage

When implementing canonical read endpoints in future sprints:

### Required Pattern
```python
# views/canonical.py (future)
from backend.api.permissions import ReadOnlyPublic
from backend.api.serializers.canonical import CanonicalReadSerializerBase

class StopSerializer(CanonicalReadSerializerBase):
    name = serializers.CharField()
    location = serializers.JSONField()
    
    class Meta:
        allowed_fields = {'name', 'location'}

class StopListView(APIView):
    permission_classes = [ReadOnlyPublic]
    
    def get(self, request):
        # Implementation with pagination
        pass
```

### Validation Checklist
- [ ] Uses `ReadOnlyPublic` permission
- [ ] Serializer inherits from `CanonicalReadSerializerBase`
- [ ] Declares `Meta.allowed_fields`
- [ ] No blocked fields in serializer
- [ ] Implements pagination with bounds
- [ ] Tests verify no evidence/contributor leakage

---

## Rationale

### Why Guardrails Before Features?

1. **Prevent Future Mistakes**: Easier to enforce constraints before code exists than to fix violations later
2. **Clear Contract**: Future developers know exactly what is allowed/forbidden
3. **Testable Now**: Validate patterns work before implementing real endpoints
4. **Defense-in-Depth**: Multiple layers of protection (permission + serializer + runtime)
5. **Evidence-Driven Architecture**: Canonical truth must never reveal how it was derived

### Why Abstract Base Serializer?

- Forces explicit field whitelisting (no accidental inclusions)
- Centralizes blocked field logic (single source of truth)
- Runtime validation catches violations even if code review misses them
- Clear inheritance hierarchy (canonical vs export vs internal)

### Why Future-Facing Tests?

- Validates contract is correct **before** real implementations
- Catches design flaws early (cheaper to fix)
- Serves as documentation and examples
- Prevents "just ship it" shortcuts under pressure

---

## Validation Commands

### Run Guardrail Tests
```bash
docker compose exec web uv run python backend/manage.py test \
  api.tests.test_canonical_read_guardrails
```

### Run All API Tests
```bash
docker compose exec web uv run python backend/manage.py test api.tests
```

### Check Serializer Import
```bash
docker compose exec web uv run python -c \
  "from backend.api.serializers.canonical import CanonicalReadSerializerBase; print('OK')"
```

---

## Next Steps (Future Sprints)

When implementing canonical read endpoints:

1. **Review Guardrails**: Re-read this document and `canonical.py`
2. **Inherit Base**: Use `CanonicalReadSerializerBase` for all canonical serializers
3. **Use Pattern**: Apply `ReadOnlyPublic` permission
4. **Write Tests**: Verify no blocked fields leak, pagination works
5. **Document**: Update API documentation with canonical endpoint behavior

**Do NOT**:
- Skip the base serializer to "move faster"
- Use `ModelSerializer` for canonical data (too easy to leak fields)
- Add endpoints without pagination
- Assume authentication is required (canonical is public)

---

## Definition of Done

- ✅ Guardrail patterns exist and are documented
- ✅ Tests enforce future-facing constraints (35 tests pass)
- ✅ No new endpoints exposed
- ✅ No models or migrations changed
- ✅ Documentation clearly explains intent and scope
- ✅ Code is minimal and explicit
- ✅ No emojis or special characters in code

---

## Philosophy

This sprint is about **preventing future mistakes**, not delivering features.

Every change in this sprint is something that future developers and agents will rely on to avoid breaking core invariants.

Canonical data represents what the backend conservatively believes to be true. It must never reveal:
- How that truth was derived
- Who contributed to it
- What alternatives were considered
- Internal evaluation mechanics

These guardrails enforce that philosophy at the serialization and permission layers.
