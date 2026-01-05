# Backend Vision & Philosophy

## 1. Purpose of the Backend

This backend exists to **transform messy, incomplete, human observations into reliable transit knowledge over time**.

It is not:

* A direct editor for OpenStreetMap
* A GTFS authoring tool
* A CRUD database for routes and stops

It *is*:

* A knowledge refinement system
* A confidence-based truth engine
* A long-lived, auditable data platform

---

## 2. Core Philosophy

### 2.1 Evidence, Not Authority

Users never edit truth.

They submit:

* What they saw
* Where they were
* When it happened

The backend decides *what it means*.

---

### 2.2 Nothing Is Ever Deleted

* Data fades through decay, not deletion
* Old knowledge can be revived
* History is always preserved

Deletion is treated as data loss.

---

### 2.3 Truth Is Versioned and Temporal

Every accepted fact:

* Has a lifespan
* Has provenance
* Can change over time

There is no timeless truth in transit systems.

---

### 2.4 Publishing Is Downstream

The backend’s internal model is **not optimized for GTFS or OSM**.

GTFS feeds and OSM updates are:

* Derived products
* Generated only from stable canonical knowledge
* Optional and reversible

---

### 2.5 Canonical State Is Materialized (Derived but Stored)

Canonical entities are **derived from contribution events and evaluation rules**, but they are **materialized and stored** for performance, querying, and spatial operations.

They are *not* recomputed on every read. Instead:

* Canonical state is updated incrementally as new evidence arrives
* Its authority comes from evidence + rules, not from direct edits
* It can be fully regenerated if evaluation logic changes

Canonical storage exists for efficiency; contribution events remain the ultimate source of authority.

---

## 3. What the Backend Will Do

### 3.1 Accept Contributions Safely

* Accept incomplete data
* Accept conflicting data
* Accept offline data
* Never block user intent

---

### 3.2 Preserve All Evidence

* Store contributions as immutable events
* Allow replay and rescoring
* Support rule evolution without data loss

---

### 3.2.1 Incremental First, Recomputable Always

The system updates canonical knowledge **incrementally by default** as new contributions arrive.

Full recomputation from historical events is a **safety mechanism**, not the normal operational path. It exists to:

* Fix bugs in evaluation logic
* Introduce improved scoring or decay rules
* Audit or validate system behavior

This balance keeps the system efficient in daily use while remaining correct and recoverable long-term.

---

### 3.3 Refine Knowledge Over Time

* Aggregate independent observations
* Use confidence and decay
* Prefer recent, observed reality
* Allow ambiguity

---

### 3.4 Expose Simple, Honest APIs

* Show best-known facts
* Hide internal complexity
* Communicate uncertainty in human language

---

### 3.5 Enable Future Integrations

* GTFS export
* OSM publishing (opt-in, curated)
* Third-party APIs

Without requiring architectural rewrites.

---

## 4. What the Backend Will Explicitly NOT Do

### 4.1 It Will Not Allow Direct Edits

* No PATCH/PUT on canonical entities
* No direct geometry edits
* No manual overrides without audit

---

### 4.2 It Will Not Expose Confidence Math

* No numeric confidence in public APIs
* No voting counts
* No contributor comparisons

---

### 4.3 It Will Not Promise Completeness

* Coverage may be partial
* Schedules may be approximate
* Data quality may vary by region

Honesty beats false precision.

---

### 4.4 It Will Not Hard-Code External Standards

* OSM schemas are not internal schemas
* GTFS tables are not canonical models

Adapters handle translation.

---

## 5. Architectural Invariants (Never Break These)

1. Contributions are append-only
2. Canonical data is derived, not edited
3. All decisions are reversible
4. Moderators add evidence, not truth
5. Public APIs expose conclusions, not process

These invariants protect long-term viability.

---

## 6. Mental Model for Contributors

For users, the system should feel like:

> "I noticed something, I shared it, and it helped over time."

Not:

> "I edited a database and hope I didn’t break anything."

---

## 7. Mental Model for Developers

For developers, the backend should feel like:

> "A slow, careful reasoning engine that can always change its mind."

Not:

> "A fragile set of tables that must never be wrong."

---

## 8. Long-Term Outlook

This philosophy supports:

* Incremental rollout
* Regional pilots
* Community trust
* Institutional partnerships
* Safe automation

The system is designed to age well.

---

## 9. Final Statement

This backend is intentionally conservative, explicit, and disciplined.

It trades short-term convenience for:

* Safety
* Auditability
* Evolvability
* Trust

That tradeoff is deliberate and permanent.

The licensing and governance guarantees that protect this philosophy are defined in `GOVERNANCE.md` at the repository root.
