#!/usr/bin/env bash
set -euo pipefail

BRANCH="$(git branch --show-current)"
if [ -z "$BRANCH" ]; then
  echo "ERROR: not on a git branch"
  exit 1
fi

if [ "$#" -lt 2 ]; then
  echo "Usage: scripts/pr_create.sh <A-PATCH|A-MINOR|A-MAJOR> \"<title>\""
  exit 1
fi

CLASS="$1"
TITLE="$2"

case "$CLASS" in
  A-PATCH|A-MINOR|A-MAJOR) ;;
  *) echo "ERROR: classification must be A-PATCH|A-MINOR|A-MAJOR"; exit 1 ;;
esac

gh pr create --base main --head "$BRANCH" \
  --title "$CLASS: $TITLE" \
  --body-file - <<'EOF'
WHY_NOW: <why now>
VERIFY: <how you verified>
BREAK_RISK: Low
DESIGN_ARTIFACT: n/a
STAGE: infra
EOF
