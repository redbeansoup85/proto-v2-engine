from __future__ import annotations

from typing import Any


FORBIDDEN_KEYS = {
    "api_key",
    "private_key",
    "seed_phrase",
    "mnemonic",
    "password",
    "secret",
    "token",
    "execute",
    "order",
    "place_order",
    "broker",
    "trade",
    "qty",
    "size",
    "price",
    "sl",
    "tp",
    "leverage",
    "position",
    "approve",
    "reject",
    "commit",
}


def _scan_forbidden_keys(obj: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in FORBIDDEN_KEYS:
                hits.append(f"{path}.{k}")
            hits.extend(_scan_forbidden_keys(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            hits.extend(_scan_forbidden_keys(v, f"{path}[{idx}]"))
    return hits


def validate_trade_intent(intent: dict[str, Any]) -> dict[str, Any]:
    hits = _scan_forbidden_keys(intent)
    if hits:
        raise RuntimeError(f"FAIL_CLOSED: forbidden keys found: {hits}")
    if intent.get("no_execute") is not True:
        raise RuntimeError("FAIL_CLOSED: no_execute must be true")
    return intent


def validate_simulation_intent(intent: dict[str, Any]) -> None:
    validate_trade_intent(intent)
    if intent.get("track_id") != "SIMULATION":
        raise RuntimeError("FAIL_CLOSED: simulation validator requires track_id=SIMULATION")


def enforce_conservative_behavior(intent: dict[str, Any]) -> dict[str, Any]:
    """
    If data quality is stale, force conservative behavior (HOLD/FLAT).
    """
    quality = intent.get("quality") if isinstance(intent.get("quality"), dict) else {}
    stale = bool(quality.get("staleness_flag"))
    if not stale:
        return intent
    updated = dict(intent)
    updated["side"] = "FLAT"
    q2 = dict(quality)
    flags = list(q2.get("quality_flags") or [])
    if "STALE_DATA_HOLD" not in flags:
        flags.append("STALE_DATA_HOLD")
    q2["quality_flags"] = flags
    updated["quality"] = q2
    return updated
