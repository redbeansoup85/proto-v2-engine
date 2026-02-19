from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_FORBIDDEN_PREFIXES = ("order_", "exchange_", "api_", "execute_")
_FORBIDDEN_EXACT = {"leverage", "qty", "margin", "reduce_only", "client_order_id"}
_REQUIRED_KEYS = ("run_id", "ts_utc", "symbol", "timeframe", "decision", "reason", "evidence")
_ALLOWED_DECISIONS = {"NO_TRADE", "LONG", "SHORT"}


def _is_forbidden_field_name(name: str) -> bool:
    low = name.lower()
    if low in _FORBIDDEN_EXACT:
        return True
    return any(low.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES)


def find_forbidden_fields(obj: Any) -> list[str]:
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


def validate_decision(decision: dict) -> list[dict]:
    violations: list[dict] = []

    for key in _REQUIRED_KEYS:
        if key not in decision:
            violations.append(_violation("missing_required_key", key, expected="present"))

    got_decision = decision.get("decision")
    if got_decision not in _ALLOWED_DECISIONS:
        violations.append(
            _violation(
                "invalid_decision_enum",
                "decision",
                expected=sorted(_ALLOWED_DECISIONS),
                got=got_decision,
            )
        )

    for path in find_forbidden_fields(decision):
        violations.append(_violation("forbidden_field_name", path))

    evidence = decision.get("evidence")
    if not isinstance(evidence, dict):
        violations.append(_violation("evidence_not_object", "evidence", expected="object", got=type(evidence).__name__))
    elif "provider_schema_id" not in evidence:
        violations.append(_violation("missing_evidence_provider_schema_id", "evidence.provider_schema_id", expected="present"))

    return violations


def validate_or_record(decision: dict, exceptions_dir: str | Path = "Exceptions") -> bool:
    violations = validate_decision(decision)
    if not violations:
        return True

    run_id = str(decision.get("run_id") or "unknown_run_id")
    record = {
        "ts_utc": decision.get("ts_utc", ""),
        "layer": "authority_decision_gate",
        "violations": violations,
    }
    out_dir = Path(exceptions_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{run_id}.jsonl"
    with out_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, ensure_ascii=False))
        f.write("\n")
    return False
