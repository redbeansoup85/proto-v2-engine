from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Optional, Sequence, Any

from core.adapters.mock_adapter import AdapterError
from core.adapters.registry import AdapterRegistryError, resolve_adapter
from core.contracts.actions import ExecutionAction
from core.contracts.errors import (
    ContractMalformedError,
    ContractExpiredError,
    ContractForbiddenActionError,
    ContractConstraintError,
)
from core.contracts.execution_envelope import ExecutionEnvelope


@dataclass(frozen=True)
class ExecutionContext:
    action: ExecutionAction
    confidence: float
    input_sources: Sequence[str]
    dpa_id: str
    selected_option_id: str
    context: Optional[dict] = None
    estimated_latency_ms: Optional[int] = None
    cpu_pct_estimate: Optional[float] = None
    mem_mb_estimate: Optional[int] = None


class ShadowAdapterError(RuntimeError):
    pass


_CONTRACT_DIR = Path(__file__).resolve().parents[1] / "contracts"
_TRUE_SET = {"1", "true", "yes", "y", "on"}
_FALSE_SET = {"0", "false", "no", "n", "off"}


def is_shadow_only() -> bool:
    """
    Routing toggle point (Step 1: NO policy change).

    Semantics:
      - Default: True (shadow-only)
      - Missing env: True
      - Invalid/unrecognized value: True (fail-closed)
    """
    raw = os.getenv("SHADOW_ONLY")
    if raw is None:
        return True

    val = raw.strip().lower()
    if val in _TRUE_SET:
        return True
    if val in _FALSE_SET:
        return False
    return True


def _load_schema(name: str) -> dict:
    path = _CONTRACT_DIR / name
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _check_type(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_check_type(value, item) for item in expected)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _validate_schema(value: Any, schema: dict, path: str = "$") -> None:
    expected = schema.get("type")
    if expected is not None and not _check_type(value, expected):
        raise ShadowAdapterError(f"{path}: type mismatch")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise ShadowAdapterError(f"{path}: missing required key '{key}'")

        props = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        if additional is False:
            extras = [k for k in value.keys() if k not in props]
            if extras:
                raise ShadowAdapterError(f"{path}: unexpected keys {extras}")

        for key, sub_schema in props.items():
            if key in value and isinstance(sub_schema, dict):
                _validate_schema(value[key], sub_schema, f"{path}.{key}")
        return

    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                _validate_schema(item, item_schema, f"{path}[{idx}]")
        return


def run_shadow_adapter(*, adapter_name: str | None, request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ShadowAdapterError("request must be an object")

    _validate_schema(request, _load_schema("engine_request_v1.json"))

    try:
        adapter = resolve_adapter(adapter_name)
    except AdapterRegistryError as exc:
        raise ShadowAdapterError(str(exc)) from exc

    try:
        response = adapter.call(request)
    except AdapterError as exc:
        raise ShadowAdapterError(f"adapter call failed: {exc}") from exc

    if not isinstance(response, dict):
        raise ShadowAdapterError("adapter response must be an object")

    _validate_schema(response, _load_schema("engine_result_v1.json"))

    adapter_contract = {
        "adapter_name": adapter.name,
        "version": adapter.version,
        "request": request,
        "response": response,
    }
    _validate_schema(adapter_contract, _load_schema("adapter_contract_v1.json"))

    return response


def run_execution(*, envelope: ExecutionEnvelope, port: Any, ctx: ExecutionContext) -> Any:
    # 0) hard type check (fail-closed)
    if not isinstance(envelope, ExecutionEnvelope):
        raise ContractMalformedError("Envelope is not an ExecutionEnvelope instance")

    # 0.1) context sanity (fail-closed)
    if not (0.0 <= float(ctx.confidence) <= 1.0):
        raise ContractMalformedError(f"Invalid confidence: {ctx.confidence}")
    if not ctx.input_sources:
        raise ContractConstraintError("Missing input_sources (fail-closed)")

    # 1) expiry
    if envelope.is_expired():
        raise ContractExpiredError("ExecutionEnvelope expired")

    # 2) action allow/deny
    if ctx.action in set(envelope.authority.forbidden_actions):
        raise ContractForbiddenActionError(f"Execution action forbidden: {ctx.action}")
    if ctx.action not in set(envelope.authority.allowed_actions):
        raise ContractForbiddenActionError(f"Execution action not allowed: {ctx.action}")

    # 3) confidence floor
    if ctx.confidence < envelope.authority.confidence_floor:
        raise ContractConstraintError(
            f"Confidence below floor: {ctx.confidence:.4f} < {envelope.authority.confidence_floor:.4f}"
        )

    # 4) data scope
    allowed = set(envelope.constraints.data_scope.allowed_sources)
    forbidden = set(envelope.constraints.data_scope.forbidden_sources)
    srcs = set(ctx.input_sources)

    bad_forbidden = srcs.intersection(forbidden)
    if bad_forbidden:
        raise ContractConstraintError(f"Forbidden input sources used: {sorted(bad_forbidden)}")

    bad_not_allowed = srcs.difference(allowed)
    if bad_not_allowed:
        raise ContractConstraintError(f"Input sources not allowed: {sorted(bad_not_allowed)}")

    # 5) budgets
    if ctx.estimated_latency_ms is not None and ctx.estimated_latency_ms > envelope.constraints.latency_budget_ms:
        raise ContractConstraintError(
            f"Latency budget exceeded: {ctx.estimated_latency_ms} > {envelope.constraints.latency_budget_ms}"
        )
    if ctx.cpu_pct_estimate is not None and ctx.cpu_pct_estimate > envelope.constraints.resource_ceiling.cpu_pct:
        raise ContractConstraintError(
            f"CPU ceiling exceeded: {ctx.cpu_pct_estimate} > {envelope.constraints.resource_ceiling.cpu_pct}"
        )
    if ctx.mem_mb_estimate is not None and ctx.mem_mb_estimate > envelope.constraints.resource_ceiling.mem_mb:
        raise ContractConstraintError(
            f"Memory ceiling exceeded: {ctx.mem_mb_estimate} > {envelope.constraints.resource_ceiling.mem_mb}"
        )

    # 6) side-effect call (single choke point)
    if ctx.action == ExecutionAction.apply:
        # port is expected to implement apply(dpa_id=..., selected_option_id=..., context=...)
        return port.apply(dpa_id=ctx.dpa_id, selected_option_id=ctx.selected_option_id, context=ctx.context)

    raise ContractForbiddenActionError(f"Unknown execution action: {ctx.action}")
