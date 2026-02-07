# Flow Space OS — Responsibility-First Core (One Pager)

## What it is
Flow Space OS is a **responsibility-first execution operating system**.
It ensures automation and agent-driven actions are **auditable, reproducible, and fail-closed** by design.

## The problem
As systems become agentic, risk shifts to **execution risk**:
- unclear authority,
- non-reproducible behavior,
- weak post-incident explanations.

## Our solution
We separate the system into two layers:

### B0 Core OS (Engine)
A governance and execution engine that enforces:
- **Determinism** (local = CI reproducibility)
- **Fail-Closed Gates** (no bypass)
- **Approval & Expiry** (scoped authority with TTL)
- **Audit Chain** (tamper-evident evidence logs)

### B1 Modules (Applications)
Domain modules that define intent and signals, but **do not execute independently**.
They must pass B0 pipeline to act.

## Pipeline
Change / Intent
→ Determinism Layer
→ Verification Layer
→ LOCK Gates
→ Audit Chain
→ Execution / Release (only if all passed)

## Why it matters
- Accountability by default
- Safety through fail-closed design
- Compliance-ready evidence
- Scalable modular expansion

## Current status
- Core governance gates (LOCK-1/2/3) operational
- Bootstrap pipeline constitution established
- Execution cards integrated under constitutional enforcement
