# Phase-2 Sprint-7 — Rate Limiting and Idempotency

> **Completion Date:** 2026-01-25  
> **Sprint Prompt:** `docs/06_contributing/copilot_prompts/phase_2/07_rate_limiting_and_idempotency.md`

---

## Sprint Goal

Implement traffic safety mechanisms (rate limiting and idempotency) to protect exposed APIs from flooding, scraping, and duplicate writes without affecting evaluation logic or canonical semantics.

**Scope:** Operational protections only. No semantic, evaluation, or model changes.

---

## What This Sprint Delivers

### 1. Per-IP Rate Limiting for Read Endpoints

Implemented IP-based throttling for public read endpoints:

| Endpoint | Rate Limit |
|----------|------------|
| GET /api/v1/stops | 100/minute |
| GET /api/v1/stops/{public_id} | 100/minute |
| GET /api/v1/routes | 100/minute |
| GET /api/v1/routes/{public_id} | 100/minute |

**Features:**
- Anonymous requests throttled by IP address
- Returns HTTP 429 when limit exceeded
- Includes `Retry-After` header in throttle responses
- Configurable via `settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`

---

### 2. Per-User Rate Limiting for Write Endpoints

Implemented user-based throttling for authenticated write endpoints:

| Endpoint | Rate Limit |
|----------|------------|
| POST /api/v1/contributions | 30/minute |
| DELETE /api/me | 30/minute |

**Features:**
- Authenticated users throttled independently per user
- Returns HTTP 429 when limit exceeded
- Does not affect authorization semantics

---

### 3. Idempotency-Key Header Support

Implemented transport-level replay protection via `Idempotency-Key` header:

**Behavior:**
- Same key + same payload → Cached response returned (original status code)
- Same key + different payload → 409 Conflict
- No key → Normal non-idempotent behavior

**Applies to:**
- POST /api/v1/contributions
- DELETE /api/me

**Layer Distinction:**
- `Idempotency-Key` header: Transport-level replay protection
- `client_generated_id`: Domain-level deduplication

Both coexist as layered protection (Stripe/AWS pattern).

---

## Implementation Summary

### Files Created

1. **backend/api/throttling.py** (NEW)
   - `AnonReadThrottle` - IP-based throttle for anonymous reads
   - `UserWriteThrottle` - User-based throttle for authenticated writes

2. **backend/api/idempotency.py** (NEW)
   - `IdempotencyMixin` - Mixin for Idempotency-Key header support
   - `get_idempotency_cache_key()` - Cache key generation
   - `compute_payload_hash()` - Deterministic payload hashing

3. **backend/api/tests/test_rate_limiting.py** (NEW)
   - 11 tests across 4 test classes
   - Validates rate limiting behavior and invariants

4. **backend/api/tests/test_idempotency.py** (NEW)
   - 9 tests across 4 test classes
   - Validates idempotency key behavior and safety

### Files Modified

1. **backend/backend/settings.py**
   - Added `DEFAULT_THROTTLE_RATES` configuration to `REST_FRAMEWORK`

2. **backend/api/views/canonical.py**
   - Added `throttle_classes = [AnonReadThrottle]` to:
     - `StopListView`
     - `StopDetailView`
     - `RouteListView`
     - `RouteDetailView`

3. **backend/api/views/contributions.py**
   - Added `throttle_classes = [UserWriteThrottle]`
   - Added `IdempotencyMixin` to `ContributionSubmissionView`
   - Updated `post()` method for idempotency handling

4. **backend/api/views/me.py**
   - Added `throttle_classes = [UserWriteThrottle]`
   - Added `IdempotencyMixin` to `AccountDeletionView`
   - Updated `delete()` method for idempotency handling

---

## Test Results

All tests pass (314 total):

**RateLimitingReadEndpointsTests** (6 tests):
- Excessive anonymous reads return 429 (stops list, detail, routes list, detail)
- Rate limit headers present
- Throttle errors do not leak diagnostics

**RateLimitingWriteEndpointsTests** (2 tests):
- Excessive writes return 429
- Authenticated users throttled independently

**RateLimitingInvariantTests** (2 tests):
- Rate limiting does not affect authorization (unauthenticated write)
- Rate limiting does not affect authorization (authenticated read)

**RateLimitingUIModeBoundaryTests** (1 test):
- UI mode does not affect throttling

**IdempotencyKeyContributionTests** (5 tests):
- Same key, same payload returns cached response
- Same key, different payload returns 409
- Missing key is non-idempotent
- Idempotency does not leak internal state
- Different users have separate namespaces

**IdempotencyKeyAccountDeletionTests** (2 tests):
- Different users can reuse key (namespaces)
- Same user replay returns cached deletion response

**IdempotencyKeyAuthorizationTests** (1 test):
- Idempotency key does not bypass auth

**IdempotencyKeyConflictMessageTests** (2 tests):
- Conflict response is JSON
- Conflict response does not leak payload hash

---

## Invariants Enforced

### INV-RL1: Rate Limiting Does Not Affect Truth ✅
Rate limiting is a seatbelt, not a steering wheel. Disabling throttling does not change correctness.

### INV-RL2: UI Mode Independence ✅
X-UI-Mode header has no effect on rate limiting. Tests verify UI mode does not affect throttling.

### INV-RL3: No Diagnostic Leakage ✅
Throttle error responses do not expose cache, scope, or internal details.

### INV-RL4: Authorization Semantics Preserved ✅
Rate limiting does not change auth requirements. Unauthenticated writes fail with 401/403, not 429.

### INV-ID1: Idempotency Does Not Bypass Authorization ✅
Requests still require authentication even with Idempotency-Key header.

### INV-ID2: Idempotency Does Not Leak Internal State ✅
Responses do not expose hash, cache, or replay details.

### INV-ID3: Layered Protection Coexistence ✅
Idempotency-Key (transport-level) and client_generated_id (domain-level) coexist safely.

---

## API Examples

### Rate Limiting (429 Response)

```bash
# After exceeding 100 requests/minute
curl http://localhost:8000/api/v1/stops
```

**Response (HTTP 429)**:
```json
{
  "detail": "Request was throttled. Expected available in 45 seconds."
}
```

**Headers**:
```
Retry-After: 45
```

### Idempotent Request

```bash
curl -X POST http://localhost:8000/api/v1/contributions \
  -H "Authorization: Bearer <token>" \
  -H "Idempotency-Key: unique-request-id-123" \
  -H "Content-Type: application/json" \
  -d '{"client_generated_id": "...", ...}'
```

**First Response (HTTP 201)**:
```json
{
  "id": "uuid",
  "client_generated_id": "...",
  "contribution_type": "stop_exists",
  "created": true
}
```

**Replay Response (HTTP 200)**:
```json
{
  "id": "uuid",
  "client_generated_id": "...",
  "contribution_type": "stop_exists",
  "created": true
}
```

### Idempotency Conflict (409)

```bash
# Same Idempotency-Key with different payload
curl -X POST http://localhost:8000/api/v1/contributions \
  -H "Idempotency-Key: unique-request-id-123" \
  -d '{"different": "payload"}'
```

**Response (HTTP 409)**:
```json
{
  "error": "Idempotency key already used with different request body"
}
```

---

## Error Semantics

All error responses follow a **stable, minimal contract**:

| Status | Scenario | Response |
|--------|----------|----------|
| 429 | Rate limit exceeded | `{"detail": "Request was throttled..."}` |
| 409 | Idempotency conflict | `{"error": "Idempotency key already used..."}` |

**No leakage:** No cache details, hashes, scopes, or internal identifiers exposed.

---

## Non-Goals Confirmed

This sprint explicitly did NOT:
- ✅ Add or modify evaluation logic
- ✅ Add or modify models
- ✅ Add migrations
- ✅ Change canonical semantics
- ✅ Modify visibility logic
- ✅ Modify authorization logic
- ✅ Add Redis or other infrastructure dependencies
- ✅ Add global throttles (applied per-view only)

---

## Phase-2 Invariant Compliance

**P2-INV-1: Truth Authority Invariant** ✅
- Rate limiting does not affect belief or evaluation
- Idempotency does not alter canonical data

**P2-INV-2: Visibility-Only UI Modes** ✅
- UI mode does not affect throttling
- Tests verify UI mode independence

**P2-INV-3: Canonical Read Safety** ✅
- Throttle errors do not leak diagnostics
- Idempotency does not expose internal state

**P2-INV-4: API Boundary Explicitness** ✅
- Throttles applied explicitly per-view
- Idempotency scoped to mutation endpoints only

**P2-INV-5: Authentication Before Mutation** ✅
- Idempotency does not bypass authentication
- Rate limiting does not change auth requirements

**P2-INV-10: Guardrails Before Features** ✅
- Traffic safety established before abuse signals (Sprint-8)
- All failure modes tested

---

## Configuration

Rate limits are configurable in `settings.py`:

```python
REST_FRAMEWORK = {
    # ...
    "DEFAULT_THROTTLE_RATES": {
        "anon_read": "100/minute",   # IP-based for public reads
        "user_write": "30/minute",   # User-based for mutations
    },
}
```

Idempotency cache uses Django's cache framework:
- **Development:** LocMemCache (default)
- **Production:** Redis recommended (not configured in this sprint)

---

## Lessons Learned

1. **DRF Throttle Testing**
   - `override_settings` does not work for throttle rates (classes cache at import)
   - Mock-based testing with `@patch('api.throttling.X.get_rate')` required

2. **Layered Idempotency**
   - Transport-level (Idempotency-Key) and domain-level (client_generated_id) coexist
   - Both provide independent protection (industry standard pattern)

3. **Cache Clearing in Tests**
   - Tests must clear cache in `setUp()` and `tearDown()`
   - Throttle state persists across test methods otherwise

4. **Canonical Entity Test Setup**
   - Use `_internal_save()` for creating canonical entities in tests
   - Direct `objects.create()` blocked by model guardrails

---

## Next Steps (Out of Scope for Sprint-7)

Sprint-8 will implement:
- Abuse signal collection from rate-limited requests
- Flag submission endpoints
- Abuse pattern detection hooks

Future considerations:
- Redis-backed cache for production idempotency
- Custom rate limit headers (X-RateLimit-Remaining)
- Per-endpoint rate customization

---

## Sprint Completion Checklist

- [x] AnonReadThrottle implemented for read endpoints
- [x] UserWriteThrottle implemented for write endpoints
- [x] IdempotencyMixin implemented for mutation endpoints
- [x] Settings configured with throttle rates
- [x] All 4 read views throttled
- [x] All 2 write views throttled and idempotent
- [x] All tests pass (314 total, 20 new)
- [x] Rate limiting does not affect authorization
- [x] UI mode does not affect throttling
- [x] Idempotency does not bypass auth
- [x] No diagnostic leakage
- [x] No evaluation logic modified
- [x] No model changes
- [x] Documentation complete

---

**Sprint-7 Status: COMPLETE** ✅

End of Phase-2 Sprint-7 execution history.
