#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    pattern: str
    excerpt: str


FORBIDDEN_PATTERNS: List[Tuple[str, str]] = [
    (r"\bvar/ai\b", "INTERNAL_PATH_var_ai"),
    (r"\b\.worktrees\b", "INTERNAL_PATH_worktrees"),
    (r"\btools/\b", "INTERNAL_PATH_tools_dir"),
    (r"\bcontracts/\b", "INTERNAL_PATH_contracts_dir"),
    (r"\bpolicies/\b", "INTERNAL_PATH_policies_dir"),
    (r"\btests/\b", "INTERNAL_PATH_tests_dir"),
    (r"\b\.github/\b", "INTERNAL_PATH_dotgithub_dir"),
    (r"\bDATABASE_URL\b", "INTERNAL_ENV_DATABASE_URL"),
    (r"\bVF_[A-Z0-9_]+\b", "INTERNAL_ENV_VF_PREFIX"),
    (r"\bapproval_ledger\.jsonl\b", "INTERNAL_LEDGER_APPROVAL"),
    (r"\bmemory\.jsonl\b", "INTERNAL_LEDGER_MEMORY"),
    (r"\bverification_factory\.py\b", "INTERNAL_TOOL_VF"),
    (r"\bfailure_packetize\.py\b", "INTERNAL_TOOL_FAILURE_PACKETIZE"),
    (r"\bself_healing_orchestrator\.py\b", "INTERNAL_TOOL_ORCH"),
    (r"\bhuman_approval_gate\.py\b", "INTERNAL_TOOL_HUMAN_GATE"),
    (r"\bapply_approved\.py\b", "INTERNAL_TOOL_APPLY_APPROVED"),
    (r"\bmerge_gate\.py\b", "INTERNAL_TOOL_MERGE_GATE"),
    (r"\bvfctl\.py\b", "INTERNAL_TOOL_VFCTL"),
    (r"\breport_pack\.py\b", "INTERNAL_TOOL_REPORT_PACK"),
    (r"\bredbeansoup85\b", "FINGERPRINT_OWNER"),
    (r"\bproto-v2-engine\b", "FINGERPRINT_REPO"),
]


def iter_public_md(root: Path) -> Iterable[Path]:
    base = root / "docs" / "public"
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("*.md") if p.is_file())


def scan_file(path: Path) -> List[Finding]:
    findings: List[Finding] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return [Finding(str(path), 1, "UTF8_REQUIRED", "file is not valid UTF-8")]

    for i, line in enumerate(lines, start=1):
        for rx, tag in FORBIDDEN_PATTERNS:
            if re.search(rx, line):
                excerpt = line.strip()
                if len(excerpt) > 160:
                    excerpt = excerpt[:157] + "..."
                findings.append(Finding(str(path), i, tag, excerpt))
    return findings


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    files = list(iter_public_md(root))

    findings: List[Finding] = []
    for f in files:
        findings.extend(scan_file(f))

    if findings:
        print("FAIL: public docs leak gate triggered (fail-closed).")
        for f in findings:
            print(f"- file={f.file} line={f.line} pattern={f.pattern}")
            print(f"  excerpt: {f.excerpt}")
        print(json.dumps({
            "status": "FAIL",
            "files_scanned": len(files),
            "findings_count": len(findings),
            "findings": [f.__dict__ for f in findings],
        }, separators=(",", ":")))
        return 1

    print(json.dumps({
        "status": "PASS",
        "files_scanned": len(files),
        "findings_count": 0,
        "findings": [],
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
