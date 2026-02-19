from __future__ import annotations
import hashlib
from tools.gates.gate_live_execution import validate_or_record
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

# NOTE: we call existing append tool to keep audit semantics consistent.
import subprocess

router = APIRouter()

OUTBOX_DIR = Path(os.getenv("SENTINEL_OUTBOX_DIR", "/tmp/orch_outbox_live/SENTINEL_EXEC"))
AUDIT_ROOT = Path(os.getenv("AURALIS_AUDIT_PATH", str(Path.cwd() / "var/audit_chain")))
AUDIT_EXEC_INTENT = Path(os.getenv("AUDIT_EXECUTION_INTENT_JSONL", str(AUDIT_ROOT / "execution_intent.jsonl")))


def is_live_enabled() -> bool:
    return os.getenv("LIVE_TRADING_ENABLED") == "true"



def _recent_event_id_exists(audit_path: Path, event_id: str, scan_lines: int = 500) -> bool:
    if not audit_path.exists():
        return False
    try:
        lines = audit_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return False
    for line in lines[-scan_lines:]:
        if f'"event_id":"{event_id}"' in line:
            return True
    return False

@router.post("/execute_market")
def execute_market(intent: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Minimal executor endpoint:
    - Accepts an intent JSON payload
    - Writes it to a tmp file (for existing tooling)
    - Appends to execution_intent audit chain
    - Returns status

    This is OBSERVER/EXECUTOR side; loop should be outbox-only by default.
    """
    # hard fail-safe: default-disabled live trading kill switch
    if not is_live_enabled():
        return {"status": "blocked_by_env", "reason": "LIVE_TRADING_DISABLED"}

    # optional hard kill-switch (can be wired to UI later)
    if os.getenv("EXECUTOR_KILL_SWITCH", "0") == "1":
        raise HTTPException(status_code=423, detail="executor_kill_switch=1")

    # guardrail: require at least asset/symbol if present in your schema
    if not isinstance(intent, dict) or len(intent) == 0:
        raise HTTPException(status_code=400, detail="empty intent")

    # fail-closed: accept only execution_intent.v1 payloads
    if intent.get("schema") != "execution_intent.v1":
        raise HTTPException(status_code=400, detail="invalid_schema_expected_execution_intent_v1")

    # 🔒 LIVE gate enforcement (optional; fail-closed when enabled)
    if os.getenv("LIVE_GATE_ENFORCE", "0") == "1":
        # 📦 LIVE policy capsule (fail-closed when enforcement enabled)
        capsule_path = Path("policies/live_caps.v1.json")
        try:
            capsule_bytes = capsule_path.read_bytes()
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail="live_capsule_missing")
        capsule_sha256 = hashlib.sha256(capsule_bytes).hexdigest()
        try:
            _capsule = json.loads(capsule_bytes.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=500, detail=f"live_capsule_invalid_json:{capsule_sha256}")
        try:
            ok = validate_or_record(
                intent,
                exceptions_dir="data/live_exceptions",
                last_price_usd=intent.get("last_price_usd"),
            )
            if ok is False:
                mode = os.getenv("LIVE_GATE_MODE", "hard").lower()
                if mode == "soft":
                    return {"status": "blocked_by_gate", "reason": f"live_gate_blocked:{capsule_sha256}"}
                raise HTTPException(status_code=403, detail=f"live_gate_blocked:{capsule_sha256}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"live_gate_error:{type(e).__name__}:{capsule_sha256}")
    if intent.get("domain") not in ("SENTINEL_EXEC",):
        raise HTTPException(status_code=400, detail="invalid_domain_expected_SENTINEL_EXEC")

    event_id = intent.get("event_id")
    if not event_id:
        raise HTTPException(status_code=400, detail="missing_event_id")

    # idempotency: reject duplicates by event_id (prevents retry double-append)
    if _recent_event_id_exists(AUDIT_EXEC_INTENT, event_id):
        raise HTTPException(status_code=409, detail="already_applied_event_id")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tmp_dir = Path("/tmp/metaos_executor")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    intent_path = tmp_dir / f"intent_http_{ts}.json"
    intent_path.write_text(json.dumps(intent, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    # append execution_intent audit (fail-closed)
    try:
        cp = subprocess.run(
            [
                "python",
                "tools/observer_append_execution_intent.py",
                "--intent-file",
                str(intent_path),
                "--audit-jsonl",
                str(AUDIT_EXEC_INTENT),
            ],
            text=True,
            capture_output=True,
        )
        if cp.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"append_execution_intent_failed rc={cp.returncode} stderr={cp.stderr.strip()} stdout={cp.stdout.strip()}",
            )
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"append_execution_intent_failed rc={e.returncode}")

    return {"status": "ok", "intent_file": str(intent_path), "audit": str(AUDIT_EXEC_INTENT), "audit_resolved": str(Path(AUDIT_EXEC_INTENT).resolve()), "module_file": __file__}
