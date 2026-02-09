from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import json
import subprocess
import re


@dataclass(frozen=True)
class Finding:
    rule_id: str
    file: str
    line: int
    pattern: str
    snippet: str


DENY_PATTERNS = [
    ("EXEC_TRADE", re.compile(r"\b(place_order|submit_order|send_order|execute_trade|broker\.|exchange\.)\b")),
]

EXCLUDE_DIRS = {
    ".venv", "venv", "__pycache__", "site-packages",
    ".git", ".mypy_cache", ".pytest_cache",
    "proto_v2_engine.egg-info",
}

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



def _walk_tree_targets(root: Path) -> list[Path]:
    """
    Full-tree scan target iterator (used for non-PR contexts and for tests tmp_path).
    Must exclude virtualenv/vendor/cache dirs to avoid false positives + noise.
    """
    exclude_dirs = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "dist",
        "build",
    }

    targets: list[Path] = []
    for p in root.rglob("*"):
        # skip directories + excluded trees
        if p.is_dir():
            continue
        parts = set(p.parts)
        if parts & exclude_dirs:
            continue
        # only scan text-ish files we care about
        if p.suffix.lower() in {".py", ".yml", ".yaml", ".json", ".md", ".txt"}:
            targets.append(p)

    # deterministic order
    return sorted(targets)

def _iter_targets(root: Path) -> list[Path]:
    workspace = os.getenv("GITHUB_WORKSPACE")
    is_actions_workspace = False

    if workspace:
        try:
            is_actions_workspace = root.resolve() == Path(workspace).resolve()
        except Exception:
            is_actions_workspace = False

    # PR 최적화는 실제 GitHub Actions 워크스페이스에서만 허용
    if os.getenv("GITHUB_EVENT_NAME") == "pull_request" and is_actions_workspace:
        changed = _git_changed_files_from_pr_event()
        if not changed:
            # FAIL-CLOSED 유지
            raise RuntimeError(
                "FAIL-CLOSED: could not determine PR changed files for static scan"
            )
        return [root / p for p in changed if (root / p).exists()]

    # 그 외(테스트 tmp_path 포함): 전체 트리 스캔
    return _walk_tree_targets(root)

def scan_tree(root: Path) -> list[Finding]:
    targets = _iter_targets(root)

    # PR에서 스캔 대상 없으면 OK (파이썬 코드 변경 없음)
    if not targets:
        return []

    findings: list[Finding] = []
    for p in targets:
        txt = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(txt, start=1):
            for rule_id, rx in DENY_PATTERNS:
                if rx.search(line):
                    findings.append(Finding(rule_id, str(p), i, rx.pattern, line.strip()[:200]))
    return findings
