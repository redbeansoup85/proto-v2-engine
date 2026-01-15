# Governance Map — Meta OS v1.0

**Status:** LOCKED  
**Purpose:** Single-page authoritative map of governance, responsibility, and execution boundaries.

This document is a control map. It is not an implementation guide.

---

## 1. Layered Governance Model



Layers may depend downward but must never override upward.

---

## 2. L4 — Constitution (LOCKED)

### Section AQ — Approval Queue

- fixes responsibility and evaluation order
- Approval Queue does not judge policy quality

Deterministic order:
1. noop
2. duplicate
3. mismatch
4. apply / skip

No-op / duplicate are normal and silent.  
Mismatch requires human attention.

---

## 3. L3 — Operational Canon (LOCKED)

### Learning → Policy Cycle v1.0

- learning never edits policy
- proposal requires:
  - observation window
  - sufficient samples
  - stability confirmation
  - explanation
- proposal rate is limited
- human gate is mandatory for sensitive change

---

## 4. L3 — Operational Pack (LOCKED)

### Learning→Policy Governance Pack v1.0

Contains:
- proposal schema (JSON/Pydantic)
- human approval gate checklist
- canon index

---

## 5. L2 — Contracted Code (ENFORCEMENT)

### Governance package (`core/governance`)

Enforces:
- proposal structure validation
- canon eligibility pre-queue
- human gate correctness
- AQ order via queue adapter

Key artefacts:
- `PolicyProposal`
- `validate_proposal_prequeue`
- `QueueOutcome`
- `evaluate_proposal_constitutional`

Invariant:
> If governance rules are broken, code must fail.

---

## 6. L1 — Runtime Systems

### Learning OS (Proposal Producer)
- observes signals continuously
- proposes only when Canon allows
- cannot bypass rate limits or human gate

### Approval Queue (Structural Evaluator)
- evaluates proposals structurally
- emits outcomes, not decisions

### Policy Store
- holds policy state
- provides hashes and snapshots

---

## 7. L0 — Observations

Sources:
- metrics
- events
- logs
- human input

Rule:
- observations never directly change policy

---

## 8. Responsibility Boundaries (Critical)

| Actor | Allowed | Forbidden |
|---|---|---|
| Learning OS | learn, propose | apply policy |
| Approval Queue | evaluate structure | judge quality |
| Governance Code | enforce rules | decide outcomes |
| Human Operator | approve/reject | abdicate responsibility |

---

## 9. Change Rules Summary

| Change Type | Allowed Via |
|---|---|
| responsibility rules | constitutional amendment |
| proposal eligibility | canon revision |
| schema / checklist | pack revision |
| algorithm tuning | code update (must not violate contracts) |

Silent changes are prohibited at all layers.

---

## 10. Final Lock Statement

**LOCKED — Meta OS Governance v1.0**
