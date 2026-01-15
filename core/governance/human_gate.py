from __future__ import annotations

from typing import List, Tuple

from .proposal_schema import PolicyProposal


# Reason codes should be stable strings (operators learn these)
REASON_BLAST_RADIUS = "BLAST_RADIUS_EXPANSION"
REASON_ROLLBACK_COST = "ROLLBACK_COST_INCREASE"
REASON_EXTERNAL_EFFECT = "EXTERNAL_REAL_WORLD_EFFECT"
REASON_SAFETY_COMPLIANCE = "SAFETY_COMPLIANCE_REPUTATION"
REASON_GOVERNANCE_SENSITIVE = "GOVERNANCE_SENSITIVE"


def evaluate_human_gate(proposal: PolicyProposal) -> Tuple[bool, List[str]]:
    """
    Deterministic checklist-based gate evaluation.
    This function should not depend on runtime mood or external context.
    """
    reasons: List[str] = []

    # A) Blast radius expansion
    if proposal.scope.blast_radius in {"system", "external"}:
        reasons.append(REASON_BLAST_RADIUS)

    # B) Rollback cost increase (heuristic from text fields; keep conservative)
    rollback_text = (proposal.explain.rollback_scope or "").lower()
    if any(k in rollback_text for k in ["migration", "downtime", "irreversible", "multi-service", "coordination"]):
        reasons.append(REASON_ROLLBACK_COST)

    # C) External / real-world effect
    if proposal.scope.blast_radius == "external":
        reasons.append(REASON_EXTERNAL_EFFECT)

    # D) Safety / compliance / reputation (heuristic; conservative)
    risks = " ".join([r.lower() for r in (proposal.explain.risks or [])])
    if any(k in risks for k in ["safety", "legal", "compliance", "reputation", "privacy"]):
        reasons.append(REASON_SAFETY_COMPLIANCE)

    # E) Governance change (domain/subsystem naming convention; adapt as needed)
    if proposal.scope.domain.lower() in {"governance", "constitution", "approval"}:
        reasons.append(REASON_GOVERNANCE_SENSITIVE)

    required = len(reasons) > 0
    return required, reasons
