# CARD SCHEMA v0.1 (LOCK CANDIDATE)

> Purpose: define a minimal, enforceable “Card” contract for Meta OS.
> Cards are *contracts*, not recommendations. They must be audit-ready and fail-closed.

---

## 0) Constitutional Principles (Enforced)

- A Card is a **Contract**, not an instruction.
- A Card **must not** be used as “auto-decision” justification.
- A Card **must not** be used as “auto-execution” justification.
- Missing/ambiguous inputs are **Fail-Closed**.
- Cards must be **explainable** and **auditable**.
- Locked cards are **immutable**.

---

## 1) Locations & Invariants

### 1.1 Tasks folder (runtime contract)
- Root: `tasks/`
- Valid TASK_LOOP location: `tasks/<l1>/<l2>/TASK_LOOP.yaml` (depth=2)
- `_template/` is excluded from validation.

### 1.2 Schemas folder (case-safe invariant)
- Schemas live under `schemas/`
- Legacy `SCHEMAS/` directory is forbidden (fail-closed).

---

## 2) Card Types

Two primary types:

- **DECISION**: expresses allow/block conditions and records decision outcome (PASS/FAIL/BLOCKED).
- **EXECUTION**: expresses a procedure/commands with safety gates, verification, rollback.

---

## 3) CORE Fields (Required for ALL Cards)

These fields apply to both DECISION and EXECUTION.

```yaml
CARD_SCHEMA_VERSION: "0.1"
CARD_TYPE: "DECISION" | "EXECUTION"
CARD_ID: "<deterministic-id>"

STATUS: "DRAFT" | "LOCKED"
MUTABILITY: "CONTROLLED" | "FORBIDDEN"

CREATED_AT_UTC: "YYYY-MM-DDTHH:MM:SSZ"
OWNER: "<team|role>"
DOMAIN: "<sentinel|auralis|ops|meta>"

INTENT: "<one-line intent>"
WHY_NOW: "<trigger/rationale>"

ALLOW_CONDITIONS:
  - "<verifiable condition 1>"
BLOCK_CONDITIONS:
  - "<verifiable condition 1>"

RISK:
  CLASS: "LOW" | "MED" | "HIGH"
  BREAK_RISK: "<what breaks if wrong>"
  FAIL_CLOSED_DEFAULT: true
3.1 Fail-Closed Rules (CORE)
Validation MUST fail if:

Missing any of: CARD_SCHEMA_VERSION, CARD_TYPE, CARD_ID, STATUS, MUTABILITY, CREATED_AT_UTC, INTENT

STATUS=LOCKED but MUTABILITY!=FORBIDDEN

ALLOW_CONDITIONS is empty (no allow-basis)

CREATED_AT_UTC is not UTC Zulu format (...Z)

4) DECISION Card (Additional Fields)
DECISION:
  SCOPE: "<what this decision governs>"
  INPUTS_REQUIRED:
    - "<input name>"
  EVIDENCE:
    - "<artifact/log pointer>"
  OUTPUT:
    DECISION_RESULT: "PASS" | "FAIL" | "BLOCKED"
    REASON: "<brief reason>"
4.1 Decision Constraints
DECISION cards must not embed “forced action”. They specify conditions + outcome record only.

EVIDENCE must be pointer-like and verifiable (file path, registry entry, log id, PR, etc.).

5) EXECUTION Card (Additional Fields)
EXECUTION:
  EXECUTION_SCOPE: "simulation" | "dry_run" | "automation" | "manual"
  COMMANDS:
    - "<command or procedure step>"
  SAFETY_GATES:
    - "<gate name>"
  VERIFICATION:
    - "<post-check>"
  ROLLBACK:
    - "<rollback step>"
5.1 Execution Safety Constraints (Fail-Closed)
Validation MUST fail if:

EXECUTION_SCOPE=automation AND any of SAFETY_GATES, ROLLBACK is empty

COMMANDS is empty or contains placeholder-only content.

6) Minimal Card Examples
6.1 DECISION example
CARD_SCHEMA_VERSION: "0.1"
CARD_TYPE: "DECISION"
CARD_ID: "DEC-LOOP-GATE-PRBODY-v1"

STATUS: "LOCKED"
MUTABILITY: "FORBIDDEN"

CREATED_AT_UTC: "2026-02-03T00:00:00Z"
OWNER: "governance"
DOMAIN: "meta"

INTENT: "Fail-closed if PR body missing required keys"
WHY_NOW: "Prevent silent regressions in governance gates"

ALLOW_CONDITIONS:
  - "PR body includes DESIGN_ARTIFACT, STAGE, WHY_NOW, VERIFY, BREAK_RISK"
BLOCK_CONDITIONS:
  - "PR body is empty or missing required keys"

RISK:
  CLASS: "LOW"
  BREAK_RISK: "PRs merge without governance context"
  FAIL_CLOSED_DEFAULT: true

DECISION:
  SCOPE: "Pull request governance metadata gate"
  INPUTS_REQUIRED:
    - "pull_request.body"
  EVIDENCE:
    - ".github/workflows/design_gate.yml"
  OUTPUT:
    DECISION_RESULT: "PASS"
    REASON: "All required fields present"
6.2 EXECUTION example
CARD_SCHEMA_VERSION: "0.1"
CARD_TYPE: "EXECUTION"
CARD_ID: "EXE-TASK-LOOP-VALIDATE-v1"

STATUS: "DRAFT"
MUTABILITY: "CONTROLLED"

CREATED_AT_UTC: "2026-02-03T00:00:00Z"
OWNER: "ops"
DOMAIN: "meta"

INTENT: "Validate TASK_LOOP YAML files against schema"
WHY_NOW: "Ensure tasks folder is never empty and remains machine-verifiable"

ALLOW_CONDITIONS:
  - "schemas/task_loop.schema.json exists"
BLOCK_CONDITIONS:
  - "schema missing or YAML invalid"

RISK:
  CLASS: "MED"
  BREAK_RISK: "invalid task loops bypass CI and reduce auditability"
  FAIL_CLOSED_DEFAULT: true

EXECUTION:
  EXECUTION_SCOPE: "automation"
  COMMANDS:
    - "python scripts/validate_task_loop.py tasks --schema schemas/task_loop.schema.json"
  SAFETY_GATES:
    - "loop-gate/gate"
  VERIFICATION:
    - "CI step summary contains OK: TASK_LOOP validation passed."
  ROLLBACK:
    - "Revert commit introducing invalid TASK_LOOP and re-run CI"
7) Versioning & Locking
CARD_SCHEMA_VERSION increments only when compatibility changes.

STATUS=LOCKED implies:

MUTABILITY=FORBIDDEN

Any change requires a new CARD_ID (new version) and PR review.

