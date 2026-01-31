from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from infra.api.endpoints.models.execution_run import ExecutionRun
from datetime import datetime, timezone

async def execute_job(execution_id: UUID, session: AsyncSession):
    er = await session.get(ExecutionRun, execution_id)
    if not er or er.status != "RUN":
        return
    er.ended_at = datetime.now(timezone.utc)
    er.status = "HALTED"
    await session.commit()
