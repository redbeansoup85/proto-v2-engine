from __future__ import annotations

import subprocess  # tests monkeypatch infra.api.app.subprocess.run
from fastapi import FastAPI

from infra.api.endpoints.approvals import router as approvals_router
from infra.api.endpoints.execution import router as execution_router  # LOCK2_ALLOW_EXEC
from infra.api.endpoints.ui_status import router as ui_status_router
from infra.api.lock4_runtime import preflight_lock4_runtime

# ✅ ADD: executor endpoint router (POST /execute_market)
from infra.api.routes.executor import router as executor_router
from infra.api.routes.risk import router as risk_router


def resolve_lock4_sig_mode(env: dict) -> str:
    """Resolve LOCK4 signature mode from provided env mapping ONLY.

    Must not implicitly read os.environ because CI workflows set LOCK4_SIG_MODE
    for the process and tests pass {} to validate deterministic defaults.
    """
    e = env or {}
    raw = (e.get("LOCK4_SIG_MODE", "") or "").strip().lower()

    if raw == "enforce":
        promote = (e.get("LOCK4_PROMOTE_ENFORCE", "") or "")
        if str(promote).strip().lower() in ("1", "true", "yes", "on"):
            return "enforce"
        return "warn"

    return "warn"


def create_app() -> FastAPI:
    app = FastAPI()

    # API v1
    app.include_router(execution_router, prefix="/api/v1")
    app.include_router(approvals_router, prefix="/api/v1")

    # ✅ ADD: executor endpoint (no prefix → POST /execute_market)
    app.include_router(executor_router)
    app.include_router(risk_router)

    # UI readonly endpoints (no prefix)
    app.include_router(ui_status_router)

    return app


def run_lock4_preflight_or_die(mode: str, workspace_dir) -> int:
    """Run LOCK4 preflight via subprocess.

    Test contract:
      - mode == "enforce": return subprocess returncode (non-zero allowed)
      - mode == "warn": always return 0 (never block startup)
    """
    wd = str(workspace_dir)

    proc = subprocess.run(
        ["python", "-m", "tools.gates.lock4_preflight", "--workspace", wd],
        capture_output=True,
        text=True,
    )
    rc = int(getattr(proc, "returncode", 1) or 0)

    if mode == "warn":
        return 0
    return rc


app = create_app()
# --- Ops endpoints (enterprise baseline) ---
@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/version")
def version():
    """
    Enterprise baseline: stable version endpoint.
    Priority: BUILD_SHA env -> git HEAD -> n/a
    """
    import os
    import subprocess

    build_sha = os.getenv("BUILD_SHA") or "n/a"

    if build_sha == "n/a":
        try:
            build_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        except Exception:
            build_sha = "n/a"

    return {
        "service": "proto-v2-engine",
        "api": "fastapi",
        "build_sha": build_sha,
    }

@app.get("/metrics")
def metrics():
    """
    Minimal Prometheus-style metrics (no external deps).
    """
    import time
    # You can expand later: request counts, last intent id, etc.
    now = int(time.time())
    lines = []
    lines.append("# HELP metaos_up Service health (1=up)")
    lines.append("# TYPE metaos_up gauge")
    lines.append("metaos_up 1")
    lines.append("# HELP metaos_build_info Build SHA info")
    lines.append("# TYPE metaos_build_info gauge")
    try:
        import os
        build_sha = os.getenv("BUILD_SHA", "n/a").replace('"', "")
    except Exception:
        build_sha = "n/a"
    lines.append(f'metaos_build_info{{build_sha="{build_sha}"}} 1')
    lines.append("# HELP metaos_time_seconds Current server time")
    lines.append("# TYPE metaos_time_seconds gauge")
    lines.append(f"metaos_time_seconds {now}")
    return "\n".join(lines) + "\n"
