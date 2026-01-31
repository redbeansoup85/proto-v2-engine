import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def assert_db_provenance(session: AsyncSession):
    # SQLite 파일 절대경로 확인
    res = await session.execute(text("PRAGMA database_list;"))
    rows = res.fetchall()

    main_db = next((r for r in rows if r[1] == "main"), None)
    if not main_db:
        raise RuntimeError("DB_PROVENANCE_FAIL: main database not found")

    db_path = main_db[2]
    abs_path = os.path.abspath(db_path)

    print(f"[DB_PROVENANCE] main.db = {abs_path}")

    # execution_runs 존재 확인
    res = await session.execute(
        text("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='execution_runs';
        """)
    )
    if res.scalar() is None:
        raise RuntimeError(
            f"DB_SCHEMA_FAIL: execution_runs not found in {abs_path}"
        )
