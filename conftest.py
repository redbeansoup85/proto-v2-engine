import os
import pytest

@pytest.fixture(scope="session", autouse=True)
def _lock_require_test_database_url():
    url = os.getenv("DATABASE_URL", "")
    # FAIL-CLOSED: 테스트는 반드시 test.db를 사용해야 한다.
    if not url or "test.db" not in url:
        raise RuntimeError(
            f"[LOCK] pytest requires DATABASE_URL pointing to test.db. DATABASE_URL={url!r}"
        )
