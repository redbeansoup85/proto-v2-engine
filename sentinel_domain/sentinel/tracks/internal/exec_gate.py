from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha8(obj: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()[:8].upper()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class IdempotencyStore:
    _seen: set[str] = field(default_factory=set)

    def assert_new(self, key: str) -> None:
        if key in self._seen:
            raise RuntimeError(f"FAIL_CLOSED: duplicate idempotency_key: {key}")
        self._seen.add(key)


def create_internal_exec_intent(
    *,
    sentinel_trade_intent: dict[str, Any],
    mode: str,
    idempotency_key: str,
    approval_id: str | None,
    producer_component: str,
    idempotency_store: IdempotencyStore,
) -> dict[str, Any]:
    if producer_component != "exec_gate":
        raise RuntimeError("FAIL_CLOSED: only exec_gate can create internal_exec_intent")
    if sentinel_trade_intent.get("schema_version") != "sentinel_trade_intent.v1":
        raise RuntimeError("FAIL_CLOSED: source schema mismatch")
    if sentinel_trade_intent.get("track_id") != "INTERNAL":
        raise RuntimeError("FAIL_CLOSED: source track_id must be INTERNAL")
    if not isinstance(idempotency_key, str) or len(idempotency_key) < 8:
        raise RuntimeError("FAIL_CLOSED: idempotency_key required")
    if mode not in {"paper", "real"}:
        raise RuntimeError("FAIL_CLOSED: mode must be paper or real")
    if mode == "real" and not approval_id:
        raise RuntimeError("FAIL_CLOSED: approval required for real mode")
    idempotency_store.assert_new(idempotency_key)

    src_intent_id = str(sentinel_trade_intent.get("intent_id") or "")
    if len(src_intent_id) < 8:
        raise RuntimeError("FAIL_CLOSED: source intent_id missing")

    quality = sentinel_trade_intent.get("quality") if isinstance(sentinel_trade_intent.get("quality"), dict) else {}
    flags = [str(x).lower() for x in (quality.get("quality_flags") or [])]
    degraded = bool(quality.get("staleness_flag")) or any(f in {"stale", "exchange_error", "rate_limited"} for f in flags)
    if degraded:
        hold_intent = dict(sentinel_trade_intent)
        hold_intent["side"] = "FLAT"
        hold_intent["mode"] = "DRY_RUN"
        hold_intent["no_execute"] = True
        hold_intent["analysis_summary"] = "HOLD: degraded market data quality"
        hold_quality = dict(quality)
        hold_flags = list(hold_quality.get("quality_flags") or [])
        if "STALE_DATA_HOLD" not in hold_flags:
            hold_flags.append("STALE_DATA_HOLD")
        if "INTERNAL_EXEC_BLOCKED_QUALITY" not in hold_flags:
            hold_flags.append("INTERNAL_EXEC_BLOCKED_QUALITY")
        hold_quality["quality_flags"] = hold_flags
        hold_intent["quality"] = hold_quality
        hold_intent["producer"] = {"domain": "sentinel", "component": "exec_gate"}
        hold_intent["created_at"] = _utc_now_iso()
        return hold_intent

    result = {
        "schema_version": "internal_exec_intent.v1",
        "exec_intent_id": f"IEXEC-{_sha8({'src': src_intent_id, 'idem': idempotency_key})}",
        "source_intent_id": src_intent_id,
        "track_id": "INTERNAL",
        "mode": mode,
        "idempotency_key": idempotency_key,
        "producer": {"component": "exec_gate"},
        "created_at": _utc_now_iso(),
    }
    if approval_id:
        result["approval_id"] = approval_id
    return result
