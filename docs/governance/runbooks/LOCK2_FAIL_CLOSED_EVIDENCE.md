# LOCK-2 / Static Scan Fail-Closed Evidence

## Scope
This document records CI evidence that LOCK-2 and the static scan step are fail-closed (i.e., any findings cause the workflow to fail with a non-zero exit code).

## Evidence (CI Run IDs)

### PASS (no findings)
- Run ID: 21824604155
  - Unit tests: 147 passed
  - LOCK-2: OK: LOCK-2 gate clean
  - Static scan: OK: static scan clean

### FAIL (findings detected -> exit 1)
- Run ID: 21823647118
  - Output: FAIL-CLOSED: LOCK-2 gate findings detected
  - Result: Process completed with exit code 1

- Run ID: 21823423023
  - Output: FAIL-CLOSED: LOCK-2 gate findings detected
  - Result: Process completed with exit code 1

### Note (log unavailable)
- Run ID: 21823956978
  - Observation: log not found (likely workflow-file issue or pre-run failure)
