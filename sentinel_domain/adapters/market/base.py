from __future__ import annotations

from typing import Dict, List, Optional, Protocol

DEFAULT_TFS = ["1m", "5m", "15m", "1h", "4h"]


class MarketAdapter(Protocol):
    def fetch_raw_market_bundle(
        self,
        asset: str,
        tfs: List[str],
        venue: str = "bybit",
        market_type: str = "perp",
    ) -> Dict[str, object]:
        ...


def parse_tfs(raw: Optional[str]) -> List[str]:
    if not raw:
        return list(DEFAULT_TFS)
    out: List[str] = []
    for token in raw.split(","):
        tf = token.strip()
        if not tf:
            continue
        out.append(tf)
    return out or list(DEFAULT_TFS)

