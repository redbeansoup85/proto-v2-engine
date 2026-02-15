#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.audit.verify_override_chain import verify_chain  # noqa: E402
from tools.override.override_registry import build_active_overrides, load_events  # noqa: E402
from tools.override.schema_override_event import canonical_json  # noqa: E402



def _exit2(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(2)



def evaluate_guard(audit_jsonl: str, symbol: str, now_ts: str) -> dict:
    verify_chain(audit_jsonl)
    events = load_events(audit_jsonl)
    active = build_active_overrides(events, now_ts)

    active_override = active.get(symbol)
    if active_override is None:
        return {"allow": True, "reason": "NO_ACTIVE_OVERRIDE", "active_override": None}

    if active_override.get("requested_action") == "block_execution":
        return {"allow": False, "reason": "ACTIVE_OVERRIDE_BLOCK", "active_override": active_override}

    return {"allow": True, "reason": "ACTIVE_OVERRIDE_NON_BLOCK", "active_override": active_override}



def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-jsonl", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--now-ts", required=True)
    args = ap.parse_args()

    try:
        out = evaluate_guard(args.audit_jsonl, args.symbol, args.now_ts)
        print(canonical_json(out))
    except SystemExit as e:
        if isinstance(e.code, int):
            raise
        _exit2(str(e.code))
    except OSError as e:
        _exit2("IO_FAIL: " + str(e))
    except Exception as e:
        _exit2("CONTRACT_FAIL: " + str(e))


if __name__ == "__main__":
    main()
