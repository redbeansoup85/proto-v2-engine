from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class MarketDataSnapshot:
    provider_id: str
    retrieved_at: str
    source_timestamp: str
    staleness_flag: bool
    quality_flags: list[str]
    asset: str
    price: float | None


class MarketDataProvider(Protocol):
    provider_id: str

    def fetch(self, asset: str) -> MarketDataSnapshot:
        ...


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
