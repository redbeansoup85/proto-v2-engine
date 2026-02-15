from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from sentinel_domain.adapters.market.base import parse_tfs
from sentinel_domain.adapters.market.bybit_rest import fetch_raw_market_bundle
from sentinel_domain.features.indicators import compute_tf_indicators
from sentinel_domain.features.snapshot_builder import build_snapshot_from_template, make_template_snapshot, select_base_tf

DEFAULT_SNAPSHOT_DIR = "audits/sentinel/snapshots"
DEFAULT_VENUE = "bybit"
DEFAULT_MARKET = "perp"
DEFAULT_TFS = "1m,5m,15m,1h,4h"
DEFAULT_STALE_MS = 60000


def _canonical_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _parse_iso_utc_to_ms(ts_utc: str) -> Optional[int]:
    try:
        dt = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def _find_latest_candle_ms(rows: List[Dict[str, Any]]) -> Optional[int]:
    latest_ms: Optional[int] = None
    for row in rows:
        ts = row.get("t")
        if not isinstance(ts, str):
            continue
        ms = _parse_iso_utc_to_ms(ts)
        if ms is None:
            continue
        if latest_ms is None or ms > latest_ms:
            latest_ms = ms
    return latest_ms


def _build_evidence(
    raw_bundle: Dict[str, Any],
    computed: Dict[str, Any],
    requested_tfs: List[str],
    stale_limit_ms: int,
    ts_utc: str,
) -> Dict[str, Any]:
    candles = raw_bundle.get("candles") or {}
    proof = raw_bundle.get("proof") or {}
    proof_errors = proof.get("errors") or []

    missing: List[str] = []
    for tf in requested_tfs:
        rows = candles.get(tf) if isinstance(candles, dict) else None
        if not isinstance(rows, list) or not rows:
            missing.append("candles.%s" % tf)

    base_tf = computed.get("base_tf")
    base_metrics = computed.get("base")
    ema20_ok = isinstance((base_metrics or {}).get("ema20"), float)
    rsi14_ok = isinstance((base_metrics or {}).get("rsi14"), float)

    stale_ms: Any = "n/a"
    if isinstance(base_tf, str) and isinstance(candles, dict):
        base_rows = candles.get(base_tf)
        if isinstance(base_rows, list) and base_rows:
            latest_ms = _find_latest_candle_ms(base_rows)
            now_ms = _parse_iso_utc_to_ms(ts_utc) or int(time.time() * 1000)
            if latest_ms is not None:
                stale_ms = max(0, now_ms - latest_ms)

    stale_bad = isinstance(stale_ms, int) and stale_ms > stale_limit_ms
    ok = not missing and not proof_errors and ema20_ok and rsi14_ok and not stale_bad
    return {
        "ok": bool(ok),
        "missing": missing,
        "stale_ms": stale_ms,
        "proof_errors": proof_errors if isinstance(proof_errors, list) else [],
    }


def build_snapshot_payload(
    asset: str,
    ts_utc: str,
    venue: str,
    market_type: str,
    tfs: List[str],
    stale_limit_ms: int,
    http_get_json: Optional[Callable[[str, float], Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    raw_bundle = fetch_raw_market_bundle(
        asset=asset,
        tfs=tfs,
        venue=venue,
        market_type=market_type,
        http_get_json=http_get_json,
    )

    candles = raw_bundle.get("candles")
    candles_map: Dict[str, List[Dict[str, Any]]] = candles if isinstance(candles, dict) else {}
    per_tf = compute_tf_indicators(candles_map)
    base_tf = select_base_tf(candles_map)
    base_metrics = per_tf.get(base_tf, {}) if isinstance(base_tf, str) else {}
    computed = {"per_tf": per_tf, "base_tf": base_tf, "base": base_metrics}
    evidence = _build_evidence(raw_bundle, computed, tfs, stale_limit_ms, ts_utc)

    template = make_template_snapshot(asset=asset, ts_utc=ts_utc)
    snapshot = build_snapshot_from_template(
        template_snapshot=template,
        raw_bundle=raw_bundle,
        computed=computed,
        evidence=evidence,
    )
    return snapshot, raw_bundle, evidence


def capture_market_snapshot(
    asset: str,
    ts_utc: str,
    snap_dir: Optional[Path] = None,
    snap_id: Optional[str] = None,
    venue: Optional[str] = None,
    market_type: Optional[str] = None,
    tfs: Optional[List[str]] = None,
    stale_limit_ms: Optional[int] = None,
    http_get_json: Optional[Callable[[str, float], Dict[str, Any]]] = None,
) -> str:
    out_dir = Path(
        str(snap_dir or os.getenv("SENTINEL_SNAPSHOT_DIR") or DEFAULT_SNAPSHOT_DIR)
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    final_snap_id = snap_id or ("SNAP-%s" % datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))
    venue_v = str(venue or os.getenv("SENTINEL_VENUE") or DEFAULT_VENUE)
    market_v = str(market_type or os.getenv("SENTINEL_MARKET") or DEFAULT_MARKET)
    tfs_v = tfs or parse_tfs(os.getenv("SENTINEL_TFS", DEFAULT_TFS))
    stale_v_raw = stale_limit_ms if stale_limit_ms is not None else os.getenv("SENTINEL_STALE_MS", str(DEFAULT_STALE_MS))
    try:
        stale_v = int(stale_v_raw)
    except Exception:
        stale_v = DEFAULT_STALE_MS

    snapshot, _, _ = build_snapshot_payload(
        asset=asset,
        ts_utc=ts_utc,
        venue=venue_v,
        market_type=market_v,
        tfs=tfs_v,
        stale_limit_ms=stale_v,
        http_get_json=http_get_json,
    )

    target = out_dir / ("%s.json" % final_snap_id)
    tmp = out_dir / ("%s.json.tmp.%d" % (final_snap_id, os.getpid()))
    tmp.write_text(_canonical_json(snapshot) + "\n", encoding="utf-8")
    tmp.replace(target)
    return str(Path("audits/sentinel/snapshots") / target.name)

