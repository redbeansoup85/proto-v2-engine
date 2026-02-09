#!/usr/bin/env python3
"""
Gatekit Template Drift Gate v1.0 (stdlib-only, fail-closed)

Rules:
- Each workflow under workflows_root matching "*-gate.yml" must contain
  "# gatekit_template: <template_key>" within the first N lines (default 5).
- template file must exist: templates_root/<template_key>.yml
- workflow content must be identical to template content (text equality).
"""

from __future__ import annotations

import argparse
import difflib
import os
import sys
from pathlib import Path
from typing import Optional, Tuple


TAG_PREFIX = "# gatekit_template:"


def fail(reason: str, file: Optional[Path] = None, detail: Optional[str] = None) -> None:
    msg = f"FAIL {reason}"
    if file is not None:
        msg += f" file={file.as_posix()}"
    if detail:
        # keep single-line-friendly output
        msg += f" detail={detail}"
    print(msg)
    sys.exit(1)


def read_text_normalized(path: Path) -> str:
    # Normalize line endings to avoid CRLF vs LF causing false drift.
    data = path.read_text(encoding="utf-8", errors="strict")
    return data.replace("\r\n", "\n").replace("\r", "\n")


def extract_template_key(workflow_path: Path, max_lines: int) -> Optional[str]:
    # Search within first max_lines lines
    try:
        raw = workflow_path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        fail("GATEKIT_WORKFLOW_NOT_UTF8", file=workflow_path)
        raise  # unreachable

    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for i, line in enumerate(lines[:max_lines]):
        s = line.strip()
        if s.startswith(TAG_PREFIX):
            key = s[len(TAG_PREFIX):].strip()
            return key or None
    return None


def unified_diff(a: str, b: str, a_name: str, b_name: str, max_lines: int = 120) -> str:
    diff_lines = list(difflib.unified_diff(
        a.splitlines(True),
        b.splitlines(True),
        fromfile=a_name,
        tofile=b_name,
        n=3,
        lineterm=""
    ))
    if not diff_lines:
        return ""
    # Limit to keep logs readable (fail-closed still)
    if len(diff_lines) > max_lines:
        diff_lines = diff_lines[:max_lines] + ["\n... (diff truncated) ...\n"]
    return "".join(diff_lines).replace("\n", "\\n")  # keep single-line safe


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workflows-root", default=".github/workflows")
    p.add_argument("--templates-root", default="gatekit/templates")
    p.add_argument("--max-tag-lines", type=int, default=5)
    p.add_argument("--require-template-tag", action="store_true", default=False)
    args = p.parse_args()

    workflows_root = Path(args.workflows_root)
    templates_root = Path(args.templates_root)

    if not workflows_root.exists() or not workflows_root.is_dir():
        fail("GATEKIT_WORKFLOWS_ROOT_MISSING", file=workflows_root)

    if not templates_root.exists() or not templates_root.is_dir():
        fail("GATEKIT_TEMPLATES_ROOT_MISSING", file=templates_root)

    targets = sorted(workflows_root.glob("*-gate.yml"))
    if not targets:
        # fail-closed: if expected gates exist and pattern changed, better to fail
        fail("GATEKIT_NO_TARGET_WORKFLOWS_FOUND", file=workflows_root, detail="pattern=*-gate.yml")

    for wf in targets:
        key = extract_template_key(wf, max_lines=args.max_tag_lines)
        if args.require_template_tag:
            if key is None:
                fail("GATEKIT_TEMPLATE_TAG_MISSING", file=wf, detail=f"expected='{TAG_PREFIX} <template_key>' within first {args.max_tag_lines} lines")
        if key is None:
            # if not required, skip
            continue

        template_path = templates_root / f"{key}.yml"
        if not template_path.exists():
            fail("GATEKIT_TEMPLATE_FILE_MISSING", file=wf, detail=f"template={template_path.as_posix()}")

        wf_text = read_text_normalized(wf)
        tpl_text = read_text_normalized(template_path)

        if wf_text != tpl_text:
            d = unified_diff(tpl_text, wf_text, template_path.as_posix(), wf.as_posix())
            fail("GATEKIT_TEMPLATE_DRIFT", file=wf, detail=d or "content_mismatch")

    print("PASS GATEKIT_TEMPLATE_DRIFT_GATE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
