#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Reuse canonical hasher used by lock3 gate
from tools.gates.lock3_observer_gate import hash_event


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _last_hash_from_file(path: Path) -> str:
    """
    Returns last 'hash' from jsonl tip.
    - If file missing/empty: GENESIS
    - If last line is not valid JSON or missing hash: fail-closed (SystemExit)
    """
    if not path.exists():
        return "GENESIS"
    txt = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not txt:
        return "GENESIS"

    last = txt.splitlines()[-1].strip()
    if not last:
        return "GENESIS"

    try:
        obj = json.loads(last)
    except Exception as e:
        raise SystemExit(f"CONTRACT_FAIL: invalid jsonl tip in {path}: {e}")

    h = obj.get("hash")
    if not (isinstance(h, str) and len(h) == 64):
        raise SystemExit(f"CONTRACT_FAIL: jsonl tip missing/invalid hash in {path}")
    return h


def _normalize_evidence_refs(intent_file: Optional[str], evidence_refs: Optional[List[str]]) -> List[str]:
    ev: List[str] = []
    if evidence_refs:
        for x in evidence_refs:
            if x is None:
                continue
            s = str(x).strip()
            if s:
                ev.append(s)

    if intent_file:
        ip = os.path.abspath(intent_file)
        if ip not in ev:
            ev.append(ip)

    # de-dupe, preserve order
    out: List[str] = []
    seen = set()
    for x in ev:
        if x not in seen:
            out.append(x)
            seen.add(x)

    # hard guard
    if not out:
        raise SystemExit("CONTRACT_FAIL: evidence_refs must be non-empty (provide --intent-file or --evidence-ref)")
    return out


def append_observer_event(
    *,
    out_path: Path,
    event_id: str,
    judgment_id: str,
    approval_record_id: str,
    execution_run_id: str,
    status: str,
    latency_ms: float,
    intent_file: Optional[str] = None,
    evidence_refs: Optional[List[str]] = None,
    ts: Optional[str] = None,
) -> Dict[str, Any]:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    prev_hash = _last_hash_from_file(out_path)
    ev = _normalize_evidence_refs(intent_file, evidence_refs)

    obj: Dict[str, Any] = {
        "schema_version": "v1",
        "event_id": event_id,
        "ts": ts or _utc_now_iso(),
        "judgment_id": judgment_id,
        "approval_record_id": approval_record_id,
        "execution_run_id": execution_run_id,
        "status": status,
        "metrics": {"latency_ms": float(latency_ms)},
        # cross-ref anchors (for joins)
        "evidence_refs": ev,
        # audit chain
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

    # cross-ref anchors
    ap.add_argument("--intent-file", default="", help="(optional) intent file path to inject into evidence_refs")
    ap.add_argument(
        "--evidence-ref",
        action="append",
        default=[],
        help="(optional, repeatable) extra evidence ref paths/ids; at least one evidence ref is required",
    )

    args = ap.parse_args()

    intent_file = args.intent_file.strip() or None
    evidence_refs = [x for x in (args.evidence_ref or []) if isinstance(x, str) and x.strip()]

    obj = append_observer_event(
        out_path=Path(args.out),
        event_id=args.event_id,
        judgment_id=args.judgment_id,
        approval_record_id=args.approval_record_id,
        execution_run_id=args.execution_run_id,
        status=args.status,
        latency_ms=args.latency_ms,
        intent_file=intent_file,
        evidence_refs=evidence_refs,
    )
    print(json.dumps(obj, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
