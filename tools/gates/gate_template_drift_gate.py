#!/usr/bin/env python3
"""
Fail-closed gate: ensure workflow instances are structurally identical to canonical gate template.

Allowed substitutions:
- name: <anything>
- .github/workflows/<file>.yml path entry inside on.pull_request.paths (or other on.*.paths)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Iterable, Tuple, List

RE_NAME = re.compile(r'^\s*name\s*:\s*.+\s*$')
RE_COMMENT = re.compile(r'^\s*#.*$')
RE_EMPTY = re.compile(r'^\s*$')

def read_lines(p: Path) -> List[str]:
    try:
        return p.read_text(encoding="utf-8").splitlines(keepends=False)
    except FileNotFoundError:
        print(f"FAIL GATE_TEMPLATE_MISSING file={p}", file=sys.stderr)
        sys.exit(2)

def normalize_template(lines: Iterable[str]) -> List[str]:
    out: List[str] = []
    for ln in lines:
        # keep comments to be strict? -> we ignore pure comment lines for stability.
        if RE_COMMENT.match(ln):
            continue
        if RE_EMPTY.match(ln):
            continue
        out.append(ln.rstrip())
    return out

def normalize_instance(lines: Iterable[str], gate_file: str) -> List[str]:
    out: List[str] = []
    for ln in lines:
        if RE_COMMENT.match(ln):
            continue
        if RE_EMPTY.match(ln):
            continue

        # Allow any workflow name
        if RE_NAME.match(ln):
            out.append("name: __GATE_NAME__")
            continue

        # Allow the workflow file self-reference under paths (common patterns)
        # Replace exact occurrences of the gate file with __GATE_FILE__
        # (We do not allow other path changes.)
        ln2 = ln.replace(gate_file, "__GATE_FILE__")
        out.append(ln2.rstrip())
    return out

def sha256_lines(lines: Iterable[str]) -> str:
    h = hashlib.sha256()
    for ln in lines:
        h.update(ln.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()

def first_diff(a: List[str], b: List[str]) -> Tuple[int, str, str]:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i, a[i], b[i]
    if len(a) != len(b):
        i = n
        a_ln = a[i] if i < len(a) else "<EOF>"
        b_ln = b[i] if i < len(b) else "<EOF>"
        return i, a_ln, b_ln
    return -1, "", ""

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, help="Path to canonical template YAML")
    ap.add_argument("--instance", required=True, action="append", help="Path to workflow instance YAML (repeatable)")
    ap.add_argument("--root", default=".", help="Repo root")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    template_path = (root / args.template).resolve()

    tmpl_lines = normalize_template(read_lines(template_path))
    tmpl_hash = sha256_lines(tmpl_lines)

    failures = 0

    for inst in args.instance:
        inst_path = (root / inst).resolve()
        gate_file = os.path.basename(str(inst_path))
        inst_lines_raw = read_lines(inst_path)
        inst_lines = normalize_instance(inst_lines_raw, gate_file=gate_file)
        inst_hash = sha256_lines(inst_lines)

        if inst_hash != tmpl_hash:
            failures += 1
            idx, a_ln, b_ln = first_diff(tmpl_lines, inst_lines)
            print(
                "FAIL GATE_TEMPLATE_DRIFT "
                f"instance={inst} template={args.template} "
                f"template_sha256={tmpl_hash} instance_sha256={inst_hash} "
                f"diff_line={idx+1} expected={repr(a_ln)} got={repr(b_ln)}",
                file=sys.stderr,
            )
        else:
            print(f"OK GATE_TEMPLATE_MATCH instance={inst}")

    if failures:
        sys.exit(1)

if __name__ == "__main__":
    main()
