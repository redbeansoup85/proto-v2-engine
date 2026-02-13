from __future__ import annotations

"""
Observe + audit chain append with fail-closed semantics.

Deterministic hashing rules:
- canonical_json(obj) := json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
- chain_record["hash"] := sha256(canonical_json(chain_record_without_hash))
- chain_record["prev_hash"] := previous record hash, or "0"*64 for genesis

Atomicity rule:
- if validation/forbidden-key/chain checks fail, nothing is appended.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from jsonschema import Draft202012Validator

FORBIDDEN_KEYS = {
    "api_key",
    "private_key",
    "seed_phrase",
    "mnemonic",
    "password",
    "secret",
    "token",
}

DEFAULT_OBSERVER_PATH = Path("var/observer/events.jsonl")
DEFAULT_CHAIN_PATH = Path("var/audit/lock3_chain.jsonl")
SCHEMA_ID = "kernel.observe_event.v1"

_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Kernel Observe Event v1",
    "type": "object",
    "additionalProperties": False,
    "required": ["event_id", "ts", "schema_id", "kind", "meta", "preview"],
    "properties": {
        "event_id": {"type": "string", "minLength": 1},
        "ts": {"type": "string", "minLength": 1},
        "schema_id": {"type": "string", "const": SCHEMA_ID},
        "kind": {"type": "string", "minLength": 1},
        "meta": {"type": "object"},
        "preview": {"type": "object"},
    },
}


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _schema_hash() -> str:
    raw = _canonical_json(_SCHEMA).encode("utf-8")
    return _sha256_hex(raw)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = line.strip()
        if not raw:
            raise RuntimeError(f"blank line found in chain at line {idx}")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid json in chain at line {idx}: {exc}") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError(f"invalid chain row type at line {idx}")
        rows.append(parsed)
    return rows


def _check_forbidden_keys(obj: Any, path: str = "$") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str) and key.lower() in FORBIDDEN_KEYS:
                raise RuntimeError(f"forbidden key detected at {path}.{key}")
            _check_forbidden_keys(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            _check_forbidden_keys(value, f"{path}[{i}]")


def _verify_existing_chain(rows: list[dict[str, Any]]) -> None:
    prev = "0" * 64
    expected_schema_hash = _schema_hash()
    for idx, row in enumerate(rows, start=1):
        found_prev = row.get("prev_hash")
        found_hash = row.get("hash")
        if not isinstance(found_prev, str) or not isinstance(found_hash, str):
            raise RuntimeError(f"invalid chain hash fields at line {idx}")
        if found_prev != prev:
            raise RuntimeError(f"prev_hash mismatch at line {idx}")
        if row.get("schema_hash") != expected_schema_hash:
            raise RuntimeError(f"schema_hash mismatch at line {idx}")
        body = {k: v for k, v in row.items() if k != "hash"}
        calc = _sha256_hex(_canonical_json(body).encode("utf-8"))
        if calc != found_hash:
            raise RuntimeError(f"broken chain hash at line {idx}")
        prev = found_hash


def _build_chain_record(event: dict[str, Any], prev_hash: str) -> dict[str, Any]:
    row = {
        "event_id": event["event_id"],
        "ts": _now_utc_iso(),
        "schema_id": SCHEMA_ID,
        "schema_hash": _schema_hash(),
        "canonical_event_hash": _sha256_hex(_canonical_json(event).encode("utf-8")),
        "prev_hash": prev_hash,
    }
    row["hash"] = _sha256_hex(_canonical_json(row).encode("utf-8"))
    return row


def observe_event(
    event: dict[str, Any],
    *,
    channel: str,
    source_path: str,
    request_id: str | None,
) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise RuntimeError("event must be an object")
    if not isinstance(channel, str):
        raise RuntimeError("channel must be string")
    if not isinstance(source_path, str):
        raise RuntimeError("source_path must be string")
    if request_id is not None and not isinstance(request_id, str):
        raise RuntimeError("request_id must be string or null")

    # Keep signature stable and enforce schema id.
    event_obj = dict(event)
    event_obj.setdefault("event_id", "obs_" + uuid4().hex)
    event_obj.setdefault("ts", _now_utc_iso())
    event_obj["schema_id"] = SCHEMA_ID

    validator = Draft202012Validator(_SCHEMA)
    violations = list(validator.iter_errors(event_obj))
    if violations:
        msg = "; ".join(sorted(err.message for err in violations))
        raise RuntimeError(f"observe event schema violation: {msg}")

    _check_forbidden_keys(event_obj)

    observer_path = DEFAULT_OBSERVER_PATH
    chain_path = DEFAULT_CHAIN_PATH
    existing_rows = _iter_jsonl(chain_path)
    _verify_existing_chain(existing_rows)
    prev_hash = existing_rows[-1]["hash"] if existing_rows else ("0" * 64)
    chain_row = _build_chain_record(event_obj, prev_hash)

    # Atomic append: build all lines first, then append.
    observer_path.parent.mkdir(parents=True, exist_ok=True)
    chain_path.parent.mkdir(parents=True, exist_ok=True)
    with observer_path.open("a", encoding="utf-8") as f_obs, chain_path.open("a", encoding="utf-8") as f_chain:
        f_obs.write(_canonical_json(event_obj) + "\n")
        f_chain.write(_canonical_json(chain_row) + "\n")

    return {
        "event_id": event_obj["event_id"],
        "request_id": request_id,
        "channel": channel,
        "source_path": source_path,
        "chain_hash": chain_row["hash"],
    }
