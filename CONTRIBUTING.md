# Contributing to the Backend

Thank you for your interest in contributing 🙌
Before writing any code, please read this document carefully. It exists to protect both **contributors** and the **long-term integrity of the project**.

This backend is not a typical CRUD application. Many well‑intentioned changes can accidentally break core guarantees if the philosophy is not understood first.

---

## 1. What This Backend Is

This backend is a **transit knowledge refinement system**.

* Users submit **observations and evidence**
* The system gradually derives **canonical transit knowledge**
* Truth evolves through **time, confirmation, and decay**

The backend optimizes for:

* Long‑term correctness
* Auditability
* Reversibility
* Trust

---

## 2. What This Backend Is NOT

Please do **not** treat this project as:

* A direct editor for OpenStreetMap
* A GTFS authoring or validation tool
* A system where users "edit" routes or stops
* A place where data is overwritten or deleted

If your proposed change assumes any of the above, pause and re‑read the philosophy.

---

## 3. Core Invariants (Must Never Be Broken)

These are non‑negotiable. Every PR is evaluated against them.

1. **Contributions are append‑only**
   User input is never overwritten or deleted.

2. **Canonical data is derived, not edited**
   Canonical entities are updated only through evaluation logic, never directly by API calls or manual edits.

3. **All decisions are reversible**
   Any belief held by the system must be re‑derivable from historical evidence.

4. **Moderators add evidence, not truth**
   Moderator actions are recorded as events and processed by the same pipeline.

5. **Public APIs expose conclusions, not process**
   Internal confidence, scoring, and conflicts are not exposed to consumers.

If a change violates any of these, it will not be merged.

---

## 4. Contribution Model (Very Important)

### 4.1 Users Do Not Edit Data

Users submit **intent and observations**, such as:

* "This stop is called X"
* "Buses still stop here"
* "I rode this bus"
* "The bus passed here around 6:40 PM"

They do **not**:

* Update stop tables
* Modify geometries
* Edit routes or sequences

---

### 4.2 Contributions Are Events

All contributions are stored as **immutable events**:

* They are append‑only
* They are idempotent
* They may be replayed

Never design logic that depends on mutating past contributions.

---

## 5. Canonical Data (How Truth Exists)

Canonical entities (Stop, Route, RouteVariant, etc.) represent:

> *What the system currently believes to be true*

Important clarifications:

* Canonical state **is materialized and stored**
* It is **incrementally updated** as new evidence arrives
* It can be **fully recomputed** if rules change

Canonical tables exist for performance — **not authority**.

---

## 6. Confidence & Decay

* Confidence is **not binary**
* Confidence decays over time unless reinforced
* Negative evidence accelerates decay
* Old data fades instead of being deleted

Do not introduce logic that treats data as permanently correct.

---

## 7. Moderation Guidelines

Moderators:

* Do not directly edit canonical data
* Do not delete evidence
* Do not silently override history

Moderator actions must:

* Be recorded as events
* Be auditable
* Be reversible

---

## 8. API Design Rules

### Read APIs

* Expose simplified, human‑friendly facts
* Hide confidence numbers and internal mechanics
* Prefer honest uncertainty over false precision

### Write APIs

* Accept evidence, not edits
* Be idempotent
* Support offline submissions

Never expose CRUD endpoints on canonical entities.

---

## 9. When in Doubt

Before implementing a change, ask:

1. Is this adding evidence, or mutating truth?
2. Can this decision be reversed later?
3. Would this still make sense if rules change next month?
4. Does this leak internal complexity to users?

If unsure, open a discussion before coding.

---

## 10. Final Note

This project values **correctness over convenience** and **long‑term trust over short‑term speed**.

Thoughtful, disciplined contributions are far more valuable than rapid feature additions.

Thank you for helping build something that can last.

---

## Certificate of Origin (DCO)

Gonaj uses a **Developer Certificate of Origin (DCO)** to keep the project legally clean and trustworthy for everyone.

By contributing, you confirm that:

- You wrote the contribution yourself, **or**
- You have the right to submit it under the project’s license

This helps ensure that all code in Gonaj can remain open, auditable, and safely reusable.

### How to sign off a contribution

Each commit must include a `Signed-off-by` line in the commit message:

```
Signed-off-by: Your Name <your.email@example.com>
```

You can add this automatically by committing with:

```
git commit -s
```

That’s it — no forms, no account registration, no copyright transfer.

### What this does *not* do

- It does **not** transfer ownership of your work  
- It does **not** give anyone special relicensing rights  
- It does **not** affect how your contribution is credited  

It simply confirms that contributions are made in good faith and can be safely shared.

For the full text of the Developer Certificate of Origin, see `DCO.md`.

