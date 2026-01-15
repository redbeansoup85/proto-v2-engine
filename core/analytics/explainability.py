from __future__ import annotations

from typing import List, Dict, Tuple, Optional


def _sev_rank(s: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(s, -1)


def top_scenes_by_severity(scene_summaries: List[dict], k: int = 5) -> List[dict]:
    items = []
    for s in scene_summaries:
        sid = s.get("scene_id")
        peak = (s.get("peak_severity") or "unknown")
        td = s.get("total_decisions") or 0
        ctx = s.get("context") or {}
        if not sid:
            continue
        items.append({
            "scene_id": sid,
            "channel": ctx.get("channel"),
            "peak_severity": peak,
            "total_decisions": td,
            "ts_end": s.get("ts_end"),
            "_rank": _sev_rank(peak),
        })
    items.sort(key=lambda x: (x["_rank"], x.get("total_decisions", 0)), reverse=True)
    for it in items:
        it.pop("_rank", None)
    return items[:k]


def top_scenes_by_decisions(scene_summaries: List[dict], k: int = 5) -> List[dict]:
    items = []
    for s in scene_summaries:
        sid = s.get("scene_id")
        td = s.get("total_decisions") or 0
        peak = (s.get("peak_severity") or "unknown")
        ctx = s.get("context") or {}
        if not sid:
            continue
        items.append({
            "scene_id": sid,
            "channel": ctx.get("channel"),
            "total_decisions": td,
            "peak_severity": peak,
            "ts_end": s.get("ts_end"),
        })
    items.sort(key=lambda x: x.get("total_decisions", 0), reverse=True)
    return items[:k]
