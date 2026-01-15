# Operational Canon — Learning → Policy Cycle

**Version:** 1.0  
**Status:** LOCKED  
**Binding Level:** L3 (Constitution-Bound Operational Canon)  
**Depends on:** Constitution (L4), Section AQ — Approval Queue

---

## 0. Canon Status Declaration

This canon defines the only permitted operational rules governing how the Learning OS may generate policy proposals and how those proposals may enter the Approval Queue.

No silent modification is permitted. Any change requires a Canon revision and version increment.

---

## 1. Purpose

- Learning may evolve rapidly without destabilizing policy.
- Policy changes remain slow, explainable, and accountable.
- Human responsibility is preserved between learning and execution.

Learning informs policy; it does not mutate it.

---

## 2. Foundational Principles

1. Learning OS must never modify policy directly.
2. Learning OS may only emit policy proposals.
3. Proposals are inert until evaluated by the Approval Queue.
4. Frequent learning must not imply frequent policy change.

---

## 3. Proposal Eligibility Conditions

A proposal may be generated only if all conditions below are satisfied.

### 3.1 Observation Window Requirement

- A minimum observation window must be satisfied (time-based or event-based).
- Short-term anomalies must be filtered.
- If the window is incomplete, proposal generation is prohibited.

### 3.2 Sample Sufficiency Requirement

- Observations must meet or exceed minimum sample threshold (N_min).
- Single cases and outliers must not dominate the signal.
- Insufficient samples prohibit proposal emission.

### 3.3 Stability Confirmation

At least one of the following must hold:
- consistent directional signal for K confirmations,
- volatility contraction/stabilization,
- opposing signals below tolerance ε.

Unstable signals may not be proposed.

### 3.4 Explainability Requirement

Every proposal must include:
- summary of current policy,
- summary of proposed policy,
- rationale,
- expected impact and rollback scope.

Missing explanation invalidates the proposal.

---

## 4. Proposal Rate Limiting

Learning OS is subject to hard proposal limits.

- Proposal frequency: ≤ X per period
- Policy domain reuse: cooldown required
- Repeated rejection: mandatory rest period

Rate limits protect trust and operator credibility.

---

## 5. Interface with Approval Queue

- Learning OS must not interpret Approval Queue outcomes as rewards/penalties.
- No-op and duplicate carry no semantic meaning for learning.
- Approval Queue output is structural state only.

---

## 6. Mandatory Human Approval Gate

Automatic approval is forbidden when:
- policy impact scope expands,
- rollback cost increases materially,
- external users or real-world systems are affected.

In these cases, explicit human authorization is required.

---

## 7. Explicit Prohibitions

Learning OS must never:
- change policy due to short-term success metrics,
- optimize via reinforcement from approval outcomes,
- interpret queue acceptance as correctness.

Violation is a philosophy breach.

---

## 8. Canon Summary Statement

> Learning evolves quickly.  
> Policy evolves slowly.  
> A human always stands between them.

---

## 9. Lock Statement

**LOCKED — Operational Canon v1.0**
