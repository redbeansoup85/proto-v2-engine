#!/usr/bin/env python3
"""
Sentinel Intent Consumer (Thin Slice v1, Fail-Closed, HASH-CHAINED + CARD_EVAL + SNAPSHOT)

- Reads ONE JSON object from stdin: sentinel_trade_intent.v1
- Validates schema/domain/mode + required keys + patterns
- Captures market_snapshot.v1 (placeholder "n/a" fields for now) to audits/sentinel/snapshots/
- Deterministic Card Picker (LOCK-safe minimal)
- Appends chained judgment_event.v1 JSONL with:
    card_id, rule_hits, features_ref (snapshot file ref), outcome_ref
    prev_hash, hash
- Optional Ed25519 signature (best-effort):
    - If auralis_v1.core.signature is importable AND env enables signing,
      adds signature fields.
    - Hash-chain remains stable: event["hash"] is computed WITHOUT ANY signature fields
      (signature, signature_meta).
- Outputs judgment_stub.v1 (DRY_RUN)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- ensure repo root importable (for CI subprocess executions)
# file: tools/sentinel/consume_trade_intent.py -> parents[2] == repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sentinel_domain.services.snapshot_service import capture_market_snapshot

# --- optional signature (do NOT hard-depend)
_SIG_AVAILABLE = False
try:
    # Expected API:
    # - load_sig_config_from_env() -> dict (or None)
    # - sign_hash_hex(hash_hex: str, cfg: dict) -> dict signature payload
    from auralis_v1.core.signature import load_sig_config_from_env, sign_hash_hex  # type: ignore

    _SIG_AVAILABLE = True
except Exception:
    load_sig_config_from_env = None  # type: ignore
    sign_hash_hex = None  # type: ignore
    _SIG_AVAILABLE = False


ALLOWED_SIDE = {"LONG", "SHORT", "FLAT"}
RE_ASSET = re.compile(r"^[A-Z0-9]{3,12}$")
RE_INTENT_ID = re.compile(r"^INTENT-[A-Za-z0-9_-]{8,}$")

MAX_STDIN_BYTES = 512_000

DEFAULT_AUDIT_PATH = Path("audits/sentinel/judgment_events_chain.jsonl")
DEFAULT_SNAPSHOT_DIR = Path("audits/sentinel/snapshots")
GENESIS_HASH = "0" * 64


def _fail(code: str, detail: str = "") -> None:
    print(json.dumps({"error": code, "detail": detail}, sort_keys=True), file=sys.stderr)
    raise SystemExit(2)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_stdin_json() -> Dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
    if len(raw) > MAX_STDIN_BYTES:
        _fail("STDIN_TOO_LARGE", f">{MAX_STDIN_BYTES} bytes")

    txt = raw.decode("utf-8", errors="replace").strip()
    if not txt:
        _fail("EMPTY_INPUT")

    try:
        obj = json.loads(txt)
    except Exception:
        _fail("BAD_JSON", txt[:800])

    if not isinstance(obj, dict):
        _fail("JSON_NOT_OBJECT", type(obj).__name__)
    return obj


def _validate_intent(obj: Dict[str, Any]) -> None:
    required = ["schema", "domain_id", "intent_id", "mode", "asset", "side", "notes"]
    for k in required:
        if k not in obj:
            _fail("INTENT_MISSING_KEY", k)

    if obj.get("schema") != "sentinel_trade_intent.v1":
        _fail("INTENT_SCHEMA_MISMATCH", str(obj.get("schema")))
    if obj.get("domain_id") != "sentinel.trade":
        _fail("INTENT_DOMAIN_MISMATCH", str(obj.get("domain_id")))
    if obj.get("mode") != "DRY_RUN":
        _fail("INTENT_MODE_NOT_DRY_RUN", str(obj.get("mode")))

    intent_id = obj.get("intent_id")
    if not isinstance(intent_id, str) or not RE_INTENT_ID.match(intent_id):
        _fail("INTENT_BAD_INTENT_ID", str(intent_id))

    asset = obj.get("asset")
    if not isinstance(asset, str) or not RE_ASSET.match(asset):
        _fail("INTENT_BAD_ASSET", str(asset))

    side = obj.get("side")
    if side not in ALLOWED_SIDE:
        _fail("INTENT_BAD_SIDE", str(side))

    notes = obj.get("notes")
    if not isinstance(notes, str) or len(notes.strip()) < 1:
        _fail("INTENT_BAD_NOTES", str(notes))


def _mk_id(prefix: str) -> str:
    return prefix + "-" + uuid.uuid4().hex[:10].upper()


def _canonical_json(obj: Dict[str, Any]) -> str:
    """
    Canonical JSON for hashing/chain stability.
    - ensure_ascii=False is critical (avoid \\uXXXX escaping drift)
    - allow_nan=False prevents non-deterministic NaN/Inf encodings
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _read_last_hash(path: Path) -> str:
    if not path.exists():
        return GENESIS_HASH
    lines = path.read_text(encoding="utf-8").splitlines()
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue
        obj = json.loads(line)
        h = obj.get("hash")
        if not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h):
            _fail("AUDIT_LASTLINE_MISSING_HASH", "")
        return h
    return GENESIS_HASH


def _append_jsonl(path: Path, event: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(_canonical_json(event) + "\n")
    except Exception as e:
        _fail("AUDIT_APPEND_FAIL", str(e))


def _card_eval(intent: Dict[str, Any]) -> Dict[str, Any]:
    side = intent["side"]
    asset = intent["asset"]

    rule_hits: List[str] = ["INTENT_SCHEMA_OK", f"ASSET_{asset}", f"SIDE_{side}"]

    if side == "LONG":
        return {
            "status": "ACCEPTED",
            "reason": "card_selected",
            "card_id": "CARD-SENTINEL-LONG-v1.0",
            "rule_hits": rule_hits + ["CARD_MATCH_LONG"],
        }
    if side == "SHORT":
        return {
            "status": "ACCEPTED",
            "reason": "card_selected",
            "card_id": "CARD-SENTINEL-SHORT-v1.0",
            "rule_hits": rule_hits + ["CARD_MATCH_SHORT"],
        }

    return {
        "status": "BLOCKED",
        "reason": "no_trade_intent",
        "card_id": "CARD-SENTINEL-FLAT-NOOP-v1.0",
        "rule_hits": rule_hits + ["CARD_BLOCK_FLAT"],
    }


def _capture_market_snapshot(asset: str, ts_utc: str, snap_dir: Path) -> str:
    """
    Thin Slice v1-real:
    - Keep exact snapshot contract shape.
    - Fill EMA/RSI from market adapter when available.
    - Fail-closed behavior remains explicit through placeholder retention.
    - Returns features_ref as repo-relative path.
    """
    snap_id = _mk_id("SNAP")
    try:
        return capture_market_snapshot(asset=asset, ts_utc=ts_utc, snap_dir=snap_dir, snap_id=snap_id)
    except Exception as e:
        _fail("SNAPSHOT_WRITE_FAIL", str(e))


def _strip_sig_fields_for_hash(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hash preimage must exclude any signature-related fields.
    This matches typical audit-chain invariants and avoids mismatch with verifiers
    that remove these fields prior to hashing.
    """
    # deep copy via canonical round-trip (stable + avoids reference mutation)
    e: Dict[str, Any] = json.loads(_canonical_json(event))
    e.pop("hash", None)
    e.pop("signature", None)
    e.pop("signature_meta", None)
    return e


def _maybe_sign_event_hash(event_hash_hex: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Best-effort signature:
    - If signature module not available: disabled with reason.
    - If module available but env disables: disabled with reason.
    - If enabled: returns signature dict + meta.
    """
    if not _SIG_AVAILABLE:
        return None, {"enabled": False, "reason": "SIG_MODULE_UNAVAILABLE"}

    try:
        cfg = load_sig_config_from_env()  # type: ignore[misc]
    except Exception as e:
        return None, {"enabled": False, "reason": "SIG_CONFIG_LOAD_FAIL", "detail": str(e)}

    if not cfg or not isinstance(cfg, dict) or not cfg.get("enabled"):
        return None, {"enabled": False, "reason": "SIG_DISABLED"}

    try:
        sig = sign_hash_hex(event_hash_hex, cfg)  # type: ignore[misc]
        meta = {"enabled": True, "key_id": cfg.get("key_id", "n/a")}
        return sig, meta
    except Exception as e:
        return None, {"enabled": False, "reason": "SIG_SIGN_FAIL", "detail": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-path", default=str(DEFAULT_AUDIT_PATH))
    ap.add_argument("--snapshot-dir", default=str(DEFAULT_SNAPSHOT_DIR))
    args = ap.parse_args()

    audit_path = Path(args.audit_path)
    snap_dir = Path(args.snapshot_dir)

    intent = _read_stdin_json()
    _validate_intent(intent)

    prev_hash = _read_last_hash(audit_path)

    # timestamp is shared between snapshot + event for traceability
    ts = _utc_now_iso()
    features_ref = _capture_market_snapshot(intent["asset"], ts, snap_dir)

    ev = _card_eval(intent)
    judgment_id = _mk_id("JEVT")

    # Build event core (hash preimage: no hash/signature fields)
    event_core: Dict[str, Any] = {
        "schema": "judgment_event.v1",
        "domain_id": "sentinel.trade",
        "judgment_id": judgment_id,
        "intent_id": intent["intent_id"],
        "mode": "DRY_RUN",
        "ts_utc": ts,
        "status": ev["status"],
        "reason": ev["reason"],
        "card_id": ev["card_id"],
        "rule_hits": ev["rule_hits"],
        "features_ref": features_ref,
        "outcome_ref": f"audits/sentinel/outcomes/{judgment_id}.json",
        "prev_hash": prev_hash,
    }

    # Compute hash from canonical JSON of preimage that excludes sig fields (future-proof)
    event_hash = _sha256_hex(_canonical_json(_strip_sig_fields_for_hash(event_core)))

    # Add hash
    event_full: Dict[str, Any] = dict(event_core)
    event_full["hash"] = event_hash

    # Optional signature (AFTER hash); meta/signature MUST NOT affect hash
    sig, sig_meta = _maybe_sign_event_hash(event_hash)
    # Only attach signature-related fields if enabled/available (avoid verifier drift)
    if sig is not None:
        event_full["signature"] = sig
        event_full["signature_meta"] = sig_meta

    _append_jsonl(audit_path, event_full)

    out = {
        "schema": "judgment_stub.v1",
        "domain_id": "sentinel.trade",
        "judgment_id": judgment_id,
        "intent_id": intent["intent_id"],
        "mode": "DRY_RUN",
        "status": ev["status"],
        "reason": ev["reason"],
        "card_id": ev["card_id"],
    }
    sys.stdout.write(_canonical_json(out) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
