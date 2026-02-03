#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-tasks}"

# exclude _template
FILES=$(find "$ROOT" -mindepth 2 -maxdepth 2 -name TASK_LOOP.yaml ! -path "$ROOT/_template/*" -print 2>/dev/null || true)

total=0
open=0
closed=0
blocked=0
skipped=0

# Iterate safely even with spaces (IFS newline)
IFS='
'
for f in $FILES; do
  [ -f "$f" ] || continue
  total=$((total+1))

  # Extract scalar RESULT value (first match). If missing/invalid, count as open (defensive).
  # Gate already validates enum, so this is a reporting function.
  res="$(grep -E '^RESULT:' "$f" | head -n1 | sed -E 's/^RESULT:[[:space:]]*//; s/[[:space:]]*$//')"
  case "$res" in
    OPEN) open=$((open+1)) ;;
    CLOSED) closed=$((closed+1)) ;;
    BLOCKED) blocked=$((blocked+1)) ;;
    SKIPPED) skipped=$((skipped+1)) ;;
    *) open=$((open+1)) ;;
  esac
done
unset IFS

# Ratio (4 decimals)
ratio="0.0000"
if [ "$total" -gt 0 ]; then
  ratio="$(awk -v c="$closed" -v t="$total" 'BEGIN { printf("%.4f", c/t) }')"
fi

echo "ROOT=$ROOT"
echo "TOTAL=$total"
echo "OPEN=$open"
echo "CLOSED=$closed"
echo "BLOCKED=$blocked"
echo "SKIPPED=$skipped"
echo "CLOSED_LOOP_RATIO=$ratio"
