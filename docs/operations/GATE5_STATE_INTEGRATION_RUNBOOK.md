# Gate 5 — State & Integration Boundary Runbook (LOCK Candidate)

RECORD_ID: GATE5-RUNBOOK-METAOS-2026-01
SYSTEM: Meta OS
LEVEL: L5 (Operational Runbook / Boundary Enforcement)
STATUS: LOCK_CANDIDATE
EFFECTIVE_DATE: 2026-01-18

---

## 1. Purpose

This runbook defines operational rules and failure-handling procedures for Gate 5:
the boundary between internal state transitions and external integrations (adapters).

Primary guarantee:
External integration failures MUST NOT corrupt Core state.

---

## 2. Definitions

- Core State: internal decision/state records and invariant storage owned by Meta OS.
- Integration: any interaction with external/domain systems (via adapters).
- State Transition Record (STR): immutable record describing a proposed or executed state transition.
- Fail-Closed: if uncertainty exists, do not proceed; preserve invariants.

---

## 3. Non-Negotiables (Invariants)

- Integration is always adapter-mediated (never direct from Core).
- No integration side effects without explicit human approval path.
- Core state transitions are atomic and auditable.
- Integration failure never implies state success.
- Retry/replay must be idempotent and auditable.

---

## 4. Operating Modes

### Mode A — Observe/Explain/Audit (Default)
- No integrations executed.
- Only signals, explanations, and audit logs produced.

### Mode B — Human-Approved Action Proposal
- System produces options and required approvals.
- No direct execution until human confirmation.

### Mode C — Human-Approved Integration Attempt
- Integration attempts are executed only through adapters.
- Must produce an audit event (success or failure).

---

## 5. Failure Scenarios & Required Responses

### S1: Adapter Unavailable / Timeout
Symptoms:
- adapter call fails, timeout, or network unreachable

Required response:
- Abort integration attempt
- Preserve Core state (no transition)
- Emit audit event: INTEGRATION_FAILED_TIMEOUT
- Require human re-approval for retry if context changed

### S2: Adapter Returns Invalid Schema / Contract Violation
Symptoms:
- missing required fields, invalid schema_version, malformed payload

Required response:
- Reject payload
- Emit audit event: ADAPTER_CONTRACT_VIOLATION
- Gate 3 remains CLOSED (unless explicitly open); do not proceed

### S3: Partial Integration Success (Ambiguous)
Symptoms:
- external system returns non-deterministic or partial confirmation

Required response:
- Treat as failure (fail-closed)
- Emit audit event: INTEGRATION_AMBIGUOUS_RESULT
- Require explicit human review before any further attempt

### S4: Duplicate Integration Request / Replay
Symptoms:
- same approval_id / execution_id observed again

Required response:
- Apply idempotency guard
- Emit audit event: INTEGRATION_REPLAY_BLOCKED
- Do not re-execute side effects

### S5: Audit Sink Unavailable
Symptoms:
- cannot write audit event

Required response:
- Abort integration attempt
- Emit best-effort local error record
- Require audit sink restoration before resuming

### S6: Core State Transition Requested Without Approval
Symptoms:
- state transition requested without explicit human approval reference

Required response:
- Reject request
- Emit audit event: STATE_TRANSITION_MISSING_APPROVAL
- No state mutation

---

## 6. Approval & Change Control

- Any integration attempt must reference:
  - approval_id
  - execution_id (or correlation_id)
  - scope (single domain)
  - duration (finite)

- Any deviation from this runbook requires:
  - documented rationale
  - explicit human owner approval
  - audit trail

---

## 7. Minimal Audit Fields (Required)

Every Gate 5 relevant event MUST include:
- event_id
- ts_iso
- actor
- action
- outcome
- approval_id (if applicable)
- execution_id / correlation_id
- refs (documents, payload references)

---

## 8. Exit Criteria for LOCK

This runbook may be promoted from LOCK_CANDIDATE to LOCKED when:
- At least one pilot integration is run end-to-end under human approval,
- All failure scenarios S1–S6 are test-covered or operationally exercised,
- No case exists where integration failure corrupts Core state,
- Change control process is demonstrated in practice.

