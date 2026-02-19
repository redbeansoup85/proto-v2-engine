# LOCK Interface Constitution

## Roles And Trust Boundary
- Sentinel is a `SIGNAL_ONLY` provider forever.
- Meta OS is the sole authority for decisions, planning, and execution.
- Provider outputs are untrusted inputs and must pass fail-closed ingest validation before use.

## Allowed Provider Schemas
- `sentinel_raw_snapshot.v1`
- `sentinel_trade_intent.v1` (DRY_RUN only)
- `sentinel_signal_meta.v1`
- `score_snapshot.v1` (optional)
- `pattern_event.v1` (optional)

## Forbidden Namespaces And Field Patterns
- Forbidden namespaces:
  - `decision/*`
  - `plan/*`
  - `execution/*`
- Forbidden provider field names/patterns in payload body:
  - `order_*`
  - `exchange_*`
  - `api_*`
  - `execute_*`
  - `leverage`
  - `qty`
  - `margin`
  - `reduce_only`
  - `client_order_id`

## Envelope Rule
- Meta OS MUST wrap provider payloads in `observer_event_envelope.v1` without mutating provider body fields or values.
- `payload.body` is pass-through data from provider after validation.

## Run ID Authority
- `run_id` is issued only by Meta OS.
- Providers must not mint, override, or infer authority from run identifiers.

## Fail-Closed Ingest Gate
- Any validation failure is terminal for ingest.
- On failure, Meta OS MUST append an exception record to `Exceptions/<run_id>.jsonl`.
- Processing stops immediately after the first detected violation for deterministic behavior.

## Schema Evolution Policy
- This interface is locked by default.
- Schema additions or changes require an explicit constitution update and synchronized gate/schema test updates.
- Changes must preserve Sentinel `SIGNAL_ONLY` constraints and Meta OS authority boundaries.
