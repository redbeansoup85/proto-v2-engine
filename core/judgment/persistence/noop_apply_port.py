from __future__ import annotations

from typing import Any, Dict, Optional

from core.judgment.models import DpaRecord


class NoopDpaApplyPort:
    """
    v0.6 DEV/LOCAL only.
    Satisfies constitutional_transition() requirements without side-effects.

    Required by engine (observed from traceback):
      - get_dpa(dpa_id=...)
      - apply(...)  (shape can vary; accept **kwargs)
    """

    def __init__(self, repo: Any) -> None:
        # repo is expected to have .get(dpa_id)
        self._repo = repo

    def get_dpa(self, *, dpa_id: str) -> Optional[DpaRecord]:
        return self._repo.get(dpa_id)  # type: ignore[attr-defined]

    def apply(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        # No real side effects in v0.6
        return {"ok": True, "applied": False, "mode": "noop", "args": [str(a) for a in args], "kwargs": {k: str(v) for k, v in kwargs.items()}}
