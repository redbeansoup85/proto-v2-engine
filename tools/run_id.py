from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def make_run_id(ts_utc: str, git_sha: str, config_sha: str) -> str:
    config_sha8 = config_sha[:8]
    return f"{ts_utc}_{git_sha}_{config_sha8}"


def make_run_id_now(git_sha: str, config_sha: str) -> str:
    ts_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return make_run_id(ts_utc, git_sha, config_sha)


def compute_config_sha(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
