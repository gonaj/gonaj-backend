# Phase-2 Sprint-8 Execution History: Contribution Abuse Signal Collection

## Summary

Implemented observational-only abuse signal collection for contribution submissions.

## Changes Made

### New Files
- `backend/api/abuse_signals.py` - `AbuseSignalCollector` class with velocity, repetition, and fingerprint correlation signals
- `backend/api/tests/test_abuse_signals.py` - 10 tests covering safe failure, cache increments, and non-interference

### Modified Files
- `backend/api/views/contributions.py` - Integrated `record_contribution_signals` call after event creation

## Invariants Preserved

- No canonical truth affected
- No evaluation logic modified
- No blocking or enforcement behavior
- No new identifiers created
- All cache failures silently tolerated
- Existing fingerprints only (no new device identifiers)

## Testing Results

```
Ran 10 tests (abuse signals) - OK
Ran 18 tests (contribution API) - OK
```

## Constraints Verified

- Uses `django.core.cache` (LocMemCache sufficient)
- All cache operations wrapped in try/except
- Logs at INFO level only, structured, no PII
- Fingerprint velocity tracked separately from user velocity
