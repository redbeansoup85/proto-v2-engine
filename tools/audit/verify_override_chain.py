from __future__ import annotations

import argparse
import copy
import io
import json
import os
import sys
from contextlib import redirect_stderr
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.override.schema_override_event import (  # noqa: E402
    canonical_json,
    sha256_hex,
    validate_override_event_full,
)



def _exit2(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(2)



def _verify_fail(msg: str) -> None:
    _exit2("VERIFY_FAIL: " + msg)



def _io_fail(msg: str) -> None:
    _exit2("IO_FAIL: " + msg)



def _parse_isoz(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))



def verify_chain(audit_jsonl: str) -> dict:
    if not os.path.exists(audit_jsonl):
        _io_fail(f"audit file missing: {audit_jsonl}")

    try:
        with open(audit_jsonl, "r", encoding="utf-8") as f:
            raw_lines = f.read().splitlines()
    except OSError as e:
        _io_fail(str(e))

    nonempty = [(idx + 1, line) for idx, line in enumerate(raw_lines) if line.strip()]
    if not nonempty:
        _verify_fail(f"audit file empty: {audit_jsonl}")

    events: list[dict] = []
    prev_row_hash = None
    first_hash = None

    for file_line_no, line in nonempty:
        try:
            ev = json.loads(line)
        except Exception as e:
            _verify_fail(f"invalid json at line {file_line_no}: {e}")

        schema_err = io.StringIO()
        try:
            with redirect_stderr(schema_err):
                validate_override_event_full(ev)
        except SystemExit:
            _verify_fail(f"line {file_line_no}: schema validation failed")

        curr_prev_hash = ev["chain"]["prev_hash"]
        curr_hash = ev["chain"]["hash"]

        if prev_row_hash is None:
            if curr_prev_hash != "GENESIS":
                _verify_fail(f"line {file_line_no}: first prev_hash must be GENESIS")
            first_hash = curr_hash
        else:
            if curr_prev_hash != prev_row_hash:
                _verify_fail(f"line {file_line_no}: prev_hash mismatch")

        payload_subset = copy.deepcopy(ev)
        payload_subset["chain"].pop("hash", None)
        payload_digest = sha256_hex(canonical_json(payload_subset))
        expected = sha256_hex(curr_prev_hash + ":" + payload_digest)
        if expected != curr_hash:
            _verify_fail(f"line {file_line_no}: chain hash mismatch")

        events.append(ev)
        prev_row_hash = curr_hash

    events_by_id: dict[str, dict] = {}
    for ev in events:
        ev_id = ev["event_id"]
        if ev_id in events_by_id:
            _verify_fail(f"duplicate event_id: {ev_id}")
        events_by_id[ev_id] = ev

    for ev in events:
        ev_type = ev["type"]

        if ev_type in {"OVERRIDE_APPROVED", "OVERRIDE_REJECTED"}:
            req_id = ev["ref_request_event_id"]
            req = events_by_id.get(req_id)
            if req is None or req.get("type") != "OVERRIDE_REQUESTED":
                _verify_fail(f"missing OVERRIDE_REQUESTED: {req_id}")

            if req["actor"]["subject"] == ev["actor"]["subject"]:
                _verify_fail(f"role_separation_violation request={req_id} approval={ev['event_id']}")

            if ev_type == "OVERRIDE_APPROVED":
                try:
                    approval_ts = _parse_isoz(ev["ts"])
                    expires_at = _parse_isoz(ev["approval"]["constraints"]["expires_at"])
                except Exception:
                    _verify_fail(f"invalid_expires_at approval={ev['event_id']}")
                if expires_at <= approval_ts:
                    _verify_fail(f"invalid_expires_at approval={ev['event_id']}")

        if ev_type == "OVERRIDE_EXECUTED":
            req_id = ev["ref_request_event_id"]
            appr_id = ev["ref_approval_event_id"]

            req = events_by_id.get(req_id)
            if req is None or req.get("type") != "OVERRIDE_REQUESTED":
                _verify_fail(f"missing OVERRIDE_REQUESTED: {req_id}")

            appr = events_by_id.get(appr_id)
            if (
                appr is None
                or appr.get("type") != "OVERRIDE_APPROVED"
                or appr.get("approval", {}).get("decision") != "approved"
            ):
                _verify_fail(f"missing OVERRIDE_APPROVED: {appr_id}")

            if appr.get("ref_request_event_id") != req_id:
                _verify_fail(f"approval_request_mismatch approval={appr_id} request={req_id}")

            try:
                executed_ts = _parse_isoz(ev["ts"])
                expires_at = _parse_isoz(appr["approval"]["constraints"]["expires_at"])
            except Exception:
                _verify_fail(f"expired_override approval={appr_id} executed={ev['event_id']}")

            if executed_ts > expires_at:
                _verify_fail(f"expired_override approval={appr_id} executed={ev['event_id']}")

    return {
        "rows": len(events),
        "head": first_hash,
        "tail": prev_row_hash,
    }



def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-jsonl", required=True)
    args = ap.parse_args()

    try:
        result = verify_chain(args.audit_jsonl)
        print(
            f"OK: verified override chain rows={result['rows']} head={result['head']} tail={result['tail']}"
        )
    except SystemExit as e:
        if isinstance(e.code, int):
            raise
        _exit2(str(e.code))
    except OSError as e:
        _io_fail(str(e))
    except Exception as e:
        _verify_fail(str(e))


if __name__ == "__main__":
    main()
