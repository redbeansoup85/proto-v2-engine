import os
import pytest
from sqlalchemy import text
from infra.api.deps import get_session

@pytest.mark.asyncio
async def test_lock_db_provenance():
    async for session in get_session():
        res = await session.execute(text("PRAGMA database_list;"))
        rows = res.fetchall()
        main_db = next((r for r in rows if r[1] == "main"), None)

        assert main_db is not None
        abs_path = os.path.abspath(main_db[2])
        print(f"[TEST_DB] {abs_path}")

        res = await session.execute(
            text("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='execution_runs';
            """)
        )
        assert res.scalar() == "execution_runs"
        break
