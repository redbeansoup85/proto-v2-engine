from __future__ import annotations
import hashlib
from tools.gates.gate_live_execution import validate_or_record
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse
from infra.risk.regime import RiskRegime, get_regime_warden

# NOTE: we call existing append tool to keep audit semantics consistent.
import subprocess

router = APIRouter()


# kill-switch state file (survives restart, avoids circular imports)
EXECUTOR_KILL_SWITCH_FILE = Path("var/metaos/state/executor_kill_switch.txt")

def _read_kill_file() -> bool:
    try:
        raw = EXECUTOR_KILL_SWITCH_FILE.read_text(encoding="utf-8").strip()
        return raw == "1"
    except Exception:
        return False

def _write_kill_file(val: bool) -> None:
    EXECUTOR_KILL_SWITCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    EXECUTOR_KILL_SWITCH_FILE.write_text("1" if val else "0", encoding="utf-8")

# in-process cache (kept in sync with file)
_KILL_SWITCH: bool = _read_kill_file()

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


def _extract_regime_inputs(intent: Dict[str, Any]) -> tuple[int, list[str], bool, list[str]]:
    block = intent.get("risk_regime_input")
    if not isinstance(block, dict):
        # Fail-closed when no macro gate source is present.
        return 0, ["vix", "dxy", "real10y", "btcvol"], False, ["risk_regime_input_missing"]

    gate_hits_raw = block.get("gate_hits")
    if not isinstance(gate_hits_raw, dict):
        return 0, ["vix", "dxy", "real10y", "btcvol"], bool(block.get("hard_kill") is True), ["gate_hits_missing"]

    expected = ("vix", "dxy", "real10y", "btcvol")
    hits: dict[str, bool] = {}
    for key in expected:
        val = gate_hits_raw.get(key)
        if isinstance(val, bool):
            hits[key] = val
        else:
            hits[key] = False

    missing = block.get("missing")
    missing_list = [str(x) for x in missing] if isinstance(missing, list) else []
    hard_kill = bool(block.get("hard_kill") is True)
    gate_count = sum(1 for v in hits.values() if v)

    reasons = [f"gate_hits={hits}"]
    return gate_count, missing_list, hard_kill, reasons


def _stamp_regime(intent: Dict[str, Any], regime_meta: Dict[str, Any]) -> None:
    intent["risk_regime"] = {
        "current": regime_meta.get("current_regime"),
        "target": regime_meta.get("target_regime"),
        "reasons": regime_meta.get("reasons", []),
        "missing": regime_meta.get("missing", []),
        "cooldown_remaining_ms": int(regime_meta.get("cooldown_remaining_ms", 0) or 0),
    }
    evidence_refs = intent.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        evidence_refs = []
    evidence_refs.append(
        {
            "ref_kind": "RISK_REGIME",
            "ref": {
                "current": intent["risk_regime"]["current"],
                "target": intent["risk_regime"]["target"],
                "missing": intent["risk_regime"]["missing"],
            },
        }
    )
    intent["evidence_refs"] = evidence_refs

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

    # UI/API/file kill-switch (fail-closed)
    global _KILL_SWITCH
    _KILL_SWITCH = _read_kill_file() or _KILL_SWITCH
    if _KILL_SWITCH:
        raise HTTPException(status_code=423, detail="kill_switch_file=1")
    # guardrail: require at least asset/symbol if present in your schema
    if not isinstance(intent, dict) or len(intent) == 0:
        raise HTTPException(status_code=400, detail="empty intent")

    # fail-closed: accept only execution_intent.v1 payloads
    if intent.get("schema") != "execution_intent.v1":
        raise HTTPException(status_code=400, detail="invalid_schema_expected_execution_intent_v1")

    # SSOT regime guard. Any error here is fail-closed.
    try:
        gate_count, missing, hard_kill, regime_reasons = _extract_regime_inputs(intent)
        regime = get_regime_warden()
        regime_meta = regime.update(
            now_ms=int(time.time() * 1000),
            gate_count=gate_count,
            missing=missing,
            hard_kill=hard_kill,
        ).as_dict()
        if regime_reasons:
            regime_meta["reasons"] = list(regime_meta.get("reasons", [])) + regime_reasons
    except Exception as exc:
        intent["regime_error"] = f"{type(exc).__name__}:{exc}"
        raise HTTPException(status_code=423, detail="risk_regime_unavailable_fail_closed")

    _stamp_regime(intent, regime_meta)

    current_regime = regime_meta.get("current_regime")
    if current_regime == RiskRegime.BLACK_SWAN.value:
        _KILL_SWITCH = True
        _write_kill_file(True)
        raise HTTPException(status_code=423, detail="risk_regime_black_swan_kill_switch")
    if current_regime == RiskRegime.SHOCK.value:
        raise HTTPException(status_code=423, detail="risk_regime_shock_new_entries_blocked")
    if current_regime == RiskRegime.WARNING.value:
        payload = intent.get("intent")
        if isinstance(payload, dict):
            items = payload.get("items")
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    conf = item.get("final_confidence")
                    if isinstance(conf, (int, float)):
                        item["final_confidence"] = float(conf) * 0.5
                    q = item.get("quality")
                    if isinstance(q, dict):
                        effects = q.get("effects")
                        if isinstance(effects, dict):
                            effects["size_multiplier"] = float(effects.get("size_multiplier", 1.0)) * 0.5

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


@router.post("/api/executor/kill")
def executor_kill(payload: dict = Body(default_factory=dict)):
    """
    Request executor kill-switch ON (fail-closed).
    """
    global _KILL_SWITCH
    _KILL_SWITCH = True
    _write_kill_file(True)
    return JSONResponse({"ok": True, "kill_switch": _KILL_SWITCH, "mode": "kill"}, status_code=200)

@router.post("/api/executor/lock")
def executor_lock(payload: dict = Body(default_factory=dict)):
    """
    Alias of kill: lock execution.
    """
    global _KILL_SWITCH
    _KILL_SWITCH = True
    _write_kill_file(True)
    return JSONResponse({"ok": True, "kill_switch": _KILL_SWITCH, "mode": "lock"}, status_code=200)

@router.post("/api/executor/unlock")
def executor_unlock(payload: dict = Body(default_factory=dict)):
    """
    Request executor kill-switch OFF.
    """
    global _KILL_SWITCH
    _KILL_SWITCH = False
    _write_kill_file(False)
    return JSONResponse({"ok": True, "kill_switch": _KILL_SWITCH, "mode": "unlock"}, status_code=200)
