from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sentinel.feeds.base import MarketDataProvider, MarketDataSnapshot


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha8(obj: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()[:8].upper()


def observer_event_to_trade_intent(
    *,
    observer_event: dict[str, Any],
    provider: MarketDataProvider,
    track_id: str = "SIMULATION",
) -> tuple[dict[str, Any], MarketDataSnapshot]:
    """
    Convert observer event into sentinel_trade_intent.v1.
    This is a non-execution adapter; output is intent-only.
    """
    snapshot = provider.fetch(str(observer_event.get("asset", "BTCUSDT")))
    intent = {
        "schema_version": "sentinel_trade_intent.v1",
        "intent_id": f"SINTENT-{_sha8(observer_event)}",
        "track_id": track_id,
        "mode": "DRY_RUN",
        "producer": {
            "domain": "sentinel",
            "component": "observer_adapter",
        },
        "asset": snapshot.asset,
        "side": str(observer_event.get("side", "FLAT")).upper(),
        "analysis_summary": str(observer_event.get("summary", "observer derived intent")),
        "quality": {
            "provider_id": snapshot.provider_id,
            "retrieved_at": snapshot.retrieved_at,
            "source_timestamp": snapshot.source_timestamp,
            "staleness_flag": snapshot.staleness_flag,
            "quality_flags": snapshot.quality_flags,
        },
        "no_execute": True,
        "created_at": _utc_now_iso(),
    }
    return intent, snapshot
