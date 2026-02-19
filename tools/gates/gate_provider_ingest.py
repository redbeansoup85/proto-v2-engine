from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

_REGISTRY_LOCK_PATH = Path("schemas/schema_registry.lock.json")

_FORBIDDEN_PREFIXES = ("order_", "exchange_", "api_", "execute_")
_FORBIDDEN_EXACT = {"leverage", "qty", "margin", "reduce_only", "client_order_id"}


def _dict_get(d: Dict[str, Any], *keys: str) -> Any:
    cur: Any = d
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _iter_field_paths(value: Any, path: str = "payload.body") -> Iterable[Tuple[str, Any]]:
    if isinstance(value, dict):
        for key in sorted(value.keys(), key=lambda x: str(x)):
            key_s = str(key)
            next_path = f"{path}.{key_s}"
            yield next_path, value[key]
            yield from _iter_field_paths(value[key], next_path)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            next_path = f"{path}[{idx}]"
            yield from _iter_field_paths(item, next_path)


def _is_forbidden_field_name(name: str) -> bool:
    name_l = name.lower()
    if name_l in _FORBIDDEN_EXACT:
        return True
    return any(name_l.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES)


def get_allowed_schema_ids(registry_path: Path = _REGISTRY_LOCK_PATH) -> list[str]:
    try:
        obj = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    ids = obj.get("allowed_provider_schema_ids")
    if not isinstance(ids, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in ids:
        if not isinstance(item, str) or not item:
            return []
        if item in seen:
            return []
        seen.add(item)
        out.append(item)
    return out


def _append_exception_record(
    *,
    run_id: str,
    ts_utc: str,
    provider_id: str,
    schema_id: str,
    violations: list[dict],
) -> None:
    record = {
        "ts_utc": ts_utc,
        "provider_id": provider_id,
        "schema_id": schema_id,
        "violations": violations,
    }
    exceptions_dir = Path("Exceptions")
    exceptions_dir.mkdir(parents=True, exist_ok=True)
    out_path = exceptions_dir / f"{run_id}.jsonl"
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, ensure_ascii=False))
        f.write("\n")


def _violation(reason: str, path: str, expected: Any = None, got: Any = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"reason": reason, "path": path}
    if expected is not None:
        out["expected"] = expected
    if got is not None:
        out["got"] = got
    return out


def validate_provider_envelope(envelope: dict) -> list[dict]:
    run_id = str(envelope.get("run_id") or "unknown_run_id")
    ts_utc = str(envelope.get("ts_utc") or "")
    provider_id = str(_dict_get(envelope, "provider", "provider_id") or "")
    schema_id = str(_dict_get(envelope, "payload", "schema_id") or "")

    violations: list[dict] = []
    allowed_schema_ids = get_allowed_schema_ids()
    allowed_schema_id_set = set(allowed_schema_ids)

    provider_class = _dict_get(envelope, "provider", "provider_class")
    if provider_class != "SIGNAL_ONLY":
        violations.append(
            _violation(
                "provider_class_must_be_SIGNAL_ONLY",
                "provider.provider_class",
                expected="SIGNAL_ONLY",
                got=provider_class,
            )
        )

    if not allowed_schema_ids:
        violations.append(
            _violation(
                "schema_registry_lock_missing_or_invalid",
                str(_REGISTRY_LOCK_PATH),
            )
        )

    if schema_id not in allowed_schema_id_set:
        violations.append(
            _violation(
                "schema_id_not_allowlisted",
                "payload.schema_id",
                expected=allowed_schema_ids,
                got=schema_id,
            )
        )

    body = _dict_get(envelope, "payload", "body")

    if schema_id == "sentinel_trade_intent.v1":
        mode = _dict_get(envelope, "payload", "body", "mode")
        if mode != "DRY_RUN":
            violations.append(
                _violation(
                    "trade_intent_mode_must_be_DRY_RUN",
                    "payload.body.mode",
                    expected="DRY_RUN",
                    got=mode,
                )
            )

    if isinstance(body, dict):
        for field_path, field_value in _iter_field_paths(body):
            field_name = field_path.rsplit(".", maxsplit=1)[-1]
            if "[" in field_name:
                continue
            if _is_forbidden_field_name(field_name):
                violations.append(
                    _violation(
                        "forbidden_field_name",
                        field_path,
                        got=field_value,
                    )
                )

    if violations:
        _append_exception_record(
            run_id=run_id,
            ts_utc=ts_utc,
            provider_id=provider_id,
            schema_id=schema_id,
            violations=violations,
        )
    return violations
