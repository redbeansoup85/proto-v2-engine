from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_FORBIDDEN_PREFIXES = ("order_", "exchange_", "api_", "execute_")
_FORBIDDEN_EXACT = {"leverage", "qty", "margin", "reduce_only", "client_order_id"}
_REQUIRED_KEYS = ("run_id", "ts_utc", "symbol", "timeframe", "direction", "size", "mode", "risk", "evidence")
_ALLOWED_DIRECTIONS = {"NO_TRADE", "LONG", "SHORT"}
_ALLOWED_MODES = {"NO_EXEC", "SIMULATE", "LIVE"}


def _is_forbidden_field_name(name: str) -> bool:
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


def validate_plan(plan: dict) -> list[dict]:
    violations: list[dict] = []

    for key in _REQUIRED_KEYS:
        if key not in plan:
            violations.append(_violation("missing_required_key", key, expected="present"))

    direction = plan.get("direction")
    if direction not in _ALLOWED_DIRECTIONS:
        violations.append(_violation("invalid_direction_enum", "direction", expected=sorted(_ALLOWED_DIRECTIONS), got=direction))

    mode = plan.get("mode")
    if mode not in _ALLOWED_MODES:
        violations.append(_violation("invalid_mode_enum", "mode", expected=sorted(_ALLOWED_MODES), got=mode))

    size = plan.get("size")
    if not isinstance(size, (int, float)):
        violations.append(_violation("size_not_number", "size", expected="number", got=type(size).__name__))
    elif size < 0:
        violations.append(_violation("size_negative", "size", expected=">=0", got=size))

    risk = plan.get("risk")
    if not isinstance(risk, dict):
        violations.append(_violation("risk_not_object", "risk", expected="object", got=type(risk).__name__))
    else:
        for key in ("max_risk_pct", "sizing_method"):
            if key not in risk:
                violations.append(_violation("missing_risk_key", f"risk.{key}", expected="present"))

    evidence = plan.get("evidence")
    if not isinstance(evidence, dict):
        violations.append(_violation("evidence_not_object", "evidence", expected="object", got=type(evidence).__name__))
    elif "decision_reason" not in evidence:
        violations.append(_violation("missing_evidence_decision_reason", "evidence.decision_reason", expected="present"))

    for path in _find_forbidden_fields(plan):
        violations.append(_violation("forbidden_field_name", path))

    return violations


def validate_or_record(plan: dict, exceptions_dir: str | Path = "Exceptions") -> bool:
    violations = validate_plan(plan)
    if not violations:
        return True

    run_id = str(plan.get("run_id") or "unknown_run_id")
    record = {
        "ts_utc": plan.get("ts_utc", ""),
        "layer": "position_plan_gate",
        "violations": violations,
    }
    out_dir = Path(exceptions_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{run_id}.jsonl"
    with out_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, ensure_ascii=False))
        f.write("\n")
    return False
