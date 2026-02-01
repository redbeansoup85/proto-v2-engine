from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from infra.api.audit_sink import emit_audit_event
from infra.api.deps import get_session
from infra.api.endpoints.models.approval import Approval
from infra.api.endpoints.models.approval_decision_event import ApprovalDecisionEvent
from infra.api.endpoints.models.execution_run import ExecutionRun

router = APIRouter(tags=["approvals"])


def _utcnow() -> datetime:
    # keep naive utc for SQLite consistency (execution.py와 동일 철학)
    return datetime.utcnow()


def _coerce_sqlite_dt(value: Any) -> Optional[datetime]:
    """
    SQLite에서는 expires_at이 datetime으로도, 문자열로도 들어올 수 있음.
    LOCK 관점에서 "타입 혼용"은 허용하되, 판정은 반드시 결정론적으로 해야 함.
    - datetime -> 그대로 사용 (naive utc 가정)
    - str -> ISO / 'YYYY-MM-DD HH:MM:SS' 형태 파싱
    - 그 외 -> None (fail-closed는 _is_expired에서 수행)
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value.strip()
        # 1) "YYYY-MM-DD HH:MM:SS"
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
        # 2) ISO8601 (Z 포함/미포함)
        try:
            # 'Z' -> '+00:00'로 치환 후 fromisoformat
            s2 = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s2)
            # tz-aware면 naive로 내림(utc 기준)
            if dt.tzinfo is not None:
                dt = dt.astimezone(tz=None).replace(tzinfo=None)
            return dt
        except Exception:
            return None
    return None


def _is_expired(appr: Approval) -> bool:
    if appr.status != "pending":
        return False

    raw = getattr(appr, "expires_at", None)
    exp = _coerce_sqlite_dt(raw)

    # expires_at 필드가 존재하는데 파싱이 안 되면,
    # "만료 판정을 못해서 승인해버리는" 것이 가장 위험하므로 FAIL-CLOSED로 만료 처리.
    if raw is not None and exp is None:
        return True

    return exp is not None and _utcnow() >= exp


async def _mark_expired(session: AsyncSession, *, execution_id: str, appr: Approval) -> None:
    """
    pending approval이 expires_at을 넘겼으면:
    - approval.status = expired
    - execution_run.status = BLOCKED, blocked_reason = approval_expired
    - audit 기록
    """
    now = _utcnow()

    # approval expired
    appr.status = "expired"
    appr.resolved_at = now

    # execution run blocked (항상 고정)
    run = await session.get(ExecutionRun, execution_id)
    if run is not None:
        run.status = "BLOCKED"
        run.blocked_reason = "approval_expired"
        # expired는 "승인 불가"이므로 ended_at을 남기는 게 합리적
        if getattr(run, "ended_at", None) is None:
            run.ended_at = now

    emit_audit_event(
        {
            "event_type": "approval_expired",
            "outcome": "deny",
            "execution_id": execution_id,
            "approval_id": appr.id,
            "resolved_at": now.isoformat(),
        }
    )

    await session.commit()


@router.post("/approvals/{execution_id}/approve")
async def approve(
    execution_id: str,
    session: AsyncSession = Depends(get_session),
):
    # 1) load approval (1:1)
    res = await session.execute(
        select(Approval).where(Approval.execution_run_id == execution_id)
    )
    appr = res.scalar_one_or_none()
    if appr is None:
        raise HTTPException(status_code=404, detail="approval_not_found")

    # 1.1) expire gate (Phase 1.1) — FAIL-CLOSED
    if _is_expired(appr):
        await _mark_expired(session, execution_id=execution_id, appr=appr)
        raise HTTPException(status_code=409, detail="approval_expired")

    # 1.2) already resolved → idempotent-ish
    if appr.status in ("approved", "rejected", "expired"):
        run = await session.get(ExecutionRun, execution_id)
        run_status = run.status if run else None
        return {
            "ok": True,
            "execution_id": execution_id,
            "approval_status": appr.status,
            "run_status": run_status,
        }

    # 2) write decision event (prevent duplicate decisions via DB constraint/unique)
    decided_at = _utcnow()
    event = ApprovalDecisionEvent(
        id=str(uuid.uuid4()),
        approval_id=appr.id,
        approver_id="system",  # Phase1: fixed approver
        decision="approved",
        decided_at=decided_at,
        note=None,
    )
    session.add(event)

    # 3) update approval aggregate
    appr.approved_count = (appr.approved_count or 0) + 1
    appr.status = "approved"
    appr.resolved_at = decided_at

    # 4) transition execution run -> RUN
    run = await session.get(ExecutionRun, execution_id)
    if run is None:
        raise HTTPException(status_code=404, detail="execution_run_not_found")

    run.status = "RUN"
    run.blocked_reason = None
    if getattr(run, "started_at", None) is None:
        run.started_at = decided_at

    emit_audit_event(
        {
            "event_type": "approval_approved",
            "outcome": "allow",
            "execution_id": execution_id,
            "approval_id": appr.id,
            "decided_at": decided_at.isoformat(),
        }
    )

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="approval_decision_conflict")

    return {"ok": True, "execution_id": execution_id, "approval_status": appr.status, "run_status": run.status}


@router.post("/approvals/{execution_id}/reject")
async def reject(
    execution_id: str,
    session: AsyncSession = Depends(get_session),
):
    res = await session.execute(
        select(Approval).where(Approval.execution_run_id == execution_id)
    )
    appr = res.scalar_one_or_none()
    if appr is None:
        raise HTTPException(status_code=404, detail="approval_not_found")

    # 1.1) expire gate (Phase 1.1) — FAIL-CLOSED
    if _is_expired(appr):
        await _mark_expired(session, execution_id=execution_id, appr=appr)
        raise HTTPException(status_code=409, detail="approval_expired")

    # 1.2) already resolved → idempotent-ish
    if appr.status in ("approved", "rejected", "expired"):
        run = await session.get(ExecutionRun, execution_id)
        run_status = run.status if run else None
        return {
            "ok": True,
            "execution_id": execution_id,
            "approval_status": appr.status,
            "run_status": run_status,
        }

    decided_at = _utcnow()
    event = ApprovalDecisionEvent(
        id=str(uuid.uuid4()),
        approval_id=appr.id,
        approver_id="system",
        decision="rejected",
        decided_at=decided_at,
        note=None,
    )
    session.add(event)

    appr.rejected_count = (appr.rejected_count or 0) + 1
    appr.status = "rejected"
    appr.resolved_at = decided_at

    run = await session.get(ExecutionRun, execution_id)
    if run is None:
        raise HTTPException(status_code=404, detail="execution_run_not_found")

    # Phase1: reject => HALTED + end time
    run.status = "HALTED"
    run.blocked_reason = "approval_rejected"
    if getattr(run, "ended_at", None) is None:
        run.ended_at = decided_at

    emit_audit_event(
        {
            "event_type": "approval_rejected",
            "outcome": "deny",
            "execution_id": execution_id,
            "approval_id": appr.id,
            "decided_at": decided_at.isoformat(),
        }
    )

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="approval_decision_conflict")

    return {"ok": True, "execution_id": execution_id, "approval_status": appr.status, "run_status": run.status}
