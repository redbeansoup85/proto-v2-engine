import asyncio

from infra.api.deps import engine
from infra.api.endpoints.models.base import Base

# IMPORTANT: 모델을 import해야 Base.metadata에 테이블이 등록됩니다.
from infra.api.endpoints.models.execution_run import ExecutionRun  # noqa: F401


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created successfully")


if __name__ == "__main__":
    asyncio.run(main())
