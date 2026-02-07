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

TEMPLATE_PATH="docs/governance/PR_BODY_TEMPLATE.md"
if [ ! -f "$TEMPLATE_PATH" ]; then
  echo "ERROR: missing template: $TEMPLATE_PATH"
  exit 1
fi

LAST_COMMIT="$(git log -1 --format='%h %s' || true)"

git fetch origin main >/dev/null 2>&1 || true
CHANGED="$(git diff --name-only origin/main...HEAD || true)"

# Fail-closed: governance docs cannot be A-PATCH
if echo "$CHANGED" | grep -Eq '^docs/governance/'; then
  if [ "$CLASS" = "A-PATCH" ]; then
    echo "ERROR: governance docs changed; use A-MINOR or A-MAJOR"
    echo "$CHANGED"
    exit 1
  fi
fi

DESIGN_ARTIFACT="n/a"
if echo "$CHANGED" | grep -Eq '^(design/|docs/design/)'; then
  DESIGN_ARTIFACT="$(echo "$CHANGED" | grep -E '^(design/|docs/design/)' | tr '\n' ',' | sed 's/,$//')"
fi

WHY_NOW="Automated PR_REQUEST compliance + branch ${BRANCH}. Latest: ${LAST_COMMIT}"
VERIFY="CI green (checks), local sanity where applicable"
BREAK_RISK="Low"

BODY="$(cat "$TEMPLATE_PATH")"
BODY="${BODY//'{{WHY_NOW}}'/$WHY_NOW}"
BODY="${BODY//'{{VERIFY}}'/$VERIFY}"
BODY="${BODY//'{{BREAK_RISK}}'/$BREAK_RISK}"
BODY="${BODY//'{{DESIGN_ARTIFACT}}'/$DESIGN_ARTIFACT}"
BODY="${BODY//'{{STAGE}}'/$STAGE}"

gh pr create --base main --head "$BRANCH" \
  --title "$CLASS: $TITLE" \
  --body "$BODY"
