from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DeliveryPlan:
    """
    Action-free DeliveryPlan.
    - MUST NOT trigger any external action.
    - Output is an artifact for humans/systems to execute elsewhere.
    """
    plan_id: str
    ts_iso: str

    proposal_id: str
    channel: Optional[str]

    # Traceability
    receipt_path: str
    receipt_hash: str

    # Policy state
    policy_version: int
    policy_sha256: str

    status: str  # READY / CREATED
    summary: str
    rationale: str

    warnings: List[str]

    # Evidence (raw + promoted links)
    evidence: Dict[str, Any]
    evidence_sample_ids: List[str]
    evidence_scene_ids: List[str]
    evidence_snapshot_ids: List[str]

    patch_ops: List[Dict[str, Any]]

    # Governance metadata
    approvers_used: List[str]
    applier: Optional[str]
    strategy: Optional[str]
    noop_apply: bool

    recommended_actions: List[Dict[str, Any]]
