#!/usr/bin/env python3

import argparse
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _canonical_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False

def _read_last_record(path: Path) -> dict | None:
    if not path.is_file():
        return None
    with path.open("rb") as f:
        f.seek(0, 2)
        end = f.tell()
        if end == 0:
            return None
        size = min(8192, end)
        f.seek(end - size)
        chunk = f.read(size)
    lines = [ln for ln in chunk.splitlines() if ln.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1].decode("utf-8"))
    except Exception:
        return None

def _read_last_hash(observer_path: Path) -> str:
    last = _read_last_record(observer_path)
    if not last:
        return "GENESIS"
    # fail-closed: if someone pointed this at an audit chain, refuse
    if last.get("schema") == "audit_event.v1":
        raise RuntimeError(f"FAIL-CLOSED: observer log path points to audit_event.v1 file: {observer_path}")
    return (last.get("chain") or {}).get("hash") or "GENESIS"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intent-file", required=True)
    ap.add_argument(
        "--observer-jsonl",
        default="var/observer_events/execution_intent.ndjson",
        help="observer_event.v1 log output (MUST NOT be under var/audit_chain)",
    )
    args = ap.parse_args()

    intent_path = Path(args.intent_file)
    out_path = Path(args.observer_jsonl)

    if not intent_path.is_file():
        raise ValueError(f"intent file not found: {intent_path}")

    # hard fail-closed: never allow writing observer events into audit_chain
    if _is_under(out_path, Path("var/audit_chain")):
        raise RuntimeError(f"FAIL-CLOSED: refusing to write observer_event.v1 into audit_chain: {out_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    intent = json.loads(intent_path.read_text(encoding="utf-8"))
    prev_hash = _read_last_hash(out_path)
    regime = intent.get("risk_regime")
    regime_ref = None
    if isinstance(regime, dict):
        regime_ref = {
            "ref_kind": "RISK_REGIME",
            "ref": {
                "current": regime.get("current"),
                "target": regime.get("target"),
                "missing": regime.get("missing", []),
                "cooldown_remaining_ms": regime.get("cooldown_remaining_ms", 0),
            },
        }

    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    record = {
        "schema": "observer_event.v1",
        "event_id": str(uuid4()),
        "ts": now_iso,
        "source": {"source_type": "local", "producer": "tools/observer_append_execution_intent.py"},
        "kind": "execution_intent.append",
        "event_kind": "execution_intent",
        "ts_append_iso": now_iso,
        "payload": intent,
        "evidence_refs": [regime_ref] if regime_ref else [],
        "chain": {"prev_hash": prev_hash, "hash": None},
    }

    h = _sha256_hex(_canonical_bytes(record))
    record["chain"]["hash"] = h

    with out_path.open("ab") as f:
        f.write(_canonical_bytes(record) + b"\n")

    print(f"OK: appended observer_event.v1 to {out_path} hash={h} prev={prev_hash}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
