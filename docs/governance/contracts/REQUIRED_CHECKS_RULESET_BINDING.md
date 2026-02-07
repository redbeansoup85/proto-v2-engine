# REQUIRED CHECKS ↔ RULESET BINDING (LOCK)

- Source of Truth(SOT): GitHub Ruleset **name** is the binding key.
- Binding key: `protect-main`
- The gate MUST read required status checks from the ruleset bound by name.
- The gate MUST compare against the repo contract artifact (required checks contract).
- Any mismatch MUST fail-closed.
- Any ruleset API access failure (401/403/404/invalid JSON) MUST fail-closed.
- Debug visibility is allowed only via `workflow_dispatch` (manual run), not on PR/push.
- Runtime deps allowed in this workflow: `PyYAML>=6.0` only.
### Governance Change Merge Rules (LOCKED)

1. Any change under `docs/governance/**` MUST be merged with token A-MINOR or A-MAJOR.
2. The PR title is the single source of truth for the merge token (squash merge required).
3. A-PATCH merges touching governance paths are fail-closed on both PR and main push.

# Notes:
# - Squash merge is enforced to ensure PR title token is authoritative.
# - A-PATCH merges on governance paths remain fail-closed by design.
# - These rules form the operational "LOCK layer" for governance updates.
