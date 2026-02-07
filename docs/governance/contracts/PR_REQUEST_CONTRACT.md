# PR_REQUEST_CONTRACT (v1.0)

## Purpose
This contract defines the **mandatory PR body schema** enforced by `loop-gate`.
It prevents ambiguous PR intent and guarantees audit-ready change rationale.

## Scope
Applies to **all pull requests** in this repository.

## Required Fields (Fail-Closed)
Each PR body MUST include the following keys, exactly as written (case-sensitive, ASCII colon `:`):

DESIGN_ARTIFACT:
STAGE:
WHY_NOW:
VERIFY:
BREAK_RISK:

## Field Definitions
- DESIGN_ARTIFACT: Primary artifact(s) changed (paths/files). Multiple allowed, comma-separated.
- STAGE: Change stage token (e.g., A-PATCH, A-MINOR, A-MAJOR).
- WHY_NOW: Rationale for timing and necessity.
- VERIFY: Deterministic verification steps (commands, checks).
- BREAK_RISK: Explicit risk statement (impact, rollback).

## Validation Rules
- Missing any required key → Fail-Closed.
- Keys must appear with ASCII `:` and at least one non-empty value.
- Order is not enforced; presence is.

## Example (Minimal Valid)
DESIGN_ARTIFACT: .github/workflows/lock3-gate.yml
STAGE: A-PATCH
WHY_NOW: Required check expected by ruleset but not produced on PRs
VERIFY: gh pr checks --watch
BREAK_RISK: Low — workflow trigger metadata only

## Governance
- Owner: Repo Maintainers
- Enforcement: loop-gate (PR_REQUEST fields)
- Changes require maintainer approval.
