#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-tasks}"

if [ ! -d "$ROOT" ]; then
  echo "error: missing dir: $ROOT" >&2
  exit 1
fi

# Find TASK_LOOP.yaml under tasks/*/TASK_LOOP.yaml (exclude tasks/_template)
# bash3-safe: use find + while read, no mapfile.
total=0
closed=0

# shellcheck disable=SC2039
while IFS= read -r f; do
  total=$((total + 1))

  # Closed definition: RESULT: DONE (exact match at line start)
  if grep -qE '^RESULT:[[:space:]]*DONE([[:space:]]*(#.*)?)?$' "$f"; then
    closed=$((closed + 1))
  fi
done <<EOFIND
$(find "$ROOT" -mindepth 2 -maxdepth 2 -name TASK_LOOP.yaml ! -path "$ROOT/_template/*" 2>/dev/null || true)
EOFIND

open=$((total - closed))

# Avoid division by zero
if [ "$total" -eq 0 ]; then
  echo "tasks_total: 0"
  echo "closed_loops: 0"
  echo "open_loops: 0"
  echo "closed_loop_ratio: n/a"
  exit 0
fi

# ratio with 1 decimal using awk (portable)
ratio="$(awk -v c="$closed" -v t="$total" 'BEGIN { printf "%.1f%%", (c/t)*100 }')"

echo "tasks_total: $total"
echo "closed_loops: $closed"
echo "open_loops: $open"
echo "closed_loop_ratio: $ratio"
