#!/usr/bin/env python3
from __future__ import annotations

import sys
import yaml
from pathlib import Path
from collections import Counter

WORKFLOWS_DIR = Path(".github/workflows")

def fail(msg: str) -> None:
    print(f"FAIL-CLOSED: {msg}", file=sys.stderr)
    sys.exit(1)

def main() -> int:
    if not WORKFLOWS_DIR.exists():
        fail(".github/workflows not found")

    job_ids = []
    job_names = []

    for wf in WORKFLOWS_DIR.glob("*.yml"):
        data = yaml.safe_load(wf.read_text())
        jobs = (data or {}).get("jobs", {}) or {}

        for job_id, job in jobs.items():
            job_ids.append(job_id)
            name = job.get("name")
            if not name:
                fail(f"{wf}: job '{job_id}' missing explicit name")
            job_names.append(name)

    # forbid duplicated job id 'gate'
    counts = Counter(job_ids)
    if counts.get("gate", 0) > 1:
        fail("job id 'gate' used in multiple workflows (ambiguous check name)")

    # forbid duplicated job names
    dup_names = [n for n, c in Counter(job_names).items() if c > 1]
    if dup_names:
        fail(f"duplicated job names detected: {dup_names}")

    print("OK: CI required checks contract satisfied")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
