# Domain: sentinel.trade (Thin Slice v1)

## Purpose
Dry-run trade proposal domain. No real execution.

## Ingress
- `sentinel_trade_intent.v1` (JSON)

## Egress
- `sentinel_trade_decision.v1` (JSON)
- Observer event JSONL (LOCK-3 compliant)

## Safety
- Always dry-run.
- Fail-closed on schema mismatch.
