import uuid
from typing import List, Optional

from core.governance import PolicyProposal
from core.governance.governance_version import OP_CANON_VERSION, OP_PACK_VERSION, REQUIRED_CONSTITUTION_SECTIONS
from core.governance.human_gate import evaluate_human_gate

from .config import LearningCanonConfig
from .sampling import SampleCheck
from .stability import StabilityResult


def build_policy_proposal(
    *,
    cfg: LearningCanonConfig,
    baseline_policy_snapshot_id: str,
    baseline_policy_hash: str,
    domain: str,
    subsystem: str,
    severity: str,
    blast_radius: str,
    patch_format: str,
    patch_content,
    explain_current: str,
    explain_proposed: str,
    rationale: str,
    expected_impact: str,
    rollback_scope: str,
    risks: Optional[List[str]] = None,
    assumptions: Optional[List[str]] = None,
    evidence_refs: Optional[List[str]] = None,
    sample_check: SampleCheck,
    stability: StabilityResult,
    source_kind: str = "learning",
    source_name: str = "learning_os",
    run_id: str = "run-unknown",
    created_at: str = "1970-01-01T00:00:00Z",
) -> PolicyProposal:
    """
    Builds a PolicyProposal that conforms to the locked Pack v1.0 structure.
    The caller is responsible for running eligibility checks and rate limiting before emitting.
    """
    raw = {
        "proposal_id": f"pp-{uuid.uuid4()}",
        "proposal_type": "policy_patch",
        "source": {"kind": source_kind, "name": source_name, "run_id": run_id, "created_at": created_at},
        "scope": {"domain": domain, "subsystem": subsystem, "severity": severity, "blast_radius": blast_radius},
        "preconditions": {
            "constitution": {
                "required_sections": REQUIRED_CONSTITUTION_SECTIONS,
                "constitution_hash": "constitution-hash-not-set",  # set by caller if you track it
            },
            "observation_window": {
                "mode": cfg.window_mode,
                "t_window": cfg.t_window if cfg.window_mode == "time" else None,
                "n_events": cfg.n_events_window if cfg.window_mode == "events" else None,
            },
            "sample": {"n_min": sample_check.n_min, "n_observed": sample_check.n_observed},
            "stability": {
                "k_confirmations": cfg.k_confirmations,
                "epsilon": cfg.epsilon_max,
                "summary": stability.summary,
            },
        },
        "baseline": {"policy_snapshot_id": baseline_policy_snapshot_id, "policy_hash": baseline_policy_hash},
        "patch": {"format": patch_format, "content": patch_content},
        "explain": {
            "current_policy_summary": explain_current,
            "proposed_policy_summary": explain_proposed,
            "rationale": rationale,
            "expected_impact": expected_impact,
            "rollback_scope": rollback_scope,
            "risks": risks or [],
            "assumptions": assumptions or [],
            "evidence_refs": evidence_refs or [],
        },
        "rate_limit": {"period": cfg.period, "limit_x": cfg.limit_x, "cooldown": cfg.cooldown, "rest_required": False},
        "human_gate": {"required": False, "reasons": []},
    }

    proposal = PolicyProposal.model_validate(raw)

    # Deterministic human gate fill
    required, reasons = evaluate_human_gate(proposal)
    proposal.human_gate.required = required
    proposal.human_gate.reasons = reasons

    return proposal
