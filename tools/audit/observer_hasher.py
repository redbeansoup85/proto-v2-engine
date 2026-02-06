from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def canonical_dumps(d: Dict[str, Any]) -> str:
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _payload_without_hash_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in {"hash", "prev_hash"}}


def hash_event(prev_hash: str, payload_wo_hash: Dict[str, Any]) -> str:
    canonical_json = canonical_dumps(_payload_without_hash_fields(payload_wo_hash))
    hash_input = prev_hash + "\n" + canonical_json
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
