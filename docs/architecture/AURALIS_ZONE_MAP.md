# AURALIS_ZONE_MAP (v0.1)

## Purpose
This document defines Zone boundaries for Auralis-related components and the enforcement expectations.
Zones exist to prevent implicit coupling and to enforce fail-closed behavior.

---

## Zones

### 1) Orchestrator Zone
**Role**
- Owns pipeline sequence only.
- Must not contain domain logic, policy logic, or direct I/O.

**Allowed**
- Call Gate entrypoints.
- Assemble step order: ingest -> validate -> decide -> execute -> audit (sequence only).
- Pass through trace identifiers.

**Forbidden (Hard)**
- Importing Vault modules directly.
- Importing Brain/Domain internal modules directly (bypassing Gate interfaces).
- Performing direct I/O (DB, FS, network, hardware).

---

### 2) Gate Zone
**Role**
- Boundary enforcement layer.
- Performs validation, policy checks, and controlled I/O bridging.
- Converts exceptions into typed errors and records audit events.

**Allowed**
- Validate request/response shapes.
- Enforce policy/approval.
- Call Vault (controlled).
- Emit fail-closed decisions.

**Forbidden (Hard)**
- Business/domain algorithm expansion beyond enforcement needs.
- Hidden side effects not recorded to audit.
- Non-deterministic behavior without explicit policy.

---

### 3) Vault Zone
**Role**
- Controlled I/O: persistent storage, audit chain, secret access (if any).
- Must be callable only via Gate (direct imports from Orchestrator/Brain are forbidden).

**Allowed**
- Append-only audit logs (jsonl).
- Hash chaining / integrity verification.
- Minimal storage adapters (file/db) behind stable interfaces.

**Forbidden (Hard)**
- Policy decisions.
- Calling Orchestrator or Brain.
- Network calls unless explicitly allowed and audited.

---

### 4) Brain (Domain/Decision) Zone
**Role**
- Pure decision logic and domain computation.
- No side effects. No direct I/O.

**Allowed**
- Deterministic computation.
- Pure transformations of validated inputs to decisions.

**Forbidden (Hard)**
- Any I/O.
- Any Vault access (direct or indirect).
- Hidden global state.

---

## Interface Contract Rules

### Contract-first
- Zone-to-zone communication must use contracts (schemas/types) at the boundary.
- Internal implementation may change; boundary contract must remain stable per version.

### Single-direction Calls
- Orchestrator -> Gate -> Vault
- Orchestrator -> Gate -> Brain (or Gate -> Brain if the architecture chooses it)
- No reverse calls (Vault must never call Gate/Orchestrator; Brain must never call outward).

---

## Fail-Closed Rules (Non-negotiable)
- Unknown input shape => reject + audit.
- Missing required headers/trace => reject + audit (consumer-side) OR generate trace according to policy.
- Unexpected response shape => reject + audit.
- Any exception escaping boundary => bug (must be wrapped to error payload).

---

## Mapping to Repo Paths (v0.1 Draft)
These mappings may be refined but the zone rules remain constant.

- Orchestrator: `orchestrator/`
- Gate: `tools/gates/` and `core/gate/` (if present)
- Vault: `core/vault/` or `vault/`
- Brain: `core/brain/` or `core/domain/` (pure logic modules)

---

## Enforcement
- `tools/gates/zone_static_gate.py` MUST block direct imports crossing forbidden boundaries.
- ARCH-LOCK applies to this file (changes require CODEOWNERS + required checks).

