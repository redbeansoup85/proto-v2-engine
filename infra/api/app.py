import os
import subprocess
import sys
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import select, text

# LOCK2: execution API is disabled by default (fail-closed). Enable explicitly via EXECUTION_API_ENABLE=1.
execution_router = None
if os.environ.get("EXECUTION_API_ENABLE","").strip().lower() in ("1","true","yes","on"):
    from infra.api.endpoints.execution import router as execution_router
from infra.api.endpoints.approvals import router as approvals_router

from infra.api.deps import AsyncSessionLocal
from infra.api.endpoints.models.approval import Approval
from infra.api.endpoints.models.execution_run import ExecutionRun


def _utcnow_naive() -> datetime:
    # SQLite: naive utc 통일
    return datetime.utcnow()


from typing import Optional

def _is_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def resolve_lock4_sig_mode(env: dict[str, str]) -> str:
    requested = env.get("LOCK4_SIG_MODE", "").strip().lower()
    promote = _is_truthy(env.get("LOCK4_PROMOTE_ENFORCE"))

    if requested == "enforce" and promote:
        return "enforce"
    return "warn"


def run_lock4_preflight_or_die(resolved_mode: str, repo_root: Path) -> int:
    preflight = repo_root / "tools" / "lock4_preflight.py"
    cmd = [
        sys.executable,
        str(preflight),
        "--mode",
        resolved_mode,
        "--verifier",
    ]
    result = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = (result.stdout or "") + (result.stderr or "")
    if combined.strip():
        print(combined.rstrip(), file=sys.stderr)
    if resolved_mode == "enforce" and result.returncode != 0:
        return result.returncode
    if resolved_mode == "warn" and result.returncode != 0:
        print("LOCK4_PREFLIGHT_WARNING: preflight failed in warn mode", file=sys.stderr)
    return 0

# -----------------------------
# FAIL-CLOSED DB PRECHECK (LOCK)
# -----------------------------
async def _assert_db_provenance_and_schema() -> None:
    """
    앱이 실제로 바라보는 SQLite 파일과 스키마(필수 테이블)를 startup 시점에 강제 검증.
    - DB 경로/파일이 꼬이면 즉시 터뜨림 (fail-closed)
    - execution_runs 테이블이 없으면 즉시 터뜨림
    """
    async with AsyncSessionLocal() as session:
        # 1) SQLite 파일 경로 확인
        res = await session.execute(text("PRAGMA database_list;"))
        rows = res.fetchall()
        main_db = next((r for r in rows if r[1] == "main"), None)

        if not main_db:
            raise RuntimeError("DB_PROVENANCE_FAIL: main database not found (PRAGMA database_list)")

        db_path = main_db[2]
        abs_path = os.path.abspath(db_path)
        print(f"[DB_PROVENANCE] main.db = {abs_path}")

        # 2) 필수 테이블 존재 확인
        #    (SQLite는 sqlite_master로 테이블 존재를 확인하는 게 가장 확실)
        required_tables = ["execution_runs", "approvals", "approval_decision_events"]
        for t in required_tables:
            r = await session.execute(
                text(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name=:t
                    """
                ),
                {"t": t},
            )
            if r.scalar() is None:
                raise RuntimeError(f"DB_SCHEMA_FAIL: required table '{t}' not found in {abs_path}")


async def _approval_expirer_loop() -> None:
    enabled = os.getenv("APPROVAL_EXPIRER_ENABLED", "0") == "1"
    interval = int(os.getenv("APPROVAL_EXPIRER_INTERVAL_SECONDS", "5"))

    if not enabled:
        print("[approval-expirer] disabled (set APPROVAL_EXPIRER_ENABLED=1)")
        return

    print(f"[approval-expirer] enabled interval={interval}s")

    while True:
        try:
            async with AsyncSessionLocal() as session:
                now = _utcnow_naive()

                res = await session.execute(
                    select(Approval).where(
                        Approval.status == "pending",
                        Approval.expires_at.is_not(None),
                        Approval.expires_at <= now,
                    )
                )
                approvals = res.scalars().all()

                if approvals:
                    for appr in approvals:
                        appr.status = "expired"
                        appr.resolved_at = now

                        run = await session.get(ExecutionRun, appr.execution_run_id)
                        if run is not None and run.status == "BLOCKED":
                            run.blocked_reason = "approval_expired"

                    await session.commit()
                    print(f"[approval-expirer] expired={len(approvals)}")

        except Exception as e:
            # expirer 오류로 서버 죽지 않게
            print("[approval-expirer] ERROR:", repr(e))

        await asyncio.sleep(interval)



@asynccontextmanager
async def lifespan(app):
    await _startup()
    try:
        yield
    finally:
        pass
app = FastAPI(title="Proto V2 Engine API", lifespan=lifespan)


if execution_router is not None:
    app.include_router(execution_router, prefix="/api/v1/execution")
app.include_router(approvals_router)


async def _startup():
    resolved_mode = resolve_lock4_sig_mode(dict(os.environ))
    print(f"LOCK4_SIG_MODE_RESOLVED={resolved_mode}", file=sys.stderr)
    preflight_code = run_lock4_preflight_or_die(resolved_mode, Path(__file__).resolve().parents[2])
    if preflight_code != 0:
        raise RuntimeError("LOCK4_PREFLIGHT_FAIL_FAST")

    # 1) FAIL-CLOSED: DB가 올바른 파일/스키마인지 먼저 검증 (여기서 걸리면 서버 기동 실패)
    await _assert_db_provenance_and_schema()

    # 2) 그 다음에 background task 시작 (스키마 검증 이후에만)
    asyncio.create_task(_approval_expirer_loop())
