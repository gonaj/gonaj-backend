# Sprint-3 Implementation Complete

## Overview

Sprint-3 has been successfully completed according to the specifications in [SPRINT_3_COPILOT_AGENT_PROMPT.md](SPRINT_3_COPILOT_AGENT_PROMPT.md). All objectives have been met: canonical entity skeletons are defined with required metadata fields, guardrails prevent direct edits, and no evaluation logic exists.

---

## Deliverables

### Objective A: Canonical Entity Definitions (Skeleton Only)

Created the five Phase-1 canonical transit entities as skeleton models:

1. **Stop** - Transit stop location with name, geographic point, alternate names
2. **Route** - Logical transit route with name, short name, route type, operator
3. **RouteVariant** - Directional/variant route path with geometry, headsign, direction
4. **StopRouteLink** - Stop-route association with sequence position
5. **ObservedServiceWindow** - Observed service time patterns with day/time windows

No additional canonical entities were created. No evaluation logic exists.

### Objective B: Required Canonical Metadata

All canonical entities inherit from `CanonicalModel` base class which provides:

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID (PK) | Internal unique identifier |
| `public_id` | CharField (unique) | Stable external identifier |
| `version` | PositiveIntegerField | Version number for the entity |
| `valid_from` | DateTimeField | When this version became valid |
| `valid_until` | DateTimeField (nullable) | When superseded (NULL = current) |
| `structural_confidence` | DecimalField | Long-term stability confidence (0-1) |
| `freshness_confidence` | DecimalField | Recency-based confidence (0-1) |
| `ruleset_version` | CharField | Evaluation rules version identifier |
| `evidence_refs` | JSONField | Array of ContributionEvent IDs |
| `created_at` | DateTimeField | Record creation timestamp |
| `updated_at` | DateTimeField | Last update timestamp |

These fields exist for future sprints - they have no behavior in Sprint-3.

### Objective C: Guardrails on Canonical Models

Implemented write protection on all canonical models:

- `save()` raises `NotImplementedError` by default
- `delete()` raises `NotImplementedError` always
- `_internal_save()` provided for controlled writes by evaluation logic
- Clear docstrings document that entities represent "current belief" and are "derived, not edited"

---

## Canonical Entities Summary

### Stop

Location where transit vehicles stop to pick up/drop off passengers.

**Domain Fields:**
- `name` - Primary name of the stop
- `location` - Geographic point (PostGIS PointField)
- `alternate_names` - JSON array of alternate names observed
- `properties` - Flexible JSON for additional attributes

### Route

Logical transit route (e.g., "Bus 42", "Red Line").

**Domain Fields:**
- `name` - Full name of the route
- `short_name` - Short identifier (e.g., "42", "A")
- `route_type` - Type of service (bus, tram, metro, etc.)
- `operator` - Transit operator/agency
- `properties` - Flexible JSON for additional attributes

### RouteVariant

Directional or variant path of a Route.

**Domain Fields:**
- `route` - Foreign key to parent Route
- `name` - Descriptive name for the variant
- `direction` - Direction identifier (inbound, outbound, etc.)
- `geometry` - LineString of the route path (PostGIS)
- `headsign` - Destination sign text
- `properties` - Flexible JSON for additional attributes

### StopRouteLink

Association between Stop and RouteVariant with sequence.

**Domain Fields:**
- `stop` - Foreign key to Stop
- `route_variant` - Foreign key to RouteVariant
- `sequence` - Position in stop sequence (1, 2, 3...)
- `properties` - Flexible JSON for additional attributes

### ObservedServiceWindow

Observed service time patterns (approximations, not schedules).

**Domain Fields:**
- `route_variant` - Foreign key to RouteVariant
- `stop` - Optional foreign key to Stop
- `day_of_week` - JSON array of days
- `first_observed_time` - Earliest service time observed
- `last_observed_time` - Latest service time observed
- `typical_frequency_minutes` - Approximate frequency
- `observation_count` - Number of supporting observations
- `properties` - Flexible JSON for additional attributes

---

## Tests

### Test Coverage

Created [backend/transit/tests/test_canonical_models.py](../../backend/transit/tests/test_canonical_models.py) with 46 structural tests:

**CanonicalModelBaseTests (2):**
- CanonicalModel is abstract
- Required metadata fields exist

**StopModelStructureTests (6):**
- Model imports correctly
- Domain fields exist
- Inherits CanonicalModel
- Direct save prevented
- Internal save works
- Delete prevented

**RouteModelStructureTests (5):**
- Model imports correctly
- Domain fields exist
- Inherits CanonicalModel
- Route type choices exist
- Direct save prevented
- Internal save works

**RouteVariantModelStructureTests (6):**
- Model imports correctly
- Domain fields exist
- Inherits CanonicalModel
- Direction choices exist
- Route foreign key exists
- Direct save prevented

**StopRouteLinkModelStructureTests (6):**
- Model imports correctly
- Domain fields exist
- Inherits CanonicalModel
- Stop foreign key exists
- RouteVariant foreign key exists
- Direct save prevented

**ObservedServiceWindowModelStructureTests (6):**
- Model imports correctly
- Domain fields exist
- Inherits CanonicalModel
- RouteVariant foreign key exists
- Optional stop foreign key exists
- Direct save prevented

**MigrationIntegrityTests (1):**
- All canonical tables exist in database

**NoEvaluationLogicTests (3):**
- Stop has no evaluation methods
- Route has no evaluation methods
- CanonicalModel has no evaluation logic

**CanonicalMetadataFieldTests (6):**
- public_id is unique
- Confidence fields accept decimals
- evidence_refs accepts list
- valid_from defaults to now
- valid_until is nullable
- version defaults to 1

**RelationshipTests (4):**
- RouteVariant belongs to Route
- StopRouteLink connects Stop and Variant
- ObservedServiceWindow belongs to Variant
- ObservedServiceWindow stop is optional

**Total: 46 Sprint-3 tests**
**Combined: 151 total tests pass** (Sprint-1 + Sprint-2 + Sprint-3)

---

## Files Created/Modified

### Created:

1. `/app/backend/transit/models/base.py` - CanonicalModel base class
2. `/app/backend/transit/models/stop.py` - Stop canonical entity
3. `/app/backend/transit/models/route.py` - Route canonical entity
4. `/app/backend/transit/models/route_variant.py` - RouteVariant canonical entity
5. `/app/backend/transit/models/stop_route_link.py` - StopRouteLink canonical entity
6. `/app/backend/transit/models/observed_service_window.py` - ObservedServiceWindow canonical entity
7. `/app/backend/transit/models/__init__.py` - Model exports
8. `/app/backend/transit/apps.py` - Transit app configuration
9. `/app/backend/transit/__init__.py` - Transit app package
10. `/app/backend/transit/migrations/0001_initial.py` - Migration for all canonical models
11. `/app/backend/transit/tests/__init__.py` - Tests package
12. `/app/backend/transit/tests/test_canonical_models.py` - Structural tests
13. `/app/docs/phase-1_sprints/PHASE_1_SPRINT_3_COMPLETE.md` - This document

### Modified:

1. `/app/backend/backend/settings.py` - Added `transit` to INSTALLED_APPS

---

## Architectural Invariants Respected

From BACKEND_PHILOSOPHY.md:

1. **Canonical data is derived, not edited**
   - `save()` raises NotImplementedError by default
   - Only `_internal_save()` allows writes (for evaluation logic)
   - Clear docstrings document derived nature

2. **Nothing is ever deleted**
   - `delete()` raises NotImplementedError
   - Entities use `valid_until` for versioning instead

3. **All decisions are reversible**
   - `evidence_refs` tracks source ContributionEvents
   - `ruleset_version` enables recomputation

4. **Truth is versioned and temporal**
   - `version` field tracks entity versions
   - `valid_from` / `valid_until` provide temporal validity

5. **Canonical storage exists for efficiency, not authority**
   - Docstrings clearly state entities are materialized belief
   - Authority remains with ContributionEvent records

---

## No Evaluation Logic Confirmation

Sprint-3 contains STRUCTURE ONLY. The following do NOT exist:

- No `evaluate()` methods
- No `promote()` methods
- No `decay()` methods
- No `aggregate()` methods
- No `derive_from_events()` methods
- No `calculate_confidence()` methods
- No `process_contribution()` methods

Tests explicitly verify the absence of these methods.

---

## Sprint-1 and Sprint-2 Code Unchanged

Verified that no Sprint-1 or Sprint-2 code was modified:

- `/app/backend/core/models/base.py` - Untouched
- `/app/backend/core/models/contribution_event.py` - Untouched
- `/app/backend/api/serializers/contributions.py` - Untouched
- `/app/backend/api/views/contributions.py` - Untouched
- `/app/backend/api/urls.py` - Untouched

All 105 Sprint-1 + Sprint-2 tests continue to pass.

---

## Validation Commands

To verify the implementation:

```bash
# Run Sprint-3 tests only
cd /app/backend && python manage.py test transit.tests -v 2

# Run all tests (Sprint-1 + Sprint-2 + Sprint-3)
cd /app/backend && python manage.py test api.tests core.tests transit.tests -v 1

# Check Django system
cd /app/backend && python manage.py check

# Verify migrations
cd /app/backend && python manage.py showmigrations transit
```

---

## Definition of Done

Sprint-3 is complete because:

- [x] All five required canonical entities exist as skeletons
- [x] Required metadata fields present on all entities
- [x] No evaluation, decay, or moderation logic exists
- [x] No APIs were added or modified
- [x] All 151 tests pass (46 Sprint-3 + 105 prior)
- [x] Sprint-1 code remains untouched
- [x] Sprint-2 code remains untouched
- [x] System checks pass with no issues
- [x] Migrations apply cleanly
- [x] Guardrails prevent direct saves/deletes

---

## Implementation Metadata

**LLM / Coding Assistant Used:**
- GitHub Copilot Agent (Claude Opus 4.5)
- VS Code integrated agent interface

**IDE / Tooling Context:**
- VS Code editor
- Python 3.14
- Django 5.1.4
- Django REST Framework 3.15.2
- PostGIS (GeoDjango)
- Dev container environment (Debian GNU/Linux 12)

**Human vs AI Contribution Split:**
- AI: Generated all code, tests, and documentation based on sprint requirements
- Human: Provided requirements document, reviewed implementation, approved completion
- Collaboration: Requirements-driven implementation following SPRINT_3_COPILOT_AGENT_PROMPT.md

**Date Range of Implementation:**
- December 23, 2025 (single-day sprint completion)

**Development Approach:**
- Structure-first: Models defined as skeletons with metadata
- Test-driven: 46 tests verify structure and guardrails
- Conservative: No logic, no APIs, no Sprint-1/Sprint-2 changes
- Disciplined: Strict adherence to sprint scope

---

## Next Steps (NOT for Sprint-3)

Sprint-4 and beyond should implement:
1. Minimal evaluation pipeline (evidence to canonical truth)
2. Confidence and decay logic
3. Moderation as evidence
4. Canonical recomputation safety
5. Read APIs for canonical data
6. Audit and explainability

**Do NOT implement these yet.** Sprint-3 is strictly limited to:
- Canonical entity skeletons
- Required metadata fields
- Write protection guardrails
- Structural tests

---

## Conclusion

Sprint-3 successfully establishes the canonical entity layer for Phase-1:

- **Five entities**: Stop, Route, RouteVariant, StopRouteLink, ObservedServiceWindow
- **Full metadata**: All required fields for replay, audit, and evolution
- **Protected writes**: Guardrails enforce derived-only pattern
- **No logic**: Pure structure, ready for evaluation in Sprint-4+
- **Disciplined**: No scope creep, strict adherence to plan

The backend now has the structural foundation for canonical transit knowledge.

---

**Sprint-3 Status: COMPLETE**
**Date: December 23, 2025**
**Tests: 151/151 passing**
**Phase-1 Invariants: All respected**
**No Sprint-1 or Sprint-2 code modified**
**No evaluation logic present**
