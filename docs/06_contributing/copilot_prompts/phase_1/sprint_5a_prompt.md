# GitHub Copilot Agent Prompt — Phase-1 / Sprint-5A

> **Sprint Name:** Phase-1 Sprint-5A — Account Deletion Orchestration (DATA_RIGHTS_V1)
>
> **Project:** Gonaj Backend (Django)
>
> **Scope:** Irreversible user account deletion, token revocation, and deletion orchestration

This prompt must be provided **as-is** to the GitHub Copilot Agent.

---

## 📚 Authoritative References (Must Be Loaded)

* `docs/01_architecture/backend_philosophy.md`
* `docs/01_architecture/data_rights_v1.md`
* `docs/02_phase_1/phase_1_backend_plan.md`
* `docs/02_phase_1/rules_v0.md`
* `docs/02_phase_1/test_invariants_v0.md`
* `docs/02_phase_1/phase_1_data_rights_checklist.md`

If any conflict exists, **DATA_RIGHTS_V1 and Phase-1 rules override all other considerations**.

---

## 🎯 Sprint-5A Objectives

Implement a **single, irreversible account deletion flow** that:

* Permanently removes user identity
* Revokes all authentication credentials
* Preserves all contributed evidence
* Does not affect belief or canonical data

---

## 🚫 Out of Scope (Explicit)

The following are **explicitly out of scope for Sprint-5A** and must NOT be implemented or partially addressed:

* ❌ Evidence de-identification (handled in Sprint-5B)
* ❌ Contribution export / download APIs (handled in Sprint-5C)
* ❌ Any modification to evaluation, aggregation, or belief logic
* ❌ Moderator workflows or admin tooling related to deletion

If any of the above are implemented, Sprint-5A is considered failed.

---

## 🚫 Absolute Prohibitions

You must NOT:

* ❌ Delete or modify `ContributionEvent`
* ❌ Trigger belief recomputation
* ❌ Expose deletion events publicly
* ❌ Allow deletion reversal
* ❌ Store personal identifiers in audit logs

Any violation fails the sprint.

---

## 📁 Files & Structure (Strict)

You may create:

```
backend/accounts/services/account_deletion.py
```

You may modify (minimally):

* `backend/accounts/models.py`
* `backend/api/utils/tokens.py`

Do NOT move files or create new apps.

---

## 🧠 Required Deletion Semantics

Deletion must:

1. Be **explicit** and intentional
2. Be **idempotent** (safe on retry)
3. Be **transactional where possible**
4. Revoke all active sessions and refresh tokens
5. Leave evidence and belief intact

---

## 🧪 Tests to Implement

Add tests under:

```
backend/accounts/tests/test_account_deletion_service.py
```

Tests must verify:

* Deleted users cannot authenticate
* Tokens are revoked immediately
* Canonical Stops remain unchanged
* Deletion is irreversible

---

## 🛑 Definition of Done

Sprint-5A is complete only when:

* Account deletion service exists
* Tokens are revoked
* Identity is irreversibly removed
* All tests pass

---

## 📎 Completion Document

Create:

```
docs/05_execution_history/phase_1/sprint_5a_complete.md
```

Include:

* Summary
* Files touched
* Tests added
* DATA_RIGHTS_V1 clauses satisfied
* Implementation metadata
