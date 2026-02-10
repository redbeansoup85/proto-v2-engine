from __future__ import annotations

from typing import Any


def analyzer_create_internal_exec_intent(_: dict[str, Any]) -> dict[str, Any]:
    """
    Analyzer is not allowed to emit internal_exec_intent.
    """
    raise RuntimeError("FAIL_CLOSED: analyzer cannot create internal_exec_intent")
