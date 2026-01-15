from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional


def _parse_iso(ts: str) -> datetime:
    # supports "Z" or "+00:00"
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _sev_rank(s: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(s, -1)


@dataclass
class WeeklyRollup:
    window_start: str
    window_end: str
    days: int

    total_scenes: int
    by_channel: Dict[str, int]
    severity_distribution: Dict[str, int]
    avg_decisions_per_scene: float
    top_rationale_codes: List[Tuple[str, int]]

    childcare_human_review_ratio: Optional[float]
    sample_scene_ids: List[str]


def load_scene_summaries_jsonl(path: str) -> List[dict]:
    items: List[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                items.append(json.loads(ln))
            except Exception:
                continue
    return items


def rollup_weekly(scene_summaries: List[dict], days: int = 7) -> WeeklyRollup:
    now = _now_utc()
    start = now - timedelta(days=days)

    filtered: List[dict] = []
    for s in scene_summaries:
        ts_end = s.get("ts_end")
        if not ts_end:
            continue
        try:
            dt_end = _parse_iso(ts_end)
        except Exception:
            continue
        if dt_end >= start and dt_end <= now:
            filtered.append(s)

    by_channel: Dict[str, int] = {}
    sev_dist: Dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    rationale_counts: Dict[str, int] = {}

    total_decisions = 0.0

    childcare_total = 0
    childcare_human = 0

    for s in filtered:
        ctx = s.get("context", {}) or {}
        ch = ctx.get("channel", "unknown")
        by_channel[ch] = by_channel.get(ch, 0) + 1

        peak = (s.get("peak_severity") or "unknown")
        if peak in sev_dist:
            sev_dist[peak] += 1

        td = s.get("total_decisions") or 0
        try:
            total_decisions += float(td)
        except Exception:
            pass

        for rc in (s.get("key_rationale_codes") or []):
            if not isinstance(rc, str):
                continue
            rationale_counts[rc] = rationale_counts.get(rc, 0) + 1

        # v0.1 heuristic: childcare scenes imply human review patterns
        if ch == "childcare":
            childcare_total += 1
            # if any rationale indicates review required, count as human_review
            rcs = set(s.get("key_rationale_codes") or [])
            if "CHILDCARE_HUMAN_REVIEW_REQUIRED" in rcs:
                childcare_human += 1

    avg = (total_decisions / len(filtered)) if filtered else 0.0

    top_codes = sorted(rationale_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    ratio = None
    if childcare_total > 0:
        ratio = childcare_human / childcare_total

    sample_ids = [x.get("scene_id") for x in filtered[-10:] if x.get("scene_id")]

    return WeeklyRollup(
        window_start=start.isoformat(),
        window_end=now.isoformat(),
        days=days,
        total_scenes=len(filtered),
        by_channel=by_channel,
        severity_distribution=sev_dist,
        avg_decisions_per_scene=round(avg, 4),
        top_rationale_codes=top_codes,
        childcare_human_review_ratio=(round(ratio, 4) if ratio is not None else None),
        sample_scene_ids=sample_ids,
    )
