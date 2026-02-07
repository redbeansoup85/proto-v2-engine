#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RULE_ID = "EXECUTION_CARD_BOOTSTRAP_REQUIRED"

REQUIRES_RE = re.compile(r"(?m)^\s*requires\s*:\s*(#.*)?$")
BOOTSTRAP_ITEM_RE = re.compile(r"(?m)^\s*-\s*LOCK-BOOTSTRAP\s*(#.*)?$")


def scan_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")

    findings: list[dict] = []

    has_requires = bool(REQUIRES_RE.search(text))
    has_bootstrap = bool(BOOTSTRAP_ITEM_RE.search(text))

    if not has_requires or not has_bootstrap:
        snippet = "\n".join(text.splitlines()[:10])
        findings.append(
            {
                "rule_id": RULE_ID,
                "file": str(path),
                "line": 1,
                "pattern": "requires: + '- LOCK-BOOTSTRAP'",
                "snippet": snippet,
            }
        )

    return findings


def iter_card_files(root: Path) -> list[Path]:
    cards_dir = root / "execution_cards"
    if not cards_dir.exists():
        return []

    files = []
    for p in cards_dir.rglob("*.yaml"):
        if not p.is_file():
            continue
        if "/_template/" in str(p).replace("\\", "/"):
            continue
        files.append(p)
    return sorted(files)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="repo root (default: .)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    card_files = iter_card_files(root)

    # 🔒 POLICY:
    # execution_cards가 아직 없으면 "적용 대상 아님"으로 통과
    # (카드가 생기는 순간부터 강제)
    if not card_files:
        print("OK: no execution_cards found (bootstrap gate not applicable yet)")
        return 0

    all_findings: list[dict] = []
    for f in card_files:
        all_findings.extend(scan_file(f))

    if all_findings:
        for item in all_findings:
            print(
                f"FAIL {item['rule_id']} file={item['file']} "
                f"line={item['line']} pattern={item['pattern']}\n"
                f"{item['snippet']}\n---"
            )
        return 1

    print(f"OK: {len(card_files)} execution card(s) include LOCK-BOOTSTRAP requirement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
