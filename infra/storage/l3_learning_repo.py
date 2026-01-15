from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from typing import List, Optional, Dict, Any, Union

from core.learning.contracts import LearningSample


def _ensure_dir(p: str) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)


class FileBackedL3LearningRepo:
    def __init__(self, path: str):
        self.path = path
        _ensure_dir(self.path)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("")

    # ---------------------------------------------------------------------
    # Existing API (typed)
    # ---------------------------------------------------------------------
    def append_sample(self, sample: LearningSample) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(sample), ensure_ascii=False) + "\n")

    def list_samples(self, limit: int = 100) -> List[LearningSample]:
        rows = self._read_latest(limit=limit)
        return [LearningSample(**r) for r in rows]

    def find_by_scene(self, scene_id: str, limit: int = 200) -> List[LearningSample]:
        rows = self._read_latest(limit=5000)  # cheap scan for v0.1
        out: List[LearningSample] = []
        for r in rows:
            if r.get("scene_id") == scene_id:
                out.append(LearningSample(**r))
                if len(out) >= limit:
                    break
        return out

    def update_outcome(
        self,
        sample_id: str,
        outcome_label: str,
        outcome_notes: Optional[str],
        human_confirmed: bool = True,
    ) -> bool:
        # v0.1: rewrite file (still OK for small pilot)
        rows = self._read_all()
        found = False
        for r in rows:
            if r.get("sample_id") == sample_id:
                r["outcome_label"] = outcome_label
                r["outcome_notes"] = outcome_notes
                r["human_confirmed"] = bool(human_confirmed)
                found = True
                break
        if not found:
            return False

        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)
        return True

    # ---------------------------------------------------------------------
    # Compatibility Layer (for v2-alpha jobs / simple pipelines)
    #
    # Provides:
    # - append(item_dict)          -> append_sample(LearningSample) when possible
    # - list_recent(limit)         -> list of dicts (job-friendly)
    # - get_by_id(sample_id)       -> dict | None
    #
    # Rationale:
    # - Keep existing typed API stable
    # - Avoid forcing jobs to import LearningSample classes
    # ---------------------------------------------------------------------
    def append(self, item: Union[Dict[str, Any], LearningSample]) -> None:
        """
        Job-friendly append:
        - if dict -> stored as-is (best-effort)
        - if LearningSample -> stored via append_sample
        """
        if isinstance(item, LearningSample):
            self.append_sample(item)
            return

        if is_dataclass(item):
            # in case a dataclass other than LearningSample is passed
            payload = asdict(item)  # type: ignore[arg-type]
        else:
            payload = dict(item)  # type: ignore[arg-type]

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def list_recent(self, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Returns raw dicts (newest first) for jobs.
        """
        return self._read_latest(limit=limit)

    def get_by_id(self, sample_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns the latest matching record by scanning from the end.
        """
        if not os.path.exists(self.path):
            return None
        with open(self.path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for ln in reversed(lines):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("sample_id") == sample_id:
                return r
        return None

    # ---------------------------------------------------------------------
    # Internals
    # ---------------------------------------------------------------------
    def _read_all(self) -> List[dict]:
        if not os.path.exists(self.path):
            return []
        out: List[dict] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except Exception:
                    continue
        return out

    def _read_latest(self, limit: int = 100) -> List[dict]:
        rows = self._read_all()
        rows.reverse()  # newest first
        return rows[:limit]
