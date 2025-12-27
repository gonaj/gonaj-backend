# Consolidated Discussion Report

## 1. Original Ask

The initial objective was to **plan a backend architecture** for a crowdsourced public transport platform that:

* Supports **crowdsourced transit data** from users
* Can generate **GTFS datasets** for regions with poor or missing official data
* May **publish to OpenStreetMap (OSM)** in the future
* Does **not require users to understand OSM or GTFS complexity**
* Is **safe, reversible, auditable, and future-proof**

The discussion explicitly focused on **planning and architecture**, not on implementation or code generation.

---

## 2. Key Problems Identified Early

1. **OSM editing is complex and unsuitable for normal users**

   * Route relations, variants, and route masters are hard even for experienced mappers
   * Asking users to learn OSM workflows would destroy participation

2. **User-contributed data is often incomplete, noisy, or uncertain**

   * GPS traces may be partial
   * Names may be local or inconsistent
   * Schedules are fuzzy and time-dependent

3. **GTFS and OSM have fundamentally different goals**

   * GTFS = scheduling & routing
   * OSM = geographic ground truth
   * One cannot be treated as the canonical source for the other

---

## 3. Strategic Decisions Taken

### 3.1 OSM Publishing Postponed

**Decision:** Defer OSM publishing to a later phase.

**Reasoning:**

* High governance and correctness burden
* Low immediate user value
* Requires mature confidence and moderation systems

**Outcome:**

* OSM treated as a **future downstream publication target**, not a core dependency
* Backend designed to remain *OSM-compatible* without being *OSM-driven*

---

### 3.2 StreetComplete-style Contribution Model Adopted

**Decision:** Treat the app as conceptually similar to *StreetComplete*, but for transit.

**Meaning:**

* Users contribute **intent and observations**, not structured edits
* Backend absorbs complexity
* Data is refined over time

**Outcome:**

* Micro-task UX
* No exposure of relations, variants, or schemas
* Users answer simple questions like:

  * "Does the bus stop here?"
  * "What is this stop called locally?"

---

## 4. Core Backend Architecture Agreed

### 4.1 Layered Architecture

1. **API / Ingestion Layer**

   * Accepts raw user observations
   * Append-only
   * No canonical writes

2. **Contribution Pipeline**

   * Normalization
   * Aggregation
   * Conflict detection
   * Confidence scoring

3. **Canonical Transit Knowledge Layer**

   * System’s current belief of truth
   * Versioned, auditable, reversible

4. **Publication / Consumption Layer**

   * GTFS export
   * Read APIs
   * (Future) OSM export

---

## 5. Phase-1 Canonical Entities Defined

Only **five canonical entities** are allowed in Phase-1:

1. Stop
2. Route (logical)
3. RouteVariant
4. StopRouteLink
5. ObservedServiceWindow

Explicitly excluded:

* Trips
* StopTimes
* Calendars
* Fares
* OSM relations

---

## 6. Phase-1 Contribution Types Locked

Users can submit **only evidence**, not edits:

* Stop name correction
* Stop existence / non-existence
* Stop location refinement
* Route existence claim
* Route traversal (GPS trace)
* Stop sequence confirmation
* Service time observation

All contributions are:

* Append-only
* Idempotent
* Never destructive

---

## 7. Confidence & Validation Model

### 7.1 Multi-layer Confidence

* **Structural confidence**: long-term stability
* **Freshness confidence**: recency of confirmation

Final confidence = structural × freshness

### 7.2 Natural Decay

* Time-based half-life per entity type
* No manual cleanup
* Reinforcement resets decay
* Negative signals accelerate decay

---

## 8. Moderation Philosophy

* Moderators **do not edit data directly**
* Moderator actions are also events
* Interventions are reversible
* Moderation focuses only on:

  * Conflicts
  * High-risk changes
  * External publication

---

## 9. Public API Design Decisions

### Read APIs

* Expose **simplified facts**, not internal models
* Hide confidence numbers
* Use human-friendly reliability hints

### Write APIs

* Intent-based
* Evidence-only
* No CRUD on canonical entities
* Offline-safe (idempotent, replayable)

---

## 10. Replayability & Long-term Safety

* All user input stored as immutable events
* Decisions derived, never baked in
* Rules can change without data loss
* Canonical state can be regenerated

---

## 11. Final Outcome

The discussion resulted in a **clear, disciplined backend philosophy**:

* The system is a **knowledge refinement engine**, not a CRUD app
* Users contribute evidence, not truth
* Truth evolves through time, confirmation, and decay
* GTFS and OSM are downstream products, not primary stores

This architecture is intentionally conservative, but highly durable.

---

## 12. Final Clarifications (Post-Discussion)

The following conclusions were reached **after** the initial consolidation and are now considered **final for Phase-1**. These points supersede any earlier ambiguity.

### 12.1 Canonical Data Is Derived *and* Materialized

Canonical transit data is **derived from immutable contribution events and evaluation rules**, but it is **materialized and stored** for efficient querying and spatial operations.

* Canonical data is **not recomputed on every read**
* It is updated **incrementally** as new evidence arrives
* Its *authority* comes from events + rules, not from direct edits
* It can be **fully regenerated** if evaluation logic changes

---

### 12.2 Authentication Policy (Final)

* **Reading canonical transit data does not require login**
* **Submitting contributions requires login**, to ensure accountability, auditability, and replay safety

This policy is now fixed for Phase-1.

---

### 12.3 Phase-1 Scope Freeze

Phase-1 scope is explicitly **frozen**. The following are **out of scope** and deferred to Phase-2:

* Leaderboards and reputation systems
* Gamification and incentives
* OSM account linking and publishing
* GTFS trip-level schedules (trips, stop_times, calendars)
* Developer portal and external SDKs
* Heavy observability and growth tooling

These features must not be implemented during Phase-1.

---

### 12.4 Status of This Document

With the clarifications above, this document now represents the **complete and final summary** of discussions and conclusions for Phase-1 backend planning.
