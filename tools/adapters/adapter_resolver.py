from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List


class AdapterResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class AdapterEntry:
    card_id: str
    adapter_path: str
    approval_mode: str
    capabilities: List[str]
    risk_tier: str
    enabled: bool
    notes: str = ""


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise AdapterResolutionError(f"PyYAML required but not available: {e}") from e

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise AdapterResolutionError(f"YAML parse failed: {path}: {e}") from e

    return json.loads(json.dumps(data, ensure_ascii=False, sort_keys=True))


def resolve_adapter(*, card_id: str, registry_path: Path, require_enabled: bool = True) -> Callable[..., Any]:
    if not registry_path.is_file():
        raise AdapterResolutionError(f"Registry file not found: {registry_path}")

    registry = _load_yaml(registry_path)
    entries = registry.get("entries") or []
    if not isinstance(entries, list) or not entries:
        raise AdapterResolutionError("Registry missing entries (fail-closed).")

    found = None
    for e in entries:
        if isinstance(e, dict) and str(e.get("card_id", "")).strip() == card_id:
            found = e
            break

    if not found:
        raise AdapterResolutionError(f"Card not registered (fail-closed): {card_id}")

    if require_enabled and not bool(found.get("enabled", False)):
        raise AdapterResolutionError(f"Card registered but disabled (fail-closed): {card_id}")

    adapter_path = str(found.get("adapter_path", "")).strip()
    if not adapter_path or "." not in adapter_path:
        raise AdapterResolutionError(f"Invalid adapter_path (fail-closed): {adapter_path!r}")

    module_path, _, attr = adapter_path.rpartition(".")
    try:
        mod = importlib.import_module(module_path)
    except Exception as e:
        raise AdapterResolutionError(f"Adapter import failed (fail-closed): {adapter_path}: {e}") from e

    fn = getattr(mod, attr, None)
    if fn is None or not callable(fn):
        raise AdapterResolutionError(f"Adapter not callable (fail-closed): {adapter_path}")

    return fn
