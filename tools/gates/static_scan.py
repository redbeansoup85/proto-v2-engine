from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re

@dataclass(frozen=True)
class Finding:
    rule_id: str
    file: str
    line: int
    pattern: str
    snippet: str

DENY_PATTERNS = [
    ("EXEC_CALL", re.compile(r"\b(execute|dispatch|place_order|send_order|broker\.|exchange\.)\b")),
    ("EXEC_IMPORT", re.compile(r"\b(import\s+.*executor|from\s+.*executor\s+import)\b")),
]

ALLOW_PATH_HINTS = ["approval", "handlers/approval", "approval_handler"]

def scan_tree(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for p in root.rglob("*.py"):
        txt = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        allow = any(h in str(p).lower() for h in ALLOW_PATH_HINTS)

        for i, line in enumerate(txt, start=1):
            for rule_id, rx in DENY_PATTERNS:
                if rx.search(line):
                    if allow:
                        continue
                    findings.append(Finding(rule_id, str(p), i, rx.pattern, line.strip()[:200]))
    return findings
