from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVENT_SCHEMA_ID = "sentinel.intent_event.v1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_intent_hash(intent: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(intent).encode("utf-8")).hexdigest()


def _validate_event_shape(event: dict[str, Any]) -> None:
    required = {"event_id", "schema_id", "source", "track", "asset", "timeframe", "intent", "quality", "ts"}
    missing = sorted(required.difference(event.keys()))
    if missing:
        raise RuntimeError(f"FAIL_CLOSED: missing event fields: {missing}")
    if event.get("schema_id") != EVENT_SCHEMA_ID:
        raise RuntimeError(f"FAIL_CLOSED: schema_id must be {EVENT_SCHEMA_ID}")
    for key in ("event_id", "source", "track", "asset", "timeframe", "ts"):
        if not isinstance(event.get(key), str) or not event[key]:
            raise RuntimeError(f"FAIL_CLOSED: invalid event field: {key}")
    if not isinstance(event.get("quality"), dict):
        raise RuntimeError("FAIL_CLOSED: quality must be an object")
    intent = event.get("intent")
    if not isinstance(intent, dict):
        raise RuntimeError("FAIL_CLOSED: intent must be an object")
    # Local import avoids circular dependency with simulation pipeline module import graph.
    from sentinel.tracks.simulation.validators import validate_trade_intent

    validate_trade_intent(intent)


def append_intent_event(event: dict, path: str = "var/observer/sentinel/intent_events.jsonl") -> dict:
    """
    Validate and append a single sentinel.intent_event.v1 line atomically.
    Fail-closed on validation or I/O errors.
    """
    if not isinstance(event, dict):
        raise RuntimeError("FAIL_CLOSED: event must be an object")

    _validate_event_shape(event)

    out_event = dict(event)
    out_event["intent_hash"] = canonical_intent_hash(out_event["intent"])
    line = _canonical_json(out_event) + "\n"

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(out_path), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError as exc:
        raise RuntimeError(f"FAIL_CLOSED: intent event write failed: {exc}") from exc

    return out_event
