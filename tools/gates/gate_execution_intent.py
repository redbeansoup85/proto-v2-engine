from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_FORBIDDEN_PREFIXES = ("order_", "exchange_", "api_", "execute_")
_FORBIDDEN_EXACT = {"leverage", "margin", "reduce_only", "client_order_id"}
_REQUIRED_KEYS = ("run_id", "ts_utc", "symbol", "side", "order_type", "qty", "mode", "risk", "evidence")


def _is_forbidden_field_name(name: str) -> bool:
    if name == "order_type":
        return False
    low = name.lower()
    if low in _FORBIDDEN_EXACT:
        return True
    return any(low.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES)


def _find_forbidden_fields(obj: Any) -> list[str]:
    out: list[str] = []

    def _walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key in sorted(value.keys(), key=lambda x: str(x)):
                key_s = str(key)
                next_path = f"{path}.{key_s}" if path else key_s
                if _is_forbidden_field_name(key_s):
                    out.append(next_path)
                _walk(value[key], next_path)
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                _walk(item, f"{path}[{idx}]")

    _walk(obj, "")
    return out


def _violation(reason: str, path: str, expected: Any = None, got: Any = None) -> dict:
    item: dict[str, Any] = {"reason": reason, "path": path}
    if expected is not None:
        item["expected"] = expected
    if got is not None:
        item["got"] = got
    return item


def validate_intent(intent: dict) -> list[dict]:
    violations: list[dict] = []

    for key in _REQUIRED_KEYS:
        if key not in intent:
            violations.append(_violation("missing_required_key", key, expected="present"))

    if intent.get("order_type") != "MARKET":
        violations.append(_violation("order_type_must_be_market", "order_type", expected="MARKET", got=intent.get("order_type")))

    if intent.get("mode") != "LIVE":
        violations.append(_violation("mode_must_be_live", "mode", expected="LIVE", got=intent.get("mode")))

    qty = intent.get("qty")
    if not isinstance(qty, (int, float)):
        violations.append(_violation("qty_not_number", "qty", expected="number", got=type(qty).__name__))
    elif qty <= 0:
        violations.append(_violation("qty_not_positive", "qty", expected=">0", got=qty))

    risk = intent.get("risk")
    if not isinstance(risk, dict):
        violations.append(_violation("risk_not_object", "risk", expected="object", got=type(risk).__name__))
    else:
        for key in ("max_qty", "max_notional_usd"):
            if key not in risk:
                violations.append(_violation("missing_risk_key", f"risk.{key}", expected="present"))

    evidence = intent.get("evidence")
    if not isinstance(evidence, dict):
        violations.append(_violation("evidence_not_object", "evidence", expected="object", got=type(evidence).__name__))
    else:
        for key in ("decision_reason", "plan_mode"):
            if key not in evidence:
                violations.append(_violation("missing_evidence_key", f"evidence.{key}", expected="present"))

    for path in _find_forbidden_fields(intent):
        violations.append(_violation("forbidden_field_name", path))

    return violations


def validate_or_record(intent: dict, exceptions_dir: str | Path = "Exceptions") -> bool:
    violations = validate_intent(intent)
    if not violations:
        return True

    run_id = str(intent.get("run_id") or "unknown_run_id")
    record = {
        "ts_utc": intent.get("ts_utc", ""),
        "layer": "execution_intent_gate",
        "violations": violations,
    }
    out_dir = Path(exceptions_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{run_id}.jsonl"
    with out_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, ensure_ascii=False))
        f.write("\n")
    return False
