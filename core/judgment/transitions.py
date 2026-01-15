from __future__ import annotations

from datetime import datetime, timezone

from .errors import conflict, forbidden, unprocessable
from .models import DpaRecord, HumanDecision
from .status import DecisionStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_TERMINAL = {DecisionStatus.ABORTED, DecisionStatus.APPLIED}


def start_review(dpa: DpaRecord, *, reviewer: str) -> DpaRecord:
    if dpa.status in _TERMINAL:
        raise conflict("STATUS_TERMINAL", "Cannot start review on terminal DPA.", {"status": dpa.status})

    if dpa.status not in {DecisionStatus.DPA_CREATED, DecisionStatus.HUMAN_REVIEWING}:
        raise conflict(
            "STATUS_INVALID_TRANSITION",
            "Review can only start from DPA_CREATED/HUMAN_REVIEWING.",
            {"status": dpa.status},
        )

    dpa.status = DecisionStatus.HUMAN_REVIEWING
    dpa.updated_at = _utcnow()
    return dpa


def submit_human_decision(dpa: DpaRecord, decision: HumanDecision) -> DpaRecord:
    if dpa.status in _TERMINAL:
        raise conflict("STATUS_TERMINAL", "Cannot approve a terminal DPA.", {"status": dpa.status})

    if dpa.status not in {DecisionStatus.DPA_CREATED, DecisionStatus.HUMAN_REVIEWING}:
        raise conflict(
            "STATUS_INVALID_TRANSITION",
            "Human decision can only be submitted from DPA_CREATED/HUMAN_REVIEWING.",
            {"status": dpa.status},
        )

    # 422: approver fields required (policy-level)
    if not decision.approver_name or not decision.approver_role or not decision.signature:
        raise unprocessable("APPROVER_REQUIRED", "Approver fields are required.")

    # option existence + blocked guard
    opt_map = {o.option_id: o for o in dpa.options_json}
    opt = opt_map.get(decision.selected_option_id)
    if not opt:
        raise unprocessable(
            "OPTION_NOT_FOUND",
            "selected_option_id not present in options.",
            {"selected_option_id": decision.selected_option_id},
        )
    if opt.blocked:
        raise conflict(
            "OPTION_BLOCKED",
            "Selected option is blocked and cannot be approved.",
            {"selected_option_id": opt.option_id, "blocked_reason": opt.blocked_reason},
        )

    dpa.human_decision_json = decision
    dpa.status = DecisionStatus.APPROVED
    dpa.approved_at = decision.decided_at
    dpa.approved_by = f"{decision.approver_name} ({decision.approver_role})"
    dpa.updated_at = _utcnow()
    return dpa


def apply(dpa: DpaRecord) -> DpaRecord:
    if dpa.status in _TERMINAL:
        raise conflict("STATUS_TERMINAL", "Cannot apply a terminal DPA.", {"status": dpa.status})

    if dpa.status != DecisionStatus.APPROVED:
        raise conflict(
            "STATUS_INVALID_TRANSITION",
            "Apply requires status=APPROVED.",
            {"status": dpa.status},
        )

    # 403: human_decision 없이 apply 금지 (서버 강제 핵심)
    if dpa.human_decision_json is None:
        raise forbidden("HUMAN_DECISION_REQUIRED", "Cannot apply without human_decision.")

    if not dpa.approved_at or not dpa.approved_by:
        raise conflict("APPROVAL_FIELDS_REQUIRED", "approved_at and approved_by must exist before apply.")

    dpa.status = DecisionStatus.APPLIED
    dpa.updated_at = _utcnow()
    return dpa


def abort(dpa: DpaRecord, *, reason: str | None = None) -> DpaRecord:
    if dpa.status == DecisionStatus.APPLIED:
        raise conflict("STATUS_TERMINAL", "Cannot abort an already applied DPA.", {"status": dpa.status})

    if dpa.status == DecisionStatus.ABORTED:
        return dpa  # idempotent

    dpa.status = DecisionStatus.ABORTED
    dpa.updated_at = _utcnow()
    if reason:
        dpa.constraints_json = {**dpa.constraints_json, "abort_reason": reason}
    return dpa
