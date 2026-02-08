# Sprint‑12 — Performance & Recompute Control

## Audience
This prompt is written for a **coding agent** with no prior context beyond this document and the repository.

You **must** treat this document as authoritative for Sprint‑12.

---

## Sprint Context (Authoritative)

Project: **Gonaj Backend**  
Phase: **Phase‑2**  
Sprint: **Sprint‑12 — Performance & Recompute Control**

### Sprint Goal
Make evaluation scalable **without race conditions**, **without semantic drift**, and **without modifying evaluation rules or canonical semantics**.

This sprint is about **execution mechanics**, not meaning.

---

## Non‑Negotiable Constraints

You MUST NOT:
- Change evaluation rules or thresholds
- Change canonical schemas or belief semantics
- Introduce new canonical states
- Add new public APIs
- Add UI‑driven behavior
- Block or reject evidence ingestion

You MAY:
- Add internal orchestration code
- Add background‑safe execution abstractions
- Add locking around evaluation execution
- Add admin‑only operational tooling

Completed Phase‑2 sprints are **frozen**. Consume them, do not reinterpret them.

---

## Core Architectural Principles (Must Hold)

- Canonical truth is evaluator‑owned only
- Evidence is immutable and append‑only
- Evaluation is deterministic and replay‑safe
- Visibility ≠ evaluation ≠ authorization
- No partial canonical states
- Read paths must never mutate state

---

## What Sprint‑12 Must Introduce

Sprint‑12 introduces **explicit orchestration for evaluation execution**.

This includes:
1. A formal **evaluation job abstraction**
2. A **pluggable executor** (minimal executor required)
3. **Scoped advisory locking** to prevent race conditions
4. **Explicit recompute orchestration** (Stops, Routes, or All)
5. **Failure‑safe execution** (no partial writes)

Sprint‑12 does **not** introduce distributed workflow engines or heavy schedulers.

---

## 1. Evaluation Job Abstraction (NEW)

Create an internal representation of an evaluation job.

### Requirements
- Immutable once created
- Purely descriptive (no logic)
- Deterministic inputs

### Required Fields (Conceptual)
- job_id (UUID)
- target_type: `stop` | `route`
- target_ids: list of UUIDs OR `None` (means full scope for that type)
- trigger: `contribution` | `admin` | `replay`
- ruleset_version (string)
- created_at (timestamp)

This abstraction MUST NOT contain evaluation logic.

---

## 2. Executor Abstraction (Pluggable)

Define an **executor interface** responsible for running evaluation jobs.

### Requirements
- Executor API must be stable
- Execution semantics must be deterministic
- Executor must enforce locking and atomicity

### Minimal Executor (Required for Sprint‑12)

Implement a **minimal inline executor** that:
- Executes jobs immediately (in‑process)
- Acquires scoped advisory locks
- Runs evaluation inside a database transaction

This executor exists to prove correctness, not scale.

DO NOT introduce Celery, Redis, or worker pools in this sprint.

---

## 3. Scoped Advisory Locking (MANDATORY)

Use **PostgreSQL advisory locks** to prevent concurrent evaluation of the same canonical entity.

### Locking Rules

- Locks are **entity‑scoped**, not table‑scoped
- Lock keys MUST be deterministic and namespaced

Examples:
- `stop:<stop_id>`
- `route:<route_id>`

### Properties
- Lock is held only during evaluation execution
- Lock auto‑releases on crash or connection drop
- No lock table is allowed

### Forbidden
- Table‑level locks
- Global recompute locks
- Blocking evidence writes

---

## 4. Automatic Evaluation on New Evidence

When a new `ContributionEvent` is created:

1. Evidence is written immediately
2. An evaluation job is created for affected entity scope
3. Job is enqueued via executor

### Critical Rules
- Evidence ingestion MUST NOT block on evaluation
- Evaluation MUST NOT run inside request threads
- Multiple evidence events may enqueue multiple jobs
- Redundant jobs are acceptable; race conditions are not

---

## 5. Recompute Orchestration (Admin‑Only)

Sprint‑12 must support **explicit recompute requests**.

### Entry Point

- **Management command only** (no API)

### Required Command Semantics

The recompute command MUST require an explicit target:

- `stops`
- `routes`
- `all`

No default target is allowed.

Examples (conceptual):

```
python manage.py recompute stops
python manage.py recompute routes
python manage.py recompute all
```

---

## 6. Dependency Ordering (MANDATORY)

Canonical dependency rules:

- Stops do NOT depend on Routes
- Routes MAY read Stop canonical state
- Routes MUST NOT evaluate against partially recomputed Stops

### Enforcement

If target = `all`:

1. Enqueue Stop recompute jobs
2. Wait until Stop jobs complete
3. Enqueue Route recompute jobs

This ordering is orchestration logic.

Evaluation logic must remain untouched.

---

## 7. Failure Safety

Evaluation execution MUST be:

- Atomic
- Idempotent
- Replay‑safe

### Required Guarantees

- If evaluation fails, canonical state MUST remain unchanged
- Partial writes are forbidden
- Retry must produce identical results

Use `transaction.atomic()` around canonical writes.

---

## 8. What Must NOT Be Added

Explicitly forbidden in Sprint‑12:

- Public recompute APIs
- UI triggers
- Job dashboards
- Lock tables
- Background schedulers
- Any semantic change to evaluation

---

## 9. Expected Code Shape (Guidance Only)

Likely areas to modify or add:

- `transit/evaluation/jobs.py`
- `transit/evaluation/executor.py`
- `transit/evaluation/orchestration.py`
- `transit/management/commands/recompute.py`

This is guidance, not a mandate. Follow architectural intent.

---

## 10. Acceptance Criteria

Sprint‑12 is complete only if:

- Evaluation jobs exist as first‑class abstractions
- Scoped advisory locks prevent concurrent mutation of same entity
- Evidence ingestion is never blocked
- Recompute supports `stops`, `routes`, and `all` explicitly
- `all` enforces Stops → Routes ordering
- Failures leave canonical state unchanged
- No evaluation semantics are modified

---

## 11. Review Checklist (Self‑Audit)

Before marking work complete, verify:

- No table locks exist
- No new canonical fields were added
- No evaluation logic was touched
- No implicit recompute behavior exists
- All recompute actions are explicit and intentional

---

## Final Rule

If any change weakens determinism, replay safety, or trust boundaries, it is **incorrect**, even if tests pass.

Sprint‑12 exists to make execution safe — not clever.

