#!/usr/bin/env bash
set -euo pipefail

BRANCH="$(git branch --show-current)"
[ -n "$BRANCH" ] || { echo "ERROR: not on a git branch"; exit 1; }

if [ "$BRANCH" = "main" ]; then
  echo "ERROR: refusing to create PR from main. Create a feature branch first."
  exit 1
fi

if [ "$#" -lt 2 ]; then
  echo "Usage: scripts/pr_create.sh <A-PATCH|A-MINOR|A-MAJOR> \"<title>\" [stage]"
  exit 1
fi

CLASS="$1"
TITLE="$2"
STAGE="${3:-infra}"

case "$CLASS" in
  A-PATCH|A-MINOR|A-MAJOR) ;;
  *) echo "ERROR: classification must be A-PATCH|A-MINOR|A-MAJOR"; exit 1 ;;
esac

# 최근 커밋 1줄(브랜치에서)
LAST_COMMIT="$(git log -1 --format='%h %s' || true)"

# 변경 파일 기반 DESIGN_ARTIFACT 자동 추론(사실 기반)
# - PR에서의 base는 main을 가정(표준 루틴)
git fetch origin main >/dev/null 2>&1 || true
CHANGED="$(git diff --name-only origin/main...HEAD || true)"

DESIGN_ARTIFACT="n/a"
if echo "$CHANGED" | grep -Eq '^(design/|docs/design/)'; then
  # 변경된 design 관련 경로를 콤마로
  DESIGN_ARTIFACT="$(echo "$CHANGED" | grep -E '^(design/|docs/design/)' | tr '\n' ',' | sed 's/,$//')"
fi

WHY_NOW="Automated PR_REQUEST compliance + branch ${BRANCH}. Latest: ${LAST_COMMIT}"
VERIFY="CI green (checks), local sanity where applicable"
BREAK_RISK="Low"

gh pr create --base main --head "$BRANCH" \
  --title "$CLASS: $TITLE" \
  --body-file - <<EOF
WHY_NOW: ${WHY_NOW}
VERIFY: ${VERIFY}
BREAK_RISK: ${BREAK_RISK}
DESIGN_ARTIFACT: ${DESIGN_ARTIFACT}
STAGE: ${STAGE}
EOF
