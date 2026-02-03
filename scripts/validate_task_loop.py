#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from jsonschema import Draft202012Validator

ISO_UTC_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@dataclass(frozen=True)
class FileResult:
    path: Path
    ok: bool
    errors: Tuple[str, ...]


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def find_task_loops(root: Path) -> List[Path]:
    matches: List[Path] = []
    for l1 in root.iterdir():
        if not l1.is_dir() or l1.name == "_template":
            continue
        for l2 in l1.iterdir():
            if not l2.is_dir():
                continue
            p = l2 / "TASK_LOOP.yaml"
            if p.is_file():
                matches.append(p)
    return sorted(matches)


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_one(path: Path, validator: Draft202012Validator) -> FileResult:
    errors: List[str] = []

    try:
        data = load_yaml(path)
    except Exception as ex:
        return FileResult(path, False, (f"YAML parse error: {ex}",))

    if not isinstance(data, dict):
        return FileResult(path, False, ("Root YAML must be a mapping/object.",))

    for err in validator.iter_errors(data):
        loc = ".".join(str(p) for p in err.path) if err.path else "(root)"
        errors.append(f"{loc}: {err.message}")

    created = data.get("CREATED_AT_UTC")
    if not isinstance(created, str) or not ISO_UTC_Z_RE.match(created):
        errors.append('CREATED_AT_UTC must match "YYYY-MM-DDTHH:MM:SSZ"')

    return FileResult(path, not errors, tuple(errors))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--schema", default="schemas/task_loop.schema.json")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    schema_path = Path(args.schema).resolve()

    if not root.is_dir():
        eprint(f"Fail-Closed: ROOT not found: {root}")
        return 2

    if not schema_path.is_file():
        eprint(f"Fail-Closed: schema not found: {schema_path}")
        return 3

    with schema_path.open() as f:
        schema = json.load(f)

    files = find_task_loops(root)
    if not files:
        eprint("Fail-Closed: no TASK_LOOP.yaml found")
        return 4

    validator = Draft202012Validator(schema)
    bad = []

    for p in files:
        r = validate_one(p, validator)
        if not r.ok:
            bad.append(r)

    if bad:
        for r in bad:
            print(f"❌ {r.path}")
            for e in r.errors:
                print(f"  - {e}")
        return 1

    for p in files:
        print(f"✅ {p}")

    print("OK: TASK_LOOP validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
