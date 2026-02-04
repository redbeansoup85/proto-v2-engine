from __future__ import annotations

import hashlib
import json
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

    name: str = "mock"
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
        if mode == "ambiguous":
            return {
                "ok": False,
                "engine_output": {
                    "meta": {"adapter": {"name": self.name, "version": self.version}},
                    "decision": {"status": "AMBIGUOUS", "reason": "mock_ambiguous_state"},
                    "signals": [],
                },
            }
        if mode == "error":
            raise AdapterError("ADAPTER_GENERIC_ERROR")

        payload = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        request_hash = hashlib.sha256(payload).hexdigest()
        return {
            "ok": True,
            "engine_output": {
                "meta": {
                    "adapter": {"name": self.name, "version": self.version},
                    "request_hash": request_hash,
                },
                "decision": {"status": "ALLOW", "reason": "mock_ok"},
                "signals": [],
            },
        }
