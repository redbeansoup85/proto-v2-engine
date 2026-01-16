from __future__ import annotations

from typing import Any, Dict, Optional


class NoopDpaApplyPort:
    """
    Fail-closed apply port.
    - Methods exist (no AttributeError)
    - But always denies apply unless someone replaces with real port.
    """

    def get_dpa(self, *, dpa_id: str) -> Optional[Dict[str, Any]]:
        return None

    def apply(self, *, dpa_id: str, selected_option_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise PermissionError("No DPA apply port (fail-closed)")
