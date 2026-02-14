#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TS_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")


def _load_json(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return obj


def _validate_summary(summary: dict) -> str:
    if summary.get("schema") != "sentinel_summary.v0":
        raise ValueError("summary.schema must be sentinel_summary.v0")
    ts = summary.get("ts")
    if not isinstance(ts, str) or not TS_RE.fullmatch(ts):
        raise ValueError("summary.ts must match yyyymmddTHHMMSSZ")
    items = summary.get("items")
    if not isinstance(items, list):
        raise ValueError("summary.items must be a list")
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"summary.items[{i}] must be object")
        if not isinstance(item.get("symbol"), str) or not item.get("symbol"):
            raise ValueError(f"summary.items[{i}].symbol invalid")
        if not isinstance(item.get("score"), int):
            raise ValueError(f"summary.items[{i}].score must be int")
        if item.get("risk_level") not in ("low", "medium", "high"):
            raise ValueError(f"summary.items[{i}].risk_level invalid")
        if not isinstance(item.get("confidence"), (int, float)):
            raise ValueError(f"summary.items[{i}].confidence must be number")
    return ts


def _validate_events(events: dict, ts: str) -> None:
    if events.get("schema") != "sentinel_events.v0":
        raise ValueError("events.schema must be sentinel_events.v0")
    if events.get("ts") != ts:
        raise ValueError("events.ts must match summary.ts")
    arr = events.get("events")
    if not isinstance(arr, list):
        raise ValueError("events.events must be a list")
    count = events.get("count")
    if not isinstance(count, int) or count != len(arr):
        raise ValueError("events.count must equal len(events.events)")
    for i, ev in enumerate(arr):
        if not isinstance(ev, dict):
            raise ValueError(f"events.events[{i}] must be object")
        if ev.get("type") not in ("SCORE_JUMP", "RISK_UP", "CONF_DROP"):
            raise ValueError(f"events.events[{i}].type invalid")
        if not isinstance(ev.get("symbol"), str) or not ev.get("symbol"):
            raise ValueError(f"events.events[{i}].symbol invalid")
        if ev.get("ts") != ts:
            raise ValueError(f"events.events[{i}].ts must match summary.ts")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-file", required=True, help="/tmp/metaos_domain_events/_summary/summary_<TS>.json")
    ap.add_argument("--events-dir", default="/tmp/_events")
    ap.add_argument("--output-dir", default="/tmp/_observer_test")
    args = ap.parse_args()

    try:
        summary_path = Path(args.summary_file)
        summary = _load_json(summary_path)
        ts = _validate_summary(summary)

        events_path = Path(args.events_dir) / f"event_{ts}.json"
        if not events_path.exists():
            raise ValueError(f"missing events file: {events_path}")
        events = _load_json(events_path)
        _validate_events(events, ts)

        out = {
            "schema": "observer_replay.v0",
            "ts": ts,
            "summary_file": str(summary_path),
            "events_file": str(events_path),
            "summary_item_count": len(summary["items"]),
            "event_count": events["count"],
        }

        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"replay_{ts}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote {out_path}")
        return 0
    except Exception as exc:
        print(f"FAIL-CLOSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
