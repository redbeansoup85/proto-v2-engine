from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.gates.gate_macro_regime import apply_macro_gate
from tools.policy.live_caps import load_live_caps_or_record


def plan_to_execution_intent(plan: dict) -> dict | None:
    if plan.get("mode") != "LIVE":
        return None
    if plan.get("direction") == "NO_TRADE":
        return None
    side_map = {"LONG": "BUY", "SHORT": "SELL"}
    side = side_map.get(plan.get("direction"))
    if side is None:
        return None
    qty = plan.get("size")
    if not isinstance(qty, (int, float)) or qty <= 0:
        return None

    evidence = plan.get("evidence", {})
    return {
        "run_id": plan["run_id"],
        "ts_utc": plan["ts_utc"],
        "symbol": plan["symbol"],
        "side": side,
        "order_type": "MARKET",
        "qty": float(qty),
        "mode": "LIVE",
        "risk": {
            "max_qty": 1.0,
            "max_notional_usd": 100.0,
        },
        "evidence": {
            "decision_reason": evidence.get("decision_reason", ""),
            "plan_mode": plan.get("mode", ""),
        },
    }


def write_execution_intent(
    intent: dict,
    out_dir: str,
    exceptions_dir: str,
    last_price_usd: float | None,
    policy_path: str = "policies/live_caps.v1.json",
    plan: dict | None = None,
    macro_path: str = "data/macro_snapshot.v1.json",
) -> str | bool:
    plan_obj = plan if isinstance(plan, dict) else {
        "run_id": intent.get("run_id", ""),
        "ts_utc": intent.get("ts_utc", ""),
        "symbol": intent.get("symbol", ""),
        "timeframe": "",
        "direction": "LONG" if intent.get("side") == "BUY" else "SHORT",
        "size": intent.get("qty", 0.0),
        "mode": intent.get("mode", ""),
        "risk": {"max_risk_pct": 0.0, "sizing_method": "intent_fallback"},
        "evidence": {"decision_reason": intent.get("evidence", {}).get("decision_reason", "")},
    }
    macro_adj, macro_info = apply_macro_gate(plan_obj, macro_path=macro_path)
    if not macro_adj.get("allow_new", False):
        record = {
            "ts_utc": intent.get("ts_utc", ""),
            "layer": "macro_gate",
            "violations": [
                {
                    "reason": "macro_blocks_new_positions",
                    "path": "macro",
                    "got": macro_info,
                }
            ],
        }
        out_dir_e = Path(exceptions_dir)
        out_dir_e.mkdir(parents=True, exist_ok=True)
        out_file_e = out_dir_e / f"{intent.get('run_id', 'unknown_run_id')}.jsonl"
        with out_file_e.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True, ensure_ascii=False))
            f.write("\n")
        return False

    intent["qty"] = float(intent["qty"]) * float(macro_adj["risk_multiplier"])

    caps = load_live_caps_or_record(
        run_id=str(intent.get("run_id", "unknown_run_id")),
        ts_utc=str(intent.get("ts_utc", "")),
        exceptions_dir=exceptions_dir,
        policy_path=policy_path,
    )
    if caps is None:
        return False
    caps_multiplier = float(macro_adj["caps_multiplier"])
    intent["risk"]["max_qty"] = float(caps["max_qty"]) * caps_multiplier
    intent["risk"]["max_notional_usd"] = float(caps["max_notional_usd"]) * caps_multiplier
