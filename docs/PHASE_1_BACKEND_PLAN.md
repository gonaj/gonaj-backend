# Phase-1 Backend Master Plan

> **This document is the single source of truth for Phase-1 backend work.**
> It supersedes all earlier sprint plans, task lists, and provisional designs.

This plan is derived from:

* BACKEND_PHILOSOPHY.md (constitutional principles)
* CONTRIBUTING.md (contributor rules)
* Phase-1 implementation order & sprint breakdown discussions

Any document or plan that conflicts with this one is considered **obsolete**.

---

## 1. Phase-1 Goal (Why This Exists)

Phase-1 exists to build a **correct, safe, and evolvable backend foundation** for a crowdsourced public-transport system.

Success in Phase-1 is **not** measured by features, growth, or polish.

Phase-1 is successful **only if**:

* User-contributed data cannot corrupt truth
* All knowledge can be re-derived from evidence
* Uncertainty, change, and conflict are handled safely

---

## 2. Non-Negotiable Invariants

These invariants come directly from `BACKEND_PHILOSOPHY.md` and must never be violated.

1. **Contributions are append-only**
   Evidence is never overwritten or deleted.

2. **Canonical data is derived, not edited**
   Canonical state is materialized belief, updated only via evaluation logic.

3. **All decisions are reversible**
   Truth can always be recomputed from historical evidence.

4. **Moderators add evidence, not truth**
   Human intervention is auditable and reversible.

5. **Public APIs expose conclusions, not process**
   Internal scoring, conflicts, and mechanics remain hidden.

If any implementation step violates an invariant, Phase-1 is broken.

---

## 3. Phase-1 Explicit Scope

### Included

* ContributionEvent ingestion (evidence)
* Canonical transit entities (derived belief)
* Incremental evaluation & promotion
* Confidence, freshness & decay
* Moderation as evidence
* Public read APIs (simplified)

### Explicitly Excluded (Deferred to Phase-2)

* Leaderboards & reputation economy
* Gamification
* GTFS trip-level schedules
* OSM publishing & linking
* Developer portal
* Real-time guarantees

---

## 4. High-Level Architecture (Mental Model)

```
User Observation
      ↓
ContributionEvent (immutable)
      ↓
Evaluation & Aggregation Logic
      ↓
Canonical Transit Knowledge (materialized belief)
      ↓
Read APIs / Exports
```

There are **no direct writes** to canonical entities.

---

## 5. Canonical Transit Entities (Phase-1)

Only the following entities may exist in Phase-1:

* Stop
* Route (logical)
* RouteVariant
* StopRouteLink
* ObservedServiceWindow

Each canonical entity **must** include:

* Stable internal ID + public ID
* Temporal validity (`valid_from`, `valid_until`)
* Version number
* Structural + freshness confidence
* Evidence references (ContributionEvent IDs)
* Evaluation ruleset version

---

## 6. Contribution Model

### 6.1 What Users Submit

Users submit **observations**, not edits, for example:

* "This stop is called X"
* "Buses still stop here"
* "I rode this route"
* "Bus passed here around 6:40 PM"

### 6.2 Authentication Rule

* Reading canonical data: **no login required**
* Submitting contributions: **login required**

### 6.3 Contribution Storage

All contributions are stored as **ContributionEvent** records:

* Immutable
* Append-only
* Idempotent
* Replayable

---

## 7. Evaluation & Confidence Model

### 7.1 Incremental First

* New contributions trigger incremental evaluation
* Canonical state is updated conservatively

### 7.2 Confidence

* Structural confidence (long-term stability)
* Freshness confidence (recency)
* Final confidence derived from both

### 7.3 Decay

* Confidence decays over time without reinforcement
* Negative signals accelerate decay
* Data fades instead of being deleted

---

## 8. Moderation Model

* Moderators do not edit canonical data
* Moderator actions create **ModeratorEvents**
* Overrides are scoped, auditable, and reversible

Moderation exists to resolve conflicts, not to assert authority.

---

## 9. Public API Rules

### Read APIs

* Expose simplified, human-friendly data
* Hide internal confidence math
* Communicate uncertainty via language, not numbers

### Write APIs

* Accept evidence only
* All write endpoints under `/contributions/*`
* Auth required

---

## 10. Phase-1 Implementation Order (Authoritative)

This order must be followed.

1. Architectural guardrails
2. ContributionEvent backbone
3. Write APIs (evidence ingestion)
4. Canonical entity skeletons
5. Minimal evaluation pipeline
6. Confidence & decay
7. Moderation as evidence
8. Canonical recomputation safety
9. Read APIs
10. Audit & explainability
11. Phase-1 freeze

---

## 11. Sprint-Based Execution Plan (Solo Developer)

> This is the **only valid sprint plan** for Phase-1.

* Month 0: Guardrails + events
* Month 1: Contribution ingestion
* Month 2: Spatial & temporal evidence
* Month 3: Canonical structure
* Month 4: Evaluation pipeline
* Month 5: Confidence & decay
* Month 6: Moderation & safety
* Month 7: Read APIs
* Month 8: Audit & Phase-1 freeze

This plan assumes disciplined, part-time solo development.

---

## 12. Phase-1 Completion Criteria

Phase-1 is complete **only when**:

* Evidence can be submitted safely
* Canonical truth evolves without direct edits
* Confidence decays naturally
* Conflicts do not corrupt data
* Truth can be recomputed from events
* Read APIs are stable and honest

If any of the above is false, Phase-1 is not complete.

---

## 13. What Happens After Phase-1

Only after Phase-1 freeze may the project consider:

* Reputation & leaderboards
* GTFS schedules
* OSM publishing
* Public contributor incentives

Phase-2 work must not leak into Phase-1.

---

## 14. Final Statement

> **Phase-1 is about making the system safe to be wrong.**

Once that is achieved, features can grow without fear.

This document is intentionally conservative and final for Phase-1.
