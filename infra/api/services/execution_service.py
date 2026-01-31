from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from infra.api.endpoints.models.execution_run import ExecutionRun

class ExecutionBlocked(Exception):
    def __init__(self, reason: str):
        self.reason = reason

async def create_execution_run(session: AsyncSession, *, project_id: str, decision_card_id, execution_scope: str, idempotency_key: str) -> ExecutionRun:
    er = ExecutionRun(
        project_id=project_id,
        decision_card_id=decision_card_id,
        execution_scope=execution_scope,
        idempotency_key=idempotency_key,
    )
    session.add(er)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        row = await session.execute(
            select(ExecutionRun).where(ExecutionRun.idempotency_key == idempotency_key)
        )
        er = row.scalar_one()
    await session.refresh(er)
    if er.status != "RUN":
        raise ExecutionBlocked(er.blocked_reason or "unknown")
    return er
