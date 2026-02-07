# REQUIRED CHECKS ↔ RULESET BINDING (LOCK)

- Source of Truth(SOT): GitHub Ruleset **name** is the binding key.
- Binding key: `protect-main`
- The gate MUST read required status checks from the ruleset bound by name.
- The gate MUST compare against the repo contract artifact (required checks contract).
- Any mismatch MUST fail-closed.
- Any ruleset API access failure (401/403/404/invalid JSON) MUST fail-closed.
- Debug visibility is allowed only via `workflow_dispatch` (manual run), not on PR/push.
- Runtime deps allowed in this workflow: `PyYAML>=6.0` only.
