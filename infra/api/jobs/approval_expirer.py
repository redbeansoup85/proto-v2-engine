import os
import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.api.endpoints.models.approval import Approval
from infra.api.endpoints.models.execution_run import ExecutionRun


def _utcnow_naive() -> datetime:
    # SQLite(naive datetime) 일관성 유지
    return datetime.utcnow()


async def expire_pending_approvals_once(
    session: AsyncSession,
    *,
    limit: int = 500,
) -> int:
    """
    만료 조건:
      - approvals.status == 'pending'
      - approvals.expires_at IS NOT NULL
      - now >= expires_at

    전이:
      - approvals.status -> 'expired'
      - approvals.resolved_at -> now
      - execution_runs(해당 run)이 아직 BLOCKED & approval_pending이면
        blocked_reason -> 'approval_expired' (fail-closed)
    """
    now = _utcnow_naive()

    res = await session.execute(
        select(Approval)
        .where(
            Approval.status == "pending",
            Approval.expires_at.is_not(None),
            Approval.expires_at <= now,
        )
        .limit(limit)
    )
    rows = res.scalars().all()
    if not rows:
        return 0

    # approval 만료 + run 상태 fail-closed 고정
    for appr in rows:
        appr.status = "expired"
        appr.resolved_at = now

        run = await session.get(ExecutionRun, appr.execution_run_id)
        if run is not None:
            # 이미 RUN/HALTED 등으로 전이됐으면 건드리지 않음
            if run.status == "BLOCKED" and (run.blocked_reason in (None, "approval_pending")):
                run.blocked_reason = "approval_expired"

    await session.commit()
    return len(rows)


async def expiry_loop(
    session_maker,
    *,
    interval_seconds: int = 5,
) -> None:
    """
    session_maker: async session factory (예: async_sessionmaker)
    """
    while True:
        try:
            async with session_maker() as session:
                await expire_pending_approvals_once(session)
        except Exception:
            # fail-closed 철학: 스캐너가 죽어도 시스템이 RUN으로 풀리면 안 됨.
            # 따라서 예외는 삼키되, 루프는 계속.
            pass

        await asyncio.sleep(interval_seconds)


def is_enabled() -> bool:
    return os.getenv("APPROVAL_EXPIRER_ENABLED", "1") == "1"


def interval() -> int:
    try:
        return int(os.getenv("APPROVAL_EXPIRER_INTERVAL_SECONDS", "5"))
    except Exception:
        return 5
