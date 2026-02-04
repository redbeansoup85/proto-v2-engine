# Verification Factory — Pipeline Specification

This document describes the end-to-end pipeline enforced by the Verification Factory.
Each phase is a **gate**, not an optimization.

---

## Pipeline Overview

Phase 1 Proposal Intake
Phase 2 Verification Factory
Phase 3 Self-Healing Orchestrator (Bounded)
Phase 4 Human Approval Gate
Phase 5 Apply-Approved (Isolated Re-verify)
Phase 6 PR Package Generation
Phase 7 Merge Gate Enforcement
Phase 8 Retention & Archival
Phase 9 Evidence Report Pack
No phase may be skipped.
Backward transitions are not allowed.

---

## Phase 1 — Proposal Intake

**Input:** AI-generated proposal (intent + patch)  
**Output:** Structured proposal artifact

Key rules:
- Proposals are immutable inputs.
- No code is modified at this stage.
- Proposal identity (`proposal_id`) is globally unique.

---

## Phase 2 — Verification Factory

**Purpose:** Determine technical correctness without authority.

Actions:
- Apply patch in isolated worktree
- Run deterministic test suite
- Enforce path / policy gates
- Produce verdict + evidence bundle

Invariant:
- `PASS` ⇒ `PROPOSED`
- Never implies apply, merge, or deploy

---

## Phase 3 — Self-Healing (Bounded)

**Purpose:** Allow constrained retries without autonomy.

Rules:
- Only retry on allowed failure classes
- Retry count is capped
- All attempts are recorded
- No authority escalation

Failure beyond bounds escalates to human review.

---

## Phase 4 — Human Approval Gate

**Purpose:** Explicit human decision.

Rules:
- Only `PROPOSED` may be approved or rejected
- Approval is append-only
- Approver identity is required
- Approval is cryptographically linked to evidence

---

## Phase 5 — Apply-Approved

**Purpose:** Re-verify before exposure.

Actions:
- Apply approved patch in fresh isolated worktree
- Re-run tests
- Capture apply evidence

Output status:
- `READY_FOR_PR` or failure

---

## Phase 6 — PR Package

**Purpose:** Prepare human-reviewable change.

Artifacts:
- Diff
- Evidence references
- Checklists
- Reproducibility commands

No PR is created automatically.

---

## Phase 7 — Merge Gate

**Purpose:** Enforce evidence-based merge.

Checks:
- Approval exists and matches hashes
- Apply evidence present
- No-touch zones respected
- Required artifacts exist

Without PASS, merge is impossible.

---

## Phase 8 — Retention & Archival

**Purpose:** Long-term traceability.

Rules:
- Evidence archived after policy-defined period
- Ledgers and memory are never deleted
- Archival is verifiable and reversible

---

## Phase 9 — Report Pack

**Purpose:** External audit, review, and regulatory use.

Outputs:
- Deterministic report
- Evidence index
- Lineage hashes
- Reproducibility instructions

---

## Global Invariants

- Fail-Closed everywhere
- Isolation by default
- Evidence before authority
- Humans decide, systems enforce

---

End of document.
