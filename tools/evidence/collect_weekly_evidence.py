#!/usr/bin/env python3
"""
Collect weekly R&D evidence across repos and build a submission file (A+B).

A) Time basis:
- Extracts "Estimated hours: <number>" from each weekly doc and totals per repo and overall.

B) Evidence appendix:
- Adds evidence pointers and lightweight repo signals (audit dirs, recent commits).

Usage:
  python tools/evidence/collect_weekly_evidence.py \
    --repos proto-v2-engine meta-os auralis-childcare \
    --weeks 2026-W06 2026-W07 \
    --out docs/evidence/submissions/2026-Q1.md
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional

HOURS_RE = re.compile(r"^\s*Estimated hours\s*:\s*([0-9]+(\.[0-9]+)?)\s*$", re.IGNORECASE | re.MULTILINE)

def _safe_git_log(repo: Path, n: int = 5) -> List[str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "log", "--oneline", f"-n{n}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        if r.returncode != 0:
            return []
        return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    except Exception:
        return []

def _hours_from_text(text: str) -> Optional[float]:
    m = HOURS_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None

def _read_week(repo: Path, week: str) -> Tuple[str, float]:
    p = repo / "docs" / "evidence" / "weekly" / f"{week}.md"
    if not p.exists():
        body = f"\n## {repo.name} – {week}\n(MISSING)\n"
        return body, 0.0

    txt = p.read_text(encoding="utf-8").strip()
    hrs = _hours_from_text(txt) or 0.0
    body = f"\n## {repo.name} – {week}\n{txt}\n"
    return body, hrs

def _evidence_appendix(repo: Path) -> str:
    # simple, deterministic pointers
    pointers = []
    # common evidence dirs
    for rel in [
        "audits",
        "audits/sentinel",
        "audits/sentinel/judgment_events_chain.jsonl",
        "audits/sentinel/snapshots",
        "audits/sentinel/outcomes",
        ".github/workflows",
    ]:
        if (repo / rel).exists():
            pointers.append(f"- {rel}")

    git_head = ""
    try:
        r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
        if r.returncode == 0:
            git_head = r.stdout.strip()
    except Exception:
        pass

    commits = _safe_git_log(repo, n=5)
    lines = []
    lines.append(f"\n### Evidence appendix – {repo.name}\n")
    if git_head:
        lines.append(f"- HEAD: `{git_head}`")
    if pointers:
        lines.append("- Evidence pointers:")
        lines.extend([f"  {p}" for p in pointers])
    if commits:
        lines.append("- Recent commits:")
        lines.extend([f"  - `{c}`" for c in commits])
    if not (git_head or pointers or commits):
        lines.append("- (No repo signals detected)")
    return "\n".join(lines) + "\n"

def main() -> int:
    ap = argparse.ArgumentParser(description="Collect weekly R&D evidence across repos (A+B)")
    ap.add_argument("--repos", nargs="+", required=True, help="Repo paths")
    ap.add_argument("--weeks", nargs="+", required=True, help="Weeks (e.g., 2026-W06)")
    ap.add_argument("--out", required=True, help="Output markdown file")
    args = ap.parse_args()

    repos = [Path(r).resolve() for r in args.repos]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    repo_hours: Dict[str, float] = {r.name: 0.0 for r in repos}
    overall_hours = 0.0

    lines: List[str] = []
    lines.append("# R&D Activity Summary (Consolidated)\n")
    lines.append("## Scope\n- Consolidated weekly evidence across repositories\n")

    # main body
    for w in args.weeks:
        lines.append(f"\n# {w}\n")
        for r in repos:
            body, hrs = _read_week(r, w)
            repo_hours[r.name] += hrs
            overall_hours += hrs
            lines.append(body)

    # A) totals
    lines.append("\n# Time Basis (Estimated)\n")
    lines.append("> Basis: weekly logs (\"Estimated hours\") + versioned repo activity (git/CI/audits)\n")
    for name, hrs in repo_hours.items():
        lines.append(f"- {name}: {hrs:.1f} hours")
    lines.append(f"\n**Overall total: {overall_hours:.1f} hours**\n")

    # B) evidence appendix
    lines.append("\n# Evidence Appendix\n")
    for r in repos:
        lines.append(_evidence_appendix(r))

    out.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(f"Written: {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
