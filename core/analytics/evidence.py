from __future__ import annotations

import json
import os
from typing import Dict, List, Optional


def load_decision_snapshots_jsonl(path: str) -> List[dict]:
    items: List[dict] = []
    if not os.path.exists(path):
        return items
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


def build_scene_to_snapshot_ids(decision_snapshots: List[dict], limit_per_scene: int = 50) -> Dict[str, List[str]]:
    """
    Returns: scene_id -> [snapshot_id, ...] (latest-first)
    """
    m: Dict[str, List[str]] = {}

    # latest-first: iterate reversed if snapshots are append-only
    for s in reversed(decision_snapshots):
        snap_id = s.get("snapshot_id")
        meta = s.get("meta") or {}
        scene = (meta.get("scene_id") or (s.get("scene") or {}).get("scene_id"))
        if not snap_id or not scene:
            continue

        arr = m.get(scene)
        if arr is None:
            arr = []
            m[scene] = arr

        if len(arr) < limit_per_scene:
            arr.append(snap_id)

    return m


def resolve_decision_snapshots_path(l2) -> Optional[str]:
    """
    Try common attribute names; fallback to base_dir/decision_snapshots.jsonl
    """
    for attr in ["decision_snapshots_path", "snapshots_path"]:
        p = getattr(l2, attr, None)
        if isinstance(p, str) and p:
            return p

    base_dir = getattr(l2, "base_dir", None)
    if isinstance(base_dir, str) and base_dir:
        return os.path.join(base_dir, "decision_snapshots.jsonl")

    return None
