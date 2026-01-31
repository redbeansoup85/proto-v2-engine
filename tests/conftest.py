import os
import pytest
import asyncio
from alembic import command
from alembic.config import Config

@pytest.fixture(scope="session", autouse=True)
def _migrate_and_lock():
    os.environ.setdefault(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./infra/api/test.db",
    )

    cfg = Config("infra/api/alembic.ini")
    command.upgrade(cfg, "head")

    # 여기서 앱 startup guard 실행 (fail-closed)
