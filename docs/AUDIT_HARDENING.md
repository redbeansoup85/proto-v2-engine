# Audit Hardening (v3.x)

## Goal
Increase tamper-resistance and provenance of the Audit Chain while preserving:
- Fail-closed behavior
- Deterministic replay
- Minimal operational friction

## Threat Model
### Assets
- Audit record integrity (no modification)
- Audit record ordering (no deletion/reorder without detection)
- Provenance (who/what produced the record)
- Policy decision traceability (policy_id + policy_sha pinned)

### Attack Surfaces
- Local file modification / deletion
- Replay / duplicate injection
- Producer impersonation (fake device/service id)
- Key leakage (future signing)

## Invariants (MUST hold)
- I1: Append-only semantics.
- I2: Hash-linked chain; replay reproduces record hashes.
- I3: Record includes policy identifiers and schema version.
- I4: Verification failure is fail-closed.
- I5: Time is advisory; determinism takes priority in CI.

## Roadmap
1) Canonical JSON hashing
2) Record envelope standardization
3) Signing v0 (local key, structure proof)
4) Signing v1 (managed keys + rotation)
5) Device attestation
6) WORM / sealing storage
