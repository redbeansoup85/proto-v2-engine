# PHASE2 — EXECUTION ADAPTER INTERFACE (v0.2)

## Status
STATUS: LOCK CANDIDATE  
MUTABILITY: FORBIDDEN after approval

---

## 1. Adapter Contract (Abstract)

### execute(envelope, approval, evidence_refs) → ExecutionResult

**Inputs (ALL REQUIRED):**
- envelope: ExecutionEnvelope (immutable)
- approval: ApprovalArtifact (validated, not expired)
- evidence_refs: list[str] (non-empty)

**Output:**
- ExecutionResult { status, event_ids[] }

No optional parameters. No defaults. No inference.

---

## 2. ExecutionEnvelope (Minimum Fields)

- execution_scope
- allowed_actions[]
- allowed_venues[]
- max_size
- time_limit_utc
- idempotency_key
- risk_flags[]

Missing or extra fields → DENY.

---

## 3. ApprovalArtifact (Minimum Fields)

- approval_id
- decision = APPROVE | DENY
- approver_id
- expires_at_utc
- policy_refs[]

Expired or decision ≠ APPROVE → DENY.

---

## 4. Capability Declaration (Static)

Adapter MUST ship with:
- CAPABILITIES.yaml (read-only at runtime)

Request not in CAPABILITIES → DENY.

---

## 5. Mandatory Events

Adapter MUST emit:
- EXECUTION_REQUESTED
- EXECUTION_AUTHORIZED
- EXECUTION_STARTED
- EXECUTION_COMPLETED | EXECUTION_FILLED
- EXECUTION_BLOCKED (on any deny)
- AUDIT_LOGGED

Silent execution is forbidden.

---

## 6. Fail-Closed Matrix

If ANY of the following → EXECUTION_BLOCKED:
- approval invalid
- envelope mismatch
- evidence missing
- idempotency replay
- timeout / ambiguous external response
- registry/schema mismatch

---

## 7. Test Invariants (Non-Negotiable)

- deny_without_approval
- deny_on_expired_approval
- deny_on_missing_capability
- deny_on_missing_evidence
- deny_on_timeout
- audit_event_on_all_paths

