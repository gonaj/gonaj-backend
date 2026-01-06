# Gonaj Backend — Governance & Licensing

> **Status:** Authoritative
>
> This document defines the governance, licensing intent, and non-negotiable guarantees of the Gonaj backend project.
>
> It exists to protect contributor trust, ensure long-term auditability, and prevent silent shifts in project values.

---

## 1. Purpose of This Document

Gonaj is not just a software project; it is a **public-interest knowledge system**.

This document exists to:

* Make licensing intent explicit and durable
* Protect contributors from future ambiguity
* Encode constraints on how the project may evolve
* Ensure that openness, auditability, and reversibility are never compromised

This file is the **single source of truth** for governance and licensing intent. Any interpretation that conflicts with this document is incorrect.

---

## 2. Project Stewardship

The Gonaj backend is stewarded with the following priorities, in order:

1. **Public trust over growth**
2. **Auditability over convenience**
3. **Reversibility over speed**
4. **Clarity over flexibility**

Decisions are evaluated not by short-term adoption or revenue potential, but by their effect on long-term trust and correctness.

The project explicitly rejects models that:

* Privately appropriate community knowledge
* Introduce hidden authority or opaque truth
* Trade openness for rapid scaling

---

## 3. Default License (Non-Negotiable)

The Gonaj backend is licensed under **GNU Affero General Public License v3.0 (AGPL-3.0)**.

This license applies permanently to the **backend core**, including but not limited to:

* Contribution ingestion and evidence storage
* Evaluation rules and belief materialization logic
* Canonical data models
* Replay, recomputation, and audit mechanisms

These components together form the **public reasoning engine** of Gonaj.

They will **always remain open, inspectable, forkable, and auditable** under AGPL-3.0.

---

## 4. Community Contributions

All contributions to the backend are accepted under the same AGPL-3.0 license.

Community contributions:

* Will not be relicensed silently
* Will not be incorporated into a closed or proprietary core
* Will remain part of the auditable public engine

The integrity of the reasoning engine depends on the ability of any party to inspect how conclusions are derived.

This guarantee is fundamental and permanent.

---

## 5. Bounded Commercial Licensing (Future Possibility)

To support long-term sustainability, the project **may** offer limited commercial licenses in the future.

If offered, such licenses are intended to:

* Provide deployment or operational exceptions to AGPL obligations
* Support regulated or institutional environments
* Fund continued open development of the AGPL core

These licenses:

* **Do not replace** the AGPL license
* **Do not weaken** AGPL guarantees
* **Do not create** a closed or superior core

AGPL remains the default and governing license for the public engine at all times.

---

## 6. Explicit Red Lines

The following actions are explicitly forbidden and will never occur:

* Closing or obscuring the canonical reasoning engine
* Introducing an “enterprise-only” evaluation or truth system
* Silently relicensing community contributions
* Removing AGPL rights from public releases

Any future licensing decision must preserve these guarantees in full.

---

## 7. Separation of Concerns

The AGPL license applies to the backend implementation itself.

Client applications, integrations, and external services may be licensed independently, provided that:

* They interact with the backend only through public APIs
* They do not embed or modify AGPL-licensed backend code
* They do not alter canonical belief or evaluation logic

This separation ensures openness of the reasoning engine without restricting experimentation at the edges.

---

## 8. Contributor Assurance

The project uses a **Developer Certificate of Origin (DCO)** to ensure that all contributions are made in good faith and can be safely shared.

At present:

* No Contributor License Agreement (CLA) is required
* No copyright transfer is requested
* No special relicensing rights are granted

Any future changes to contributor agreements, if ever required, must be introduced **prospectively, transparently, and with explicit notice**.

---

## 9. Constitutional Documents

Certain documents define the constitutional guarantees of the Gonaj backend, including:

* Backend philosophy
* Evaluation rulesets
* Data rights and deletion guarantees
* This governance document

Changes to these documents must:

* Be explicit and written
* Preserve existing guarantees
* Add clarity rather than reduce constraints

Silent or informal evolution of constitutional rules is not permitted.

---

## 10. Amendment Policy

This document may be amended only to:

* Clarify intent
* Strengthen guarantees
* Improve precision

Amendments must **never**:

* Reduce openness
* Introduce ambiguity around licensing
* Enable private appropriation of public reasoning

All amendments must be clearly versioned and justified.

---

## 11. Final Principle

> **AGPL protects the public engine.**
>
> **Governance exists to ensure that protection is never weakened — even under pressure.**

This document is a commitment to contributors, users, and future maintainers.

It is intended to outlast individual decisions, deployments, or maintainers.
