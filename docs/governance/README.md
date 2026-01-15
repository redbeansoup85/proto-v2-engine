# Governance — Meta OS (v1.0)

**Status:** LOCKED  
**Scope:** Governance control plane (documents + contracts + enforcement)

This directory is the authoritative source of truth for Meta OS governance rules.
Implementation must conform to these artefacts; implementation convenience must not override them.

---

## Artefacts (v1.0)

### L4 — Constitution
- `constitution_AQ.md` — Approval Queue (responsibility fixation and deterministic evaluation)

### L3 — Operational Governance
- `operational_canon_v1.0.md` — Learning → Policy Cycle (proposal eligibility, rate limiting, human gate)
- `operational_pack_v1.0.md` — Proposal schema + human checklist + canon index (enforceable contracts)
- `governance_map_v1.0.md` — Single-page governance map (system-wide boundary truth)

---

## Change Control

- **No silent changes.**
- Any governance change requires:
  1) Document revision
  2) Version bump
  3) Code + tests aligned
  4) New tag release

---

## Lock Statement

**LOCKED — Governance v1.0**
