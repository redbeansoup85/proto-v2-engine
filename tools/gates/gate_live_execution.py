from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.gates.gate_execution_intent import validate_intent


def _violation(reason: str, path: str, expected: Any = None, got: Any = None) -> dict:
    item: dict[str, Any] = {"reason": reason, "path": path}
    if expected is not None:
        item["expected"] = expected
    if got is not None:
        item["got"] = got
    return item


def validate_live(intent: dict, last_price_usd: float | None) -> list[dict]:
    violations = list(validate_intent(intent))

    qty = intent.get("qty")
    risk = intent.get("risk") if isinstance(intent.get("risk"), dict) else {}
    max_qty = risk.get("max_qty")
    if isinstance(qty, (int, float)) and isinstance(max_qty, (int, float)) and qty > max_qty:
        violations.append(_violation("qty_exceeds_max_qty", "qty", expected=f"<= {max_qty}", got=qty))

    if last_price_usd is None:
        violations.append(_violation("missing_price_for_notional_cap", "last_price_usd", expected="number", got=None))
    else:
        max_notional = risk.get("max_notional_usd")
        if isinstance(qty, (int, float)) and isinstance(max_notional, (int, float)):
            notional = qty * last_price_usd
            if notional > max_notional:
                violations.append(
                    _violation(
                        "notional_exceeds_max_notional_usd",
                        "qty",
                        expected=f"<= {max_notional / last_price_usd if last_price_usd != 0 else max_notional}",
                        got=qty,
                    )
                )

    return violations


def validate_or_record(intent: dict, exceptions_dir: str | Path = "Exceptions", last_price_usd: float | None = None) -> bool:
    violations = validate_live(intent, last_price_usd=last_price_usd)
    if not violations:
        return True

    run_id = str(intent.get("run_id") or "unknown_run_id")
    record = {
        "ts_utc": intent.get("ts_utc", ""),
        "layer": "live_execution_gate",
        "violations": violations,
    }
    out_dir = Path(exceptions_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{run_id}.jsonl"
    with out_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, ensure_ascii=False))
        f.write("\n")
    return False
