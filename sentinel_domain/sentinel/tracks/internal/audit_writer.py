from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _assert_internal_paths(events_path: Path, chain_path: Path) -> None:
    ev = events_path.as_posix()
    ch = chain_path.as_posix()
    if "/internal/" not in f"/{ev}" or "/internal/" not in f"/{ch}":
        raise RuntimeError("FAIL_CLOSED: internal audit paths must include /internal/")
    if "/simulation/" in f"/{ev}" or "/simulation/" in f"/{ch}":
        raise RuntimeError("FAIL_CLOSED: internal audit path cannot point to simulation area")


def _read_last_hash(path: Path) -> str:
    if not path.exists():
        return GENESIS_HASH
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        raw = line.strip()
        if not raw:
            continue
        row = json.loads(raw)
        h = row.get("hash")
        if isinstance(h, str) and len(h) == 64:
            return h
        raise RuntimeError("FAIL_CLOSED: malformed internal chain tail")
    return GENESIS_HASH


def append_internal_audit(
    *,
    exec_intent: dict[str, Any],
    events_path: Path,
    chain_path: Path,
) -> dict[str, Any]:
    _assert_internal_paths(events_path, chain_path)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    chain_path.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "ts": _utc_now_iso(),
        "track_id": "INTERNAL",
        "schema_version": "internal_exec_intent.v1",
        "exec_intent_id": exec_intent.get("exec_intent_id"),
        "payload": exec_intent,
    }
    prev_hash = _read_last_hash(chain_path)
    chain = {
        "ts": event["ts"],
        "track_id": "INTERNAL",
        "exec_intent_id": exec_intent.get("exec_intent_id"),
        "prev_hash": prev_hash,
        "event_hash": _sha256_hex(_canonical_json(exec_intent)),
    }
    chain["hash"] = _sha256_hex(_canonical_json(chain))

    with events_path.open("a", encoding="utf-8") as fev, chain_path.open("a", encoding="utf-8") as fch:
        fev.write(_canonical_json(event) + "\n")
        fch.write(_canonical_json(chain) + "\n")
    return chain
