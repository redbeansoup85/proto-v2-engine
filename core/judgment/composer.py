from __future__ import annotations

from typing import Any, Dict, List, Protocol

from .models import DpaOption, DpaRecord


class DpaComposer(Protocol):
    """
    Domain-specific DPA builder.

    Core does NOT know:
      - what an event is (schema)
      - how options/constraints are computed
      - what "system_position" means

    A (adapter/service) provides an implementation.
    """

    def compose(
        self,
        *,
        dpa_id: str,
        event_id: str,
        context: Dict[str, Any],
    ) -> DpaRecord:
        """
        Must return a DpaRecord with:
          - context_json, options_json, constraints_json, system_position_json filled
          - status defaulted to DPA_CREATED
        """
        ...


class SimpleStaticComposer:
    """
    Minimal composer useful for smoke tests / scaffolding.
    Not intended for production use.
    """

    def __init__(
        self,
        *,
        options: List[DpaOption],
        constraints: Dict[str, Any] | None = None,
        system_position: Dict[str, Any] | None = None,
    ) -> None:
        self._options = options
        self._constraints = constraints or {}
        self._system_position = system_position or {}

    def compose(self, *, dpa_id: str, event_id: str, context: Dict[str, Any]) -> DpaRecord:
        return DpaRecord(
            dpa_id=dpa_id,
            event_id=event_id,
            context_json=context,
            options_json=self._options,
            constraints_json=self._constraints,
            system_position_json=self._system_position,
        )

# =========================
# API bring-up minimal composer (v0)
# =========================
class MinimalDpaComposer:
    """
    Minimal composer for API bring-up.
    Keeps constitutional gate alive without domain-specific option building.

    NOTE:
      - Replace with domain composers later (Childcare/Kisetsu/Trading).
    """
    def compose(self, *, dpa_id: str, event_id: str, context: dict):
        from core.judgment.models import DpaRecord, DpaOption

        return DpaRecord(
            dpa_id=dpa_id,
            event_id=event_id,
            context_json=context or {},
            options_json=[
                DpaOption(
                    option_id="opt_001",
                    title="Proceed (minimal)",
                    summary="Minimal option for API bring-up",
                    blocked=False,
                    payload={},
                )
            ],
        )
