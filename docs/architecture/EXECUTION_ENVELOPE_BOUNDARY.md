# ExecutionEnvelope Boundary Policy (LOCK Candidate)

## Purpose
Define invariant rules for execution eligibility across API boundary and core runtime.

## Canonical Flow
1) Approval is resolved from JudgmentPort (source of truth).
2) API boundary mints ExecutionEnvelope using approval_id + authority_id.
3) Core enforces fail-closed: missing/invalid/expired envelope blocks execution.

## Invariants (MUST)
- Minting occurs ONLY at infra/api boundary.
- Core MUST NOT mint or modify ExecutionEnvelope.
- Missing ExecutionEnvelope => fail-closed (PermissionError / HTTP 403).
- approval_id / authority_id MUST be sourced from JudgmentPort, not request payload.
- expires_at MUST be checked; expired => fail-closed.
- Audit MUST record immutable envelope meta + approval linkage.

## Forbidden Patterns (MUST NOT)
- Core creating default envelope
- Trusting request.approval_id / request.authority_id
- Allowing execution without envelope
- Silent bypass of apply gate / envelope gate

## Error Semantics
- Boundary: translate PermissionError => HTTP 403
- Core: raise PermissionError on any invariant violation

