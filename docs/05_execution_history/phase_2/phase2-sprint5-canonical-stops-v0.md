# Phase-2 Sprint-5 — Canonical Read Endpoints (Stops v0)

**Status**: ✅ Complete  
**Date**: 2026-01-21  
**Sprint**: Phase-2 Sprint-5  
**Branch**: `main` (or feature branch as appropriate)

---

## Critical Context

This sprint implements the **first public canonical read APIs** for Stops.

These endpoints expose what the backend conservatively believes to be true about transit stops, never how it arrived at that belief or who contributed to it.

---

## What This Sprint Delivers

### 1. Versioned Public APIs

Implemented versioned canonical read endpoints at `/api/v1/stops`:

- **GET /api/v1/stops** - Paginated list of canonical stops
- **GET /api/v1/stops/{public_id}** - Single stop detail

### 2. Canonical Stop Serializer

Created `StopSerializer` inheriting from `CanonicalReadSerializerBase`:

**Exposed Fields** (whitelist-only):
- `public_id` - Stable public identifier
- `name` - Primary stop name
- `location` - Geographic coordinates (GeoJSON Point format)
- `belief_state` - Human-readable confidence projection

**Blocked Fields** (never exposed):
- Internal UUID (`id`)
- Evidence references (`evidence_refs`)
- Confidence scores (`structural_confidence`, `freshness_confidence`)
- Timestamps (`created_at`, `updated_at`, `valid_from`, `valid_until`)
- Contributor information
- Alternate names (deferred to future API versions)

### 3. Safety Guarantees

**Anonymous Access**:
- Public endpoints accessible without authentication
- ReadOnlyPublic permission enforced

**Read-Only Enforcement**:
- Only GET, HEAD, OPTIONS methods allowed
- POST, PUT, PATCH, DELETE rejected with 403/405

**Pagination Bounds**:
- Default page size: 20 items
- Maximum page size: 100 items
- Prevents scraping and DoS attacks

**Deterministic Ordering**:
- Results ordered by `public_id`
- Stable pagination cursors
- Reproducible results across requests

**Snapshot Safety**:
- Each request observes self-consistent canonical data
- No transactional guarantees across requests

**Error Safety**:
- 404 responses do not leak existence, evaluation status, or contributor information

### 4. API Versioning

**Path-Based Versioning**:
- All canonical endpoints at `/api/v1/*`
- Version is part of the public contract
- Query surface frozen for v1 (pagination only, no filtering/sorting)

**Rationale**:
- Prevents silent client breakage
- Allows conservative schema evolution
- Long-lived API contracts

---

## Implementation Summary

### Files Created

1. **backend/api/views/canonical.py** (NEW)
   - `StopSerializer` - Canonical read serializer for Stops
   - `StopListView` - Paginated list endpoint
   - `StopDetailView` - Single stop detail endpoint

2. **backend/api/tests/test_canonical_stop_endpoints.py** (NEW)
   - 35 tests across 6 test classes
   - Validates all safety guarantees and invariants

### Files Modified

1. **backend/api/urls.py**
   - Added `canonical_read_urlpatterns` with versioned Stop routes
   - Updated imports to include `StopListView` and `StopDetailView`
   - Combined canonical read URLs into main `urlpatterns`

---

## Test Results

All 35 tests pass:

```bash
docker compose exec web uv run python backend/manage.py test \
  api.tests.test_canonical_stop_endpoints --verbosity=2
```

### Test Coverage

**StopListEndpointTests** (14 tests):
- Anonymous access allowed
- Response structure valid
- Deterministic ordering by public_id
- Only canonical-safe fields exposed
- No internal IDs, evidence, confidence scores, or timestamps leaked
- Location formatted as GeoJSON Point
- Pagination default, custom, max, negative, zero, malformed cases

**StopDetailEndpointTests** (7 tests):
- Anonymous access allowed
- Valid public_id returns stop
- Only canonical-safe fields exposed
- Invalid public_id returns 404
- 404 does not leak information
- No internal IDs leaked
- Location formatted as GeoJSON

**StopReadOnlyEnforcementTests** (6 tests):
- POST, PUT, PATCH, DELETE rejected (403/405)
- HEAD and OPTIONS allowed

**StopUIModePresentationTests** (2 tests):
- UI mode does not affect anonymous access
- Canonical fields independent of UI mode

**StopSnapshotSafetyTests** (2 tests):
- Single request returns consistent data
- Deterministic ordering per request

**StopVersioningTests** (3 tests):
- Versioned path required (`/api/v1/stops`)
- Pagination parameter allowed
- Unsupported parameters handled safely

---

## API Examples

### List Stops (Default Pagination)

```bash
curl http://localhost:8000/api/v1/stops
```

**Response**:
```json
{
  "results": [
    {
      "public_id": "stop-001",
      "name": "Main Street Station",
      "location": {
        "type": "Point",
        "coordinates": [-74.006, 40.7128]
      },
      "belief_state": "active_high"
    },
    {
      "public_id": "stop-002",
      "name": "Central Park West",
      "location": {
        "type": "Point",
        "coordinates": [-73.973, 40.7829]
      },
      "belief_state": "active_low"
    }
  ],
  "count": 2
}
```

### List Stops (Custom Pagination)

```bash
curl http://localhost:8000/api/v1/stops?page_size=5
```

### Get Stop Detail

```bash
curl http://localhost:8000/api/v1/stops/stop-001
```

**Response**:
```json
{
  "public_id": "stop-001",
  "name": "Main Street Station",
  "location": {
    "type": "Point",
    "coordinates": [-74.006, 40.7128]
  },
  "belief_state": "active_high"
}
```

### Not Found (404)

```bash
curl http://localhost:8000/api/v1/stops/nonexistent
```

**Response**:
```json
{
  "detail": "Not found."
}
```

---

## Invariants Enforced

### INV-CR1: Canonical Data is Read-Only ✅
All canonical endpoints use `ReadOnlyPublic` permission and `http_method_names` restrictions.

### INV-CR2: No Evidence Exposure ✅
Serializer blocks `evidence_refs`, `evidence_count`, confidence scores.

### INV-CR3: No Contributor Identity ✅
Serializer blocks all contributor-related fields.

### INV-CR4: Whitelist-Only Fields ✅
`StopSerializer` declares explicit `Meta.allowed_fields` and inherits from `CanonicalReadSerializerBase`.

### INV-CR5: Bounded Pagination ✅
`CanonicalReadPaginationMixin` enforces `DEFAULT_PAGE_SIZE=20` and `MAX_PAGE_SIZE=100`.

### INV-CR6: Anonymous Safety ✅
`ReadOnlyPublic` permission allows anonymous GET/HEAD/OPTIONS.

### P2-INV-2: Visibility-Only UI Modes ✅
UI mode does not affect query logic or authorization (tests verify independence).

### P2-INV-3: Canonical Read Safety ✅
No evidence metadata, contributor identity, or diagnostics exposed.

### P2-INV-4: API Boundary Explicitness ✅
Endpoints have explicit namespace (`/api/v1/`), permission (`ReadOnlyPublic`), and allowed methods.

---

## What This Sprint Does NOT Do

This sprint explicitly **does not**:

- ❌ Add Route, RouteVariant, or other transit entity endpoints (future sprints)
- ❌ Implement filtering, searching, or custom sorting (v1 freeze)
- ❌ Expose alternate names (deferred to future API versions)
- ❌ Modify evaluation logic or models
- ❌ Add migrations
- ❌ Change write or contribution behavior
- ❌ Implement pagination cursors (simple offset-based for v1)

---

## Integration with Existing Guardrails

This sprint builds on Phase-2 Sprint-2A guardrails:

**From Sprint-2A**:
- `CanonicalReadSerializerBase` (mandatory inheritance)
- `CanonicalReadPaginationMixin` (pagination bounds)
- `ReadOnlyPublic` permission (read-only enforcement)
- `CANONICAL_BLOCKED_FIELDS` (field blocking contract)

**New in Sprint-5**:
- First concrete implementation of canonical read endpoints
- Versioned URL structure (`/api/v1/`)
- Stop-specific serializer with GeoJSON location formatting
- Comprehensive test suite validating all invariants

---

## Future Enhancements (Not in v1)

The following are explicitly **out of scope** for v1 but may appear in future API versions:

- Filtering by belief state, geographic bounds, or name
- Searching and full-text search
- Custom sorting
- Pagination cursors (offset vs cursor-based)
- Alternate names in response
- Distance-based queries
- Batch operations

Any additions require a new API version (v2+) to preserve v1 contract stability.

---

## Validation Commands

### Run Sprint-5 Tests
```bash
docker compose exec web uv run python backend/manage.py test \
  api.tests.test_canonical_stop_endpoints
```

### Run All API Tests
```bash
docker compose exec web uv run python backend/manage.py test api.tests
```

### Run All Tests
```bash
docker compose exec web uv run python backend/manage.py test
```

### Manual API Testing
```bash
# List stops
curl http://localhost:8000/api/v1/stops

# List stops with pagination
curl http://localhost:8000/api/v1/stops?page_size=5

# Get stop detail (replace with actual public_id)
curl http://localhost:8000/api/v1/stops/stop-001

# Verify 404 on nonexistent stop
curl http://localhost:8000/api/v1/stops/nonexistent

# Verify POST rejected
curl -X POST http://localhost:8000/api/v1/stops
```

---

## Migration Path for Existing Code

No existing code is affected by this sprint. This is a **pure addition** of new endpoints.

**New endpoints added**:
- `/api/v1/stops` (list)
- `/api/v1/stops/{public_id}` (detail)

**No breaking changes** to:
- Authentication endpoints
- Contribution endpoints
- User self-service endpoints
- Internal APIs

---

## Architecture Notes

### Why GeoJSON for Location?

GeoJSON is the standard format for geographic data in JSON APIs:
- Industry-standard (RFC 7946)
- Compatible with mapping libraries (Leaflet, Mapbox, etc.)
- Clear coordinate order convention ([lon, lat])
- Future-proof for LineStrings, Polygons, etc.

### Why Deterministic Ordering by public_id?

Ordering by `public_id` ensures:
- Stable pagination (same results across requests)
- No dependency on database insertion order
- No dependency on evaluation timing
- Reproducible for debugging and testing

Alternative orderings (by name, location, belief_state) could be added in future API versions as opt-in query parameters.

### Why v1 Query Surface Freeze?

Freezing query parameters prevents:
- Accidental client dependencies on unstable behavior
- Silent breakage when backend changes filtering logic
- Confusion about supported vs unsupported parameters

Future versions can add filtering/sorting with explicit documentation and guarantees.

---

## Definition of Done

This sprint is complete when:

- ✅ Canonical Stop data is publicly readable via `/api/v1/stops`
- ✅ All reads are safe, bounded, and non-leaky
- ✅ Ordering and pagination are deterministic
- ✅ UI modes affect visibility only
- ✅ API versioning is explicit and enforced
- ✅ No truth or evaluation logic is modified
- ✅ Tests enforce all invariants
- ✅ No code or string formatting issues

**All criteria met** ✅

---

## Lessons Learned

### Permission vs HTTP Method Restrictions

DRF evaluates permissions before checking `http_method_names`, which means unsafe methods may return 403 (Forbidden) instead of 405 (Method Not Allowed). Both status codes are acceptable as they deny mutation; tests were updated to accept either.

### GeoJSON Coordinate Order

GeoJSON uses [lon, lat] order, which is the opposite of many geographic conventions. This is explicitly documented in serializer and tests to prevent confusion.

### Test Isolation Best Practices

Each test creates its own Stop instances with unique `public_id` values to ensure test isolation and prevent cross-contamination.

---

## Related Documentation

- [Phase-2 Invariant Checklist](../../02_phases/phase_2/phase_2_invariant_checklist.md)
- [Phase-2 Sprint-2A: Canonical Read Guardrails](./phase2-sprint2a-canonical-read-guardrails.md)
- [UI Constitution v1](../../01_architecture/ui_constitution_v1.md)
- [Backend Philosophy](../../01_architecture/backend_philosophy.md)
- [API Quick Reference](../../04_api/api_quick_reference.md)

---

## Sign-Off

This sprint successfully delivers the first public canonical read APIs for Stops while maintaining all safety guarantees, respecting existing guardrails, and enforcing Phase-2 invariants.

**Next Steps**:
- Future sprints may add Route, RouteVariant canonical read endpoints
- Future API versions (v2+) may add filtering, searching, sorting
- Performance optimization if needed (caching, database indexing)

End of document.
