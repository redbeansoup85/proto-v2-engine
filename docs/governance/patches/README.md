# Governance Patches Index

This directory contains **LOCKDOC patch records** for governance/runtime changes.
Each patch record is an **audit-grade, immutable** markdown artifact.

---

## Rules (Fail-Closed)

### 1) File naming
- Format: `PATCH-YYYYMMDD-<TOPIC>.md`
- Example: `PATCH-20260202-FASTAPI-LIFESPAN.md`

### 2) Required metadata block
Each patch must include a YAML metadata block near the top:

- `DOCUMENT_ID`
- `SYSTEM`
- `SCOPE`
- `STATUS` (LOCKED)
- `MUTABILITY` (FORBIDDEN)
- `TIMEZONE`
- `EFFECTIVE_DATE`
- `CHANGE_TYPE` (A-MAJOR / A-MINOR / A-PATCH)
- `RISK`
- `BEHAVIOR_CHANGE`

### 3) References required
Each patch must include references:
- PR number
- Commit SHA
- Tag (if used)
- CI run id(s)

### 4) Classification token policy (repo gate)
- Any change under `docs/governance/**` **REQUIRES**:
  - `A-MINOR:` or `A-MAJOR:` token (per CI gate)
- `A-PATCH:` is **NOT permitted** for governance documentation.

Violation results in **PR rejection**.

### 5) Drift gate (CI) — REQUIRED
Any PR that changes `docs/governance/patches/**` **MUST** keep
`docs/governance/patches/README.md` consistent with
`tools/update_governance_patches_index.py`.

CI behavior:
- The expected Patch Records table is regenerated automatically
- If a diff is detected, the build **FAILS (fail-closed)**

This guarantees:
- No silent governance drift
- No human-maintained indexes
- Deterministic, reproducible patch history

---

## Patch Records

> **Policy (Fail-Closed):**  
> The Patch Records table below is **machine-maintained**.  
> Human edits are forbidden. Update only via `./tools/update_governance_patches_index.py`.

<!-- PATCH_RECORDS_BEGIN -->

| Date (TZ) | Patch | Scope | Change Type | Notes |
|---|---|---|---|---|
| 2026-02-02 (Australia/Sydney) | `PATCH-20260202-FASTAPI-LIFESPAN.md` | Runtime lifecycle / framework deprecation hardening | A-MINOR | — |

<!-- PATCH_RECORDS_END -->

---

## Quick checks (local)

### Markdown fence balance
- Ensure the number of triple-backtick fences is even

### Index regeneration (manual)
```bash
./tools/update_governance_patches_index.py

