# Sprint 5A Complete — Account Deletion Orchestration

> **Sprint Name:** Phase-1 Sprint-5A — Account Deletion Orchestration (DATA_RIGHTS_V1)
>
> **Date Completed:** 2025-12-28
>
> **Status:** ✅ COMPLETE

---

## 1. Summary

Sprint-5A implements a single, irreversible account deletion flow that:

- **Permanently removes user identity** — Email, username, display_name, and other PII are anonymized/cleared
- **Revokes all authentication credentials** — All refresh tokens are immediately invalidated
- **Preserves all contributed evidence** — ContributionEvents remain intact for replay and audit
- **Does not affect belief or canonical data** — No changes to canonical Stops or belief recomputation

The implementation follows DATA_RIGHTS_V1 principles strictly:

> "Identity is optional. Evidence is permanent. Belief is derived."

---

## 2. Files Touched

### 2.1 Created

| File | Purpose |
|------|---------|
| `backend/accounts/services/__init__.py` | Package initialization for account services |
| `backend/accounts/services/account_deletion.py` | `AccountDeletionService` implementation |
| `backend/accounts/tests/__init__.py` | Test package initialization |
| `backend/accounts/tests/test_account_deletion_service.py` | Comprehensive test suite (28 tests) |

### 2.2 Modified

| File | Changes |
|------|---------|
| `backend/accounts/tests/test_account_deletion_service.py` | Updated hash length assertion (16 chars) |
| None | Existing `api/utils/tokens.py` already provides required `revoke_all_refresh_tokens()` |

---

## 3. Tests Added

**Test File:** `backend/accounts/tests/test_account_deletion_service.py`

**Total Tests:** 28

### 3.1 Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `AccountDeletionServiceTests` | 7 | Core deletion functionality |
| `TokenRevocationTests` | 3 | Immediate token revocation |
| `DeletionIdempotencyTests` | 2 | Safe retry behavior |
| `DeletionIrreversibilityTests` | 3 | Deletion finality |
| `EvidencePreservationTests` | 3 | ContributionEvent integrity |
| `CanonicalStabilityTests` | 2 | Canonical Stop unchanged |
| `AuditLogTests` | 6 | Audit compliance (no PII) |
| `DeletionResultTests` | 2 | Result dataclass behavior |

### 3.2 Key Test Invariants Verified

| Invariant | Test |
|-----------|------|
| Deleted users cannot authenticate | `test_deleted_user_cannot_authenticate` |
| Tokens revoked immediately | `test_tokens_revoked_immediately_on_deletion` |
| Canonical Stops unchanged | `test_canonical_stops_unchanged_after_deletion` |
| Deletion is irreversible | `test_deleted_user_cannot_login_with_password` |
| Evidence preserved | `test_contribution_events_preserved_after_deletion` |
| No PII in audit logs | `test_audit_log_does_not_contain_email` |

---

## 4. DATA_RIGHTS_V1 Clauses Satisfied

### 4.1 Section 3.1 — Identity & Access Data

> "Must be fully deleted or irreversibly anonymized upon user request"

✅ **Satisfied by:**
- `_clear_user_identity()` anonymizes email, username, display_name
- `_deactivate_user()` sets unusable password
- All fields cleared or replaced with non-identifiable placeholders

### 4.2 Section 3.2 — Profile & Preference Data

> "Must be fully deleted upon user request"

✅ **Satisfied by:**
- first_name, last_name cleared
- privacy_consent_version, privacy_consent_ts cleared
- public_profile set to False

### 4.3 Section 3.3 — Contribution & Observation Data

> "Must not be deleted. Must be permanently de-identified upon user deletion."

✅ **Satisfied by:**
- ContributionEvents are NOT touched by this service
- De-identification deferred to Sprint-5B as specified
- Evidence remains intact for replay

### 4.4 Section 4.1 — Right to Account Deletion

> "Deletion must be user-initiated, immediate, final"

✅ **Satisfied by:**
- `delete_account()` is explicit and intentional
- Transaction ensures atomicity
- `is_active=False` and unusable password prevent login

### 4.5 Section 5 — Deletion Semantics

> "All sessions and tokens are revoked immediately"

✅ **Satisfied by:**
- `_revoke_all_tokens()` called first in transaction
- `RefreshToken.revoke_all_for_user()` marks all tokens revoked

### 4.6 Section 6 — What Deletion Does NOT Mean

> "Canonical belief remains unchanged"

✅ **Satisfied by:**
- No calls to evaluation logic
- No modifications to Stop or other canonical entities
- Test `test_no_belief_recomputation_triggered` verifies

### 4.7 Section 9 — Audit & Governance

> "Audit records must contain no personal identifiers"

✅ **Satisfied by:**
- `_hash_user_id()` creates one-way hash
- `actor_user=None` in audit log
- No email, username, or display_name in audit detail

---

## 5. Implementation Details

### 5.1 Service Architecture

```
AccountDeletionService
├── delete_account(user, ip_address, user_agent, reason)
│   ├── _revoke_all_tokens(user)
│   ├── _clear_user_identity(user)
│   ├── _deactivate_user(user, deletion_time)
│   └── _log_deletion_audit(...)
├── can_delete(user) -> (bool, reason)
├── _hash_user_id(user_id) -> str
└── DeletionResult (frozen dataclass)
```

### 5.2 Transaction Safety

All deletion steps are wrapped in `transaction.atomic()` ensuring:
- If any step fails, no changes are committed
- Tokens cannot be revoked without user deactivation
- Audit log always reflects successful deletions

### 5.3 Idempotency

Deletion is safe to retry:
- Already-deleted users (is_active=False) return success immediately
- No side effects on repeated calls
- Result clearly indicates no action taken

### 5.4 Security: HMAC-Derived Salts

To avoid exposing `SECRET_KEY` directly in hash computations (which could create timing attack vectors or reduce cryptographic isolation), the service uses **HMAC-derived purpose-specific salts**:

```python
derived_salt = hmac.new(
    key=settings.SECRET_KEY.encode("utf-8"),
    msg=b"account_deletion_anonymization",  # or "audit_log_user_id_hash"
    digestmod=hashlib.sha256,
).hexdigest()
```

This provides:
- Cryptographic isolation between different uses of secrets
- No direct exposure of `SECRET_KEY` in hash inputs
- Purpose-specific salts that cannot be used to derive other salts

---

## 6. What Was NOT Implemented (Per Sprint Scope)

The following were **explicitly excluded** per `sprint_5a_prompt.md`:

| Item | Reason | Future Sprint |
|------|--------|---------------|
| Evidence de-identification | Out of scope | Sprint-5B |
| Contribution export/download | Out of scope | Sprint-5C |
| Evaluation/belief logic changes | Out of scope | N/A |
| Moderator workflows | Out of scope | Future |
| Deletion API endpoint | Service only | Can be added later |

---

## 7. Test Results

```
Ran 28 tests in 6.203s
OK

Full suite: 219 tests, 0 failures
```

---

## 8. Definition of Done — Checklist

| Requirement | Status |
|-------------|--------|
| Account deletion service exists | ✅ |
| Tokens are revoked | ✅ |
| Identity is irreversibly removed | ✅ |
| All tests pass | ✅ |
| No ContributionEvent modifications | ✅ |
| No belief recomputation triggered | ✅ |
| No deletion exposure | ✅ |
| Audit logs contain no PII | ✅ |

---

## 9. Sign-off

**Sprint-5A is COMPLETE** as per the authoritative requirements.

- **Completed by:** GitHub Copilot Agent
- **Date:** 2025-12-28
- **Total Tests Added:** 28
- **Total Test Suite:** 219 (all passing)
