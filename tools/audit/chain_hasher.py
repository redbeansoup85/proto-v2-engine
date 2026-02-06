from __future__ import annotations
import hashlib
import json
from typing import Any, Dict

def canonical_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def event_hash(event_obj: Dict[str, Any]) -> str:
    return sha256_hex(canonical_json(event_obj))
