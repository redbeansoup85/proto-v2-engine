#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Tuple


README_PATH = Path("docs/governance/patches/README.md")
PATCH_DIR = Path("docs/governance/patches")

# We replace ONLY the table block between these anchors (fail-closed).
ANCHOR_BEGIN = "<!-- PATCH_RECORDS_BEGIN -->"
ANCHOR_END = "<!-- PATCH_RECORDS_END -->"

PATCH_FILE_RE = re.compile(r"^PATCH-(\d{8})-(.+)\.md$")


@dataclass(frozen=True)
class PatchRow:
    date_tz: str
    patch_file: str
    scope: str
    change_type: str
    notes: str


def die(msg: str) -> None:
    raise SystemExit(f"[FAIL-CLOSED] {msg}")


def read_text(p: Path) -> str:
    if not p.exists():
        die(f"missing file: {p}")
    return p.read_text(encoding="utf-8")


def extract_yaml_block(md: str) -> Dict[str, str]:
    """
    Extract first ```yaml fenced block. If missing or malformed, return {}.
    No inference: caller must handle blanks.
    """
    fence = "```yaml"
    endf = "```"
    start = md.find(fence)
    if start < 0:
        return {}
    after = md.find("\n", start)
    if after < 0:
        return {}
    end = md.find(endf, after + 1)
    if end < 0:
        return {}  # unmatched fence inside patch file -> treat as missing
    block = md[after + 1 : end]
    out: Dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # simple KEY: value parser (no YAML features; fail-closed)
        m = re.match(r"^([A-Z0-9_]+)\s*:\s*(.*)\s*$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        out[k] = v
    return out


def safe_val(v: Optional[str]) -> str:
    if not v:
        return "—"
    v = v.strip()
    return v if v else "—"


def normalize_effective_date(d: str) -> str:
    # Expect YYYY-MM-DD. Otherwise return as-is (no inference).
    d = d.strip()
    return d


def build_rows() -> List[PatchRow]:
    if not PATCH_DIR.exists():
        die(f"missing patches dir: {PATCH_DIR}")

    files = sorted([p for p in PATCH_DIR.iterdir() if p.is_file() and PATCH_FILE_RE.match(p.name)])
    rows: List[PatchRow] = []

    for p in files:
        md = read_text(p)
        meta = extract_yaml_block(md)

        effective = safe_val(meta.get("EFFECTIVE_DATE"))
        tz = safe_val(meta.get("TIMEZONE"))
        scope = safe_val(meta.get("SCOPE"))
        change_type = safe_val(meta.get("CHANGE_TYPE"))

        date_tz = f"{normalize_effective_date(effective)} ({tz})" if effective != "—" and tz != "—" else "—"

        # Notes: prefer Patch Summary first bullet if available; else —
        notes = "—"
        # find "## 2) Patch Summary" section and take first bullet line
        m = re.search(r"^##\s*2\)\s*Patch Summary\s*$", md, flags=re.MULTILINE)
        if m:
            tail = md[m.end():]
            bm = re.search(r"^\*\s+(.*)\s*$", tail, flags=re.MULTILINE)
            if bm:
                notes = bm.group(1).strip() or "—"

        rows.append(
            PatchRow(
                date_tz=date_tz,
                patch_file=p.name,
                scope=scope,
                change_type=change_type,
                notes=notes,
            )
        )

    # Sort by date desc if date is parseable, else keep filename sort
    def sort_key(r: PatchRow) -> Tuple[int, str]:
        # key: 0 for parseable date, 1 for non-parseable (non-parseable goes last)
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})\s", r.date_tz)
        if not m:
            return (1, r.patch_file)
        y, mo, da = m.group(1), m.group(2), m.group(3)
        return (0, f"{y}{mo}{da}")

    parseables = [r for r in rows if sort_key(r)[0] == 0]
    non_parseables = [r for r in rows if sort_key(r)[0] != 0]

    parseables.sort(key=lambda r: sort_key(r)[1], reverse=True)
    non_parseables.sort(key=lambda r: r.patch_file)

    return parseables + non_parseables


def render_table(rows: List[PatchRow]) -> str:
    header = (
        "| Date (TZ) | Patch | Scope | Change Type | Notes |\n"
        "|---|---|---|---|---|\n"
    )
    lines = [header]
    for r in rows:
        patch = f"`{r.patch_file}`"
        lines.append(f"| {r.date_tz} | {patch} | {r.scope} | {r.change_type} | {r.notes} |\n")
    return "".join(lines)


def update_readme(dry_run: bool) -> None:
    # Fail-Closed: read current README text once, then compare.
    if not README_PATH.exists():
        raise SystemExit(f"[FAIL-CLOSED] missing README: {README_PATH}")
    old_txt = README_PATH.read_text(encoding="utf-8")

    txt = read_text(README_PATH)

    if ANCHOR_BEGIN not in txt or ANCHOR_END not in txt:
        die(f"README missing anchors: {ANCHOR_BEGIN} / {ANCHOR_END}")

    begin_i = txt.index(ANCHOR_BEGIN) + len(ANCHOR_BEGIN)
    end_i = txt.index(ANCHOR_END)

    if begin_i >= end_i:
        die("README anchors are malformed (begin after end)")

    rows = build_rows()
    table = render_table(rows)

    new_mid = "\n\n" + table + "\n"
    new_txt = txt[:begin_i] + new_mid + txt[end_i:]

    if dry_run:
        print(new_txt)
        return

        old_txt = README_PATH.read_text(encoding="utf-8")
    if new_txt == old_txt:
        print("[OK] README patch records table already up to date")
        return

    README_PATH.write_text(new_txt, encoding="utf-8")
    print("[OK] README patch records table updated")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    update_readme(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
