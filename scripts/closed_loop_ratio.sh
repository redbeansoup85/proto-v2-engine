#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-tasks}"

if [ ! -d "$ROOT" ]; then
  echo "ERROR: directory not found: $ROOT" >&2
  exit 1
fi

started=0
closed=0

echo "ROOT=$ROOT"

for d in "$ROOT"/*; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  case "$name" in
    _template|.*) continue ;;
  esac

  loop="$d/TASK_LOOP.yaml"
  [ -f "$loop" ] || continue
  started=$((started + 1))

  # RESULT 스칼라가 CLOSED면 closed로 카운트
  if grep -Eq '^RESULT:\s*CLOSED\s*$' "$loop"; then
    closed=$((closed + 1))
  fi
done

echo "STARTED=$started"
echo "CLOSED=$closed"

if [ "$started" -eq 0 ]; then
  echo "CLOSED_LOOP_RATIO=n/a"
  exit 0
fi

ratio=$(awk -v c="$closed" -v s="$started" 'BEGIN { printf "%.3f", c/s }')
echo "CLOSED_LOOP_RATIO=$ratio"
