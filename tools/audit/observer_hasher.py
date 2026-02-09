from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_event(*args: Any) -> str:
    """
    Backward-compatible hashing.

    Supported:
      - hash_event(event_dict)
      - hash_event(prev_hash, event_dict)
    """

    # hash_event(event_dict)
    if len(args) == 1:
        event = args[0]
        if not isinstance(event, dict):
            raise TypeError("hash_event(event): event must be dict")

        obj = dict(event)
        obj.pop("hash", None)
        return sha256_hex(canonical_json(obj).encode("utf-8"))

    # hash_event(prev_hash, event_dict)
    if len(args) == 2:
        prev_hash, event = args

        if not isinstance(prev_hash, str):
            raise TypeError("hash_event(prev_hash, event): prev_hash must be str")
        if not isinstance(event, dict):
            raise TypeError("hash_event(prev_hash, event): event must be dict")

        if "prev_hash" in event and event["prev_hash"] != prev_hash:
            raise ValueError("Fail-Closed: prev_hash mismatch")

        obj = dict(event)
        obj.pop("hash", None)

        payload = (prev_hash + "\n" + canonical_json(obj)).encode("utf-8")
        return sha256_hex(payload)

    raise TypeError("hash_event expects 1 or 2 positional arguments")
