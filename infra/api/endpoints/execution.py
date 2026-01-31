from datetime import datetime, timedelta
import hashlib
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from infra.api.audit_sink import emit_audit_event
from infra.api.deps import get_session
from infra.api.endpoints.models.execution_run import ExecutionRun
from infra.api.endpoints.models.approval import Approval
from infra.api.endpoints.schemas.execution import (
    ExecutionRunRequest,
    ExecutionRunResponse,
    ExecutionRunDetailResponse,
)

router = APIRouter()

def _utcnow() -> datetime:
    # keep naive utc for SQLite consistency
    return datetime.utcnow()

def _calc_expires_at(timeout_seconds: int) -> datetime:
    return _utcnow() + timedelta(seconds=int(timeout_seconds))


# Phase 1: default approval timeout (seconds)
DEFAULT_APPROVAL_TIMEOUT_SECONDS = 3600


def _fingerprint(req: ExecutionRunRequest) -> str:
    payload = {
        "project_id": req.project_id,
        "decision_card_id": str(req.decision_card_id),
        "execution_scope": req.execution_scope,
    }
    s = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _audit_base(req: ExecutionRunRequest, *, fp: str) -> dict:
    return {
        "project_id": req.project_id,
        "idempotency_key": req.idempotency_key,
        "decision_card_id": str(req.decision_card_id),
        "execution_scope": req.execution_scope,
        "request_fingerprint": fp,
    }


async def _ensure_approval(session: AsyncSession, *, execution_run_id: str, timeout_seconds: int = 3600) -> None:
    # ensure exactly ONE approval row per execution_run_id (UNIQUE)
    res = await session.execute(
        select(Approval).where(Approval.execution_run_id == execution_run_id)
    )
    a = res.scalar_one_or_none()

    if a is None:
        session.add(
            Approval(
                id=str(uuid.uuid4()),
                execution_run_id=execution_run_id,
                requester_type="system",
                requester_id="execution_api",
                mode="single",
                required_approvers=1,
                timeout_seconds=timeout_seconds,
                expires_at=_calc_expires_at(timeout_seconds),
                status="pending",
            )
        )
        # do NOT commit here; caller owns transaction boundary
        await session.flush()
        return

    # backfill expires_at for legacy rows (NULL)
    if getattr(a, "expires_at", None) is None and a.status == "pending":
        ts = int(getattr(a, "timeout_seconds", timeout_seconds) or timeout_seconds)
        a.expires_at = _calc_expires_at(ts)
        await session.flush()

async def run_execution(
    req: ExecutionRunRequest,
    session: AsyncSession = Depends(get_session),
):
    fp = _fingerprint(req)

    # 1) pre-check (idempotency)
    res = await session.execute(
        select(ExecutionRun).where(
            ExecutionRun.project_id == req.project_id,
            ExecutionRun.idempotency_key == req.idempotency_key,
        )
    )
    er = res.scalar_one_or_none()

    if er is not None:
        # conflict check
        if (
            (str(er.decision_card_id) != str(req.decision_card_id))
            or (er.execution_scope != req.execution_scope)
            or (er.request_fingerprint != fp)
        ):
            emit_audit_event(
                {
                    "event_type": "execution_run_idempotency_conflict",
                    "outcome": "deny",
                    **_audit_base(req, fp=fp),
                    "existing_execution_id": er.execution_id,
                    "existing_request_fingerprint": er.request_fingerprint,
                }
            )
            raise HTTPException(status_code=409, detail="idempotency_key_conflict")

        # ensure approval exists even on dedup-hit (fail-closed)
        await _ensure_approval(session, execution_run_id=er.execution_id)
        await session.commit()

        emit_audit_event(
            {
                "event_type": "execution_run_dedup_hit",
                "outcome": "allow",
                **_audit_base(req, fp=fp),
                "execution_id": er.execution_id,
                "status": er.status,
                "dedup_hit": True,
            }
        )

        return ExecutionRunResponse(
            execution_id=er.execution_id,
            status=er.status,
            blocked_reason=er.blocked_reason,
            dedup_hit=True,
            request_fingerprint=er.request_fingerprint,
        )

    # 2) create new run (Phase 1: starts BLOCKED)
    new_run = ExecutionRun(
        project_id=req.project_id,
        decision_card_id=str(req.decision_card_id),
        execution_scope=req.execution_scope,
        status="BLOCKED",
        blocked_reason="approval_pending",
        idempotency_key=req.idempotency_key,
        request_fingerprint=fp,
    )
    session.add(new_run)

    try:
        # flush to get PK populated (new_run.execution_id)
        await session.flush()

        # create exactly ONE approval row (id is required; execution_run_id is UNIQUE)
        await _ensure_approval(session, execution_run_id=new_run.execution_id)

        await session.commit()
    except IntegrityError:
        await session.rollback()

        # race recovery: read again by (project_id, idempotency_key)
        res2 = await session.execute(
            select(ExecutionRun).where(
                ExecutionRun.project_id == req.project_id,
                ExecutionRun.idempotency_key == req.idempotency_key,
            )
        )
        er2 = res2.scalar_one_or_none()
        if er2 is None:
            emit_audit_event(
                {
                    "event_type": "execution_run_idempotency_race_inconsistent_state",
                    "outcome": "deny",
                    **_audit_base(req, fp=fp),
                }
            )
            raise HTTPException(status_code=500, detail="idempotency_race_inconsistent_state")

        if (
            (str(er2.decision_card_id) != str(req.decision_card_id))
            or (er2.execution_scope != req.execution_scope)
            or (er2.request_fingerprint != fp)
        ):
            emit_audit_event(
                {
                    "event_type": "execution_run_idempotency_conflict",
                    "outcome": "deny",
                    **_audit_base(req, fp=fp),
                    "existing_execution_id": er2.execution_id,
                    "existing_request_fingerprint": er2.request_fingerprint,
                }
            )
            raise HTTPException(status_code=409, detail="idempotency_key_conflict")

        # ensure approval exists for recovered run as well
        await _ensure_approval(session, execution_run_id=er2.execution_id)
        await session.commit()

        await _ensure_approval(session, execution_run_id=er2.execution_id)
        await session.commit()

        emit_audit_event(
            {
                "event_type": "execution_run_dedup_hit",
                "outcome": "allow",
                **_audit_base(req, fp=fp),
                "execution_id": er2.execution_id,
                "status": er2.status,
                "dedup_hit": True,
                "race_recovered": True,
            }
        )

        return ExecutionRunResponse(
            execution_id=er2.execution_id,
            status=er2.status,
            blocked_reason=er2.blocked_reason,
            dedup_hit=True,
            request_fingerprint=er2.request_fingerprint,
        )

    await session.refresh(new_run)

    emit_audit_event(
        {
            "event_type": "execution_run_created",
            "outcome": "allow",
            **_audit_base(req, fp=fp),
            "execution_id": new_run.execution_id,
            "status": new_run.status,
            "dedup_hit": False,
        }
    )

    return ExecutionRunResponse(
        execution_id=new_run.execution_id,
        status=new_run.status,
        blocked_reason=new_run.blocked_reason,
        dedup_hit=False,
        request_fingerprint=new_run.request_fingerprint,
    )



@router.post("/run", response_model=ExecutionRunResponse)
async def run_execution(
    req: ExecutionRunRequest,
    session: AsyncSession = Depends(get_session),
):
    fp = _fingerprint(req)

    # 1) pre-check (idempotency)
    res = await session.execute(
        select(ExecutionRun).where(
            ExecutionRun.project_id == req.project_id,
            ExecutionRun.idempotency_key == req.idempotency_key,
        )
    )
    er = res.scalar_one_or_none()

    if er is not None:
        if (
            (str(er.decision_card_id) != str(req.decision_card_id))
            or (er.execution_scope != req.execution_scope)
            or (er.request_fingerprint != fp)
        ):
            emit_audit_event(
                {
                    "event_type": "execution_run_idempotency_conflict",
                    "outcome": "deny",
                    **_audit_base(req, fp=fp),
                    "existing_execution_id": er.execution_id,
                    "existing_request_fingerprint": er.request_fingerprint,
                }
            )
            raise HTTPException(status_code=409, detail="idempotency_key_conflict")

        await _ensure_approval(session, execution_run_id=er.execution_id)
        await session.commit()

        emit_audit_event(
            {
                "event_type": "execution_run_dedup_hit",
                "outcome": "allow",
                **_audit_base(req, fp=fp),
                "execution_id": er.execution_id,
                "status": er.status,
                "dedup_hit": True,
            }
        )

        return ExecutionRunResponse(
            execution_id=er.execution_id,
            status=er.status,
            blocked_reason=er.blocked_reason,
            dedup_hit=True,
            request_fingerprint=er.request_fingerprint,
        )

    # 2) create new run (Phase 1: starts BLOCKED)
    new_run = ExecutionRun(
        project_id=req.project_id,
        decision_card_id=str(req.decision_card_id),
        execution_scope=req.execution_scope,
        status="BLOCKED",
        blocked_reason="approval_pending",
        idempotency_key=req.idempotency_key,
        request_fingerprint=fp,
    )
    session.add(new_run)

    try:
        await session.flush()
        await _ensure_approval(session, execution_run_id=new_run.execution_id)
        await session.commit()
    except IntegrityError:
        await session.rollback()

        res2 = await session.execute(
            select(ExecutionRun).where(
                ExecutionRun.project_id == req.project_id,
                ExecutionRun.idempotency_key == req.idempotency_key,
            )
        )
        er2 = res2.scalar_one_or_none()
        if er2 is None:
            emit_audit_event(
                {
                    "event_type": "execution_run_idempotency_race_inconsistent_state",
                    "outcome": "deny",
                    **_audit_base(req, fp=fp),
                }
            )
            raise HTTPException(status_code=500, detail="idempotency_race_inconsistent_state")

        if (
            (str(er2.decision_card_id) != str(req.decision_card_id))
            or (er2.execution_scope != req.execution_scope)
            or (er2.request_fingerprint != fp)
        ):
            emit_audit_event(
                {
                    "event_type": "execution_run_idempotency_conflict",
                    "outcome": "deny",
                    **_audit_base(req, fp=fp),
                    "existing_execution_id": er2.execution_id,
                    "existing_request_fingerprint": er2.request_fingerprint,
                }
            )
            raise HTTPException(status_code=409, detail="idempotency_key_conflict")

        await _ensure_approval(session, execution_run_id=er2.execution_id)
        await session.commit()

        emit_audit_event(
            {
                "event_type": "execution_run_dedup_hit",
                "outcome": "allow",
                **_audit_base(req, fp=fp),
                "execution_id": er2.execution_id,
                "status": er2.status,
                "dedup_hit": True,
                "race_recovered": True,
            }
        )

        return ExecutionRunResponse(
            execution_id=er2.execution_id,
            status=er2.status,
            blocked_reason=er2.blocked_reason,
            dedup_hit=True,
            request_fingerprint=er2.request_fingerprint,
        )

    await session.refresh(new_run)

    emit_audit_event(
        {
            "event_type": "execution_run_created",
            "outcome": "allow",
            **_audit_base(req, fp=fp),
            "execution_id": new_run.execution_id,
            "status": new_run.status,
            "dedup_hit": False,
        }
    )

    return ExecutionRunResponse(
        execution_id=new_run.execution_id,
        status=new_run.status,
        blocked_reason=new_run.blocked_reason,
        dedup_hit=False,
        request_fingerprint=new_run.request_fingerprint,
    )


@router.get("/run/by_key", response_model=ExecutionRunDetailResponse)
async def get_execution_run_by_key(
    project_id: str = Query(...),
    idempotency_key: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    res = await session.execute(
        select(ExecutionRun).where(
            ExecutionRun.project_id == project_id,
            ExecutionRun.idempotency_key == idempotency_key,
        )
    )
    er = res.scalar_one_or_none()
    if er is None:
        raise HTTPException(status_code=404, detail="execution_run_not_found")

    return ExecutionRunDetailResponse(
        execution_id=er.execution_id,
        project_id=er.project_id,
        decision_card_id=str(er.decision_card_id),
        execution_scope=er.execution_scope,
        status=er.status,
        blocked_reason=er.blocked_reason,
        idempotency_key=er.idempotency_key,
        request_fingerprint=er.request_fingerprint,
        created_at=str(er.created_at),
        started_at=str(er.started_at) if er.started_at else None,
        ended_at=str(er.ended_at) if er.ended_at else None,
    )


@router.get("/run/{execution_id}", response_model=ExecutionRunDetailResponse)
async def get_execution_run(
    execution_id: str,
    session: AsyncSession = Depends(get_session),
):
    # execution_id maps to PK column (id)
    er = await session.get(ExecutionRun, execution_id)
    if er is None:
        raise HTTPException(status_code=404, detail="execution_run_not_found")

    return ExecutionRunDetailResponse(
        execution_id=er.execution_id,
        project_id=er.project_id,
        decision_card_id=str(er.decision_card_id),
        execution_scope=er.execution_scope,
        status=er.status,
        blocked_reason=er.blocked_reason,
        idempotency_key=er.idempotency_key,
        request_fingerprint=er.request_fingerprint,
        created_at=str(er.created_at),
        started_at=str(er.started_at) if er.started_at else None,
        ended_at=str(er.ended_at) if er.ended_at else None,
    )
