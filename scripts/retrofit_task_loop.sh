#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-dry-run}"   # dry-run | apply
ROOT="${2:-tasks}"     # default: tasks
TEMPLATE="tasks/_template/TASK_LOOP.yaml"

if [ ! -f "$TEMPLATE" ]; then
  echo "ERROR: template not found: $TEMPLATE" >&2
  exit 1
fi

if [ ! -d "$ROOT" ]; then
  echo "ERROR: directory not found: $ROOT" >&2
  exit 1
fi

echo "MODE=$MODE"
echo "ROOT=$ROOT"
echo "TEMPLATE=$TEMPLATE"
echo

created=0
skipped=0

# POSIX-safe directory iteration (1-depth)
for d in "$ROOT"/*; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"

  # 제외
  case "$name" in
    _template|.*) continue ;;
  esac

  f="$d/TASK_LOOP.yaml"
  readme="$d/README.md"

  if [ -f "$f" ]; then
    echo "SKIP  : $f (exists)"
    skipped=$((skipped + 1))
    continue
  fi

  if [ "$MODE" = "dry-run" ]; then
    echo "WOULD : create $f"
    [ ! -f "$readme" ] && echo "WOULD : create $readme"
    continue
  fi

  if [ "$MODE" = "apply" ]; then
    cp "$TEMPLATE" "$f"
    echo "CREATE: $f"

    if [ ! -f "$readme" ]; then
      cat > "$readme" <<'MD'
이 작업은 TASK_LOOP 기반으로 운영된다.
- TASK_LOOP.yaml 없이는 작업이 성립하지 않는다.
- 성공/실패 판정과 실행 방법을 반드시 명시한다.
MD
      echo "CREATE: $readme"
    fi

    created=$((created + 1))
    continue
  fi

  echo "ERROR: unknown mode '$MODE' (use dry-run|apply)" >&2
  exit 1
done

echo
echo "DONE: created=$created skipped=$skipped"
