#!/usr/bin/env bash
set -euo pipefail

# 항상 repo root에서 실행 (어느 디렉토리에서 호출해도 동일)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# FAIL-CLOSED: 테스트 DB는 항상 새로
rm -f test.db

# FAIL-CLOSED: pytest가 test.db 강제하도록
export DATABASE_URL="sqlite+aiosqlite:///test.db"

# (옵션) 승인 만료 로직을 CI와 동일하게 강제하고 싶으면 1로 고정
export APPROVAL_EXPIRER_ENABLED=1

# FAIL-CLOSED: 외부/전역 site-packages 테스트를 절대 줍지 않도록
# pytest.ini testpaths만 따라가게 하고, --ignore로 방어선 추가
pytest -q \
  --ignore=.venv \
  --ignore=infra/api/.venv \
  --ignore=infra/api/venv \
  --ignore=venv
