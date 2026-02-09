from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import argparse
import os
import json
import subprocess


@dataclass(frozen=True)
class Finding:
    rule_id: str
    file: str
    line: int
    pattern: str
    snippet: str


# "execution" 관련 참조가 승인 경로 밖에서 나타나면 fail-closed
ALLOW_MARKERS = ["LOCK2_ALLOW_EXEC"]

DENY_PATTERNS = [
    ("EXEC_IMPORT", re.compile(r"\b(from\s+.*execution\s+import|import\s+.*execution)\b")),
    ("EXEC_ENDPOINT", re.compile(r"\b(/execution\b|endpoints\.execution|execution\.py)\b")),
    ("EXEC_CALL", re.compile(r"\b(execute_trade|place_order|submit_order|send_order)\b")),
]

ALLOW_PATH_HINTS = [
    "approval", "human_approval", "handlers/approval", "approval_gate",
]

EXCLUDE_DIRS = {
    ".venv", "venv", "__pycache__", "site-packages",
    ".git", ".mypy_cache", ".pytest_cache",
    "proto_v2_engine.egg-info",
}

# gate/test/workflow는 스캔 제외 (자기 패턴/테스트 문자열 때문에 무조건 걸리는 것 방지)
IGNORE_PREFIXES = (
    "tools/gates/",
    "tests/",
    ".github/workflows/",
)


def _excluded(p: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in p.parts)


def _ignored_relpath(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return rel.startswith(IGNORE_PREFIXES)


def _git_changed_files_from_pr_event() -> list[str]:
    event_path = os.getenv("GITHUB_EVENT_PATH", "")
    if not event_path:
        return []
    try:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        pr = payload.get("pull_request") or {}
        base = (pr.get("base") or {}).get("sha")
        head = (pr.get("head") or {}).get("sha")
        if not base or not head:
            return []
        out = subprocess.check_output(["git", "diff", "--name-only", base, head], text=True)
        return [x.strip() for x in out.splitlines() if x.strip()]
    except Exception:
        return []


def _git_changed_files_fallback() -> list[str]:
    """
    Best-effort fallback for CI environments where PR event payload
    is unavailable or missing base/head fields.
    """
    try:
        out = subprocess.check_output(["git", "diff", "--name-only", "origin/main...HEAD"], text=True)
        return [x.strip() for x in out.splitlines() if x.strip()]
    except Exception:
        return []


def _git_changed_files_from_push_event() -> list[str]:
    event_path = os.getenv("GITHUB_EVENT_PATH", "")
    if not event_path:
        return []
    try:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        before = payload.get("before")
        after = payload.get("after")
        if not before or not after:
            return []
        out = subprocess.check_output(["git", "diff", "--name-only", before, after], text=True)
        return [x.strip() for x in out.splitlines() if x.strip()]
    except Exception:
        return []


def iter_scan_targets(root: Path) -> list[Path]:
    # GitHub Actions: PR/push 모두 "변경 파일만" 스캔 (새 위반 유입 차단 목적)
    # - pull_request: base..head
    # - push: before..after
    if os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("GITHUB_EVENT_NAME") in {"pull_request", "push"}:
        ev = os.getenv("GITHUB_EVENT_NAME")
        changed = _git_changed_files_from_pr_event() if ev == "pull_request" else _git_changed_files_from_push_event()
        if ev == "pull_request" and not changed:
            changed = _git_changed_files_fallback()

        # FAIL-CLOSED: CI 이벤트인데 변경 파일을 못 읽으면 차단
        if not changed:
            raise RuntimeError("FAIL-CLOSED: could not determine changed files for LOCK-2 scan")

        targets: list[Path] = []
        for rel in changed:
            rel_n = rel.replace("\\", "/")
            if _ignored_relpath(rel_n):
                continue
            p = root / rel_n
            if p.is_file() and p.suffix == ".py" and not _excluded(p):
                targets.append(p)

        # 스캔 대상 py가 0이면 OK (파이썬 코드 변경이 없었음)
        return targets

    # push/local: 전체 스캔 (단, ignore prefixes는 동일 적용)

        changed = _git_changed_files_from_pr_event()

        # FAIL-CLOSED: PR인데 변경 파일 자체를 못 읽으면 차단
        if not changed:
            raise RuntimeError("FAIL-CLOSED: could not determine PR changed files for LOCK-2 scan")

        targets: list[Path] = []
        for rel in changed:
            rel_n = rel.replace("\\", "/")
            if _ignored_relpath(rel_n):
                continue
            p = root / rel_n
            if p.is_file() and p.suffix == ".py" and not _excluded(p):
                targets.append(p)

        # PR에서 스캔 대상 py가 0이면 OK (파이썬 코드 변경이 없었음)
        return targets

    # push/local: 전체 스캔 (단, ignore prefixes는 동일 적용)
    targets: list[Path] = []
    for p in root.rglob("*.py"):
        if _excluded(p):
            continue
        try:
            rel = p.relative_to(root).as_posix()
        except Exception:
            rel = p.as_posix()
        if _ignored_relpath(rel):
            continue
        targets.append(p)
    return targets


def scan_targets(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for p in paths:
        path_l = str(p).lower()
        allow = any(h in path_l for h in ALLOW_PATH_HINTS)

        txt = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(txt, start=1):
            # explicit allow marker on the same line → suppress EXEC_* findings
            if any(m in line for m in ALLOW_MARKERS):
                continue

            for rule_id, rx in DENY_PATTERNS:
                if rx.search(line):
                    if allow:
                        continue
                    findings.append(Finding(rule_id, str(p), i, rx.pattern, line.strip()[:200]))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="root directory to scan")
    args = ap.parse_args()
    root = Path(args.root)

    try:
        targets = iter_scan_targets(root)
    except RuntimeError as e:
        print(str(e))
        return 1

    # PR에서 스캔 대상이 없으면 OK
    if not targets:
        print("OK: LOCK-2 gate clean (no changed .py files to scan)")
        return 0

    findings = scan_targets(targets)
    if findings:
        print("FAIL-CLOSED: LOCK-2 gate findings detected")
        for f in findings[:200]:
            print(f"- {f.rule_id} | {f.file}:{f.line} | {f.snippet}")
        if len(findings) > 200:
            print(f"... ({len(findings)-200} more)")
        return 1

    print("OK: LOCK-2 gate clean")
    return 0


# -------------------------------------------------------------------
# Back-compat export for unit tests
# -------------------------------------------------------------------
def scan_tree(root: Path) -> list[Finding]:
    """
    Backward-compatible API for unit tests.

    NOTE:
    - This scans all *.py under the provided root.
    - It intentionally does NOT apply IGNORE_PREFIXES, because tests commonly
      build a temporary directory tree and expect it to be fully scanned.
    """
    targets: list[Path] = []
    for p in root.rglob("*.py"):
        if _excluded(p):
            continue
        targets.append(p)
    return scan_targets(targets)


if __name__ == "__main__":
    raise SystemExit(main())
