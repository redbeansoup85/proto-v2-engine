from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from core.contracts.policy import Channel


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def make_context_key(
    *,
    org_id: str,
    site_id: str,
    channel: Channel,
    scene_id: Optional[str] = None,
) -> str:
    """
    v0.1: minimal non-identifying context key.
    - We intentionally do NOT include personal identifiers.
    - We keep it stable across calls for the same org/site/channel.
    """
    raw = f"{org_id}|{site_id}|{channel.value}"
    # scene_id is not used (may be null) - keep context stable.
    return _sha256(raw)[:24]
