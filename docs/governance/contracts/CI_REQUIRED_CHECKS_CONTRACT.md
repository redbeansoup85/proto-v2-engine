# CI REQUIRED CHECKS CONTRACT (v1.0)

## Purpose
Protect branch rulesets from silent breakage caused by mismatched
GitHub Actions check names vs required_status_checks.

## Canonical Rule
- Required checks MUST match GitHub CheckRun.name exactly.
- Canonical source is `statusCheckRollup.__typename == "CheckRun"` → `name`.

## Workflow Naming Rules
- workflow `name:` MUST be unique.
- each job MUST define `name:` explicitly.
- job id `gate` is FORBIDDEN if more than one workflow uses it.
- required_status_checks MUST reference:
  - `<workflow-name>/<job-name>` OR
  - `<job-name>` (if repo standardised that way)

## Change Control
Any change to:
- `.github/workflows/*.yml`
- branch ruleset required checks

REQUIRES:
- Updated evidence (CI log showing CheckRun.name)
- This contract remains satisfied (gate must pass)

## Fail-Closed
If any required check cannot be resolved to an existing workflow job,
merge MUST be blocked.
