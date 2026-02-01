# conftest.py
import os
import pytest

@pytest.fixture(scope="session", autouse=True)
def _require_test_database():
    url = os.getenv("DATABASE_URL", "")
    if not url or "test.db" not in url:
        raise RuntimeError(
            f"[LOCK] pytest requires test database. DATABASE_URL={url!r}"
        )
