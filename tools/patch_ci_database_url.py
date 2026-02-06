#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

FILES = [
    Path(".github/workflows/ci.yml"),
    Path(".github/workflows/design_gate.yml"),
    Path(".github/workflows/lock2-gate.yml"),
]

KEY = "DATABASE_URL"
VALUE = "sqlite+aiosqlite:///test.db"


def indent_of(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" "))]


def ensure_job_env_block(lines: list[str], job_name: str) -> tuple[list[str], bool]:
    changed = False

    job_header_idx = None
    for i, line in enumerate(lines):
        if line.startswith("  " + job_name + ":"):
            job_header_idx = i
            break
    if job_header_idx is None:
        return lines, False

    job_indent = indent_of(lines[job_header_idx])
    end = len(lines)
    for j in range(job_header_idx + 1, len(lines)):
        if lines[j].startswith(job_indent) and lines[j].strip().endswith(":") and not lines[j].startswith(job_indent + " "):
            end = j
            break

    block = lines[job_header_idx:end]

    runs_on_idx = None
    steps_idx = None
    env_idx = None

    for k, line in enumerate(block):
        s = line.strip()
        if s.startswith("runs-on:"):
            runs_on_idx = k
        if s == "steps:":
            steps_idx = k
        if s == "env:":
            env_idx = k

    if env_idx is not None:
        env_indent = indent_of(block[env_idx])
        child_indent = env_indent + "  "
        env_end = len(block)
        for k in range(env_idx + 1, len(block)):
            if block[k].startswith(env_indent) and block[k].strip().endswith(":") and indent_of(block[k]) == env_indent:
                env_end = k
                break

        found_key = None
        for k in range(env_idx + 1, env_end):
            if block[k].startswith(child_indent + KEY + ":"):
                found_key = k
                break

        desired_line = f'{child_indent}{KEY}: "{VALUE}"\n'

        if found_key is None:
            block.insert(env_end, desired_line)
            changed = True
        else:
            if block[found_key] != desired_line:
                block[found_key] = desired_line
                changed = True

        return lines[:job_header_idx] + block + lines[end:], changed

    insert_after = job_header_idx
    if runs_on_idx is not None:
        insert_after = job_header_idx + runs_on_idx + 1
    elif steps_idx is not None:
        insert_after = job_header_idx + steps_idx
    else:
        insert_after = job_header_idx + 1

    prop_indent = job_indent + "  "
    env_block = [
        f"{prop_indent}env:\n",
        f'{prop_indent}  {KEY}: "{VALUE}"\n',
    ]
    lines = lines[:insert_after] + env_block + lines[insert_after:]
    changed = True
    return lines, changed


def find_jobs(lines: list[str]) -> list[str]:
    jobs_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "jobs:" and indent_of(line) == "":
            jobs_idx = i
            break
    if jobs_idx is None:
        return []

    jobnames: list[str] = []
    for j in range(jobs_idx + 1, len(lines)):
        if indent_of(lines[j]) == "" and lines[j].strip().endswith(":"):
            break
        if lines[j].startswith("  ") and lines[j].strip().endswith(":") and indent_of(lines[j]) == "  ":
            job = lines[j].strip()[:-1]
            jobnames.append(job)
    return jobnames


def patch_file(path: Path) -> bool:
    if not path.exists():
        print(f"[SKIP] missing: {path}")
        return False

    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)

    jobs = find_jobs(lines)
    if not jobs:
        print(f"[WARN] no top-level jobs found in: {path}")
        return False

    changed_any = False
    for job in jobs:
        lines, changed = ensure_job_env_block(lines, job)
        changed_any = changed_any or changed

    if not changed_any:
        print(f"[OK] no change: {path}")
        return False

    backup = path.with_suffix(path.suffix + ".bak")
    backup.write_text(original, encoding="utf-8")

    path.write_text("".join(lines), encoding="utf-8")
    print(f"[PATCHED] {path} (backup: {backup})")
    return True


def main() -> int:
    changed = False
    for f in FILES:
        changed = patch_file(f) or changed

    print("[DONE] patched workflows." if changed else "[DONE] nothing patched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
