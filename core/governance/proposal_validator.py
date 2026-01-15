from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .errors import CanonViolation, HumanGateViolation, ProposalInvalid
from .governance_version import OP_CANON_VERSION, OP_PACK_VERSION, REQUIRED_CONSTITUTION_SECTIONS
from .human_gate import evaluate_human_gate
from .proposal_schema import PolicyProposal


@dataclass(frozen=True)
class CanonParams:
    # Canon parameters should be explicitly configured (v1: provided by caller)
    t_window_required: Optional[str] = None  # e.g., "7d" (informational check)
    n_min: Optional[int] = None
    k_confirmations: Optional[int] = None
    epsilon_max: Optional[float] = None
    limit_x: Optional[int] = None


def validate_proposal_schema(raw: dict) -> PolicyProposal:
    """Schema validation only (Pydantic)."""
    try:
        return PolicyProposal.model_validate(raw)
    except Exception as e:
        raise ProposalInvalid(str(e)) from e


def validate_proposal_prequeue(
    proposal: PolicyProposal,
    *,
    canon_params: CanonParams,
    embedded_canon_version: str,
    embedded_pack_version: str,
) -> None:
    """
    Canon-bound pre-queue validation:
    - constitution section requirements are present
    - observation window / sample sufficiency / stability meet minimums
    - rate limiting fields are coherent
    - human gate is correctly marked when required
    """
    # --- No silent changes guard (versions embedded in proposal metadata somewhere)
    if embedded_canon_version != OP_CANON_VERSION:
        raise CanonViolation(f"canon version mismatch: embedded={embedded_canon_version} expected={OP_CANON_VERSION}")
    if embedded_pack_version != OP_PACK_VERSION:
        raise CanonViolation(f"pack version mismatch: embedded={embedded_pack_version} expected={OP_PACK_VERSION}")

    # --- Constitution required sections
    req = set(proposal.preconditions.constitution.required_sections or [])
    missing = [s for s in REQUIRED_CONSTITUTION_SECTIONS if s not in req]
    if missing:
        raise CanonViolation(f"missing required constitution sections: {missing}")

    # --- Observation window (minimal, conservative)
    ow = proposal.preconditions.observation_window
    if ow.mode == "time" and not ow.t_window:
        raise CanonViolation("observation window invalid: time mode requires t_window")
    if ow.mode == "events" and (ow.n_events is None or ow.n_events <= 0):
        raise CanonViolation("observation window invalid: events mode requires n_events>0")

    # --- Sample sufficiency
    sample = proposal.preconditions.sample
    if canon_params.n_min is not None and sample.n_min != canon_params.n_min:
        raise CanonViolation(f"n_min must match canon params (got {sample.n_min}, expected {canon_params.n_min})")
    if sample.n_observed < sample.n_min:
        raise CanonViolation(f"insufficient samples: observed={sample.n_observed} < n_min={sample.n_min}")

    # --- Stability confirmation
    st = proposal.preconditions.stability
    if canon_params.k_confirmations is not None and st.k_confirmations < canon_params.k_confirmations:
        raise CanonViolation(
            f"stability insufficient: k_confirmations={st.k_confirmations} < required={canon_params.k_confirmations}"
        )
    if canon_params.epsilon_max is not None and st.epsilon > canon_params.epsilon_max:
        raise CanonViolation(f"stability epsilon too high: epsilon={st.epsilon} > max={canon_params.epsilon_max}")
    if not st.summary.strip():
        raise CanonViolation("stability.summary must be non-empty")

    # --- Rate limit coherence
    rl = proposal.rate_limit
    if canon_params.limit_x is not None and rl.limit_x != canon_params.limit_x:
        raise CanonViolation(f"rate_limit.limit_x must match canon params (got {rl.limit_x}, expected {canon_params.limit_x})")
    if rl.limit_x < 0:
        raise CanonViolation("rate_limit.limit_x must be >= 0")

    # --- Human gate correctness (deterministic)
    required, reasons = evaluate_human_gate(proposal)
    if required and proposal.human_gate.required is not True:
        raise HumanGateViolation(f"human gate required but proposal marked required={proposal.human_gate.required}; reasons={reasons}")
    if required:
        # ensure reasons are present
        if not proposal.human_gate.reasons:
            raise HumanGateViolation("human gate required but reasons empty")
