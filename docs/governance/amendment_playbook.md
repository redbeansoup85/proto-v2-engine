# Amendment Playbook — Governance / Contracts

Status: LOCK CANDIDATE (v0.1)

## Purpose
Define a deterministic, auditable procedure for changing any LOCKED governance artifact:
- Constitution sections (L4)
- Operational canon/pack contracts (L3)
- Engine/ports/queues safety contracts (v0.x LOCK candidates)

No silent changes. Every change must be attributable, reviewable, and revertible.

## Scope
This playbook applies when changing:
- Any file under `proto-v2-engine/docs/governance/constitution_*.md`
- Any file referenced by `core/governance/constitution_refs.py`
- Any file marked as LOCK / LOCK CANDIDATE in docs or tags
- Any interface/contract surface used as a gate (ports, approval queue reducer, transition facade)

## Amendment Types
### Patch (A-PATCH)
- Clarification only (no behavior change)
- Examples, wording, formatting
- Requires: single reviewer (human), tests unchanged

### Minor (A-MINOR)
- Additive change (backward compatible)
- New optional fields, new docs sections, new endpoints with no bypass
- Requires: reviewer + test addition + version bump in the affected contract/doc header

### Major (A-MAJOR)
- Breaking change or semantics change to a gate/contract
- Any change affecting fail-closed behavior or approval semantics
- Requires: reviewer + explicit rationale + migration notes + new tag (lock-candidate) + rollout plan

## Required Artifacts (per amendment)
1) Change Summary (what/why)
2) Diff (code + docs)
3) Risk Notes (what could break)
4) Tests (proof of invariants)
5) Tagging/Versioning decision

## Procedure (Deterministic)
1) Identify target artifact(s) and current lock tag/version
2) Classify amendment type (Patch/Minor/Major)
3) Create branch: `amend/<scope>/<short-name>`
4) Implement change + tests
5) Run:
   - Root guard: `cd meta-os && pytest`
   - Engine full: `cd proto-v2-engine && pytest -q`
6) Update references:
   - Constitution docs: add "Change Control" note
   - `constitution_refs.py`: add/update paths/requirements
7) Commit message format:
   - `A-PATCH: ...` / `A-MINOR: ...` / `A-MAJOR: ...`
8) Tag:
   - `vX.Y-lock-candidate` (when a lock boundary is affected)
   - `vX.Y-lock` (after review/acceptance)

## Enforcement Notes
- Any gate/contract change without tests is invalid.
- Any fail-open drift is invalid.
- Reducer semantics changes require explicit test coverage.

