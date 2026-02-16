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
        raise RuntimeError("FAIL_CLOSED: malformed chain tail")
    return GENESIS_HASH


def append_simulation_audit(
    *,
    intent: dict[str, Any],
    out_path: Path,
    chain_path: Path,
) -> dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    chain_path.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "ts": _utc_now_iso(),
        "track_id": "SIMULATION",
        "schema_version": "sentinel_trade_intent.v1",
        "intent_id": intent.get("intent_id"),
        "quality_flags": ((intent.get("quality") or {}).get("quality_flags") or []),
        "intent": intent,
    }
    event_line = _canonical_json(event)

    prev_hash = _read_last_hash(chain_path)
    chain_record = {
        "ts": event["ts"],
        "track_id": "SIMULATION",
        "intent_id": intent.get("intent_id"),
        "prev_hash": prev_hash,
        "event_hash": _sha256_hex(_canonical_json(intent)),
    }
    chain_record["hash"] = _sha256_hex(_canonical_json(chain_record))

    with out_path.open("a", encoding="utf-8") as f_events, chain_path.open("a", encoding="utf-8") as f_chain:
        f_events.write(event_line + "\n")
        f_chain.write(_canonical_json(chain_record) + "\n")
    return chain_record
