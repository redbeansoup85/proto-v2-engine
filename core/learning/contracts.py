from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List


# =============================================================================
# Learning / Governance Contracts (SSoT)
#
# This module is the single source of truth for:
# - Learning samples (feedback/training artifacts)
# - Anomaly events (auto-proposal trigger inputs)
# - Policy patch proposals (auto-proposal outputs)
# - Auto-proposal receipts (audit records for "system proposed X")
#
# Design rule (v2-alpha):
# - Emotion/learning signals do NOT directly "decide".
# - They can only trigger an audited, human-approved proposal flow.
# =============================================================================


# -----------------------------------------------------------------------------
# v2-rc+ (Feedback loop) primitive:
# "What happened" sample that can be used to learn / propose improvements later.
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class LearningSample:
    # Identity / evidence
    sample_id: str
    ts_created: str  # ISO 8601 recommended (kept as-is for backward compatibility)

    org_id: str
    site_id: str
    channel: str

    scene_id: str
    snapshot_id: Optional[str]  # decision snapshot evidence (can be None initially)

    # What the system decided at that time
    mode: str
    severity: str
    rationale_codes: List[str]
    delivery_plan: str  # Consider migrating to delivery_plan_id in a later version.

    # Raw signals/features (keep minimal in v0.1)
    signals: Dict[str, Any]

    # Outcomes (filled later)
    outcome_label: Optional[str]  # e.g., "safe", "incident", "false_alarm"
    outcome_notes: Optional[str]  # human notes
    human_confirmed: bool         # True when human confirmed/entered outcome

    # Quality / control
    quality_score: float          # 0~1


# -----------------------------------------------------------------------------
# v2-alpha primitive:
# "Something is abnormal" event detected by Learning OS (or analytics),
# used to trigger an auto-proposal attempt.
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class AnomalyEvent:
    anomaly_id: str
    detected_ts: str  # ISO 8601

    org_id: str
    site_id: str
    channel: str

    anomaly_type: str    # e.g. "threshold_trend" | "chronic_breach" | "spike" | "quality_degradation"
    signal: str          # e.g. "noise_level" | "high_negative_child_emotion"
    severity: str        # "low" | "medium" | "high" | "critical"
    confidence: float    # 0~1

    # Optional structured context about the detection window
    # Example: {"kind": "rolling", "size": 72, "unit": "hours"} or {"start_iso": "...", "end_iso": "..."}
    window: Dict[str, Any]

    # Human-readable summary (safe to show to approvers)
    summary: str

    # Evidence pointers (scene ids, receipt ids, snapshot ids, etc.)
    evidence_scene_ids: List[str]

    # Minimal metrics, flexible schema:
    # Examples: {"baseline_mean": 0.31, "current_mean": 0.58, "breach_count": 9, "trend_slope": 0.07}
    metrics: Dict[str, Any]


# -----------------------------------------------------------------------------
# v2-alpha primitive:
# Output artifact representing "a proposed patch".
# This is NEVER auto-applied; it must go through the normal approval flow.
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class PolicyPatchProposal:
    proposal_id: str
    created_ts: str  # ISO 8601

    # DoD / audit anchors
    created_by: str        # "auto_proposal_engine_v2"
    auto_proposed_by: str  # "learning_os_v2"

    org_id: str
    site_id: str
    channel: str

    # What policy was used as the base (optional for early alpha)
    policy_version_base: Optional[str]

    # Proposal payload
    proposal_kind: str               # "JSONPATCH"
    patches: List[Dict[str, Any]]    # RFC6902 JSON Patch operations

    # Rationale and constraints (approver-facing)
    reasoning: Dict[str, Any]        # e.g. {"title": "...", "rationale": [...], "risk_notes": [...], "template_id": "..."}
    evidence: Dict[str, Any]         # e.g. {"anomaly_id": "...", "evidence_scene_ids": [...], "metrics": {...}}

    # Proposal lifecycle (alpha)
    status: str                      # "PROPOSED" | "SKIPPED"


# -----------------------------------------------------------------------------
# v2-alpha DoD:
# Every auto-proposal attempt must emit an audit receipt.
# Even a "skip" must be receipted (with skip_reason).
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class AutoProposalReceipt:
    receipt_type: str  # Must be "AUTO_PROPOSAL_RECEIPT_V1"
    ts: str            # ISO 8601

    org_id: str
    site_id: str
    channel: str

    anomaly_id: str
    proposal_id: Optional[str]

    auto_proposed_by: str  # "learning_os_v2"
    engine: str            # "auto_proposal_engine_v2"

    evidence_scene_ids: List[str]

    status: str            # "queued_for_approval" | "skipped"
    skip_reason: Optional[str]
