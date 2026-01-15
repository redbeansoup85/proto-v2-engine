from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, Optional

from core.contracts.scene import SceneContext, SceneRef, SceneStatus
from core.utils.ids import new_id


class FileBackedSceneRepo:
    """
    Stores ACTIVE scenes index by context_key.
    v0.1:
      - index.json keeps current active scene per context_key
      - closed scenes are not indexed here (they live in L2 scene_summaries.jsonl)
    """

    def __init__(self, base_dir: str = "data/scene") -> None:
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.index_path = os.path.join(self.base_dir, "active_index.json")
        self._index: Dict[str, dict] = {}
        self._load()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load(self) -> None:
        if not os.path.exists(self.index_path):
            self._index = {}
            return
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                self._index = json.load(f) or {}
        except Exception:
            self._index = {}

    def _save(self) -> None:
        tmp = self.index_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.index_path)

    def get_active_by_context(self, context_key: str) -> Optional[SceneRef]:
        item = self._index.get(context_key)
        if not item:
            return None
        return SceneRef(
            scene_id=item["scene_id"],
            status=SceneStatus(item["status"]),
            context=SceneContext(**item["context"]),
            ts_start=item["ts_start"],
            ts_end=item.get("ts_end"),
        )

    def upsert_active(self, ref: SceneRef) -> None:
        self._index[ref.context.context_key] = {
            "scene_id": ref.scene_id,
            "status": ref.status.value,
            "context": {
                "org_id": ref.context.org_id,
                "site_id": ref.context.site_id,
                "channel": (ref.context.channel.value if hasattr(ref.context.channel, "value") else ref.context.channel),
                "context_key": ref.context.context_key,
            },
            "ts_start": ref.ts_start,
            "ts_end": ref.ts_end,
            "ts_updated": self._now_iso(),
        }
        self._save()

    def clear_active(self, context_key: str) -> None:
        if context_key in self._index:
            del self._index[context_key]
            self._save()

    def list_active(self) -> Dict[str, dict]:
        return self._index.copy()

    def open_new_scene(self, context: SceneContext, ts_start: str) -> SceneRef:
        scene_id = new_id("scene")
        ref = SceneRef(
            scene_id=scene_id,
            status=SceneStatus.OPEN,
            context=context,
            ts_start=ts_start,
            ts_end=None,
        )
        self.upsert_active(ref)
        return ref
