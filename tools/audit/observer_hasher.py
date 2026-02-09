from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def hash_event(event: Dict[str, Any]) -> str:
    """
    Deterministic event hash helper used by lock3 observer gate.
    Canonicalization: sort_keys=True, separators=(',', ':'), ensure_ascii=False
    """
    return sha256_hex(canonical_json(event).encode("utf-8"))
