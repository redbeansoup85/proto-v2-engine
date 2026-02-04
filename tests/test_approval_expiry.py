from asgi_lifespan import LifespanManager
from typing import Optional, Dict, Any

import pytest
import uuid
from sqlalchemy import text

from infra.api.app import app
from infra.api.deps import AsyncSessionLocal

try:
    # httpx가 있으면 FastAPI ASGI 테스트가 깔끔함
    import httpx
except Exception:  # pragma: no cover
    httpx = None


pytestmark = pytest.mark.anyio


async def _db_exec(sql: str, params: Optional[Dict[str, Any]] = None) -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(text(sql), params or {})
        await s.commit()


async def _db_fetchone(sql: str, params: Optional[Dict[str, Any]] = None):
    async with AsyncSessionLocal() as s:
        res = await s.execute(text(sql), params or {})
        return res.first()


@pytest.mark.skipif(httpx is None, reason="httpx not installed")
async def test_approve_denied_when_expired_marks_db_state():
    async with LifespanManager(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # 1) create run
            r = await client.post(
                "/api/v1/execution/run",
                json={
                    "project_id": "project-123",
                    "decision_card_id": "11111111-1111-1111-1111-111111111111",
                    "execution_scope": "automation",
                    "idempotency_key": f"pytest-expire-001-{uuid.uuid4().hex[:8]}",
                },
            )
            assert r.status_code == 200
            exec_id = r.json()["execution_id"]

            # 2) force expires_at into the past
            await _db_exec(
                "update approvals set expires_at=:ts where execution_run_id=:eid",
                {"ts": "2000-01-01 00:00:00", "eid": exec_id},
            )

            # 3) approve -> 409 approval_expired
            r2 = await client.post(f"/approvals/{exec_id}/approve")
            assert r2.status_code == 409
            assert r2.json()["detail"] == "approval_expired"

            # 4) DB state locked
            row_a = await _db_fetchone(
                "select status, blocked_reason from execution_runs where id=:eid",
                {"eid": exec_id},
            )
            assert row_a is not None
            assert row_a[0] == "BLOCKED"
            assert row_a[1] == "approval_expired"

            row_b = await _db_fetchone(
                "select status from approvals where execution_run_id=:eid",
                {"eid": exec_id},
            )
            assert row_b is not None
            assert row_b[0] == "expired"


@pytest.mark.skipif(httpx is None, reason="httpx not installed")
async def test_dedup_hit_backfills_expires_at_and_commits():
    async with LifespanManager(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            idem = f"pytest-backfill-001-{uuid.uuid4().hex[:8]}"
            # 1) create run
            r = await client.post(
                "/api/v1/execution/run",
                json={
                    "project_id": "project-123",
                    "decision_card_id": "11111111-1111-1111-1111-111111111111",
                    "execution_scope": "automation",
                    "idempotency_key": idem,
                },
            )
            assert r.status_code == 200
            exec_id = r.json()["execution_id"]

            # 2) set timeout_seconds small + expires_at NULL
            await _db_exec(
                "update approvals set timeout_seconds=5, expires_at=NULL where execution_run_id=:eid",
                {"eid": exec_id},
            )

            # 3) re-run same idempotency_key -> dedup-hit, and must COMMIT expires_at
            r2 = await client.post(
                "/api/v1/execution/run",
                json={
                    "project_id": "project-123",
                    "decision_card_id": "11111111-1111-1111-1111-111111111111",
                    "execution_scope": "automation",
                    "idempotency_key": idem,
                },
            )
            assert r2.status_code == 200
            assert r2.json()["dedup_hit"] is True

            # 4) DB now has expires_at not null
            row = await _db_fetchone(
                "select expires_at from approvals where execution_run_id=:eid",
                {"eid": exec_id},
            )
            assert row is not None
            assert row[0] is not None
