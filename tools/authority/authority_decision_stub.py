from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def decide_no_trade(envelope: dict[str, Any]) -> dict[str, Any]:
    body = envelope.get("payload", {}).get("body", {})
    evidence = {
        "authority": "authority_stub",
        "provider_schema_id": envelope["payload"]["schema_id"],
    }
    return {
        "run_id": envelope["run_id"],
        "ts_utc": envelope["ts_utc"],
        "symbol": body.get("symbol", ""),
        "timeframe": body.get("tf", ""),
        "decision": "NO_TRADE",
        "reason": "authority_stub_no_trade",
        "evidence": evidence,
    }


def write_decision(decision: dict[str, Any], out_dir: str | Path, exceptions_dir: str | Path = "Exceptions") -> Path | None:
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    out = p / "direction_decision.v1.json"
    out.write_text(json.dumps(decision, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
