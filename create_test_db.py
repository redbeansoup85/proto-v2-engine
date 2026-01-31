# create_test_db.py
import asyncio
from infra.api.endpoints.models.execution_run import Base
from infra.api.deps import engine

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Test DB and ExecutionRun table created")

if __name__ == "__main__":
    asyncio.run(main())
