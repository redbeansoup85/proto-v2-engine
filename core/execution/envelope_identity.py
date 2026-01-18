from __future__ import annotations

from typing import Any


def extract_envelope_id(envelope: Any) -> str:
    """
    Stable identity for replay defense.
    Contract: ExecutionEnvelope.meta.envelope_id MUST exist.

    Fail-closed:
    - Missing meta/envelope_id => PermissionError
    """
    meta = getattr(envelope, "meta", None)
    if meta is None:
        raise PermissionError("ExecutionEnvelope missing meta (fail-closed)")

    v = getattr(meta, "envelope_id", None)
    if isinstance(v, str) and v.strip():
        return v.strip()

    raise PermissionError("ExecutionEnvelope missing meta.envelope_id (fail-closed)")
