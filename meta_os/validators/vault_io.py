from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from meta_os.boundary import vault_root
from pathlib import Path

VAULT_ROOT = Path(vault_root())


def resolve_vault_root() -> Path:
    """
    meta_os/validators/vault_io.py 기준으로 proto-v2-engine/vault를 찾는다.
    .../proto-v2-engine/meta_os/validators/vault_io.py
    """
    here = Path(__file__).resolve()
    proto_root = here.parents[2]  # proto-v2-engine
    return proto_root / "vault"


VAULT_ROOT = resolve_vault_root()


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def date_path(ts: datetime) -> Path:
    return Path(ts.strftime("%Y/%m/%d"))


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)  # atomic replace


def runs_index_path() -> Path:
    return VAULT_ROOT / "manifests" / "runs_index.jsonl"


def schema_registry_path() -> Path:
    return VAULT_ROOT / "manifests" / "schema_registry.json"


def find_latest_complete_run(run_id: str) -> Optional[Dict[str, Any]]:
    """
    runs_index.jsonl을 끝에서부터 읽어 해당 run_id의 최신 status를 반환.
    status가 COMPLETE인 엔트리를 우선 반환.
    """
    idx = runs_index_path()
    if not idx.exists():
        return None

    latest_any = None
    latest_complete = None

    # jsonl 라인을 통째로 읽되, 파일이 커지면 tail 방식으로 바꾸면 됨 (v0.2)
    with open(idx, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if entry.get("run_id") != run_id:
                continue
            latest_any = entry
            if entry.get("status") == "COMPLETE":
                latest_complete = entry

    return latest_complete or latest_any


def exception_output_path(run_id: str, code: str, ts: datetime) -> Path:
    return VAULT_ROOT / "exceptions" / date_path(ts) / f"exception_{run_id}__{code}.json"

