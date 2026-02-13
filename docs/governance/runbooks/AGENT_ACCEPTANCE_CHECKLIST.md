# AGENT_ACCEPTANCE_CHECKLIST (LOCK-safe)

## A. Scope Check
- [ ] Only intended files were changed
- [ ] No L4 / constitutional documents were modified unintentionally

## B. Boundary Check
- [ ] Fail-Closed behavior preserved
- [ ] No execution / order / decision fields added
- [ ] No gate conditions weakened

## C. Local Inspection
- Run:
  git status
  git diff
- [ ] No unexpected changes
- [ ] conftest.py untouched

## D. Test Verification
- Run:
  DATABASE_URL="" pytest -q
  DATABASE_URL="sqlite+aiosqlite:///test.db" pytest -q <target>
- [ ] First command FAILS
- [ ] Second command PASSES

## E. Commit Hygiene
- [ ] Commits logically separated
- [ ] Commit message tokens correct

## F. Decision
- [ ] ALL GREEN → safe to merge
- [ ] ANY RED → stop and escalate
