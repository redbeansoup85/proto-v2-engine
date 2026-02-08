# ARCH-LOCK: Auralis Bridge + Zone Boundary (v0.1)

## Status
- **LOCKED**: Architecture boundary, contracts, and gates are now treated as constitutional artifacts.

## Scope (Locked Artifacts)
### Zone Boundary
- `docs/architecture/AURALIS_ZONE_MAP.md`
- `tools/gates/zone_static_gate.py`

### Bridge Contract & Consumer Gate
- `docs/architecture/BRIDGE_CONTRACT_ROADMAP.md`
- `contracts/bridge/auralis_bridge.contract.v0.1.schema.json`
- `contracts/bridge/auralis_bridge.contract.v0.2.schema.json`
- `tools/gates/auralis_bridge_gate.py`
- `.github/workflows/auralis-bridge-gate.yml`

## Change Control (Hard Rule)
- Any change to the above files requires:
  1) CODEOWNERS approval (mandatory)
  2) Required CI checks passing (no bypass)
  3) Versioned change note in `docs/architecture/BRIDGE_CONTRACT_ROADMAP.md` (if contract/gate behavior changes)

## CI Policy
- PR Required:
  - `zone-static-gate`
  - `auralis-bridge-gate (v0.1 contract)`
- Main Required (after E2E readiness):
  - `auralis-bridge-gate (v0.2 E2E strict)`

## Notes
- v0.1 is permissive (stability-first).
- v0.2 is strict (additionalProperties=false, required keys enforced).
- v0.2 is activated as required only when E2E boot is stable.
