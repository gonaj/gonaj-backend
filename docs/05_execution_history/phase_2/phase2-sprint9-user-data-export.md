# Phase-2 Sprint-9 — Data Rights: User Data Export

> **Completion Date:** 2026-01-25
> **Sprint Prompt:** `docs/06_contributing/copilot_prompts/phase_2/09_data_rights_user_data_export.md`
> **Sprint Plan:** `docs/plans/2026-01-25-user-data-export.md`

---

## Sprint Goal

Allow authenticated users to **export all of their own data deterministically** in a safe, privacy-preserving manner, implementing GDPR-style "right to access" without exposing system internals or other users' data.

**Scope:** Read-only export of user-owned contribution data. No evaluation changes, no canonical entity export.

---

## What This Sprint Delivers

### 1. Versioned User Export API

Implemented versioned export endpoint at `/api/v1/me/contributions/export`:

- **GET /api/v1/me/contributions/export** - Atomic, complete export of user contributions.

**API Version:** v1 (path-based versioning)

---

### 2. Frozen v1 Export Format

Defined a stable, deterministic JSON schema for data portability:

**Envelope Semantics:**
- `export_version`: "v1" (Frozen)
- `generated_at`: ISO-8601 timestamp
- `user`: Minimal account metadata (user_id, created_at)
- `contributions`: List of user-submitted events

**Contribution Fields** (whitelist-only):
- `contribution_id`: User-generated idempotency key (client_generated_id)
- `contribution_type`: Type of observation
- `observed_at`: User-provided timestamp
- `submitted_at`: Server receipt timestamp (GDPR requirement)
- `subject_ref`: Location/entity reference
- `payload`: Raw submitted evidence

**Blocked Fields** (never exposed):
- Internal UUID (`id`)
- Contributor fingerprints (`contributor_fingerprint`)
- Device identifiers (`device_id`)
- System context (`context`)
- Internal relationships (`contributor_id`, `contributor`)

---

### 3. Safety & Determinism

**ContributionExportView** features:
- **Atomic & Complete:** No pagination in v1. Returns full dataset.
- **Deterministic Ordering:** Sorted by `submitted_at ASC` (and `id` tie-breaker) for bit-for-bit reproducibility.
- **Ownership Isolation:** Strictly scoped to `request.user`.
- **Capability Check:** Requires `Capability.CONTRIBUTE`.

---

## Implementation Summary

### Files Modified

1. **backend/api/urls.py**
   - Added `v1_me_urlpatterns` for versioned self-service endpoints.
   - Removed legacy unversioned export route.

2. **backend/api/views/export.py**
   - Implemented `ContributionExportView` with v1 frozen semantics.
   - Enforced `Capability.CONTRIBUTE` check.
   - Removed pagination logic (v1 is atomic).
   - Enforced deterministic ordering.

3. **backend/api/serializers/export.py**
   - Implemented `ContributionExportSerializer` with explicit field whitelist.
   - Implemented `ContributionExportListSerializer` for v1 envelope metadata.
   - Added security invariants checking (blocking restricted fields).

### Tests Updated

1. **backend/api/tests/test_contribution_export.py** (Rewrite)
   - Verified v1 schema and envelope.
   - Verified ownership isolation (User A vs User B).
   - Verified deterministic ordering and reproducibility.
   - Verified non-leakage consistency (no fingerprints/internal IDs).
   - Verified UI mode independence.

2. **backend/api/tests/test_canonical_read_hardening.py**
   - Updated to use v1 endpoint.
   - Verified hardening against information leakage with new format.

3. **backend/api/tests/test_api_surface_boundaries.py**
   - Updated to use v1 endpoint.
   - Verified authentication and method restrictions.

---

## Test Results

All tests pass (100% pass rate):

**ContributionExportTests**:
- Authorization: ✅ (Anonymous denied, Auth allowed)
- Ownership: ✅ (Users only see own data)
- Format: ✅ (v1 schema, timestamps, user section correct)
- Determinism: ✅ (Repeated calls identical except `generated_at`)
- Privacy: ✅ (No internal IDs, fingerprints, or devices leaked)
- UI Mode: ✅ (Header ignored)
- Deletion: ✅ (Inactive users denied)

**Hardening & Boundary Tests**:
- Method restrictions (POST/PUT/DELETE denied) enforced.
- No stack traces or debug info leaked.
- Canonical path `/api/v1/me/...` enforced.

---

## Invariants Enforced

### P2-INV-8: User Data Rights Preserved ✅
Export provides complete access to user-owned data without requiring administrative intervention.

### INV-D1: No System-Internal Identifiers ✅
Export exposes only user-facing or user-generated identifiers (`contribution_id`, `user_id`). Internal UUIDs and DB keys are stripped.

### INV-D3: Deleted Users Scope ✅
Inactive/deleted users are denied access (authorization check precedes export), preserving "right to be forgotten" consistency.

### INV-D4: No Leaking Contributor Fingerprint ✅
Evaluation identity (`contributor_fingerprint`) is strictly blocked from export to prevent correlation attacks.

### Export v1 Frozen Semantics ✅
- **Atomic**: Complete dataset or error.
- **Non-Paginated**: No hidden pages.
- **Deterministic**: Stable sorting.
- **Non-Filterable**: "All or nothing" access.

---

## API Examples

### Export Contributions

```bash
GET /api/v1/me/contributions/export
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "export_version": "v1",
  "generated_at": "2026-01-25T10:30:00Z",
  "user": {
    "user_id": "uuid...",
    "created_at": "2026-01-01T00:00:00Z"
  },
  "contributions": [
    {
      "contribution_id": "client-uuid-1",
      "contribution_type": "stop_exists",
      "observed_at": "2026-01-20T10:00:00Z",
      "submitted_at": "2026-01-20T10:05:00Z",
      "subject_ref": {"lat": 40.7, "lon": -74.0},
      "payload": {"confidence": "high"}
    }
  ]
}
```

---

## Non-Goals Confirmed

- ✅ No export of canonical entities (Stops/Routes)
- ✅ No export of evaluation results or abuse scores
- ✅ No export of other users' data
- ✅ No new persistence models
- ✅ No changes to evaluation logic

---

## Sprint Completion Checklist

- [x] Versioned Endpoint `/api/v1/me/contributions/export`
- [x] v1 Frozen Export Format (Atomic, Complete)
- [x] Metadata Envelope (Version, Timestamp, User)
- [x] Whitelisted Contribution Fields
- [x] Deterministic Ordering (`submitted_at ASC`)
- [x] Privacy Hardening (Fingerprints/IDs blocked)
- [x] Zero-Pagination implementation
- [x] Automated Tests Passing (Logic, Privacy, Boundaries)
- [x] Documentation Complete

---

**Sprint-9 Status: COMPLETE** ✅

End of Phase-2 Sprint-9 execution history.
