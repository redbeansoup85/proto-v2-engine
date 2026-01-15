# core/learning/proposals.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Protocol, Tuple
import uuid


# -----------------------------
# Contracts (import from your SSoT if present)
# -----------------------------
# If you already have these in core/learning/contracts.py, import them instead:
# from core.learning.contracts import AnomalyEvent, PolicyPatchProposal, AutoProposalReceipt

@dataclass(frozen=True)
class AnomalyEvent:
    anomaly_id: str
    detected_ts: str  # ISO 8601
    org_id: str
    site_id: str
    channel: str
    anomaly_type: str
    signal: str
    severity: str
    confidence: float
    window: Dict[str, Any]
    summary: str
    evidence_scene_ids: List[str]
    metrics: Dict[str, Any]


@dataclass(frozen=True)
class PolicyPatchProposal:
    proposal_id: str
    created_ts: str
    status: str                     # "PROPOSED" | "SKIPPED"
    created_by: str                 # "auto_proposal_engine_v2"
    auto_proposed_by: Optional[str] # "learning_os_v2"

    org_id: str
    site_id: Optional[str]
    channel: str
    window_days: int

    sample_count: int
    confirmed_count: int
    false_alarm_rate: float
    incident_rate: float
    min_quality_score: Optional[float]

    patch_type: str                 # "JSONPATCH"
    patch: Dict[str, Any]           # {"ops":[...]} or {"op":..., ...}
    policy_version_base: Optional[str]

    rationale: str
    rationale_detail: Optional[Dict[str, Any]]

    evidence_sample_ids: List[str]
    evidence_scene_ids: List[str]
    evidence_snapshot_ids: List[str]
    evidence_metrics: Optional[Dict[str, Any]]

    requires_human_approval: bool
    blocked_reason: Optional[str]

    approval_id: Optional[str]
    applied_policy_version: Optional[str]


@dataclass(frozen=True)
class AutoProposalReceipt:
    receipt_type: str               # "AUTO_PROPOSAL_RECEIPT_V1"
    ts: str                         # ISO 8601
    org_id: str
    site_id: str
    channel: str
    anomaly_id: str
    proposal_id: Optional[str]
    auto_proposed_by: str           # "learning_os_v2"
    engine: str                     # "auto_proposal_engine_v2"
    evidence_scene_ids: List[str]
    status: str                     # "queued_for_approval" | "skipped"
    skip_reason: Optional[str]


# -----------------------------
# Ports / interfaces (adapt to your infra/storage + logs)
# -----------------------------
class PolicyStorePort(Protocol):
    def get_active_policy_version(self, *, org_id: str, site_id: Optional[str], channel: str) -> Optional[str]:
        ...

class ProposalRepoPort(Protocol):
    def save_proposal(self, proposal: PolicyPatchProposal) -> None:
        ...

class ReceiptRepoPort(Protocol):
    def append_receipt(self, receipt: AutoProposalReceipt) -> None:
        ...

class ApprovalSinkPort(Protocol):
    """
    This is NOT the 'apply'. It only queues a proposal for human review.
    Could write to logs/approvals, a queue, Slack, etc.
    """
    def enqueue_for_review(self, proposal: PolicyPatchProposal) -> str:
        """Returns approval_id"""
        ...

class CooldownRepoPort(Protocol):
    def get_last_proposal_ts(
        self,
        *,
        org_id: str,
        site_id: Optional[str],
        channel: str,
        template_id: str,
        signal: str,
    ) -> Optional[str]:
        """Returns ISO timestamp if exists."""
        ...


# -----------------------------
# Template Registry (whitelist-driven)
# -----------------------------
@dataclass(frozen=True)
class TemplateSpec:
    template_id: str
    description: str

    # Matching & generation
    supported_channels: List[str]
    supported_signals: List[str]
    supported_anomaly_types: List[str]

    # Safety guards
    min_confidence: float
    min_evidence_scenes: int
    cooldown_hours: int

    # JSONPatch allowlist: list of allowed JSON pointer prefixes
    # Example: ["/channels/childcare/thresholds/noise_level", "/channels/*/modes/holiday_mode"]
    allowed_path_prefixes: List[str]

    # Patch builder: must return RFC6902 ops list
    # Each op is dict like {"op":"replace","path":"/...","value":123}
    def build_patch_ops(self, event: AnomalyEvent, *, policy_version_base: Optional[str]) -> List[Dict[str, Any]]:
        raise NotImplementedError


class TemplateRegistry:
    def __init__(self, templates: List[TemplateSpec]) -> None:
        self._templates = templates

    def match(self, event: AnomalyEvent) -> Optional[TemplateSpec]:
        for t in self._templates:
            if event.channel not in t.supported_channels:
                continue
            if event.signal not in t.supported_signals:
                continue
            if event.anomaly_type not in t.supported_anomaly_types:
                continue
            if event.confidence < t.min_confidence:
                continue
            if len(event.evidence_scene_ids) < t.min_evidence_scenes:
                continue
            return t
        return None


# -----------------------------
# Helpers
# -----------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _uuid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"

def _parse_iso(ts: str) -> datetime:
    # robust-enough for UTC isoformat; adjust if you store Z
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)

def _is_allowed_path(path: str, allowed_prefixes: List[str]) -> bool:
    # Simple prefix match. Supports "*" wildcard only at segment level (coarse).
    # You can tighten later.
    # Example allowed: "/channels/*/thresholds/noise_level"
    # path: "/channels/childcare/thresholds/noise_level"
    if not path.startswith("/"):
        return False
    p_segs = path.strip("/").split("/")
    for pref in allowed_prefixes:
        if not pref.startswith("/"):
            continue
        pref_segs = pref.strip("/").split("/")
        if len(pref_segs) > len(p_segs):
            continue
        ok = True
        for i, seg in enumerate(pref_segs):
            if seg == "*":
                continue
            if seg != p_segs[i]:
                ok = False
                break
        if ok:
            return True
    return False

def validate_jsonpatch_ops(ops: List[Dict[str, Any]], allowed_prefixes: List[str]) -> Tuple[bool, Optional[str]]:
    if not isinstance(ops, list) or len(ops) == 0:
        return False, "empty_patch"
    for op in ops:
        if not isinstance(op, dict):
            return False, "invalid_op_type"
        if "op" not in op or "path" not in op:
            return False, "missing_op_or_path"
        if op["op"] not in ("add", "remove", "replace", "move", "copy", "test"):
            return False, f"unsupported_op:{op.get('op')}"
        path = op["path"]
        if not isinstance(path, str):
            return False, "path_not_string"
        if not _is_allowed_path(path, allowed_prefixes):
            return False, f"path_not_allowed:{path}"
    return True, None


# -----------------------------
# Default template example (you should add more)
# -----------------------------
class ChildcareNoiseChronicEscalateV1(TemplateSpec):
    def __init__(self) -> None:
        super().__init__(
            template_id="childcare_noise_chronic_escalate_v1",
            description="Escalate noise threshold slightly after chronic breach pattern.",
            supported_channels=["childcare"],
            supported_signals=["noise_level"],
            supported_anomaly_types=["chronic_breach", "threshold_trend"],
            min_confidence=0.70,
            min_evidence_scenes=3,
            cooldown_hours=24,
            allowed_path_prefixes=[
                "/channels/childcare/thresholds/noise_level",
                "/channels/childcare/modes/observe_more",
            ],
        )

    def build_patch_ops(self, event: AnomalyEvent, *, policy_version_base: Optional[str]) -> List[Dict[str, Any]]:
        # Very conservative patch: small threshold delta with clamp.
        # Uses event.metrics if present.
        base = float(event.metrics.get("baseline_mean", 0.0) or 0.0)
        curr = float(event.metrics.get("current_mean", 0.0) or 0.0)

        # heuristic: raise threshold toward current but cap the change
        delta = max(0.0, min(0.10, (curr - base) * 0.25))  # cap to +0.10
        # If no signal, do a minimal nudge
        if delta == 0.0:
            delta = 0.03

        return [
            {
                "op": "replace",
                "path": "/channels/childcare/thresholds/noise_level",
                "value": {"adjustment": {"op": "increase", "delta": round(delta, 3), "cap": 0.10}},
            },
            {
                "op": "replace",
                "path": "/channels/childcare/modes/observe_more",
                "value": {"enabled": True, "reason": "chronic_noise_pressure"},
            },
        ]


# -----------------------------
# Engine result (for jobs/cli/api)
# -----------------------------
@dataclass(frozen=True)
class AutoProposalResult:
    receipt: AutoProposalReceipt
    proposal: Optional[PolicyPatchProposal]


# -----------------------------
# v2-alpha: single entrypoint
# -----------------------------
def auto_propose_from_anomaly(
    event: AnomalyEvent,
    *,
    policy_store: PolicyStorePort,
    proposal_repo: ProposalRepoPort,
    receipt_repo: ReceiptRepoPort,
    approval_sink: ApprovalSinkPort,
    cooldown_repo: Optional[CooldownRepoPort] = None,
    template_registry: Optional[TemplateRegistry] = None,
    engine_name: str = "auto_proposal_engine_v2",
    auto_proposed_by: str = "learning_os_v2",
    default_window_days: int = 3,
) -> AutoProposalResult:
    """
    v2-alpha Auto-Proposal Engine.

    Guarantees:
    - Always emits an AutoProposalReceipt (even on skip).
    - Never auto-applies patches.
    - Enforces template whitelist + evidence minimum + cooldown.
    """

    registry = template_registry or TemplateRegistry([ChildcareNoiseChronicEscalateV1()])

    # 1) Template match (includes min_confidence & min_evidence checks)
    tpl = registry.match(event)
    if tpl is None:
        receipt = AutoProposalReceipt(
            receipt_type="AUTO_PROPOSAL_RECEIPT_V1",
            ts=_now_iso(),
            org_id=event.org_id,
            site_id=event.site_id,
            channel=event.channel,
            anomaly_id=event.anomaly_id,
            proposal_id=None,
            auto_proposed_by=auto_proposed_by,
            engine=engine_name,
            evidence_scene_ids=list(event.evidence_scene_ids),
            status="skipped",
            skip_reason="no_matching_template_or_insufficient_evidence_or_low_confidence",
        )
        receipt_repo.append_receipt(receipt)
        return AutoProposalResult(receipt=receipt, proposal=None)

    # 2) Cooldown check (optional but recommended)
    if cooldown_repo is not None:
        last_ts = cooldown_repo.get_last_proposal_ts(
            org_id=event.org_id,
            site_id=event.site_id,
            channel=event.channel,
            template_id=tpl.template_id,
            signal=event.signal,
        )
        if last_ts:
            last_dt = _parse_iso(last_ts)
            if datetime.now(timezone.utc) - last_dt < timedelta(hours=tpl.cooldown_hours):
                receipt = AutoProposalReceipt(
                    receipt_type="AUTO_PROPOSAL_RECEIPT_V1",
                    ts=_now_iso(),
                    org_id=event.org_id,
                    site_id=event.site_id,
                    channel=event.channel,
                    anomaly_id=event.anomaly_id,
                    proposal_id=None,
                    auto_proposed_by=auto_proposed_by,
                    engine=engine_name,
                    evidence_scene_ids=list(event.evidence_scene_ids),
                    status="skipped",
                    skip_reason=f"cooldown_active:{tpl.cooldown_hours}h",
                )
                receipt_repo.append_receipt(receipt)
                return AutoProposalResult(receipt=receipt, proposal=None)

    # 3) Resolve policy base
    policy_version_base = policy_store.get_active_policy_version(
        org_id=event.org_id, site_id=event.site_id, channel=event.channel
    )

    # 4) Build patch ops (template-controlled)
    ops = tpl.build_patch_ops(event, policy_version_base=policy_version_base)

    ok, why = validate_jsonpatch_ops(ops, tpl.allowed_path_prefixes)
    if not ok:
        receipt = AutoProposalReceipt(
            receipt_type="AUTO_PROPOSAL_RECEIPT_V1",
            ts=_now_iso(),
            org_id=event.org_id,
            site_id=event.site_id,
            channel=event.channel,
            anomaly_id=event.anomaly_id,
            proposal_id=None,
            auto_proposed_by=auto_proposed_by,
            engine=engine_name,
            evidence_scene_ids=list(event.evidence_scene_ids),
            status="skipped",
            skip_reason=f"patch_validation_failed:{why}",
        )
        receipt_repo.append_receipt(receipt)
        return AutoProposalResult(receipt=receipt, proposal=None)

    # 5) Create proposal artifact
    proposal_id = _uuid("pp")
    created_ts = _now_iso()

    proposal = PolicyPatchProposal(
        proposal_id=proposal_id,
        ts_created=created_ts,
        status="PROPOSED",
        created_by=engine_name,
        auto_proposed_by=auto_proposed_by,
        org_id=event.org_id,
        site_id=event.site_id,
        channel=event.channel,
        window_days=int(event.window.get("size", default_window_days)) if isinstance(event.window, dict) else default_window_days,
        sample_count=int(event.metrics.get("sample_count", 0) or 0),
        confirmed_count=int(event.metrics.get("confirmed_count", 0) or 0),
        false_alarm_rate=float(event.metrics.get("false_alarm_rate", 0.0) or 0.0),
        incident_rate=float(event.metrics.get("incident_rate", 0.0) or 0.0),
        min_quality_score=float(event.metrics.get("min_quality_score", 0.0)) if "min_quality_score" in event.metrics else None,
        patch_type="JSONPATCH",
        patch={"ops": ops},
        policy_version_base=policy_version_base,
        rationale=event.summary,
        rationale_detail={
            "title": f"Auto proposal via template {tpl.template_id}",
            "template_id": tpl.template_id,
            "anomaly_type": event.anomaly_type,
            "signal": event.signal,
            "severity": event.severity,
            "confidence": event.confidence,
            "risk_notes": [
                "Auto-proposed; requires explicit human approval.",
                "Patch restricted to whitelist paths.",
            ],
        },
        evidence_sample_ids=list(event.metrics.get("evidence_sample_ids", [])) if isinstance(event.metrics.get("evidence_sample_ids", []), list) else [],
        evidence_scene_ids=list(event.evidence_scene_ids),
        evidence_snapshot_ids=list(event.metrics.get("evidence_snapshot_ids", [])) if isinstance(event.metrics.get("evidence_snapshot_ids", []), list) else [],
        evidence_metrics={"metrics": event.metrics, "window": event.window},
        requires_human_approval=True,
        blocked_reason=None,
        approval_id=None,
        applied_policy_version=None,
    )

    # 6) Persist proposal
    proposal_repo.save_proposal(proposal)

    # 7) Queue for human review (approval)
    approval_id = approval_sink.enqueue_for_review(proposal)

    # (optional) if you want to store approval_id in proposal, you can emit a second artifact
    # In alpha, keep immutable artifacts and store approval_id in receipt only, or create a new "proposal_update" event.
    # Here we keep proposal immutable and record approval_id in receipt.

    # 8) Emit receipt (DoD)
    receipt = AutoProposalReceipt(
        receipt_type="AUTO_PROPOSAL_RECEIPT_V1",
        ts=_now_iso(),
        org_id=event.org_id,
        site_id=event.site_id,
        channel=event.channel,
        anomaly_id=event.anomaly_id,
        proposal_id=proposal_id,
        auto_proposed_by=auto_proposed_by,
        engine=engine_name,
        evidence_scene_ids=list(event.evidence_scene_ids),
        status="queued_for_approval",
        skip_reason=None,
    )
    receipt_repo.append_receipt(receipt)

    return AutoProposalResult(receipt=receipt, proposal=proposal)
