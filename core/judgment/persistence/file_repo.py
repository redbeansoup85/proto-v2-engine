from __future__ import annotations

import json
from datetime import datetime, date
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Optional

from core.judgment.errors import conflict
from core.judgment.models import DpaRecord

from dataclasses import asdict, is_dataclass

def _to_plain_obj(x):
    # dataclass
    if is_dataclass(x):
        return asdict(x)
    # pydantic v2
    if hasattr(x, "model_dump") and callable(getattr(x, "model_dump")):
        return x.model_dump()
    # pydantic v1 / generic mapping-like
    if hasattr(x, "dict") and callable(getattr(x, "dict")):
        return x.dict()
    # fallback
    if hasattr(x, "__dict__"):
        return dict(x.__dict__)
    return x

def _jsonify(obj):
    # recursively make JSON-safe
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, tuple):
        return [_jsonify(v) for v in obj]
    # datetime/date
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    # enums / objects
    if hasattr(obj, "value"):
        try:
            return obj.value
        except Exception:
            pass
    if hasattr(obj, "isoformat") and callable(getattr(obj, "isoformat")):
        try:
            return obj.isoformat()
        except Exception:
            pass
    return obj

from core.judgment.status import DecisionStatus


def _jsonify(x: Any) -> Any:
    # best-effort JSON serialization for dataclasses / enums / primitives
    if is_dataclass(x):
        return {k: _jsonify(v) for k, v in asdict(x).items()}
    if hasattr(x, "name") and hasattr(x, "value"):  # Enum-like
        return x.name
    if isinstance(x, (list, tuple)):
        return [_jsonify(v) for v in x]
    if isinstance(x, dict):
        return {k: _jsonify(v) for k, v in x.items()}
    return x


class FileBackedDpaRepository:
    """
    Append-only JSONL store + latest-snapshot read.
    v0.6 baseline: single-process / demo.
    """

    def __init__(self, root_dir: str) -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "dpa.jsonl"

    def _iter_lines(self):
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    yield ln

    def get(self, dpa_id: str) -> Optional[DpaRecord]:
        last: Optional[dict] = None
        for ln in self._iter_lines():
            obj = json.loads(ln)
            if obj.get("dpa_id") == dpa_id:
                last = obj
        if last is None:
            return None

        # status restore (string -> DecisionStatus)
        st = last.get("status")
        if isinstance(st, str):
            try:
                last["status"] = DecisionStatus[st]
            except Exception:
                # fallback: keep as-is; DpaRecord may accept string
                pass

        return DpaRecord(**last)

    def create(self, dpa: DpaRecord) -> DpaRecord:
        if self.get(dpa.dpa_id) is not None:
            raise conflict("DPA_ALREADY_EXISTS", "DPA with same id already exists.", {"dpa_id": dpa.dpa_id})
        self.save(dpa)
        return dpa

    def save(self, dpa: DpaRecord) -> DpaRecord:
        obj = _jsonify(_to_plain_obj(dpa))
        # normalize status as enum name for stable restore
        obj["status"] = getattr(dpa.status, "name", str(dpa.status))
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        return dpa
