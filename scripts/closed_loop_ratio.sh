#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-tasks}"

FILES=$(find "$ROOT" -mindepth 2 -maxdepth 2 -name TASK_LOOP.yaml ! -path "$ROOT/_template/*" -print 2>/dev/null || true)

total=0
open=0
closed=0
blocked=0
skipped=0

closed_with_ts=0
sum_hours="0.0"

to_epoch_utc() {
  local iso="$1"
  if date -u -d "$iso" +%s >/dev/null 2>&1; then
    date -u -d "$iso" +%s
    return 0
  fi
  if date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$iso" +%s >/dev/null 2>&1; then
    date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$iso" +%s
    return 0
  fi
  return 1
}

get_scalar() {
  local key="$1" file="$2"
  grep -E "^${key}:" "$file" | head -n1 | sed -E "s/^${key}:[[:space:]]*//; s/[[:space:]]*$//"
}

IFS='
'
for f in $FILES; do
  [ -f "$f" ] || continue
  total=$((total+1))

  res="$(get_scalar RESULT "$f")"
  case "$res" in
    OPEN) open=$((open+1)) ;;
    CLOSED) closed=$((closed+1)) ;;
    BLOCKED) blocked=$((blocked+1)) ;;
    SKIPPED) skipped=$((skipped+1)) ;;
    *) open=$((open+1)) ;;
  esac

  if [ "$res" = "CLOSED" ]; then
    start_iso="$(get_scalar CREATED_AT_UTC "$f")"
    vfile="$(dirname "$f")/VERDICT.yaml"
    if [ -f "$vfile" ]; then
      end_iso="$(get_scalar verified_at_utc "$vfile")"

      if [ -n "$start_iso" ] && [ -n "$end_iso" ]; then
        start_epoch="$(to_epoch_utc "$start_iso" 2>/dev/null || true)"
        end_epoch="$(to_epoch_utc "$end_iso" 2>/dev/null || true)"
        if [ -n "${start_epoch:-}" ] && [ -n "${end_epoch:-}" ]; then
          if [ "$end_epoch" -ge "$start_epoch" ]; then
            closed_with_ts=$((closed_with_ts+1))
            sum_hours="$(awk -v s="$sum_hours" -v e="$end_epoch" -v st="$start_epoch" 'BEGIN { printf("%.6f", s + ((e-st)/3600.0)) }')"
          fi
        fi
      fi
    fi
  fi
done
unset IFS

ratio="0.0000"
if [ "$total" -gt 0 ]; then
  ratio="$(awk -v c="$closed" -v t="$total" 'BEGIN { printf("%.4f", c/t) }')"
fi

avg_hours="0.00"
if [ "$closed_with_ts" -gt 0 ]; then
  avg_hours="$(awk -v s="$sum_hours" -v n="$closed_with_ts" 'BEGIN { printf("%.2f", s/n) }')"
fi

echo "ROOT=$ROOT"
echo "TOTAL=$total"
echo "OPEN=$open"
echo "CLOSED=$closed"
echo "BLOCKED=$blocked"
echo "SKIPPED=$skipped"
echo "CLOSED_LOOP_RATIO=$ratio"
echo "CLOSED_WITH_VERDICT_TS=$closed_with_ts"
echo "AVG_TIME_TO_CLOSE_HOURS=$avg_hours"
