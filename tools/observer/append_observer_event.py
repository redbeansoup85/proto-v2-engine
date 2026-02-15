#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Reuse canonical hasher used by lock3 gate
from tools.gates.lock3_observer_gate import hash_event

# Optional signature support
_SIG_AVAILABLE = False
try:
    from auralis_v1.core.signature import load_sig_config_from_env, sign_hash_hex  # type: ignore

    _SIG_AVAILABLE = True
except Exception:
    load_sig_config_from_env = None  # type: ignore
    sign_hash_hex = None  # type: ignore
    _SIG_AVAILABLE = False


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


def _maybe_sign_event_hash(event_hash_hex: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    if not _SIG_AVAILABLE:
        return None, {"enabled": False, "reason": "SIG_MODULE_UNAVAILABLE"}

    try:
        cfg = load_sig_config_from_env()  # type: ignore[misc]
    except Exception as e:
        return None, {"enabled": False, "reason": "SIG_CONFIG_LOAD_FAIL", "err": str(e)}

    if not cfg:
        return None, {"enabled": False, "reason": "SIG_DISABLED"}

    cfg_enabled = bool(cfg.get("enabled")) if isinstance(cfg, dict) else bool(getattr(cfg, "enabled", False))
    if not cfg_enabled:
        return None, {"enabled": False, "reason": "SIG_DISABLED"}

    try:
        sig = sign_hash_hex(event_hash_hex, cfg)  # type: ignore[misc]
        if not sig:
            return None, {"enabled": False, "reason": "SIG_DISABLED"}

        key_id = cfg.get("key_id", "n/a") if isinstance(cfg, dict) else str(getattr(cfg, "key_id", "n/a"))
        return sig, {"enabled": True, "reason": "SIG_OK", "key_id": key_id}
    except Exception as e:
        return None, {"enabled": False, "reason": "SIG_ERROR", "err": str(e)}


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
    sig, meta = _maybe_sign_event_hash(obj["hash"])
    obj["signature_meta"] = meta
    if sig is not None:
        obj["signature"] = sig

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
