# Gonaj — Stop Evaluation Rules v0

> **Status: FINAL DRAFT (Ready for Review)**

This document defines **Evaluation Rules v0** for the canonical **Stop** entity in Gonaj.

Rules v0 are intentionally conservative. Their goal is **safety, replayability, and honest uncertainty**, not completeness or speed.

---

## 1. Purpose of Rules v0

Evaluation Rules v0 define how immutable user contributions are transformed into **canonical belief**.

Specifically, they govern:

* When a Stop comes into existence
* How confidence is accumulated and lost
* How conflicts are handled
* How belief fades over time
* Why Stops are never deleted in Phase-1

These rules must be:

* Globally plausible
* Operator-agnostic
* Biased toward false negatives
* Safe to replay and revise later

---

## 2. Core Invariants (Non-Negotiable)

* Contributions are **append-only**
* Canonical Stops are **derived, not edited**
* Canonical belief is **materialized**, not recomputed per read
* Evaluation must be **deterministic** for a given ruleset and evidence history
* All decisions are **replayable**
* Confidence and uncertainty are first-class
* Missing data is preferable to wrong data

---

## 3. Belief Model

A Stop is a **canonical entity** whose *belief* evolves over time.

Belief consists of:

* Existence belief
* Structural confidence (long-term)
* Freshness confidence (recency)
* An interpretable **Belief State**

Belief State is a human-legible projection of confidence, not a workflow state.

### Belief States (v0)

* **Proposed** — Newly created, fragile belief
* **Active (Low Confidence)** — Exists but uncertain
* **Active (High Confidence)** — Stable, reinforced belief
* **Contested** — Conflicting evidence present
* **Dormant** — Belief exists but is outdated

Stops are never hard-deleted.

---

## 4. Positive Evidence

Positive evidence for a Stop includes:

* Explicit assertions of existence
* Behavioral observations (vehicles stopping)
* Temporal reinforcement across days

Rules:

* Evidence is **weighted, never gated**
* Independence matters more than volume
* Same-user repetition is progressively down-weighted
* No single observation can create a Stop

---

## 5. Negative Evidence

Negative evidence is **explicit, intentional negation**.

Valid types:

* Explicit non-existence assertion
* Observed bypass behavior (repeated)
* Explicit decommissioning claims

Rules:

* Negative evidence **never deletes** a Stop
* It **reduces confidence** and **accelerates decay**
* It is weaker than aggregated independent positive evidence
* It decays faster than positive evidence

---

## 6. Stop Creation Threshold

A Stop is created only when **cumulative belief crosses a threshold**.

Requirements:

* At least **two independent contributors**
* Contributions on **different days**
* **Multiple evidence types**
* Spatial coherence
* Temporal plausibility

Creation rules:

* Creation is gradual, not event-driven
* Initial belief state is always **Proposed**
* Negative evidence raises the threshold but never blocks creation

Sub-threshold evidence must not be rendered as Stops.

---

## 7. Conflict Handling — Stop Names

Principles:

* Names are **attributes of belief**, not identity
* Multiple names may coexist
* Naming conflicts never affect Stop existence

Rules:

* Each name accumulates belief independently
* Negative name evidence applies only to that name
* A primary name may emerge but is never final

---

## 8. Conflict Handling — Spatial Clusters

Principles:

* Proximity alone never implies sameness
* Bias toward **under-merge**, not over-merge

Rules:

* Nearby Stops may coexist temporarily
* Merges require strong, time-stable, behavioral evidence
* Splits are rare and heavily constrained
* Hysteresis prevents oscillation

---

## 9. Confidence Decay

### Time-Based Decay

* All belief decays without reinforcement
* Decay applies even without negative evidence

### Asymmetric Decay (Locked)

* Newly created Stops decay faster
* Long-standing Stops decay slowly

### Interaction with Negative Evidence

* Negative evidence accelerates decay
* Never replaces decay
* Never causes immediate deletion

### Explainability (Required)

Belief state transitions caused by decay **must be explainable** in human language.

Examples:

* "This stop hasn’t been confirmed recently"
* "Information about this stop may be outdated"

No numeric confidence is exposed.

---

## 10. Deletion Policy (Phase-1)

* Hard deletion is **forbidden**
* Stops disappear only by decaying to near-zero confidence
* Dormant Stops persist indefinitely
* Any Stop may be revived by new evidence

Negative evidence alone can never delete a Stop.

---

## 11. Visibility Rules

* Only canonical Stops may be shown as Stops
* Sub-threshold belief must never be rendered as Stops
* Personal (author-only) views of contributions are allowed
* Shared truth requires canonical existence

---

## 12. Explicit Non-Goals (v0)

Rules v0 do **not**:

* Enforce correctness guarantees
* Perform operator-specific logic
* Use reputation or trust scores
* Use ML or probabilistic inference
* Support explicit merge assertions
* Perform GTFS or OSM publishing

---

## 13. Final Statement

> **Rules v0 are designed to make the system safe to be wrong.**

Belief evolves, confidence fades, truth is never deleted, and uncertainty is always honest.

---

## 14. Ruleset Freeze (v0)

* Rules v0 are **frozen** after approval
* Thresholds, evidence definitions, belief states, and decay behavior **must not be changed** within v0
* Any modification requires a new ruleset version (v1+)
* Historical evidence must remain replayable under its original ruleset
