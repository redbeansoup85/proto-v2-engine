# CONSTITUTION MAP

Status: LOCKED
Scope: B0 Core OS / All B1 Modules
Principle: Fail-Closed · Deterministic · Audit-Ready

---

## 1) Constitutional Layer (L4)

- **L4-BOOTSTRAP-PIPELINE**
  - Defines immutable pipeline: Change → Determinism → Verification → Gates → Audit → Execution

- **HUMAN_BOUNDARY**
  - Defines human authority and non-delegable rights

- **PROHIBITIONS**
  - Defines forbidden actions/paths and irreversible constraints

- **APPROVAL_RIGHTS**
  - Defines approval authority, scope, expiry, and accountability

---

## 2) Enforcement Layer (CI / Gates)

### Core Gates
- **bootstrap_ref_gate**
  - Rule: execution card must reference `LOCK-BOOTSTRAP` in `requires:`
  - Activation: conditional until execution cards exist; then enforced fail-closed

### LOCK Gates
- **LOCK-1 Public Boundary Gate**
  - Prevents leakage of internal paths/tools/secrets to public docs

- **LOCK-2 Approval Chain Gate**
  - Requires approval events to be valid, scoped, and (if enabled) expirable

- **LOCK-3 Observer / Replay / Hash Chain Gate**
  - Requires observable evidence chain and replayability of decisions/events

---

## 3) B1 Integration Layer (Execution Cards)

Execution Cards are **non-executable intent definitions**.
They become executable only through B0 Bootstrap Pipeline + Gates + Audit.

Minimum requirement for any card:
- must declare `requires: - LOCK-BOOTSTRAP`
- must be compatible with LOCK-2/3 if execution implies external action

Example:
- `execution_cards/SENTINEL_TRADE_CARD.yaml`

---

## 4) Non-Bypass Declaration

Any bypass of:
- Determinism layer,
- Gate enforcement,
- Audit chain,
invalidates system trust and must be rejected by design.
