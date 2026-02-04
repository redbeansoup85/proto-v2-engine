# Verification Factory
## Public Specification (Draft v1.0)

> **Purpose**  
> This document specifies a reference architecture for **controlling AI-generated code changes**
> using deterministic verification, explicit human approval, and evidence-based gating.
>
> It is designed to prevent unsafe automation while preserving AI-assisted productivity.

---

## 1. Problem Statement

Modern AI systems can generate code faster than humans can safely review it.

This creates three systemic risks:

1. **Non-determinism**  
   AI output is probabilistic. The same prompt may produce different results.

2. **Authority Collapse**  
   If AI output is executed automatically, responsibility becomes ambiguous.

3. **Audit Failure**  
   Without immutable evidence, post-incident analysis is impossible.

> **Core observation:**  
> *AI speed exceeds human verification capacity unless verification is automated and enforced structurally.*

---

## 2. Design Goals

The Verification Factory is built on five non-negotiable goals:

1. **Fail-Closed by Default**  
   Any missing evidence, schema violation, or unexpected state halts progress.

2. **Human Authority is Explicit**  
   AI may propose. Humans decide. The system enforces this boundary.

3. **Evidence Over Trust**  
   Every state transition is justified by artifacts, not assumptions.

4. **Isolation Everywhere**  
   No AI-generated code is ever tested or applied in place.

5. **Reproducibility**  
   Every accepted change can be replayed from artifacts alone.

---

## 3. Core Principle: PASS ≠ APPLY

A central invariant of this system is:

> **A successful verification does NOT imply permission to apply changes.**

| Concept | Meaning |
|------|---------|
| **PASS** | Automated verification succeeded |
| **PROPOSED** | Eligible for human decision |
| **APPROVED** | Explicit human authorization |
| **READY_FOR_PR** | Applied and re-verified in isolation |

This separation prevents **accidental autonomy**.

---

## 4. High-Level Architecture


AI → Proposal
↓
Verification Factory
↓
PROPOSED
↓
Human Approval
↓
APPROVED
↓
Isolated Re-Apply
↓
READY_FOR_PR
↓
Merge Gate
Each arrow represents a **gate**, not a suggestion.

---

## 5. Verification Factory (Conceptual)

The Factory is an automated verifier with **no authority to modify source code**.

### Responsibilities
- Apply AI patches in isolated environments
- Run deterministic test suites
- Enforce policy and path constraints
- Produce immutable verdict artifacts

### Non-Responsibilities
- Merging
- Deployment
- Branch creation
- Approval decisions

---

## 6. Self-Healing (Constrained)

The system supports limited self-healing loops:

- AI may retry **only** when:
  - Tests fail
  - Infrastructure errors occur
- Retries are:
  - Bounded
  - Recorded
  - Never self-escalating

> **Self-healing does not imply self-authorization.**

---

## 7. Evidence Model

Every proposal produces an **Evidence Bundle**, including:

- Original proposal
- Patch diff
- Verification verdict
- Test outputs
- Policy and schema hashes

All evidence is:
- Append-only
- Content-addressed
- Retained independently of outcomes

---

## 8. Human Approval Gate

Approval is a **recorded act**, not a UI click.

An approval record includes:
- Approver identity
- Explicit decision
- Reason
- Cryptographic linkage to evidence

Approval cannot be modified—only superseded.

---

## 9. Merge Gate Enforcement

Code merging is guarded by automated checks that verify:

- Approval exists and matches evidence
- Re-application succeeded
- No restricted areas were modified
- Required artifacts are present

Without this proof, merge is impossible.

---

## 10. What This System Is Not

- ❌ Autonomous deployment
- ❌ AI decision-making
- ❌ Trust-based review
- ❌ CI convenience tooling

> This is **governance infrastructure**, not automation sugar.

---

## 11. Intended Audience

- Engineering teams adopting AI coding tools
- Security and compliance reviewers
- Regulators evaluating AI usage controls
- Open-source maintainers

---

## 12. Status

This specification describes a **working reference implementation**.

It is not a thought experiment.

Related documents:
- Pipeline: [PIPELINE.md](PIPELINE.md)
- Threat Model: [THREAT_MODEL.md](THREAT_MODEL.md)
- Terminology: [TERMINOLOGY.md](TERMINOLOGY.md)
- FAQ: [FAQ.md](FAQ.md)

---

_End of document._
