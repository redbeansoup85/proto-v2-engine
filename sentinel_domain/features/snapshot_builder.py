from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional

# Exact template structure copied from tools/sentinel/consume_trade_intent.py
SNAPSHOT_TEMPLATE = {
    "schema": "market_snapshot.v1",
    "asset": "n/a",
    "ts_utc": "n/a",
    "tf_state": {
        "1m": {"price": "n/a", "vwap": "n/a", "ema20": "n/a", "ema50": "n/a", "ema200": "n/a", "rsi": "n/a"},
        "5m": {"price": "n/a", "vwap": "n/a", "ema20": "n/a", "ema50": "n/a", "ema200": "n/a", "rsi": "n/a"},
        "15m": {"price": "n/a", "vwap": "n/a", "ema20": "n/a", "ema50": "n/a", "ema200": "n/a", "rsi": "n/a"},
        "1h": {"price": "n/a", "vwap": "n/a", "ema20": "n/a", "ema50": "n/a", "ema200": "n/a", "rsi": "n/a"},
        "4h": {"price": "n/a", "vwap": "n/a", "ema20": "n/a", "ema50": "n/a", "ema200": "n/a", "rsi": "n/a"},
    },
    "deriv": {
        "oi": "n/a",
        "funding": "n/a",
        "lsr": "n/a",
        "cvd_proxy": {"futures": "n/a", "spot": "n/a"},
    },
}


def make_template_snapshot(asset: str, ts_utc: str) -> Dict[str, Any]:
    snapshot = copy.deepcopy(SNAPSHOT_TEMPLATE)
    snapshot["asset"] = asset
    snapshot["ts_utc"] = ts_utc
    return snapshot


def select_base_tf(candles: Dict[str, List[Dict[str, Any]]]) -> Optional[str]:
    for tf in ("15m", "5m", "1m"):
        if candles.get(tf):
            return tf
    return None


def build_snapshot_from_template(
    template_snapshot: Dict[str, Any],
    raw_bundle: Dict[str, Any],
    computed: Dict[str, Any],
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    snapshot = copy.deepcopy(template_snapshot)
    tf_state = snapshot.get("tf_state")
    if not isinstance(tf_state, dict):
        return snapshot

    # Strict fail-closed mode: keep placeholders if quality is not OK.
    if not bool(evidence.get("ok")):
        return snapshot

    per_tf = computed.get("per_tf")
    if not isinstance(per_tf, dict):
        return snapshot

    for tf, metrics in per_tf.items():
        state = tf_state.get(tf)
        if not isinstance(state, dict) or not isinstance(metrics, dict):
            continue

        ema20 = metrics.get("ema20")
        ema50 = metrics.get("ema50")
        ema200 = metrics.get("ema200")
        rsi14 = metrics.get("rsi14")

        if isinstance(ema20, float):
            state["ema20"] = ema20
        if isinstance(ema50, float):
            state["ema50"] = ema50
        if isinstance(ema200, float):
            state["ema200"] = ema200
        if isinstance(rsi14, float):
            state["rsi"] = rsi14

    deriv = snapshot.get("deriv")
    raw_deriv = raw_bundle.get("deriv")
    if isinstance(deriv, dict) and isinstance(raw_deriv, dict):
        raw_oi = raw_deriv.get("oi")
        raw_funding = raw_deriv.get("funding")
        raw_lsr = raw_deriv.get("lsr")

        if isinstance(raw_oi, (int, float)) and math.isfinite(float(raw_oi)):
            deriv["oi"] = float(raw_oi)
        if isinstance(raw_funding, (int, float)) and math.isfinite(float(raw_funding)):
            deriv["funding"] = float(raw_funding)
        if isinstance(raw_lsr, (int, float)) and math.isfinite(float(raw_lsr)):
            deriv["lsr"] = float(raw_lsr)

    return snapshot
