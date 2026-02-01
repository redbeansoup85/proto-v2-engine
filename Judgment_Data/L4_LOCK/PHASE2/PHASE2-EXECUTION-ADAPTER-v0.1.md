# PHASE2 — EXECUTION ADAPTER (Design v0.1)

## 1. Metadata (Immutable)

DOCUMENT_ID: PHASE2-EXECUTION-ADAPTER-v0.1  
SYSTEM: Proto Meta Engine v2 / Judgment OS  
LEVEL: L4 (Execution Boundary Implementation Spec)  
STATUS: DESIGN PROPOSAL  
MUTABILITY: CONTROLLED  
EFFECTIVE_DATE: 2026-01-31 (Australia/Sydney)  
PARENT_LOCK: PHASE1 (Judgment Common Core Event + Canonical Hash + Chain Verify)

---

## 2. Purpose (Non-Negotiable)

Phase-2 defines an **Execution Adapter** that converts an approved, bounded execution request into a real action **without introducing new judgment**.

The adapter MUST:
- Execute **only** within an explicit Envelope (scope, constraints, blast radius)
- Be **fail-closed** on any ambiguity, missing approval, missing sources, or contract mismatch
- Emit audit-grade events for every state transition

---

## 3. Non-Goals (Forbidden)

The adapter MUST NOT:
- Recommend actions, choose strategies, or optimize outcomes
- Infer missing fields, “guess intent”, or auto-fill constraints
- Execute outside of an explicit approval chain
- Modify historical events or registry artifacts

---

## 4. Definitions

- **Execution Request**: a structured request describing *what* to do (not why)
- **Execution Envelope**: immutable boundary constraints (scope, risk, timeout, allowed venues, limits)
- **Approval Artifact**: a human or policy decision object that authorizes execution
- **Adapter**: implementation that performs the action while enforcing Envelope + approval invariants
- **Capability Declaration**: explicit list of allowed actions the adapter can perform

---

## 5. Adapter Input Contract (Minimum)

The adapter accepts ONLY:
1) Execution Envelope (validated, immutable)
2) Approval Artifact (validated, not expired, applied)
3) Source Evidence Bundle references (non-null, accessible)

If any of the above is missing or invalid → **DENY (fail-closed)**.

---

## 6. Capability Declaration (Fail-Closed)

Adapter MUST declare capabilities as a static document:
- allowed action types
- allowed venues/integrations
- allowed max size / rate limits
- forbidden action types

If a requested action is not explicitly declared → **DENY**.

---

## 7. Required Audit Events (Phase-2)

Every adapter run MUST emit Judgment Common Core Events:

- EXECUTION_REQUESTED
- EXECUTION_AUTHORIZED (approval verified)
- EXECUTION_STARTED
- EXECUTION_FILLED / EXECUTION_COMPLETED (as applicable)
- EXECUTION_BLOCKED (deny reason codes)
- AUDIT_LOGGED (adapter trace, no sensitive leakage)

No silent failures. No “best effort” execution without events.

---

## 8. Fail-Closed Rules (Hard)

DENY if:
- approval missing / expired / not applied
- envelope missing fields or mismatch
- idempotency conflict
- source evidence refs missing/unreadable
- time order invalid
- registry/schema integrity mismatch
- any float appears in payload (via canonical hash rules)
- external call timeout / ambiguous response (must map to EXECUTION_BLOCKED)

---

## 9. Test Invariants (Phase-2 Gate)

Phase-2 pytest MUST include:
- deny on missing approval
- deny on expired approval
- deny on capability not declared
- deny on evidence missing
- deny on ambiguous external response
- idempotency replay blocked
- audit event emitted on every deny path

---

## 10. Lock Plan

- v0.1 (now): design proposal
- v0.2: interface + runbook mapping finalized
- v1.0: LOCK CANDIDATE after test suite + CI gate enforcement

