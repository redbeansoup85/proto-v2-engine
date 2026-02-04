from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict


class AdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class MockAdapter:
    """
    Mock adapter for integration gating.
    - No side effects
    - Can simulate timeout / contract mismatch / generic error
    """

    name: str = "mock_adapter"
    version: str = "v1"

    def call(self, request: Dict[str, Any]) -> Dict[str, Any]:
        mode = os.getenv("MOCK_ADAPTER_MODE", "ok").strip().lower()
        if mode == "timeout":
            # simulate timeout
            ms = int(os.getenv("MOCK_ADAPTER_TIMEOUT_MS", "5000"))
            time.sleep(ms / 1000.0)
            raise AdapterError("ADAPTER_TIMEOUT")
        if mode == "mismatch":
            # simulate contract mismatch
            return {"unexpected_field": True}
        if mode == "error":
            raise AdapterError("ADAPTER_GENERIC_ERROR")

        # ok
        return {"ok": True, "echo": request, "adapter": {"name": self.name, "version": self.version}}
