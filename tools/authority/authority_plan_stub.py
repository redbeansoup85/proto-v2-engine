from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.gates.gate_position_plan import validate_or_record


def build_no_exec_plan(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": decision["run_id"],
        "ts_utc": decision["ts_utc"],
        "symbol": decision["symbol"],
        "timeframe": decision["timeframe"],
        "direction": decision["decision"],
        "size": 0.0,
        "mode": "NO_EXEC",
        "risk": {
            "max_risk_pct": 0.0,
            "sizing_method": "stub_no_exec",
        },
        "evidence": {
            "decision_reason": decision["reason"],
        },
    }


def write_plan(plan: dict[str, Any], out_dir: str) -> str | bool:
    if not validate_or_record(plan):
        return False
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    out = p / "position_plan.v1.json"
    out.write_text(json.dumps(plan, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(out)
