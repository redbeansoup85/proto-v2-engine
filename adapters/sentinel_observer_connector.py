from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

OBSERVER_EVENTS_PATH = Path("var/observer/sentinel/intent_events.jsonl")
SIM_CHAIN_PATH = Path("var/audit/sentinel/simulation_chain.jsonl")
FORBIDDEN_KEYS = {
    "execute",
    "order",
    "broker",
    "place_order",
    "trade",
    "qty",
    "size",
    "price",
    "leverage",
    "position",
    "approve",
    "reject",
    "commit",
}
QUALITY_HOLD_FLAGS = {"stale", "rate_limited", "exchange_error", "gap", "missing_candle"}


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _ensure_output_paths() -> tuple[Path, Path]:
    obs = OBSERVER_EVENTS_PATH
    chain = SIM_CHAIN_PATH
    if obs.as_posix() != "var/observer/sentinel/intent_events.jsonl":
        raise RuntimeError("INVALID_OUTPUT_PATH")
    if chain.as_posix() != "var/audit/sentinel/simulation_chain.jsonl":
        raise RuntimeError("INVALID_OUTPUT_PATH")
    return obs, chain


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


def _is_quality_degraded(intent: dict[str, Any]) -> bool:
    quality = intent.get("quality") if isinstance(intent.get("quality"), dict) else {}
    flags = {str(x).lower() for x in (quality.get("quality_flags") or [])}
    return bool(quality.get("staleness_flag")) or bool(flags.intersection(QUALITY_HOLD_FLAGS))


def _apply_conservative_hold(intent: dict[str, Any]) -> dict[str, Any]:
    updated = dict(intent)
    updated["side"] = "FLAT"
    updated["no_execute"] = True
    hold_reason = list(updated.get("hold_reason") or [])
    for flag in ("STALE_DATA_HOLD", "QUALITY_DEGRADED"):
        if flag not in hold_reason:
            hold_reason.append(flag)
    updated["hold_reason"] = hold_reason
    quality = dict((updated.get("quality") or {}))
    qflags = list(quality.get("quality_flags") or [])
    for flag in ("STALE_DATA_HOLD", "QUALITY_DEGRADED"):
        if flag not in qflags:
            qflags.append(flag)
    quality["quality_flags"] = qflags
    updated["quality"] = quality
    return updated


def _ensure_sentinel_import_path() -> None:
    root = Path(__file__).resolve().parents[1]
    sentinel_pkg_root = root / "sentinel_domain"
    if str(sentinel_pkg_root) not in sys.path:
        sys.path.insert(0, str(sentinel_pkg_root))


class _TimeframeProvider:
    def __init__(self, provider: Any, timeframe: str) -> None:
        self.provider = provider
        self.timeframe = timeframe
        self.provider_id = getattr(provider, "provider_id", "ccxt:unknown")

    def fetch(self, asset: str):
        return self.provider.get_ohlcv(asset=asset, timeframe=self.timeframe, limit=50)


def _build_provider(provider: str, timeframe: str):
    if provider != "ccxt":
        raise RuntimeError("FAIL_CLOSED: unsupported provider")
    from sentinel.feeds.ccxt_provider import CCXTProvider  # local import to avoid package coupling at import time

    return _TimeframeProvider(CCXTProvider(), timeframe=timeframe)


def _run_pipeline(*, observer_event: dict[str, Any], provider: Any, audit_events_path: Path, audit_chain_path: Path) -> dict[str, Any]:
    from sentinel.tracks.simulation.pipeline import run_simulation_pipeline

    return run_simulation_pipeline(
        observer_event=observer_event,
        provider=provider,
        audit_events_path=audit_events_path,
        audit_chain_path=audit_chain_path,
    )


def run_sentinel_simulation_connector(
    asset: str,
    timeframe: str,
    provider: str = "ccxt",
    now: datetime | None = None,
) -> dict:
    _ = now  # reserved for deterministic time control in future
    obs_path, chain_path = _ensure_output_paths()
    _ensure_sentinel_import_path()
    tf_provider = _build_provider(provider, timeframe)
    observer_event = {
        "asset": asset,
        "side": "LONG",
        "summary": "sentinel simulation connector event",
    }
    intent = _run_pipeline(
        observer_event=observer_event,
        provider=tf_provider,
        audit_events_path=obs_path,
        audit_chain_path=chain_path,
    )

    if _scan_forbidden_keys(intent):
        raise RuntimeError("FORBIDDEN_KEY_DETECTED")
    if intent.get("no_execute") is not True:
        raise RuntimeError("EXECUTION_NOT_ALLOWED")

    if _is_quality_degraded(intent):
        intent = _apply_conservative_hold(intent)

    return intent


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Sentinel simulation -> observer connector (fail-closed)")
    ap.add_argument("--asset", required=True)
    ap.add_argument("--timeframe", required=True)
    ap.add_argument("--provider", default="ccxt")
    args = ap.parse_args()
    out = run_sentinel_simulation_connector(
        asset=args.asset,
        timeframe=args.timeframe,
        provider=args.provider,
    )
    print(_canonical_json(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
