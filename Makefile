.PHONY: test test-expiry db-reset

db-reset:
	rm -f infra/api/test.db infra/api/test.db-wal infra/api/test.db-shm

test: db-reset
	DATABASE_URL="sqlite+aiosqlite:///infra/api/test.db" python -m pytest -q

test-expiry: db-reset
	DATABASE_URL="sqlite+aiosqlite:///infra/api/test.db" python -m pytest tests/test_approval_expiry.py::test_dedup_hit_backfills_expires_at_and_commits -q
