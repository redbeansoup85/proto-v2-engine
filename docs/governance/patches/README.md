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
- Any change under `docs/governance/**` requires:
  - `A-MINOR:` or `A-MAJOR:` token (per CI gate)
- `A-PATCH:` is not permitted for governance-doc changes.

---

## Patch Records

<!-- PATCH_RECORDS_BEGIN -->

| Date (TZ) | Patch | Scope | Change Type | Notes |
|---|---|---|---|---|
| 2026-02-02 (Australia/Sydney) | `PATCH-20260202-FASTAPI-LIFESPAN.md` | Runtime lifecycle / framework deprecation hardening | A-MINOR | — |

<!-- PATCH_RECORDS_END -->
---

## Quick checks

### Markdown fence balance (local)
Use this to detect unmatched code fences:

- Count triple fences should be even.

