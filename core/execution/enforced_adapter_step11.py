from __future__ import annotations
from typing import Any

from core.adapters.capabilities import get_adapter_capability
from core.observer.observer_hook import emit_shadow_observation
from core.execution.executor import ShadowAdapterError

def run_enforced_adapter(*, adapter_name: str | None, request: dict[str, Any]) -> dict[str, Any]:
    """LOCK-safe enforced adapter path with fail-closed."""
    if not adapter_name:
        emit_shadow_observation(outcome="deny", reason_code="ADAPTER_UNKNOWN")
        raise ShadowAdapterError("adapter_name missing or unknown")

    cap = get_adapter_capability(adapter_name)
    if not cap or not cap.get("side_effects", False):
        emit_shadow_observation(outcome="deny", reason_code="ENFORCED_FAIL_CLOSED", adapter_name=adapter_name)
        raise ShadowAdapterError(f"adapter '{adapter_name}' call blocked (fail-closed)")

    emit_shadow_observation(outcome="ok", reason_code="OK", adapter_name=adapter_name)
    return {"ok": True, "adapter_name": adapter_name}
