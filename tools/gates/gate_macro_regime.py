from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_macro_snapshot(path: str = "data/macro_snapshot.v1.json") -> dict:
    p = Path(path)
    obj = json.loads(p.read_text(encoding="utf-8"))
    return obj


def compute_macro_index(snapshot: dict) -> int:
    idx = 50
    inputs = snapshot["inputs"]
    vix = inputs["vix"]
    dxy = inputs["dxy"]
    real10y = inputs["real10y"]

    if vix >= 25:
        idx -= 15
    elif vix <= 16:
        idx += 5

    if dxy >= 105:
        idx -= 10
    elif dxy <= 101:
        idx += 5

    if real10y >= 2.0:
        idx -= 10
    elif real10y <= 1.5:
        idx += 5

    return max(0, min(100, idx))


def determine_regime(index: int) -> dict:
    if index < 30:
        return {"regime": "RISK_OFF", "allow_new": False, "risk_multiplier": 0.0, "caps_multiplier": 0.0}
    if index < 45:
        return {"regime": "DEFENSIVE", "allow_new": True, "risk_multiplier": 0.4, "caps_multiplier": 0.4}
    if index < 60:
        return {"regime": "NEUTRAL", "allow_new": True, "risk_multiplier": 0.7, "caps_multiplier": 0.7}
    if index < 75:
        return {"regime": "CONSTRUCTIVE", "allow_new": True, "risk_multiplier": 1.0, "caps_multiplier": 1.0}
    return {"regime": "EXPANSION", "allow_new": True, "risk_multiplier": 1.3, "caps_multiplier": 1.3}


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def apply_macro_gate(plan: dict, macro_path: str = "data/macro_snapshot.v1.json") -> tuple[dict, dict]:
    risk_off = {"allow_new": False, "risk_multiplier": 0.0, "caps_multiplier": 0.0}
    try:
        snap = load_macro_snapshot(macro_path)
        idx = compute_macro_index(snap)
        regime = determine_regime(idx)

        stale_after_hours = float(snap["meta"]["stale_after_hours"])
        if stale_after_hours <= 0:
            raise ValueError("stale_after_hours_must_be_positive")

        plan_ts = _parse_ts(plan["ts_utc"])
        snap_ts = _parse_ts(snap["ts_utc"])
        age_hours = (plan_ts - snap_ts).total_seconds() / 3600.0
        if age_hours > stale_after_hours:
            return risk_off, {"macro_index": idx, "regime": "RISK_OFF", "reason": "snapshot_stale"}

        return {
            "allow_new": regime["allow_new"],
            "risk_multiplier": float(regime["risk_multiplier"]),
            "caps_multiplier": float(regime["caps_multiplier"]),
        }, {"macro_index": idx, "regime": regime["regime"], "reason": "ok"}
    except Exception as exc:  # noqa: BLE001
        return risk_off, {"macro_index": 0, "regime": "RISK_OFF", "reason": f"error:{exc}"}
