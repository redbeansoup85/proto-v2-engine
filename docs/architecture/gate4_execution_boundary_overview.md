# Gate4 — Execution Boundary Overview

## Purpose

Gate4 defines and locks the execution responsibility boundary.
The goal is to make **execution explicit, auditable, and non-implicit**,
without requiring readers to inspect internal engine code.

This document is the canonical high-level explanation for:
- external auditors
- investors
- new contributors
- future maintainers

---

## Core Principle

> **No execution without an explicit ExecutionEnvelope.**

An ExecutionEnvelope is a contract that authorizes *if*, *what*, and *how*
a side effect may occur.

---

## Boundary Model

### 1. API Boundary (Minting Only)

- ExecutionEnvelope **can only be minted at the API boundary**.
- Core engine code **cannot create or modify envelopes**.
- Envelope metadata includes:
  - `envelope_id`
  - issuance time
  - expiry
  - issuer
  - version

This guarantees that execution authority is externally attributable.

---

### 2. Core Engine (Validate or Deny)

- Core functions receive an ExecutionEnvelope as an input.
- Missing envelope ⇒ **fail-closed**.
- Core may:
  - validate
  - enforce constraints
  - deny execution

Core may **never implicitly execute side effects**.

---

### 3. Execution Choke Point

All side effects flow through a single function:



This choke point enforces, by contract:

- action allow / deny
- data source scope
- confidence floor
- latency / resource budgets
- expiry checks

Any violation results in immediate denial.

---

## Replay & Idempotency

- The canonical execution key is:



- This prevents:
  - silent replays
  - ambiguous re-execution
  - hidden retries

Execution without a new envelope is structurally impossible.

---

## Auditability

- Every enforcement decision emits an audit event.
- Audit events follow a fixed JSON schema.
- Outcomes are reproducible from logs alone.

This enables post-hoc reconstruction without engine introspection.

---

## What Gate4 Is Not

- Gate4 does **not** add new business logic.
- Gate4 does **not** automate decisions.
- Gate4 does **not** expand execution capability.

Gate4 only constrains and formalizes responsibility.

---

## Summary (One Sentence)

> Gate4 ensures that **execution is explicit, constrained, attributable,
> and auditable — by structure, not convention.**
