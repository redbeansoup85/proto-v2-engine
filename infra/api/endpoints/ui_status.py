from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["ui-readonly"])

OUTBOX_DIR = Path("/tmp/orch_outbox_live/SENTINEL_EXEC")
AUDIT_DIR = Path("var/audit_chain")
AUDIT_EXECUTION_INTENT = AUDIT_DIR / "execution_intent.jsonl"
AUDIT_PAPER_ORDERS = AUDIT_DIR / "paper_orders.jsonl"
AUDIT_PAPER_FILLS = AUDIT_DIR / "paper_fills.jsonl"

EXECUTOR_STATUS_CANDIDATES = [
    Path("var/metaos/state/executor_status.json"),
]
EXECUTOR_FAIL_STREAK_FILE = Path("var/metaos/state/executor_fail_streak.txt")

SCHEMA_EXPECTED_AUDIT = "audit_event.v1"


# ---------------------------------------------------------
# helpers
# ---------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def _latest_outbox_json() -> Optional[Dict[str, Any]]:
    try:
        files = sorted(
            OUTBOX_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except Exception:
        return None

    if not files:
        return None

    return _safe_load_json(files[0])


def _last_jsonl_row(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue

    return None


def _line_count(path: Path) -> Any:
    if not path.exists():
        return "n/a"

    try:
        return len([ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()])
    except Exception:
        return "n/a"


def _last_hash(path: Path) -> str:
    """
    Support both:
    - audit_event.v1 (top-level hash/prev_hash)
    - observer_event.v1 (chain.hash/chain.prev_hash)
    """
    row = _last_jsonl_row(path)
    if not row:
        return "n/a"

    h = row.get("hash")
    if isinstance(h, str) and h:
        return h

    chain = row.get("chain")
    if isinstance(chain, dict):
        h2 = chain.get("hash")
        if isinstance(h2, str) and h2:
            return h2

    return "n/a"


def _audit_status_block(path: Path, verbose: int) -> Dict[str, Any]:
    base = {
        "lines": _line_count(path),
        "last_hash": _last_hash(path),
    }
    if verbose:
        base["path"] = str(path)
        base["schema_expected"] = SCHEMA_EXPECTED_AUDIT
    return base


# ---------------------------------------------------------
# routes
# ---------------------------------------------------------

@router.get("/api/intent/latest")
def get_latest_intent() -> Any:
    # source priority: latest outbox -> audit execution_intent tail
    outbox_obj = _latest_outbox_json()
    if outbox_obj is not None:
        return outbox_obj

    audit_obj = _last_jsonl_row(AUDIT_EXECUTION_INTENT)
    if audit_obj is not None:
        return audit_obj

    if OUTBOX_DIR.exists() or AUDIT_EXECUTION_INTENT.exists():
        return {"error": "n/a", "intent": "n/a"}

    return JSONResponse(status_code=404, content={"error": "no intent found"})


@router.get("/api/audit/chain/status")
def get_audit_chain_status(verbose: int = 0) -> Dict[str, Any]:
    # IMPORTANT: default response must remain stable for tests/clients.
    return {
        "execution_intent": _audit_status_block(AUDIT_EXECUTION_INTENT, verbose),
        "paper_orders": _audit_status_block(AUDIT_PAPER_ORDERS, verbose),
        "paper_fills": _audit_status_block(AUDIT_PAPER_FILLS, verbose),
    }


@router.get("/api/executor/status")
def get_executor_status(verbose: int = 0) -> Dict[str, Any]:
    ts_checked = _utc_now_iso()

    for path in EXECUTOR_STATUS_CANDIDATES:
        obj = _safe_load_json(path)
        if obj is None:
            continue

        base = {
            "fail_streak": obj.get("fail_streak", "n/a"),
            "last_http_code": obj.get("last_http_code", "n/a"),
            "last_event_id": obj.get("last_event_id", "n/a"),
        }
        if verbose:
            base["source_path"] = str(path)
            base["ts_checked_iso"] = ts_checked
        return base

    if EXECUTOR_FAIL_STREAK_FILE.exists():
        try:
            raw = EXECUTOR_FAIL_STREAK_FILE.read_text(encoding="utf-8").strip()
            fail_streak = int(raw)
        except Exception:
            fail_streak = "n/a"

        base = {
            "fail_streak": fail_streak,
            "last_http_code": "n/a",
            "last_event_id": "n/a",
        }
        if verbose:
            base["source_path"] = str(EXECUTOR_FAIL_STREAK_FILE)
            base["ts_checked_iso"] = ts_checked
        return base

    base = {
        "fail_streak": 0,
        "last_http_code": "n/a",
        "last_event_id": "n/a",
    }
    if verbose:
        base["source_path"] = "n/a"
        base["ts_checked_iso"] = ts_checked
    return base
