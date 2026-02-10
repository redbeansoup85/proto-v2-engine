#!/usr/bin/env python3
"""LOCK-2 Gate (FAIL-CLOSED).

Policy:
- In CI PR/push contexts, scan changed python files only.
- If changed files cannot be determined in CI, fail closed.
- Outside CI, scan full tree under --root (excluding tests/tools gates).
- Execution references are only allowed under infra/approval/**.
"""

import os
import sys
import subprocess
from pathlib import Path
import json
from typing import Iterable, List, Optional


APPROVAL_DIR = Path("infra") / "approval"

# strict-ish patterns (avoid matching random "execution" words)
EXEC_PATTERNS = (
    "from infra.api import execution",
    "from infra.api.endpoints import execution",
    "infra.api.endpoints.execution",
    "execution_service",
    "workers.executor",
)


def _run(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _git_fetch_base_ref(root: Path, base: str) -> None:
    _run(
        [
            "git",
            "fetch",
            "--no-tags",
            "--depth=1",
            "origin",
            f"+refs/heads/{base}:refs/remotes/origin/{base}",
        ],
        cwd=root,
    )


def _git_changed_files_from_pr_event(event_path: Optional[str] = None) -> List[str]:
    """
    Backward-compatible helper for tests.
    Return [] when file list is unavailable so caller can fallback.
    """
    path = event_path or os.getenv("GITHUB_EVENT_PATH")
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        return []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    out: List[str] = []
    for key in ("changed_files_list", "files", "changed_files"):
        v = payload.get(key)
        if isinstance(v, list):
            out.extend([x for x in v if isinstance(x, str)])
    # dedup preserve order
    seen = set()
    unique: List[str] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _git_changed_files_fallback() -> List[str]:
    p = _run(["git", "diff", "--name-only", "origin/main...HEAD"], cwd=Path.cwd())
    if p.returncode != 0:
        return []
    return [l for l in p.stdout.splitlines() if l.strip()]


def _changed_files_pr(root: Path, base: str) -> List[str]:
    _git_fetch_base_ref(root, base)

    p = _run(["git", "diff", f"origin/{base}...HEAD", "--name-only"], cwd=root)
    if p.returncode == 0:
        return [l for l in p.stdout.splitlines() if l.strip()]

    p2 = _run(["git", "diff", f"{base}...HEAD", "--name-only"], cwd=root)
    if p2.returncode == 0:
        return [l for l in p2.stdout.splitlines() if l.strip()]

    raise RuntimeError(
        "FAIL-CLOSED: could not determine changed files for LOCK-2 scan "
        f"(PR base={base}) | "
        f"origin/{base}: {p.stderr.strip()} | "
        f"{base}: {p2.stderr.strip()}"
    )


def _changed_files_push(root: Path) -> List[str]:
    # push/workflow_dispatch: use merge-base with origin/main as conservative base
    base = "main"
    _git_fetch_base_ref(root, base)

    mb = _run(["git", "merge-base", "HEAD", f"origin/{base}"], cwd=root)
    if mb.returncode != 0 or not mb.stdout.strip():
        raise RuntimeError(
            "FAIL-CLOSED: could not determine merge-base for LOCK-2 scan "
            f"(push base=origin/{base}) | {mb.stderr.strip()}"
        )

    base_sha = mb.stdout.strip()
    p = _run(["git", "diff", f"{base_sha}..HEAD", "--name-only"], cwd=root)
    if p.returncode == 0:
        return [l for l in p.stdout.splitlines() if l.strip()]

    raise RuntimeError(
        "FAIL-CLOSED: could not determine changed files for LOCK-2 scan "
        f"(push base_sha={base_sha}) | {p.stderr.strip()}"
    )


def determine_changed_files_fail_closed(root: Path) -> List[str]:
    is_pr = (
        os.getenv("GITHUB_EVENT_NAME") == "pull_request"
        or bool(os.getenv("GITHUB_BASE_REF"))
    )

    if is_pr:
        changed = _git_changed_files_from_pr_event()
        if changed:
            return changed
        fallback = _git_changed_files_fallback()
        if fallback:
            return fallback
        base = os.getenv("GITHUB_BASE_REF") or "main"
        return _changed_files_pr(root, base)

    return _changed_files_push(root)


def iter_scan_targets(root: Path) -> List[Path]:
    targets: List[Path] = []
    in_ci = os.getenv("GITHUB_ACTIONS") == "true"
    if in_ci:
        changed = determine_changed_files_fail_closed(root)
        for rel in changed:
            p = (root / rel).resolve()
            if p.exists() and p.is_file() and p.suffix == ".py":
                relp = p.resolve().relative_to(root.resolve()).as_posix()
                if relp.startswith("tests/"):
                    continue
                if relp.startswith("tools/gates/"):
                    continue
                targets.append(p)
        return targets

    # local/non-CI mode: full tree scan for deterministic developer checks/tests
    for p in root.rglob("*.py"):
        try:
            relp = p.resolve().relative_to(root.resolve()).as_posix()
        except Exception:
            continue
        if relp.startswith("tests/"):
            continue
        if relp.startswith("tools/gates/"):
            continue
        targets.append(p)
    return targets


def _is_allowed_approval_path(root: Path, file_path: Path) -> bool:
    try:
        rel = file_path.resolve().relative_to(root.resolve())
    except Exception:
        return False
    rel_s = rel.as_posix().lower()
    if "approval" in rel_s:
        return True
    return (APPROVAL_DIR in rel.parents) or (rel == APPROVAL_DIR)


def scan_tree(root: Path) -> List[str]:
    findings: List[str] = []

    for path in iter_scan_targets(root):
        try:
            txt = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if any(pat in txt for pat in EXEC_PATTERNS):
            if not _is_allowed_approval_path(root, path):
                findings.append(str(path))

    return findings


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv or sys.argv[1:]
    root = Path(os.getcwd())
    if "--root" in argv:
        idx = argv.index("--root")
        root = Path(argv[idx + 1]).resolve()

    try:
        findings = scan_tree(root)
    except Exception as e:
        print(str(e))
        return 1

    if findings:
        print("FAIL-CLOSED: execution references outside approval path")
        for f in findings:
            print(f"- {f}")
        return 1

    print("OK: LOCK-2 gate clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
