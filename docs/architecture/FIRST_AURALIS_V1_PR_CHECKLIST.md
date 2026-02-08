# FIRST_AURALIS_V1_PR_CHECKLIST (v0.1)

## Goal
The first auralis_v1 implementation PR must establish a minimal, verifiable boot path that satisfies:
- Zone boundary principles
- Bridge contract v0.1 (and prepares v0.2)
- Fail-closed behavior
- Deterministic audit/trace flow

---

## Scope (What this first PR MUST include)

### 1) Service Boot (ASGI)
- [ ] ASGI entrypoint is stable and documented.
  - Expected ASGI app: `auralis_v1.core.app:app`
- [ ] Service runs under uvicorn without manual steps.
- [ ] Minimal configuration for local + CI environment.

### 2) Endpoints (Contract-aligned)
- [ ] `GET /health` exists and returns JSON object.
- [ ] `POST /invoke` exists and returns JSON object.
- [ ] Contract endpoints in `contracts/bridge/...` match the actual routes.

### 3) Minimal Response Shape (v0.1 required)
- [ ] Every response includes `status` (always).
  - `status` in {"success","fail","error"} is recommended even in v0.1.
- [ ] No raw exceptions escape to the client.
  - Unknown exceptions must be converted to fail-closed error payload.

### 4) Trace / Request Headers (Bridge-ready)
- [ ] Request accepts:
  - `X-Request-Id`
  - `X-Audit-Trace`
- [ ] Trace policy is consistent:
  - Either echo `X-Audit-Trace` into response `trace_id`, or generate a trace_id deterministically and expose it.
- [ ] For failures, trace must still be present in response and audit record.

### 5) Fail-Closed Error Policy (minimum)
- [ ] When `status != success`, include `error` object (recommended in v0.1; required in v0.2):
  - `error_type` (string)
  - `message` (non-empty string)
  - `is_retryable` (boolean)

### 6) Audit Hook (minimal)
- [ ] At least one audit record is produced for `/invoke` attempt (success or fail).
- [ ] Audit event includes:
  - `trace_id`
  - timestamp
  - event_type
- [ ] Audit append is best-effort but must not silently swallow failures without signal.

---

## Tests required in the first PR (minimum 2)

### Test A: health returns status
- [ ] `/health` returns 200
- [ ] JSON object includes `status`

### Test B: invoke returns status
- [ ] `/invoke` returns 200/4xx/5xx as defined
- [ ] JSON object includes `status`
- [ ] Trace header handling is exercised

---

## Explicit non-goals for the first PR
- Domain logic completeness
- Model loading/serving
- Performance optimization
- Full v0.2 strict enforcement (only prepare compatibility)

---

## Acceptance Criteria
This PR is accepted when:
- The service boots deterministically
- `/health` and `/invoke` exist and satisfy v0.1 minimal contract
- Fail-closed behavior is observable (no uncaught exceptions)
- Minimal tests pass in CI
