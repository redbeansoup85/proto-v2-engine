from __future__ import annotations

from typing import Any

import yaml
from pathlib import Path

from .agent_schema_gate import get_agent_config

_REGISTRY_PATH = Path(__file__).resolve().parent / "AGENT_REGISTRY.yaml"


def load_registry() -> dict[str, Any]:
    try:
        data = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError("failed to load agent registry") from exc
    if not isinstance(data, dict):
        raise RuntimeError("invalid agent registry")
    return data


def route_agent(mode: str | None) -> str:
    if mode == "reasoning":
        return "reasoning"
    if mode == "design":
        return "design"
    return "fast"


def resolve_agent(mode: str | None) -> dict[str, Any]:
    key = route_agent(mode)
    cfg = get_agent_config(key)
    return {"agent_key": key, "provider": cfg.get("provider"), "model": cfg.get("model"), "role": cfg.get("role")}
