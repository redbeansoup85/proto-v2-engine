#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path
from typing import Any, Dict, List

def die(msg: str) -> None:
    raise SystemExit(f"[FAIL-CLOSED] {msg}")

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return "sha256:" + h.hexdigest()

def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        die(f"missing registry file: {path}")
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception as e:
            die(f"{path} line {i}: invalid json ({e})")
        if not isinstance(obj, dict):
            die(f"{path} line {i}: must be object")
        out.append(obj)
    return out

def dump_jsonl(items: List[Dict[str, Any]]) -> str:
    return "\n".join(
        json.dumps(x, ensure_ascii=False, separators=(",", ":"))
        for x in items
    ) + "\n"

def patch_registry(reg: Path, base: Path) -> bool:
    items = load_jsonl(reg)
    changed = False
    for obj in items:
        rel = obj.get("path")
        if not isinstance(rel, str):
            continue
        target = (base / rel).resolve()
        if not target.exists():
            die(f"{reg}: missing target file for path={rel}")
        h = sha256_file(target)
        if obj.get("sha256") != h:
            obj["sha256"] = h
            changed = True
    if changed:
        reg.write_text(dump_jsonl(items), encoding="utf-8")
    return changed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("registries", nargs="+")
    ap.add_argument("--base", required=True)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    if not args.write:
        die("must pass --write (fail-closed)")

    base = Path(args.base)
    if not base.exists():
        die(f"base dir missing: {base}")

    any_changed = False
    for r in args.registries:
        any_changed |= patch_registry(Path(r), base)

    if any_changed:
        print("[PATCHED] registry hashes updated")
    else:
        print("[OK] registry hashes already up to date")

if __name__ == "__main__":
    main()
