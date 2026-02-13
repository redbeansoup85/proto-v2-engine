# AGENT_TASK_TEMPLATE (LOCK-safe)

## 0. Goal
- Clearly state what is being improved or added (1–2 lines).

## 1. Context
- Current state summary:
  - Related PR / branch:
  - Failing logs / symptoms:
  - Reproduction command(s):

## 2. Repo Constraints (NON-NEGOTIABLE)
- Fail-Closed policy must remain intact.
- LOCK / L4 document semantics must not change.
- No execution / order / decision boundaries may be crossed.
- Existing CI and governance gates must retain meaning.

## 3. Allowed Scope
- Explicitly list allowed file paths:
  - e.g. tools/local/**
  - e.g. docs/governance/runbooks/**
- Are new files allowed? YES / NO

## 4. Do NOT (Hard Stop)
- Do NOT modify conftest.py
- Do NOT relax gate conditions
- Do NOT change schema field meanings
- Do NOT delete tests

## 5. Acceptance Criteria
The following commands must behave exactly as specified:

DATABASE_URL="" pytest -q
→ MUST FAIL (Fail-Closed preserved)

DATABASE_URL="sqlite+aiosqlite:///test.db" pytest -q <target>
→ MUST PASS

If failure occurs, explain using WHY_FAIL-style reasoning.

## 6. Commit Plan
- Commits must be logically separated:
  - A-PATCH: docs / helpers / UX
  - A-MINOR: schema / gate / tests (NOT part of this task)
- Commit messages MUST include the correct token.

## 7. Output Format
- List of changed files
- Summary of diffs
- Verification commands and results
