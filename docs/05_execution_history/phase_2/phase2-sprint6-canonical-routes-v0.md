# Phase-2 Sprint-6 — Canonical Read Endpoints (Routes v0)

> **Completion Date:** 2026-01-22
> **Sprint Prompt:** `docs/plans/2026-01-22-canonical-routes-v0.md`

---

## Sprint Goal

Expose the first canonical read APIs for Routes using existing guardrails from Sprint-2A and following the pattern established by Sprint-5 (Stop endpoints).

**Scope:** Read-only endpoints only. No evaluation changes, no write paths.

---

## What This Sprint Delivers

### 1. Versioned Public APIs

Implemented versioned canonical read endpoints at `/api/v1/routes`:

- **GET /api/v1/routes** - Paginated list of canonical routes
- **GET /api/v1/routes/{public_id}** - Single route detail

**API Version:** v1 (path-based versioning)

---

### 2. Canonical Route Serializer

Created `RouteSerializer` inheriting from `CanonicalReadSerializerBase`:

**Exposed Fields** (whitelist-only):
- `public_id` - Stable public identifier
- `name` - Full route name
- `short_name` - Short identifier (e.g., "42", "Red")
- `route_type` - Type of transit service
- `belief_state` - Human-readable confidence projection

**Blocked Fields** (never exposed):
- Internal UUID (`id`)
- Evidence references (`evidence_refs`)
- Confidence scores (`structural_confidence`, `freshness_confidence`)
- Timestamps (`created_at`, `updated_at`, `valid_from`, `valid_until`)
- Contributor information
- Operator field (deferred to future versions)
- Properties JSON (deferred to future versions)
- Related entities (variants, stops)

---

### 3. List View with Pagination

**RouteListView** features:
- Pagination-bounded (default: 20, max: 100)
- Deterministic ordering by `public_id`
- Snapshot-safe
- Anonymous access permitted
- No filtering or custom sorting in v1

---

### 4. Detail View

**RouteDetailView** features:
- Lookup by stable `public_id`
- 404-safe (no information leakage)
- No relationship expansion
- Anonymous access permitted

---

## Implementation Summary

### Files Created

1. **backend/api/tests/test_canonical_route_endpoints.py** (NEW)
   - 33 tests across 6 test classes
   - Validates all safety guarantees and invariants

### Files Modified

1. **backend/api/views/canonical.py**
   - Added `RouteSerializer` - Canonical read serializer for Routes
   - Added `RouteListView` - Paginated list endpoint with deterministic ordering
   - Added `RouteDetailView` - Single route detail endpoint

2. **backend/api/urls.py**
   - Added Route endpoints to `canonical_read_urlpatterns`
   - Updated imports to include `RouteListView` and `RouteDetailView`

3. **backend/transit/models/route.py**
   - Added `BeliefState` choices enum
   - Added `belief_state` field to Route model

4. **backend/transit/migrations/0003_add_belief_state_to_route.py** (NEW)
   - Migration to add belief_state field to Route model

---

## Test Results

All tests pass (33 tests):

**RouteListEndpointTests** (14 tests):
- Anonymous access allowed
- Response structure valid
- Deterministic ordering by public_id
- Only canonical-safe fields exposed
- No internal IDs, evidence, confidence scores, or timestamps leaked
- No relationship expansion (stops, variants)
- Pagination default, custom, max (rejects >100), negative, zero, malformed cases
- Snapshot semantics (read stability)

**RouteDetailEndpointTests** (8 tests):
- Anonymous access allowed
- Valid public_id returns route
- Only canonical-safe fields exposed
- Invalid public_id returns 404
- 404 does not leak information
- No internal IDs leaked
- No relationship expansion

**RouteReadOnlyEnforcementTests** (6 tests):
- POST, PUT, PATCH, DELETE rejected (403/405)
- HEAD and OPTIONS allowed

**RouteVersioningTests** (3 tests):
- v1 paths exist and work
- Non-versioned paths return 404

**RoutePublicIdDeterminismTests** (3 tests):
- All routes have non-null public_id
- public_id stable across requests
- public_id not internal UUID

**RouteUIModePresentationTests** (2 tests):
- UI mode does not affect anonymous access
- Canonical fields independent of UI mode

---

## Invariants Enforced

### INV-CR1: Canonical Data is Read-Only ✅
All canonical endpoints use `ReadOnlyPublic` permission and `http_method_names` restrictions.

### INV-CR2: No Evidence Exposure ✅
Serializer blocks `evidence_refs`, `evidence_count`, confidence scores.

### INV-CR3: No Contributor Identity ✅
Serializer blocks all contributor-related fields.

### INV-CR4: Whitelist-Only Fields ✅
`RouteSerializer` declares explicit `Meta.allowed_fields` and inherits from `CanonicalReadSerializerBase`.

### INV-CR5: Bounded Pagination ✅
`CanonicalReadPaginationMixin` enforces `DEFAULT_PAGE_SIZE=20` and `MAX_PAGE_SIZE=100`.

### INV-CR6: Anonymous Safety ✅
`ReadOnlyPublic` permission allows anonymous GET/HEAD/OPTIONS.

### INV-CR7: Deterministic Ordering ✅
Results ordered by `public_id` for stable pagination and replay safety.

### INV-CR8: No Relationship Expansion ✅
Routes do not embed Stops, RouteVariants, or any related entities.

### INV-CR9: Versioned API Surface ✅
All endpoints at `/api/v1/routes`, non-versioned paths return 404.

### INV-CR10: Public ID Contract ✅
- Deterministic
- Stable across requests and re-evaluation
- Independent of DB primary key
- Non-null for all routes

---

## API Examples

### List Routes (Default Pagination)

```bash
curl http://localhost:8000/api/v1/routes
```

**Response**:
```json
{
  "results": [
    {
      "public_id": "route-a-001",
      "name": "Downtown Express",
      "short_name": "42",
      "route_type": "bus",
      "belief_state": "active_high"
    },
    {
      "public_id": "route-b-002",
      "name": "Red Line",
      "short_name": "Red",
      "route_type": "metro",
      "belief_state": "active_high"
    }
  ],
  "count": 2
}
```

### List Routes (Custom Pagination)

```bash
curl http://localhost:8000/api/v1/routes?page_size=5
```

### Get Route Detail

```bash
curl http://localhost:8000/api/v1/routes/route-001
```

**Response**:
```json
{
  "public_id": "route-001",
  "name": "Downtown Express",
  "short_name": "42",
  "route_type": "bus",
  "belief_state": "active_high"
}
```

### Not Found (404)

```bash
curl http://localhost:8000/api/v1/routes/nonexistent
```

**Response**:
```json
{
  "detail": "Not found."
}
```

---

## Non-Goals Confirmed

This sprint explicitly did NOT:
- ✅ Add or modify evaluation logic
- ✅ Add write or contribution endpoints
- ✅ Modify existing models (except adding belief_state field to Route)
- ✅ Expose evidence or confidence
- ✅ Introduce route mutation logic
- ✅ Change guardrail implementations
- ✅ Add GTFS or live tracking
- ✅ Embed or expand relationships (no stops, no variants)

---

## Phase-2 Invariant Compliance

**P2-INV-1: Truth Authority Invariant** ✅
- No API changes affect belief or evaluation
- Canonical routes remain derived from evaluation logic

**P2-INV-2: Visibility-Only UI Modes** ✅
- UI mode does not change data or authorization
- Tests verify UI mode independence

**P2-INV-3: Canonical Read Safety** ✅
- No evidence, contributor, threshold, or diagnostic exposure
- Whitelist-only serialization

**P2-INV-4: API Boundary Explicitness** ✅
- Explicit namespace (`/api/v1/routes`)
- Explicit permission (`ReadOnlyPublic`)
- Explicit HTTP methods (`GET`, `HEAD`, `OPTIONS`)

**P2-INV-5: Authentication Before Mutation** ✅
- No mutation endpoints exist
- All read paths are anonymous-safe

**P2-INV-6: Determinism and Replay Safety** ✅
- Deterministic ordering by `public_id`
- Reads have no side effects

**P2-INV-9: No Silent Scope Expansion** ✅
- All changes tested and documented
- No relationship expansion

**P2-INV-10: Guardrails Before Features** ✅
- Uses existing guardrails from Sprint-2A
- All failure modes tested

---

## Lessons Learned

1. **Pattern Replication Success**
   - Mirroring Stop endpoints provided clear template
   - Minimal adaptation needed for Route entity

2. **Test Coverage Template**
   - Stop endpoint tests provided comprehensive checklist
   - All invariants systematically verified

3. **Serializer Base Class Value**
   - `CanonicalReadSerializerBase` prevented field leakage
   - Whitelist approach caught potential mistakes early

4. **Relationship Expansion Ban**
   - Explicit tests for no embedded entities
   - Future expansion requires versioned change

5. **Canonical Read Pattern Establishment**
   - This sprint establishes the canonical pattern for all multi-entity read endpoints
   - Route endpoints follow exact same pattern as Stop endpoints
   - Public ID invariants, error schemas, and query surface freeze apply universally

6. **Model Extension Required**
   - Route model needed `belief_state` field added to match Stop model
   - Migration required but straightforward

---

## Next Steps (Out of Scope for Sprint-6)

Future canonical read endpoints may include:
- RouteVariant endpoints (v2 or separate versioned API)
- Stop-Route relationship queries (requires careful design)
- Spatial filtering for Routes (bounding box queries)
- Schedule/service window visibility

All future expansions require:
- New API version or explicit feature flag
- Updated serializers with new `allowed_fields`
- Comprehensive safety tests
- Documentation updates

---

## Sprint Completion Checklist

- [x] RouteSerializer implemented with canonical safety
- [x] RouteListView with pagination and ordering
- [x] RouteDetailView with 404 safety
- [x] URL routes configured at `/api/v1/routes`
- [x] All tests pass (33 tests)
- [x] No relationship expansion
- [x] No evidence/contributor leakage
- [x] Deterministic ordering enforced
- [x] UI mode independence verified
- [x] Versioning enforced (v1 only)
- [x] Public ID contract validated
- [x] No evaluation logic modified
- [x] Model changes minimal (belief_state field added)
- [x] Documentation complete

---

**Sprint-6 Status: COMPLETE** ✅

End of Phase-2 Sprint-6 execution history.
