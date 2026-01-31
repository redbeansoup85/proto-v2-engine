# 🔒 PHASE 1 LOCK — ExecutionRun + Approval Gate (Fail-Closed)

## 1) Metadata (Immutable)

RECORD_ID: LOCK-PHASE1-EXECUTIONRUN-APPROVALGATE-2026-01-21-001
SYSTEM: Proto V2 Engine (infra/api)
DOMAIN: Execution Control
PHASE: Phase 1
STATUS: LOCKED
CLASSIFICATION: Internal / Demonstration-Ready
MUTABILITY: FORBIDDEN
EFFECTIVE_DATE: 2026-01-21

---

## 2) Purpose (What is Frozen)

This LOCK freezes the minimal fail-closed execution initiation flow:

1) An execution run can be created exactly once per (project_id, idempotency_key).
2) Every created execution run starts BLOCKED until approval is granted.
3) Approval is enforced by persisted approval records, decision events, and FK constraints.
4) A repeated request with identical payload returns a deterministic dedup response.

No external actions (dispatch, webhook, notify, execute) are permitted in this phase.

---

## 3) Invariants (Hard Guarantees)

### 3.1 Idempotency + Dedup
- Unique key: (project_id, idempotency_key)
- Same key + same fingerprint → same execution_id (dedup)
- Same key + different fingerprint → reject (409)

### 3.2 Fail-Closed by Default
- status = BLOCKED
- blocked_reason = approval_pending

### 3.3 Approval Gate Persistence
- 1:1 mapping between execution_runs and approvals
- approvals.execution_run_id → execution_runs.id (ON DELETE CASCADE)

### 3.4 Audit Traceability
- All outcomes emit audit events
- All approval decisions are persisted

### 3.5 SQLite Integrity
- PRAGMA foreign_keys=ON enforced per connection

---

## 4) Allowed Endpoints

- POST /api/v1/execution/run
- GET  /api/v1/execution/run/by_key
- GET  /api/v1/execution/run/{execution_id}
- POST /approvals/{execution_id}/approve
- POST /approvals/{execution_id}/reject

---

## 5) Forbidden in Phase 1

- execute
- dispatch
- webhook
- notify
- external side effects

---

## 6) Acceptance Criteria

- New run → BLOCKED
- Approval → RUN
- Repeat request → dedup_hit=true

---

## 7) Change Control

Any modification requires a new LOCK record.

END.
