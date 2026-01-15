from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, Sequence

from core.contracts.ports import L2AuditRepoPort
from core.contracts.scene import SceneRef, SceneSummary
from core.utils.ids import new_id


class FileBackedL2AuditRepo(L2AuditRepoPort):
    """
    Append-only audit store (JSONL).
    - No update/delete.
    - Each decision snapshot is one JSON line.
    - Each scene summary is one JSON line.
    """

    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

        self.snapshots_path = os.path.join(self.base_dir, "decision_snapshots.jsonl")
        self.scene_summaries_path = os.path.join(self.base_dir, "scene_summaries.jsonl")

        self._scene_index: Dict[str, SceneSummary] = {}
        self._load_scene_index()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append_jsonl(self, path: str, obj: dict) -> None:
        line = json.dumps(obj, ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _load_scene_index(self) -> None:
        if not os.path.exists(self.scene_summaries_path):
            return
        with open(self.scene_summaries_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    # Best-effort load; typed reconstruction can be tightened later.
                    # Keep it simple for v0.1.
                    self._scene_index[data["scene_id"]] = data  # type: ignore
                except Exception:
                    continue

    def append_decision_snapshot(self, snapshot: dict) -> str:
        snapshot_id = new_id("snap")
        item = {"snapshot_id": snapshot_id, "ts_written": self._now_iso(), **snapshot}
        self._append_jsonl(self.snapshots_path, item)
        return snapshot_id

    def list_recent_decision_snapshots(self, limit: int = 50):
        if limit <= 0:
            return []
        if not os.path.exists(self.snapshots_path):
            return []
        # Read last N lines (simple approach; OK for v0.1)
        with open(self.snapshots_path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
        out = []
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out

    def append_scene_summary(self, summary: SceneSummary) -> str:
        if isinstance(self._scene_index.get(summary.scene_id), dict) or summary.scene_id in self._scene_index:
            raise RuntimeError("L2 is append-only: scene_summary already exists for this scene_id")

        obj = asdict(summary)
        obj["ts_written"] = self._now_iso()
        self._append_jsonl(self.scene_summaries_path, obj)

        self._scene_index[summary.scene_id] = summary
        return summary.scene_id

    def list_closed_scenes(self, channel: str, limit: int = 200) -> Sequence[SceneRef]:
        # minimal stub
        return []

    def read_scene_summary(self, scene_id: str) -> SceneSummary:
        v = self._scene_index.get(scene_id)
        if v is None:
            raise KeyError(f"scene_summary not found: {scene_id}")
        # If loaded as dict (best-effort), return raw dict is not compatible.
        # For v0.1 we don't call this in E2E path.
        if isinstance(v, dict):
            raise RuntimeError("scene_summary loaded as raw dict; typed read not implemented in v0.1")
        return v


# --- v0.1 helper: allow appending dict summaries (string-based) ---
    def append_scene_summary_dict(self, summary_obj: dict) -> str:
        # Create file lazily
        os.makedirs(self.base_dir, exist_ok=True)
        self._append_jsonl(self.scene_summaries_path, summary_obj)
        return summary_obj.get("scene_id", "")

# Backward-friendly alias (in case you used this name elsewhere)
L2AuditRepo = FileBackedL2AuditRepo
