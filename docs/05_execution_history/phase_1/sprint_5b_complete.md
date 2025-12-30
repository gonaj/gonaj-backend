# Sprint-5B Complete: Evidence De-identification with Evaluation Safety

**Sprint:** Phase-1 Sprint-5B  
**Status:** Complete  
**Date:** 2025-12-30

---

## Summary

Sprint-5B implements evidence de-identification for DATA_RIGHTS_V1 compliance while preserving evaluation semantics. When a user account is deleted, the `contributor` FK on ContributionEvents is set to NULL, but the `contributor_fingerprint` field preserves the submission-time identity for evaluation purposes.

---

## What Changed

### 1. ContributionEvent Model (`core/models/contribution_event.py`)

**New Field: `contributor_fingerprint`**
- Type: `UUIDField` (non-nullable, immutable, indexed)
- Purpose: Preserves submission-time contributor identity for evaluation
- Constraint: Must be explicitly provided at creation (not auto-derived)
- Validation: Raises `ValidationError` if not provided

**Modified Field: `contributor`**
- Changed from: `on_delete=models.PROTECT, null=False`
- Changed to: `on_delete=models.SET_NULL, null=True, blank=True`
- Purpose: Allows de-identification without cascading deletes

**Updated `__str__`**
- Handles case where `contributor` is NULL after de-identification

### 2. Account Deletion Service (`accounts/services/account_deletion.py`)

**New Method: `_deidentify_contributions()`**
- Sets `contributor=NULL` on all ContributionEvents for the deleted user
- Preserves `contributor_fingerprint` for evaluation
- Called as Step 2 of the deletion flow (after token revocation)

**Updated Docstrings**
- Removed "Sprint-5B handles de-identification" note (now implemented)
- Added de-identification step to deletion flow documentation

### 3. Evaluation Logic (`transit/evaluation/stop_aggregation.py`)

**Changed Identity References (4 locations)**
- Line ~580: `user_id = event.contributor_fingerprint` (was `contributor_id`)
- Line ~603: `contributor_fingerprint` in confidence weighting
- Line ~644: `frozenset(e.contributor_fingerprint for e in ...)` for unique contributor set
- Line ~779: Same for duplicate detection

### 4. API Serializer (`api/serializers/contributions.py`)

**Updated `create()` Method**
- Explicitly sets `contributor_fingerprint=contributor.id` when creating events
- Ensures all API-submitted contributions have proper fingerprint

### 5. Migrations

**0003_contributionevent_contributor_fingerprint.py**
- Adds `contributor_fingerprint` field (nullable initially for safe rollout)

**0004_backfill_contributor_fingerprint.py**
- Backfills existing rows: `contributor_fingerprint = contributor_id`
- Enforces NOT NULL constraint after backfill

**0005_alter_contributionevent_contributor.py**
- Makes `contributor` FK nullable with `on_delete=SET_NULL`

---

## What Was Intentionally NOT Changed

### Evidence Payload
- `payload`, `subject_ref`, `observed_at`, `context` remain immutable
- No evidence content is modified during de-identification

### Belief/Canonical Entities
- Stop creation logic unchanged
- No recomputation triggered by account deletion
- Existing Stops remain stable

### Evaluation Thresholds
- Structural gates (MIN_INDEPENDENT_CONTRIBUTORS, etc.) unchanged
- Evidence diversity requirements unchanged
- Temporal separation requirements unchanged

---

## Impact Analysis

### On Evaluation & Stop Creation

**Before Sprint-5B:**
- Evaluation used `event.contributor_id` (FK to User)
- Account deletion could break evaluation (NULL FK)
- Independence counting would fail for deleted users

**After Sprint-5B:**
- Evaluation uses `event.contributor_fingerprint` (immutable UUID)
- Account deletion sets FK to NULL, fingerprint preserved
- Independence counting works identically before and after deletion

### On Data Rights Compliance

**Identity Removal:**
- `contributor` FK set to NULL on deletion
- No link between evidence and deleted user identity
- User cannot be identified from evidence records

**Evidence Preservation:**
- Evidence payload completely unchanged
- `contributor_fingerprint` is a UUID, not PII
- Evaluation semantics preserved

---

## Invariants Verified

### INV-E1: ContributionEvent Immutable After Creation ✅
- Only `contributor` FK is modified (set to NULL)
- `contributor_fingerprint` and all evidence fields remain unchanged

### INV-E2: Evidence Payload Replay-Stable ✅
- `payload`, `subject_ref`, `observed_at` never modified
- Tested in `EvidencePreservationTests`

### INV-I1: Independence Counted Correctly After Deletion ✅
- Uses `contributor_fingerprint` instead of `contributor_id`
- Multiple deleted users = multiple independent contributors
- Tested in `IndependentContributorCountTests`

### INV-I2: Deletion Does Not Change Contributor Counts ✅
- 3 contributors before deletion = 3 contributors after deletion
- Aggregation results identical pre/post deletion
- Tested in `EvaluationReplayDeterminismTests`

### INV-C1: Stop Creation Thresholds Unchanged ✅
- Same structural gates apply
- MIN_INDEPENDENT_CONTRIBUTORS still enforced
- Tested in `test_stop_creation_gate_unchanged_after_deletion`

### INV-C2: Structural Gates Correct ✅
- Independence gate uses fingerprint
- Diversity gates unchanged
- Tested via existing gate evaluator tests

### PH-1: Evidence is Permanent ✅
- No evidence rows deleted
- No payload modifications

### PH-2: Identity is Optional ✅
- User identity removable via deletion
- Evidence survives with fingerprint

### PH-3: Belief is Derived ✅
- Canonical entities unaffected by user lifecycle
- No belief recomputation on deletion

### PH-4: Replay Determinism ✅
- Evaluation before deletion = evaluation after deletion
- Tested in `test_aggregation_identical_before_and_after_deletion`

### PH-5: Independence is Event-Level ✅
- `contributor_fingerprint` captures submission-time identity
- Not dependent on live user records

---

## Tests Added

### New Test File: `core/tests/test_contributor_deidentification.py`

**ContributorFingerprintInvariantsTests (3 tests)**
- `test_contributor_fingerprint_equals_contributor_id_at_creation`
- `test_contributor_fingerprint_required_at_creation`
- `test_contributor_fingerprint_survives_contributor_nullification`

**IndependentContributorCountTests (2 tests)**
- `test_multiple_deleted_users_count_as_multiple_contributors`
- `test_single_deleted_user_contributions_not_collapsed`

**EvaluationReplayDeterminismTests (2 tests)**
- `test_aggregation_identical_before_and_after_deletion`
- `test_stop_creation_gate_unchanged_after_deletion`

**EvidencePreservationTests (1 test)**
- `test_evidence_payload_unchanged_after_deletion`

### Updated Tests
- All existing tests updated to explicitly provide `contributor_fingerprint`
- `test_account_deletion_service.py` updated for de-identification behavior
- Total: 295 tests passing

---

## Implementation Metadata

| Field | Value |
|-------|-------|
| LLM Used | Claude Opus 4.5 (via GitHub Copilot) |
| Implementation Date | 2025-12-30 |
| Sprint Duration | Single session |
| Lines Changed | ~300 (new) + ~150 (modified) |
| Test Count | 8 new + 287 existing = 295 total |

---

## Definition of Done Checklist

- [x] Identity is removable without breaking evaluation
- [x] Contributor independence remains correct after deletion
- [x] Canonical Stop logic is unaffected
- [x] All invariants listed in sprint prompt hold
- [x] Tests explicitly prove safety
- [x] Completion document created

---

## Files Changed

```
backend/
├── accounts/
│   └── services/
│       └── account_deletion.py  (added _deidentify_contributions method)
├── api/
│   └── serializers/
│       └── contributions.py  (added contributor_fingerprint to create)
├── core/
│   ├── models/
│   │   └── contribution_event.py  (added contributor_fingerprint, made contributor nullable)
│   ├── migrations/
│   │   ├── 0003_contributionevent_contributor_fingerprint.py  (new)
│   │   ├── 0004_backfill_contributor_fingerprint.py  (new)
│   │   └── 0005_alter_contributionevent_contributor.py  (new)
│   └── tests/
│       └── test_contributor_deidentification.py  (new - 8 tests)
└── transit/
    └── evaluation/
        └── stop_aggregation.py  (changed from contributor_id to contributor_fingerprint)
```
