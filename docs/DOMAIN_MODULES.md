# Domain Modules (Meta OS v3.x)

## Core vs Domain

Core (immutable baseline layer):
- Audit Chain
- Gate Engine
- Policy
- Deterministic Capsule

Domain Modules (expandable layer):
- Sentinel (trading domain)
- Auralis (safety domain)
- Future domains

## Sentinel (v3.2 status)

Current implementation lives under:
- tools/
- scripts/

This is temporary.

Planned structure (future PR, not in this change):

domains/
    sentinel/
        adapters/
        signals/
        emit/
        cli/

Important:
- Domain modules MUST emit domain_event.v1
- Core must remain domain-agnostic
- No direct modification of core audit/gate for domain logic
- signal requires: type, symbol, timeframe, score(0..100), confidence(0..1), risk_level
- meta requires: producer, version, build_sha
- evidence_refs if present must use enum ref_kind + bounded ref length

Sentinel domain_event.v1 (v0 adoption):
- Sentinel emits `domain_event.v1` `SIGNAL` events as Gate inputs.
- Current producer is `sentinel.social` with signal type `BYBIT_ALERT`.

domain_event viewer UI (read-only):
- Run: `streamlit run apps/ui_domain_event_viewer.py` (or `scripts/run_ui_domain_event_viewer.sh`)
- Default scan path: `/tmp/metaos_domain_events`
- If missing, install dev dep: `pip install streamlit`

Sentinel scoring snapshot v0.2:
- Build: `python tools/sentinel_score_snapshot_v0_2.py --symbol BTCUSDT --out /tmp/metaos_snapshots/BTCUSDT/snapshot_001.json`
- Selftest: `python tools/selftest_sentinel_score_snapshot_v0_2.py`
- Snapshot path default example: `/tmp/metaos_snapshots/<SYMBOL>/snapshot_001.json`
<<<<<<< HEAD
- Multi-symbol loop: `SYMBOLS=BTCUSDT,ETHUSDT scripts/run_sentinel_live_loop.sh`
- Summary output: `/tmp/metaos_domain_events/_summary/summary_<TS>.json`
=======
- Live loop multi-symbol: `SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT scripts/run_sentinel_live_loop.sh`
>>>>>>> origin/main
