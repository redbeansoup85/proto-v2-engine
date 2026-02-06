# LOCK-4 Security Overview (Design-only, v0.1)

## Purpose
LOCK-4 introduces cryptographic identity, authorization, and signatures on top of existing immutable logs:
- LOCK-2: approval chain immutability
- LOCK-3: observer/replay chain immutability
- LOCK-4: actor identity + authorization + signature verification (fail-closed)

LOCK-4 is **design-only** in v0.1: no enforcement is active yet. This document defines reserved fields and integration boundaries.

## Non-goals (v0.1)
- No production key management (Vault/HSM) implementation
- No signature verification gate in CI
- No breaking changes to LOCK-2/LOCK-3 schemas or gates

## Reserved Field Slots (forward-compatible)

### Observer Event (LOCK-3 artifact)
LOCK-4 reserves the following optional fields (not enforced in LOCK-3):
- `actor`: identity of emitter
- `signature`: cryptographic signature of canonical payload

Example:
```json
{
  "event_id": "evt_...",
  "execution_run_id": "run_...",
  "ts": "2026-02-07T00:00:00Z",
  "metrics": { "m1": 1 },

  "actor": { "type": "human|ai|system", "id": "string" },
  "signature": { "alg": "ed25519|secp256k1", "value": "base64" }
}
Replay Packet (LOCK-3 artifact)
LOCK-4 reserves optional authorization fields (not enforced in LOCK-3):

authorization.scope

authorization.issued_at

authorization.expires_at

Example:

{
  "packet_id": "pkt_...",
  "source_event_id": "evt_...",

  "authorization": {
    "scope": "replay.read|replay.execute",
    "issued_at": "2026-02-07T00:00:00Z",
    "expires_at": "2026-02-08T00:00:00Z"
  }
}
Future Gate (LOCK-4) — Planned Behavior
A new CI/workflow gate will be introduced (separate from existing gates):

Signature verification FAIL → FAIL-CLOSED

Missing actor/signature when required by policy → FAIL-CLOSED

Expired authorization on replay → FAIL-CLOSED

Issuer/subject mismatch rules (e.g., approver ≠ executor) → FAIL-CLOSED

Key Material Policy (Design)
Keys must never be committed into repo.

CI secrets must not contain long-lived private keys.

Future integration targets: Vault / HSM / KMS (implementation deferred).

Integration Boundary
LOCK-4 must not modify existing LOCK-2/LOCK-3 immutability semantics.
All enforcement is isolated to a dedicated LOCK-4 gate.
