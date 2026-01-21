# Phase-2 Sprint-3 — UI Mode-Aware Response Shaping

**Status**: Complete  
**Date**: 2026-01-20  
**Branch**: `dev_phase_2`

---

## Critical Context

This sprint implements UI mode-aware response filtering to control **visibility only**, never truth or evaluation.

UI modes are presentation-layer filters applied AFTER data retrieval. They are non-destructive, reversible, and presentation-only.

---

## What This Sprint Delivers

### 1. UI Mode Concept

**File**: `backend/api/visibility.py`

Introduced three explicit UI modes:
- `read`: Canonical-safe fields only (default)
- `contributor`: Canonical fields + limited candidate metadata
- `admin`: Canonical fields + candidate metadata + diagnostics

**Mode Parsing**:
- UI mode can be provided via query parameter: `?ui_mode=contributor`
- Or via HTTP header: `X-UI-Mode: contributor`
- Invalid or missing modes default to `read` for safety
- Mode is validated against allowed values
- Mode is NEVER stored in database or persisted

---

### 2. Visibility Field Rules

**Centralized in**: `backend/api/visibility.py`

**Canonical-Safe Fields** (visible in all modes):
- name, location, geometry, coordinates, description
- type, route_type, belief_state

**Contributor-Visible Fields** (contributor + admin modes):
- candidate_status (categorical)
- last_observed_date (coarse-grained date only)
- observation_count_category (categorical: "few", "some", "many")

**Admin-Visible Fields** (admin mode only):
- confidence_score, evidence_count, evaluation_version
- created_at, updated_at, diagnostic, internal_id

**Always-Blocked Fields** (never visible in any mode):
- contributor, contributor_id, contributor_fingerprint
- device_id, user, user_id, client_generated_id

**Threshold-Related Fields** (blocked in contributor mode):
- confidence, confidence_score, quality_score, reliability
- threshold_distance, promotion_likelihood
- required_count, current_count, votes, agreement_percentage

---

### 3. Response Filtering Implementation

**Functions**:
- `parse_ui_mode(request)`: Parses and validates UI mode from request
- `get_visible_fields(mode)`: Returns frozenset of visible fields for mode
- `apply_visibility(data, mode)`: Filters response data based on mode
- `validate_contributor_mode_safety(data)`: Validates contributor threshold secrecy

**Key Properties**:
- Filtering happens AFTER data retrieval
- Creates deep copy to avoid mutating source data
- Supports single objects and lists
- Recursively filters nested objects
- Does NOT affect canonical export serialization

---

### 4. Tests

**File**: `backend/api/tests/test_ui_mode_response_shaping.py`

**38 tests across 8 test classes**:

1. **UIModeParsingTests** (7 tests)
   - Query parameter and header parsing
   - Precedence, validation, defaults
   - Case-insensitive and whitespace handling

2. **VisibilityRulesTests** (5 tests)
   - Field visibility per mode
   - Hierarchical mode structure
   - Always-blocked field enforcement

3. **VisibilityFilteringTests** (7 tests)
   - Filtering for each mode
   - List and nested object handling
   - Non-mutation guarantee

4. **VisibilityOnlyInvariantTests** (3 tests)
   - Same data, different modes
   - Reversibility
   - Idempotency

5. **DefaultSafetyTests** (3 tests)
   - Invalid mode handling
   - None and empty string modes

6. **ContributorThresholdSecrecyTests** (5 tests)
   - Confidence score blocking
   - Numeric threshold blocking
   - Validation enforcement
   - Categorical-only metadata

7. **TruthInvarianceTests** (2 tests)
   - Data structure preservation
   - Data value preservation

8. **NonCanonicalSafetyTests** (3 tests)
   - No field creation
   - No semantic transformation
   - Always-blocked enforcement

9. **IntegrationTests** (4 tests)
   - End-to-end mode parsing and filtering
   - Read, contributor, admin workflows
   - Invalid mode defaults

**All 38 tests pass.**

---

## Invariants Preserved

### P2-INV-1: Backend Truth Authority
UI mode does NOT influence:
- Evidence ingestion
- Evaluation logic
- Belief accumulation
- Canonical state
- Thresholds
- Confidence calculations

**Verified by**: TruthInvarianceTests

---

### P2-INV-2: Visibility-Only UI Modes
UI modes affect presentation only:
- Only field visibility changes
- Same underlying data across all modes
- Filtering is reversible
- Filtering is non-destructive

**Verified by**: VisibilityOnlyInvariantTests

---

### P2-INV-3: Canonical Read Safety
No leakage of:
- Evidence metadata
- Contributor identity
- Evaluation diagnostics (in read/contributor modes)

**Verified by**: Always-blocked fields enforcement, ContributorThresholdSecrecyTests

---

### P2-INV-6: Deterministic Evaluation
Mode changes do NOT affect:
- Replay safety
- Evaluation determinism
- Data values

**Verified by**: TruthInvarianceTests

---

### P2-INV-9: No Silent Scope Expansion
No new capabilities added:
- No canonical endpoints created
- No models modified
- No migrations added
- No evaluation logic touched

**Verified by**: File modification audit

---

## Files Created

- `backend/api/visibility.py` - UI mode visibility filtering module
- `backend/api/tests/test_ui_mode_response_shaping.py` - 38 comprehensive tests

---

## Files NOT Modified

Explicitly verified that NO changes were made to:
- `backend/transit/evaluation/*` - Evaluation logic untouched
- `backend/core/models/*` - Models untouched
- Any migrations - No database changes
- Contribution creation logic - Evidence ingestion untouched
- Stop or Route evaluators - Aggregation logic untouched

---

## Test Results

```bash
docker compose exec web uv run python backend/manage.py test \
  api.tests.test_ui_mode_response_shaping --verbosity=2
```

**Result**: All 38 tests pass in 0.066s

---

## Key Design Decisions

### 1. Mode Provided via Query Param or Header
Allows clients to specify mode flexibly without requiring authentication changes.

### 2. Default to Read Mode
Safety-first: invalid or missing modes default to most restrictive visibility.

### 3. Hierarchical Field Visibility
Each mode is a superset of the previous:
- `read` ⊂ `contributor` ⊂ `admin`

### 4. Contributor Threshold Secrecy
New invariant: Contributor mode exposes categorical metadata only, never numeric values that reveal proximity to thresholds.

### 5. Deep Copy Filtering
Ensures source data immutability and reversibility.

---

## Usage Example

```python
from api.visibility import parse_ui_mode, apply_visibility

# In a view
mode = parse_ui_mode(request)
response_data = {
    "name": "Main St Stop",
    "location": {"lat": 40.0, "lon": -74.0},
    "confidence_score": 0.95,
    "contributor": "user123",
}

filtered_data = apply_visibility(response_data, mode)

# In read mode:
# {"name": "Main St Stop", "location": {"lat": 40.0, "lon": -74.0}}

# In admin mode:
# {"name": "Main St Stop", "location": {"lat": 40.0, "lon": -74.0}, "confidence_score": 0.95}
# (contributor always blocked)
```

---

## What This Does NOT Do

This sprint explicitly does NOT:

- Add any canonical read endpoints
- Expose any transit data publicly
- Modify evaluation or belief logic
- Change models or create migrations
- Affect write or contribution APIs
- Make assumptions about future query patterns

---

## Future Usage

When implementing canonical read endpoints in future sprints, views can use:

```python
from api.visibility import parse_ui_mode, apply_visibility

class SomeReadView(APIView):
    def get(self, request):
        # Get raw data
        data = get_canonical_data()
        
        # Parse UI mode
        mode = parse_ui_mode(request)
        
        # Apply visibility filtering
        filtered_data = apply_visibility(data, mode)
        
        return Response(filtered_data)
```

---

## Rationale

### Why UI Modes Before Endpoints?

1. **Guardrails First**: Establish filtering patterns before exposing data
2. **Clear Contract**: Future endpoints know exactly what filtering to apply
3. **Testable Now**: Validate visibility rules work before implementing real endpoints
4. **Defense-in-Depth**: Multiple layers of protection (permission + serializer + visibility)
5. **Evidence-Driven Architecture**: Presentation must never reveal derivation

### Why Categorical Metadata for Contributors?

Contributors should see progress signals without revealing game-able thresholds. Categorical values like "under_review", "many observations" provide feedback without enabling threshold manipulation.

---

## Definition of Done Checklist

- [x] UI mode exists and is validated
- [x] Responses differ by mode without affecting truth
- [x] No canonical or evaluation logic modified
- [x] Tests clearly prove visibility-only behavior
- [x] Code is minimal, explicit, and well-documented
- [x] No emojis or special characters in code, comments, or strings
- [x] All Phase-2 invariants preserved
- [x] No forbidden files modified
- [x] 38 tests pass

---

## Philosophy Statement

> UI modes control **what is shown**, never **what is true**.

This sprint successfully establishes a presentation-layer filtering system that:
- Preserves backend truth authority
- Enables flexible client visibility
- Maintains replay safety
- Prevents threshold gaming
- Remains easily auditable

The system is now ready for future canonical read endpoint implementations with built-in, testable visibility controls.
