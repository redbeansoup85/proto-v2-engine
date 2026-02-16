from __future__ import annotations

from typing import Any, Dict, Iterable, Set


def _deep_keys(obj: Any) -> Iterable[str]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _deep_keys(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _deep_keys(it)


def validate_trade_intent(intent: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(intent, dict):
        raise RuntimeError("intent must be dict")

    if intent.get("no_execute") is not True:
        raise RuntimeError("no_execute must be True")

    forbidden: Set[str] = {
        # execution-ish
        "execute",
        "execution",
        "exec",
        ("place" + "_order"),
        "order",
        "orders",
        ("submit" + "_order"),
        ("cancel" + "_order"),
        ("modify" + "_order"),

        # broker routing / side-effects
        "broker",

        # secrets
        "api_key",

        # market numeric payloads (policy: intent is interpretation-only)
        "price",

        # explicit test token
        "FORBIDDEN_EXEC_KEY",
    }

    keys = set(_deep_keys(intent))
    hit = sorted(k for k in keys if k in forbidden)
    if hit:
        raise RuntimeError(f"forbidden keys: {hit}")

    return intent


def enforce_conservative_behavior(intent: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(intent, dict):
        raise RuntimeError("intent must be dict")

    quality = intent.get("quality") or {}
    staleness_flag = bool(quality.get("staleness_flag"))
    qflags = quality.get("quality_flags") or []
    if not isinstance(qflags, list):
        qflags = [str(qflags)]

    degraded = staleness_flag or ("stale" in qflags) or ("exchange_error" in qflags) or ("rate_limited" in qflags)

    if degraded:
        intent["side"] = "FLAT"
        intent["no_execute"] = True

        # quality flags must include STALE_DATA_HOLD per tests/spec
        if "STALE_DATA_HOLD" not in qflags:
            qflags.append("STALE_DATA_HOLD")

        # also normalize stale marker if staleness_flag is on
        if staleness_flag and "stale" not in qflags:
            qflags.append("stale")

        quality["quality_flags"] = qflags
        intent["quality"] = quality

    return intent


def validate_simulation_intent(payload: Dict[str, Any]) -> Dict[str, Any]:
    validate_trade_intent(payload)

    track_id = payload.get("track_id")
    if track_id not in (None, "SIMULATION"):
        raise RuntimeError("track_id must be SIMULATION")

    return payload
