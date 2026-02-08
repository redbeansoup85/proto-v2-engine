# TASK_LOOP Contract (v1)

## Required keys
- CREATED_AT_UTC: "YYYY-MM-DDTHH:MM:SSZ"
- INTENT
- EXPECTED_OUTCOME
- EXECUTION
- NEXT_ACTION
- RESULT: OPEN|CLOSED|BLOCKED|SKIPPED

## Deprecated keys (do not use)
- STATUS
- TASK_ID

## Notes
- RESULT=CLOSED requires VERDICT.yaml in the same directory (see loop-gate).
