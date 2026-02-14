# CI Determinism Switches

These environment variables are **CI-only** and MUST be **OFF in production**.

## METAOS_CI_DETERMINISTIC_PLAN=1
- Affects: `core/C_action/plan_from_receipt.py`
- Locks:
  - `DeliveryPlan.plan_id` to `dp_<receipt_hash_prefix>`
  - `DeliveryPlan.ts_iso` to `1970-01-01T00:00:00Z`
- Purpose: deterministic `DeliveryPlan` + queue artifacts for strict CI.

## METAOS_CI_DETERMINISTIC_CONSUMER=1
- Affects: `core/C_action/queue_consumer.py`
- Locks:
  - `processed_ts_iso` to `1970-01-01T00:00:00Z`
- Purpose: deterministic processed artifacts for strict CI.

## METAOS_CI_DETERMINISTIC_ORCH_PAYLOAD=1
- Affects: `core/C_action/orch_payload.py`
- Locks:
  - `ORCH_INBOX_V1.ts_iso` to `1970-01-01T00:00:00Z`
- Purpose: deterministic orchestrator inbox payloads for strict CI.

## Baseline tag policy (immutable)
- `vX.Y-lock-stable` is an **immutable baseline tag** (no delete / no move).
- New baselines must use a **new tag name** (e.g. `v3.2-lock-stable` → `v3.3-lock-stable`), never a suffix on the same baseline name.
- `vX.Y-lock-stable.*` is **CI trigger-only** (may be created freely to re-run CI) and is **NOT** a baseline.
