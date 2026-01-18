from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Any

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
