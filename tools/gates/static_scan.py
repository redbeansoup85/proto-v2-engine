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
    ("EXEC_TRADE", re.compile(r"\b(place_order|submit_order|send_order|execute_trade|broker\.|exchange\.)\b")),
    ("EXEC_HTTP", re.compile(r"\b(requests\.(get|post|put|delete)|httpx\.(get|post|put|delete))\b")),
    ("EXEC_SHELL", re.compile(r"\b(os\.system|subprocess\.(run|Popen|call))\b")),
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
        txt = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(txt, start=1):
            for rule_id, rx in DENY_PATTERNS:
                if rx.search(line):
                    findings.append(Finding(rule_id, str(p), i, rx.pattern, line.strip()[:200]))
    return findings
