import time
from dataclasses import dataclass
from typing import Optional

from core.governance.proposal_validator import CanonParams, validate_proposal_prequeue
from core.governance.human_gate import evaluate_human_gate
from core.governance.proposal_schema import PolicyProposal

from .queue_writer import QueueWriter
from .rate_limiter import RateLimiter, RateLimitDecision
from .config import LearningCanonConfig


@dataclass(frozen=True)
class EmitDecision:
    emitted: bool
    reason: str
    rate_limit: Optional[RateLimitDecision] = None


def emit_proposal_if_allowed(
    *,
    proposal: PolicyProposal,
    cfg: LearningCanonConfig,
    canon_params: CanonParams,
    embedded_canon_version: str,
    embedded_pack_version: str,
    writer: QueueWriter,
    limiter: RateLimiter,
    limiter_key: str,
    now: Optional[float] = None,
) -> EmitDecision:
    """
    Emits a proposal to the Approval Queue only when:
    - Canon/Pack pre-queue validation passes
    - Human gate is not required (required proposals must wait for explicit human approval)
    - Rate limiting allows emission

    Returns an EmitDecision with explicit reason codes.
    """
    t = now if now is not None else time.time()

    # 1) Deterministic human gate recompute (avoid trusting upstream mutation)
    required, reasons = evaluate_human_gate(proposal)
    if required:
        return EmitDecision(emitted=False, reason=f"HUMAN_GATE_REQUIRED:{','.join(reasons)}")

    # 2) Canon-bound pre-queue validation (structure + eligibility + version pin)
    validate_proposal_prequeue(
        proposal,
        canon_params=canon_params,
        embedded_canon_version=embedded_canon_version,
        embedded_pack_version=embedded_pack_version,
    )

    # 3) Rate limit (hard stop)
    rl = limiter.check_and_record(limiter_key, now=t)
    if not rl.allowed:
        return EmitDecision(emitted=False, reason=rl.reason, rate_limit=rl)

    # 4) Emit (writer is pluggable)
    writer.write(proposal.model_dump())

    return EmitDecision(emitted=True, reason="EMITTED_OK", rate_limit=rl)
