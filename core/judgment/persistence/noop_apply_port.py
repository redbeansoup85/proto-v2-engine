from __future__ import annotations

from typing import Any, Dict, Optional


class NoopDpaApplyPort:
    """
    Fail-closed apply port.

    Compatibility notes:
    - v0.7 port contract used: apply(dpa_id, selected_option_id, context)
    - engine constitutional_transition currently calls: apply(dpa_id=...)
    This implementation accepts both shapes and always denies safely.
    """

    def get_dpa(self, *, dpa_id: str) -> Optional[Dict[str, Any]]:
        return None

    def apply(
        self,
        *,
        dpa_id: str,
        selected_option_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        raise PermissionError("No DPA apply port (fail-closed)")
