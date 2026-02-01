from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, List, Tuple


class CanonicalJSONError(ValueError):
    pass


def _parse_no_duplicate_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise CanonicalJSONError(f"duplicate key detected: {k!r}")
        out[k] = v
    return out


def loads_strict_no_duplicates(s: str) -> Any:
    """
    Strict JSON parse that fails on duplicate keys.
    Use this when ingesting raw JSON strings.
    """
    return json.loads(s, object_pairs_hook=_parse_no_duplicate_keys)


def _normalize_for_canonical(obj: Any) -> Any:
    """
    Normative:
    - float is FORBIDDEN (fail-closed)
    - int, str, bool, None OK
    - Decimal allowed but MUST be serialized deterministically -> string
    - dict keys MUST be str
    - list/dict recurse
    """
    if isinstance(obj, float):
        raise CanonicalJSONError("float is forbidden (fail-closed). Use Decimal or string.")
    if isinstance(obj, Decimal):
        return format(obj, "f")  # deterministic string
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, list):
        return [_normalize_for_canonical(x) for x in obj]
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise CanonicalJSONError("dict keys must be strings")
            out[k] = _normalize_for_canonical(v)
        return out
    raise CanonicalJSONError(f"unsupported type: {type(obj).__name__}")


def canonical_json(obj: Any) -> bytes:
    """
    Canonical JSON bytes (simplified JCS-like):
    - sort_keys=True
    - separators=(",", ":")
    - ensure_ascii=False
    - allow_nan=False
    - float forbidden
    """
    normalized = _normalize_for_canonical(obj)
    s = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        indent=None,
        allow_nan=False,
    )
    return s.encode("utf-8")
