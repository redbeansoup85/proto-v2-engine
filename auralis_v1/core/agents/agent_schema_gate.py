from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

FORBIDDEN_OUTPUT_KEYS = {
    "execute",
    "order",
    ("place" + "_order"),
    "trade",
    "qty",
    "size",
    "price",
    "leverage",
    "position",
    "approve",
    "reject",
    "commit",
}

_BASE_DIR = Path(__file__).resolve().parent
_REGISTRY_PATH = _BASE_DIR / "AGENT_REGISTRY.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"failed to load yaml: {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid yaml object: {path}")
    return data


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"failed to load json: {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid json object: {path}")
    return data


def _check_forbidden_keys(obj: Any, path: str = "$") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str) and key.lower() in FORBIDDEN_OUTPUT_KEYS:
                raise RuntimeError(f"forbidden output key: {path}.{key}")
            _check_forbidden_keys(value, f"{path}.{key}")
        return
    if isinstance(obj, list):
        for idx, value in enumerate(obj):
            _check_forbidden_keys(value, f"{path}[{idx}]")


def _validate_schema(payload: Any, schema: dict[str, Any], path: str = "$") -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(payload, dict):
            raise RuntimeError(f"{path}: expected object")
        props = schema.get("properties", {})
        required = schema.get("required", [])
        for req in required:
            if req not in payload:
                raise RuntimeError(f"{path}: missing required key {req}")
        if schema.get("additionalProperties") is False:
            extras = set(payload.keys()) - set(props.keys())
            if extras:
                raise RuntimeError(f"{path}: extra keys not allowed: {sorted(extras)}")
        for key, val in payload.items():
            if key in props and isinstance(props[key], dict):
                _validate_schema(val, props[key], f"{path}.{key}")
        return

    if schema_type == "array":
        if not isinstance(payload, list):
            raise RuntimeError(f"{path}: expected array")
        item_schema = schema.get("items", {})
        if isinstance(item_schema, dict):
            for idx, item in enumerate(payload):
                _validate_schema(item, item_schema, f"{path}[{idx}]")
        return

    if schema_type == "string":
        if not isinstance(payload, str):
            raise RuntimeError(f"{path}: expected string")
        return

    if schema_type == "integer":
        if not isinstance(payload, int):
            raise RuntimeError(f"{path}: expected integer")
        return

    if schema_type == "boolean":
        if not isinstance(payload, bool):
            raise RuntimeError(f"{path}: expected boolean")
        return

    if schema_type is None:
        return
    raise RuntimeError(f"{path}: unsupported schema type {schema_type}")


def get_agent_config(agent_key: str) -> dict[str, Any]:
    registry = _load_yaml(_REGISTRY_PATH)
    agents = registry.get("agents")
    if not isinstance(agents, dict):
        raise RuntimeError("invalid registry: agents")
    cfg = agents.get(agent_key)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"unknown agent: {agent_key}")
    return cfg


def validate_agent_output(agent_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError("payload must be object")
    cfg = get_agent_config(agent_key)
    schema_rel = cfg.get("schema")
    if not isinstance(schema_rel, str) or not schema_rel:
        raise RuntimeError(f"missing schema path for agent: {agent_key}")
    schema_path = Path(schema_rel)
    if not schema_path.is_absolute():
        schema_path = Path(__file__).resolve().parents[3] / schema_rel
    schema = _load_json(schema_path)
    _check_forbidden_keys(payload)
    _validate_schema(payload, schema)
    return payload
