from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.override.schema_override_event import require  # noqa: E402



def _exit2(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(2)



def parse_isoz(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))



def load_events(audit_jsonl: str) -> list[dict]:
    if not os.path.exists(audit_jsonl):
        _exit2("IO_FAIL: audit file missing: " + audit_jsonl)
    try:
        with open(audit_jsonl, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as e:
        _exit2("IO_FAIL: " + str(e))

    events = []
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except Exception as e:
            _exit2(f"VERIFY_FAIL: invalid json at line {line_no}: {e}")
    return events



def build_event_index(events: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for ev in events:
        ev_id = ev.get("event_id")
        if ev_id in out:
            _exit2(f"VERIFY_FAIL: duplicate event_id: {ev_id}")
        out[ev_id] = ev
    return out



def find_request(events_by_id: dict, request_id: str) -> dict:
    ev = events_by_id.get(request_id)
    if ev is None or ev.get("type") != "OVERRIDE_REQUESTED":
        _exit2(f"VERIFY_FAIL: missing OVERRIDE_REQUESTED: {request_id}")
    return ev



def find_approved(events_by_id: dict, approval_id: str) -> dict:
    ev = events_by_id.get(approval_id)
    if (
        ev is None
        or ev.get("type") != "OVERRIDE_APPROVED"
        or ev.get("approval", {}).get("decision") != "approved"
    ):
        _exit2(f"VERIFY_FAIL: missing OVERRIDE_APPROVED: {approval_id}")
    return ev



def _dedupe_refs(refs: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out



def build_active_overrides(events: list[dict], now_ts: str) -> dict[str, dict]:
    try:
        now_dt = parse_isoz(now_ts)
    except Exception:
        require(False, "invalid now_ts")
        raise AssertionError("unreachable")

    events_by_id = build_event_index(events)
    active_candidates: dict[str, tuple[datetime, int, dict]] = {}

    for line_idx, ev in enumerate(events):
        if ev.get("type") != "OVERRIDE_APPROVED":
            continue

        constraints = ev.get("approval", {}).get("constraints", {})
        try:
            expires_at_dt = parse_isoz(constraints["expires_at"])
            approval_dt = parse_isoz(ev["ts"])
        except Exception:
            continue

        if expires_at_dt <= now_dt:
            continue

        req_id = ev.get("ref_request_event_id", "")
        req = find_request(events_by_id, req_id)

        scope = constraints.get("scope") or []
        req_info = req.get("request", {})
        merged = {
            "requested_action": req_info.get("requested_action"),
            "reason_code": req_info.get("reason_code"),
            "request_event_id": req_id,
            "approval_event_id": ev.get("event_id"),
            "request_ts": req.get("ts"),
            "approval_ts": ev.get("ts"),
            "expires_at": constraints.get("expires_at"),
            "max_notional": constraints.get("max_notional"),
            "request_actor": req.get("actor"),
            "approval_actor": ev.get("actor"),
            "evidence_refs": _dedupe_refs((req.get("evidence_refs") or []) + (ev.get("evidence_refs") or [])),
        }

        for symbol in scope:
            candidate = dict(merged)
            candidate["symbol"] = symbol
            prev = active_candidates.get(symbol)
            if prev is None:
                active_candidates[symbol] = (approval_dt, line_idx, candidate)
                continue
            prev_dt, prev_line, _ = prev
            if approval_dt > prev_dt or (approval_dt == prev_dt and line_idx > prev_line):
                active_candidates[symbol] = (approval_dt, line_idx, candidate)

    return {sym: active_candidates[sym][2] for sym in active_candidates}
