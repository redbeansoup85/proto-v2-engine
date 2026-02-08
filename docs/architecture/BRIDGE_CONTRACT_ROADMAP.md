# BRIDGE CONTRACT ROADMAP

## Purpose
This document defines the evolution path of the Auralis Bridge Contract.
Contracts are treated as protocol-level artifacts and are versioned independently of implementation.

---

## v0.1 — Permissive / Contract-First (Current)
**Status:** Active (PR required)

### Characteristics
- Contract schema validation only.
- E2E execution is optional.
- Response shape is validated only for presence of minimal required keys.
- Intended to unblock early integration without runtime coupling.

### Required Guarantees
- JSON object response.
- Presence of `status` field.
- Deterministic failure (fail-closed) on contract violation.

### CI Policy
- Required on PR:
  - `auralis-bridge-gate v0.1`

---

## v0.2 — Strict / E2E Enforced
**Status:** Defined (Not yet required)

### Characteristics
- Full response schema enforcement.
- `additionalProperties=false`.
- Mandatory headers: `X-Request-Id`, `X-Audit-Trace`.
- Timeout and retry policy enforced.
- Docker-compose E2E execution required.

### Activation Conditions
v0.2 becomes **required** when all of the following are true:
- Auralis service boots reliably in CI via docker-compose.
- `/health` endpoint passes stability checks.
- `/invoke` endpoint responds deterministically to minimal payload.
- Audit/trace identifiers are present and verifiable.

### CI Policy
- Required on main branch only after activation:
  - `auralis-bridge-gate v0.2 (E2E strict)`

---

## Versioning Rules
- Backward-compatible expansions occur in v0.1.
- Restrictions and hard enforcement occur in v0.2+.
- Breaking changes require a new major contract version.

---

## Notes
- Contract stability > implementation flexibility.
- Gate behavior must always be explainable and auditable.
