#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

FINDINGS_VERSION = "v1"
GATE_NAME = "loop-gate"

@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    file: str
    line: Optional[int]
    message: str
    evidence: str = ""
    hint: str = ""

def _emit(status: str, findings: List[Finding]) -> None:
    payload: Dict[str, Any] = {
        "gate": GATE_NAME,
        "version": FINDINGS_VERSION,
        "status": status,
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity,
                "file": f.file,
                "line": f.line,
                "message": f.message,
                **({"evidence": f.evidence} if f.evidence else {}),
                **({"hint": f.hint} if f.hint else {}),
            }
            for f in findings
        ],
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")

def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def _find_task_loops(root: Path) -> List[Path]:
    res: List[Path] = []
    if not root.exists() or not root.is_dir():
        return res
    for domain in root.iterdir():
        if not domain.is_dir() or domain.name == "_template":
            continue
        for taskdir in domain.iterdir():
            if not taskdir.is_dir():
                continue
            f = taskdir / "TASK_LOOP.yaml"
            if f.exists() and f.is_file():
                res.append(f)
    return sorted(res)

def _require_key_line(text: str, key: str) -> bool:
    return re.search(rf"^{re.escape(key)}:", text, flags=re.MULTILINE) is not None

def _validate_task_loop_file(f: Path) -> List[Finding]:
    findings: List[Finding] = []
    text = _read_text(f)

    for k in ["CREATED_AT_UTC","INTENT","EXPECTED_OUTCOME","EXECUTION","NEXT_ACTION","RESULT"]:
        if not _require_key_line(text, k):
            findings.append(Finding(
                rule_id="TASK_LOOP_REQUIRED_KEY_MISSING",
                severity="ERROR",
                file=str(f),
                line=None,
                message=f"Missing required key {k} in TASK_LOOP.yaml",
                evidence=f"{k}:",
            ))

    if re.search(r"^RESULT:\s*(OPEN|CLOSED|BLOCKED|SKIPPED)\s*$", text, flags=re.MULTILINE) is None:
        findings.append(Finding(
            rule_id="TASK_LOOP_RESULT_INVALID",
            severity="ERROR",
            file=str(f),
            line=None,
            message="Invalid RESULT (allowed: OPEN|CLOSED|BLOCKED|SKIPPED)",
        ))

    if re.search(
        r'^CREATED_AT_UTC:\s*"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"\s*$',
        text, flags=re.MULTILINE
    ) is None:
        findings.append(Finding(
            rule_id="TASK_LOOP_CREATED_AT_UTC_INVALID",
            severity="ERROR",
            file=str(f),
            line=None,
            message='Invalid CREATED_AT_UTC (required: "YYYY-MM-DDTHH:MM:SSZ")',
        ))

    if re.search(r"^RESULT:\s*CLOSED\s*$", text, flags=re.MULTILINE):
        vfile = f.parent / "VERDICT.yaml"
        if not vfile.exists():
            findings.append(Finding(
                rule_id="VERDICT_MISSING",
                severity="ERROR",
                file=str(vfile),
                line=None,
                message="RESULT=CLOSED but VERDICT.yaml is missing",
                hint="Add VERDICT.yaml beside TASK_LOOP.yaml when RESULT is CLOSED.",
            ))
        else:
            vtxt = _read_text(vfile)
            for k in ["is_closed","verifier","verified_at_utc","evidence"]:
                if not _require_key_line(vtxt, k):
                    findings.append(Finding(
                        rule_id="VERDICT_REQUIRED_KEY_MISSING",
                        severity="ERROR",
                        file=str(vfile),
                        line=None,
                        message=f"VERDICT.yaml missing required key {k}",
                        evidence=f"{k}:",
                    ))
            if re.search(r"^is_closed:\s*true\s*$", vtxt, flags=re.MULTILINE) is None:
                findings.append(Finding(
                    rule_id="VERDICT_IS_CLOSED_INVALID",
                    severity="ERROR",
                    file=str(vfile),
                    line=None,
                    message="VERDICT.yaml is_closed must be true",
                ))
            if re.search(
                r'^verified_at_utc:\s*"?[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"?\s*$',
                vtxt, flags=re.MULTILINE
            ) is None:
                findings.append(Finding(
                    rule_id="VERDICT_VERIFIED_AT_UTC_INVALID",
                    severity="ERROR",
                    file=str(vfile),
                    line=None,
                    message="VERDICT.yaml verified_at_utc must be YYYY-MM-DDTHH:MM:SSZ",
                ))
            if re.search(r"^[[:space:]]*-[[:space:]]+type:[[:space:]]*(log|test|review)[[:space:]]*$",
                         vtxt, flags=re.MULTILINE) is None:
                findings.append(Finding(
                    rule_id="VERDICT_EVIDENCE_TYPE_INVALID",
                    severity="ERROR",
                    file=str(vfile),
                    line=None,
                    message="VERDICT.yaml evidence item missing/invalid type (log|test|review)",
                ))
            if re.search(r"^[[:space:]]+ref:[[:space:]]*[^[:space:]].*$",
                         vtxt, flags=re.MULTILINE) is None:
                findings.append(Finding(
                    rule_id="VERDICT_EVIDENCE_REF_MISSING",
                    severity="ERROR",
                    file=str(vfile),
                    line=None,
                    message="VERDICT.yaml evidence item missing ref",
                ))
    return findings

def _read_pr_body_from_event() -> str:
    p = os.environ.get("GITHUB_EVENT_PATH","")
    if not p:
        return ""
    try:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return ""
    pr = data.get("pull_request") or {}
    body = pr.get("body")
    return body if isinstance(body, str) else ""

def _validate_pr_request(body: str) -> List[Finding]:
    findings: List[Finding] = []
    if not body:
        findings.append(Finding(
            rule_id="PR_BODY_EMPTY",
            severity="ERROR",
            file="PR_BODY",
            line=None,
            message="Pull request body is empty or unavailable",
        ))
        return findings
    for k in ["DESIGN_ARTIFACT","STAGE","WHY_NOW","VERIFY","BREAK_RISK"]:
        if re.search(rf"^{re.escape(k)}:", body, flags=re.MULTILINE) is None:
            findings.append(Finding(
                rule_id="PR_REQUEST_REQUIRED_KEY_MISSING",
                severity="ERROR",
                file="PR_BODY",
                line=None,
                message=f"Missing {k} in PR body",
                evidence=f"{k}:",
            ))
    return findings

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get("ROOT","tasks"))
    ap.add_argument("--enforce-pr-request", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    findings: List[Finding] = []

    if not root.exists() or not root.is_dir():
        findings.append(Finding(
            rule_id="ROOT_NOT_FOUND",
            severity="ERROR",
            file=str(root),
            line=None,
            message=f"Fail-Closed: ROOT directory not found: {root}",
        ))
        _emit("FAIL", findings)
        return 1

    loops = _find_task_loops(root)
    if len(loops) < 1:
        findings.append(Finding(
            rule_id="TASK_LOOP_NOT_FOUND",
            severity="ERROR",
            file=str(root),
            line=None,
            message=f"Fail-Closed: no TASK_LOOP.yaml found under {root} (excluding _template)",
        ))
        _emit("FAIL", findings)
        return 1

    for f in loops:
        findings.extend(_validate_task_loop_file(f))

    if args.enforce_pr_request and os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
        findings.extend(_validate_pr_request(_read_pr_body_from_event()))

    status = "PASS" if not findings else "FAIL"
    _emit(status, findings)
    return 0 if status == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
