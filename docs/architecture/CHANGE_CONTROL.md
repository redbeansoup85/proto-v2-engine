# Change Control (Fail-Closed)

## Constitutional Artifacts
- Zone boundary docs/gates
- Bridge contracts (v0.1/v0.2)
- Bridge consumer gate
- CI workflows that enforce the above

## Rules
1. Constitutional artifacts must be protected by CODEOWNERS.
2. Required CI checks cannot be removed without a version bump + documented rationale.
3. Contract changes must be versioned:
   - expand safely in v0.1
   - restrict strictly in v0.2+
4. Fail-closed is default:
   - unknown status/shape => block + audit
5. Any loosening of enforcement requires explicit, versioned approval.
