#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Reuse canonical hasher used by lock3 gate
from tools.gates.lock3_observer_gate import hash_event


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _last_hash_from_file(path: Path) -> str:
    if not path.exists():
        return "0"
    txt = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not txt:
        return "0"
    last = txt.splitlines()[-1]
    try:
        obj = json.loads(last)
        h = obj.get("hash")
        if isinstance(h, str) and h:
            return h
    except Exception:
        pass
    # fail-closed is handled by the gate; here we default to "0" to avoid crashing local tooling
    return "0"


def append_observer_event(
    *,
    out_path: Path,
    event_id: str,
    judgment_id: str,
    approval_record_id: str,
    execution_run_id: str,
    status: str,
    latency_ms: float,
    ts: Optional[str] = None,
) -> Dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    prev_hash = _last_hash_from_file(out_path)
    obj: Dict[str, Any] = {
        "schema_version": "v1",
        "event_id": event_id,
        "ts": ts or _utc_now_iso(),
        "judgment_id": judgment_id,
        "approval_record_id": approval_record_id,
        "execution_run_id": execution_run_id,
        "status": status,
        "metrics": {"latency_ms": float(latency_ms)},
        "prev_hash": prev_hash,
    }
    obj["hash"] = hash_event(obj["prev_hash"], obj)

    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    return obj


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Append LOCK-3 observer event (hash-chained).")
    ap.add_argument("--out", required=True, help="Output observer jsonl file")
    ap.add_argument("--event-id", required=True)
    ap.add_argument("--judgment-id", required=True)
    ap.add_argument("--approval-record-id", required=True)
    ap.add_argument("--execution-run-id", required=True)
    ap.add_argument("--status", required=True, choices=["started", "ok", "fail"])
    ap.add_argument("--latency-ms", required=True, type=float)
    args = ap.parse_args()

    obj = append_observer_event(
        out_path=Path(args.out),
        event_id=args.event_id,
        judgment_id=args.judgment_id,
        approval_record_id=args.approval_record_id,
        execution_run_id=args.execution_run_id,
        status=args.status,
        latency_ms=args.latency_ms,
    )
    print(json.dumps(obj, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
