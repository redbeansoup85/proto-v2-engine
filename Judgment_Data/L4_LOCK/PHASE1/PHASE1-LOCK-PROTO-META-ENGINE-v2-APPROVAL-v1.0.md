# 🔒 PHASE-1 LOCK DECLARATION
Proto Meta Engine v2 — Approval Layer

## 1) Metadata (Immutable)

DOCUMENT_ID: PHASE1-LOCK-PROTO-META-ENGINE-v2-APPROVAL-v1.0  
SYSTEM: Proto Meta Engine v2  
SUBSYSTEM: Approval Layer / Execution Control  
LEVEL: L4 (LOCK Declaration)  
STATUS: LOCKED  
MUTABILITY: FORBIDDEN  
EFFECTIVE_DATE: 2026-01-24 (Australia/Sydney)  
CLASSIFICATION: Internal / Audit-Ready  
HASH_POLICY: Deterministic (content-hash recorded at tag time)

---

## 2) Scope (Immutable)

### Included
- Execution Run API Contract
- Approval tables
- execution_runs
- Idempotency enforcement
- Approval expiry
- Fail-closed hotfix migration (ensure_execution_runs_0001)

### Excluded
- FastAPI on_event → lifespan migration
- UI
- Deployment / CI pipeline

Principle: Phase-1 prohibits automatic judgment and automatic execution.

---

## 3) Reproducibility Guarantee (Immutable)

Phase-1 LOCK is verified by a single deterministic command sequence:
- Empty DB
- alembic upgrade head
- Single head confirmed
- pytest -q passes

Authoritative script: scripts/lock/phase1_verify.sh

---

## 4) Fail-Closed Policy (Immutable)

Migration failure, env.py import failure, or DB corruption MUST cause
startup/test failure (fail-closed).

---

## 5) Warning Acceptance Policy (Immutable)

FastAPI on_event DeprecationWarning is accepted in Phase-1.
lifespan migration is deferred to Phase-2.

---

## 6) Test Gate (Immutable)

pytest -q must pass.
DB reset before tests is mandatory.

---

## 7) Lock Declaration

Phase-1 of Proto Meta Engine v2 / Approval Layer is hereby LOCKED.
Any modification requires Phase-2 design and a new LOCK.
