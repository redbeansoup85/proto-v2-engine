from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.audit.verify_override_chain import verify_chain  # noqa: E402
from tools.override.override_registry import build_active_overrides, load_events, parse_isoz  # noqa: E402
from tools.override.schema_override_event import canonical_json  # noqa: E402



def _exit2(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(2)



def build_report(audit_jsonl: str, now_ts: str) -> dict:
    verify_chain(audit_jsonl)
    events = load_events(audit_jsonl)

    counts_by_type: dict[str, int] = {}
    counts_by_reason_code: dict[str, int] = {}

    latencies = []
    by_id = {ev.get("event_id"): ev for ev in events}

    for ev in events:
        et = ev.get("type")
        counts_by_type[et] = counts_by_type.get(et, 0) + 1

        if et == "OVERRIDE_REQUESTED":
            rc = ev.get("request", {}).get("reason_code")
            if rc is not None:
                counts_by_reason_code[rc] = counts_by_reason_code.get(rc, 0) + 1

        if et == "OVERRIDE_APPROVED":
            req = by_id.get(ev.get("ref_request_event_id"))
            if req and req.get("type") == "OVERRIDE_REQUESTED":
                try:
                    delta = (parse_isoz(ev["ts"]) - parse_isoz(req["ts"])).total_seconds()
                    latencies.append(float(delta))
                except Exception:
                    pass

    avg = 0.0
    if latencies:
        avg = float(sum(latencies) / len(latencies))

    active_map = build_active_overrides(events, now_ts)
    active_overrides = [active_map[sym] for sym in sorted(active_map.keys())]

    return {
        "counts_by_type": counts_by_type,
        "counts_by_reason_code": counts_by_reason_code,
        "approval_latency_sec_avg": avg,
        "active_overrides": active_overrides,
    }



def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-jsonl", required=True)
    ap.add_argument("--now-ts", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        report = build_report(args.audit_jsonl, args.now_ts)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(canonical_json(report) + "\n")
        print(f"OK: wrote override report: {args.out}")
    except SystemExit as e:
        if isinstance(e.code, int):
            raise
        _exit2(str(e.code))
    except OSError as e:
        _exit2("IO_FAIL: " + str(e))
    except Exception as e:
        _exit2("VERIFY_FAIL: " + str(e))


if __name__ == "__main__":
    main()
