from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ALLOWED_MODES = {"ok", "mismatch", "timeout", "ambiguous"}
_CAPABILITIES_PATH = Path(__file__).resolve().parents[1] / "contracts" / "adapter_capabilities_v1.json"
_CACHE: dict[str, Any] | None = None


def _validate_row(row: Any) -> None:
    if not isinstance(row, dict):
        raise RuntimeError("adapter capability row must be object")

    required = ("adapter_name", "modes", "timeouts_ms", "side_effects")
    for key in required:
        if key not in row:
            raise RuntimeError(f"missing adapter capability key: {key}")

    if not isinstance(row["adapter_name"], str) or not row["adapter_name"].strip():
        raise RuntimeError("adapter_name must be non-empty string")

    modes = row["modes"]
    if not isinstance(modes, list) or not modes:
        raise RuntimeError("modes must be non-empty list")
    if not set(modes).issubset(_ALLOWED_MODES):
        raise RuntimeError("modes contains unsupported value")

    timeout = row["timeouts_ms"]
    if not isinstance(timeout, int) or timeout <= 0:
        raise RuntimeError("timeouts_ms must be positive integer")

    if row["side_effects"] is not False:
        raise RuntimeError("side_effects must be false")


def load_adapter_capabilities_v1() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    try:
        raw = _CAPABILITIES_PATH.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"failed to read adapter capabilities: {exc}") from exc

    try:
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"failed to parse adapter capabilities json: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("adapter capabilities root must be object")
    if data.get("version") != "v1":
        raise RuntimeError("adapter capabilities version must be v1")

    adapters = data.get("adapters")
    if not isinstance(adapters, list):
        raise RuntimeError("adapters must be list")

    for row in adapters:
        _validate_row(row)

    _CACHE = data
    return data


def get_adapter_capability(adapter_name: str) -> dict | None:
    data = load_adapter_capabilities_v1()
    adapters = data.get("adapters", [])
    for row in adapters:
        if isinstance(row, dict) and row.get("adapter_name") == adapter_name:
            return row
    return None
