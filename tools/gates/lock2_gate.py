from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
import argparse

@dataclass(frozen=True)
class Finding:
    rule_id: str
    file: str
    line: int
    pattern: str
    snippet: str

# "execution" 관련 참조가 승인 경로 밖에서 나타나면 fail-closed
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

def _excluded(p: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in p.parts)

def scan_tree(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for p in root.rglob("*.py"):
        if _excluded(p):
            continue
        path_l = str(p).lower()
        allow = any(h in path_l for h in ALLOW_PATH_HINTS)

        txt = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(txt, start=1):
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

    findings = scan_tree(Path(args.root))
    if findings:
        print("FAIL-CLOSED: LOCK-2 gate findings detected")
        for f in findings[:200]:
            print(f"- {f.rule_id} | {f.file}:{f.line} | {f.snippet}")
        if len(findings) > 200:
            print(f"... ({len(findings)-200} more)")
        return 1

    print("OK: LOCK-2 gate clean")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
