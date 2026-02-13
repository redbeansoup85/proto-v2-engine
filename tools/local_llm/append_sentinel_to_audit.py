import json
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone

from auralis_v1.core.audit_chain import append_audit

ROOT = Path(__file__).resolve().parents[2]
SNAP_PATH = ROOT / "var" / "local_llm" / "snapshot.json"
DRY_PATH  = ROOT / "var" / "local_llm" / "dry_run_validated.json"
GATE_PATH = ROOT / "var" / "local_llm" / "gate_decision.json"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def make_evt(kind: str, payload: dict, run_id: str) -> dict:
    inner = {
        "event_id": str(uuid.uuid4()),
        "schema": "sentinel_event.v1",
        "kind": kind,
        "payload": payload,
        "meta": {"run_id": run_id},
        "source": {"source_type": "local_llm", "device_id": "macstudio"},
        "ts": now_iso(),
    }
    return {
        "kind": "SENTINEL_EVENT",
        "text": json.dumps(inner, ensure_ascii=False),
        "gate": {
            "source": "tools.local_llm",
            "schema": "sentinel_event.v1",
            "kind": kind,
            "device_id": "macstudio",
            "run_id": run_id,
        }
    }

def main():
    run_id = os.getenv("RUN_ID", "")
    if not run_id:
        run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    if not SNAP_PATH.exists():
        SNAP_PATH.write_text(
            json.dumps({"note": "missing snapshot.json", "ts": now_iso()}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    snap = json.loads(SNAP_PATH.read_text(encoding="utf-8"))
    dry  = json.loads(DRY_PATH.read_text(encoding="utf-8"))
    gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))

    r1 = append_audit(make_evt("sentinel.snapshot", snap, run_id))
    r2 = append_audit(make_evt("sentinel.dry_run.validated", dry, run_id))
    r3 = append_audit(make_evt("sentinel.gate.decision", gate, run_id))

    print("OK: appended 3 sentinel events")
    print("RUN_ID:", run_id)
    print("- snapshot:", r1.get("hash", "n/a"))
    print("- dry_run:",  r2.get("hash", "n/a"))
    print("- gate:",     r3.get("hash", "n/a"))

if __name__ == "__main__":
    main()
