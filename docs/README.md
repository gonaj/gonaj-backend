# Gonaj Documentation

Welcome to the Gonaj documentation.

This folder contains the **design, philosophy, and execution record** of the Gonaj backend — a crowdsourced public transport knowledge platform built to be safe, auditable, and evolvable.

If you are new here, **start from the top and read in order**.  
The documentation is intentionally structured like a book, not a wiki.

---

## 1. What Is Gonaj?

Gonaj is a backend system that transforms **messy, incomplete, human observations** about public transport into **reliable transit knowledge over time**.

It is designed for regions where:
- official data is missing, outdated, or inaccessible
- schedules are fuzzy rather than exact
- local knowledge exists but is undocumented

Gonaj prioritizes **correctness, reversibility, and trust** over speed or feature count.

---

## 2. How This Documentation Is Organized

This documentation is divided into **clear conceptual layers**.

Read depth depends on your role:

- **New readers** → Overview → Architecture → Phase-1
- **Contributors** → Phase-1 → Domain → API
- **Maintainers** → Architecture → Rules → Execution history

---

## 3. Documentation Map

### 00. Overview — Start Here
High-level context for *why* this project exists.

- `00_overview/project_vision.md`  
- `00_overview/problem_statement.md`  
- `00_overview/glossary.md`

---

### 01. Architecture — Timeless Principles
These documents define **non-negotiable truths** of the system.

They change rarely and deliberately.

- `01_architecture/backend_philosophy.md`  
- `01_architecture/architectural_invariants.md`  
- `01_architecture/system_mental_model.md`  
- `01_architecture/trust_and_uncertainty.md`

If you disagree with something here, discuss **before coding**.

---

### 02. Phase-1 — Current Canonical State
Phase-1 is **frozen** once complete.

This folder defines:
- scope
- invariants
- rules
- completion criteria

- `02_phase_1/phase_1_scope.md`  
- `02_phase_1/phase_1_backend_plan.md`  
- `02_phase_1/rules_v0.md`  
- `02_phase_1/test_invariants_v0.md`  
- `02_phase_1/phase_1_freeze_checklist.md`

Nothing outside this folder may override Phase-1 guarantees.

---

### 03. Domain — What the System Knows
Conceptual models of the system’s knowledge.

These describe *meaning*, not tables.

- `03_domain/core_models.md`  
- `03_domain/transit_domain.md`  
- `03_domain/contribution_model.md`  
- `03_domain/moderation_model.md`

---

### 04. API — How the World Interacts
Public-facing contracts and principles.

- `04_api/api_principles.md`  
- `04_api/authentication.md`  
- `04_api/api_quick_reference.md`

Public APIs expose **conclusions, not internal process**.

---

### 05. Execution History — What Happened
This is a **historical record**, not current truth.

Useful for:
- audits
- understanding decisions
- onboarding contributors

- `05_execution_history/phase_1/`

Sprint documents **never redefine architecture or rules**.

---

### 06. Contributing — How to Help Safely
Guidance for contributors and tooling.

- `06_contributing/contributor_guide.md`  
- `06_contributing/copilot_prompts/`

All contributions must respect architectural invariants.

---

### 99. Appendix — Reference & History
Supporting material that should not distract new readers.

- `99_appendix/discussion_summary.md`  
- `99_appendix/historical_decisions.md`

---

## 4. How to Read This Repo (Recommended Paths)

### If you are evaluating the idea
1. Project Vision
2. Backend Philosophy
3. Phase-1 Scope

### If you want to contribute
1. Architecture → Invariants
2. Phase-1 Rules
3. Domain Model
4. Contributor Guide

### If you want to build on the data
1. API Principles
2. API Quick Reference
3. Phase-1 Guarantees

---

## 5. Ground Rules for Documentation Changes

- Architecture and philosophy documents are **constitutional**
- Phase-1 documents are **frozen once finalized**
- Sprint documents are **historical only**
- New ideas go into **new phase folders**, not retroactively into old ones

If a change weakens auditability, reversibility, or trust, it does not belong here.

---

## 6. Final Note

Gonaj is intentionally conservative.

The system is designed to be **safe to be wrong**, to change its mind over time, and to preserve history rather than overwrite it.

This documentation exists to protect those goals.

Read carefully. Build carefully.
