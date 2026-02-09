#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Tuple


class ReplayStoreError(RuntimeError):
    pass


def _find_repo_root(start: Path) -> Path | None:
    current = start.resolve()
    for _ in range(100):
        git_dir = current / ".git"
        if git_dir.exists():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_store_path(path: Path) -> None:
    repo_root = _find_repo_root(Path.cwd())
    if repo_root is None:
        raise ReplayStoreError("repo root not found")
    allowed_root = repo_root / "var" / "security"
    try:
        path.resolve().relative_to(allowed_root.resolve())
    except Exception as exc:  # noqa: BLE001
        raise ReplayStoreError("store path must be under var/security") from exc


def _normalize_fingerprint(fp: str) -> str:
    if not fp or len(fp) != 64:
        raise ReplayStoreError("fingerprint must be 64 hex chars")
    if any(c not in "0123456789abcdef" for c in fp.lower()):
        raise ReplayStoreError("fingerprint must be hex")
    return fp.lower()


def record_fingerprint(path: Path, fingerprint: str) -> Tuple[bool, str]:
    _validate_store_path(path)
    fp = _normalize_fingerprint(fingerprint)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception as exc:  # noqa: BLE001
                    raise ReplayStoreError(f"invalid jsonl line: {exc}") from exc
                if obj.get("fingerprint") == fp:
                    return False, "replay detected"

    record = {"fingerprint": fp, "ts": _utc_now_iso()}
    line = json.dumps(record, separators=(",", ":"), sort_keys=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())

    return True, "recorded"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LOCK-4 replay store (single-writer, append-only)")
    ap.add_argument("--path", required=True, help="Path to replay store jsonl (under var/security)")
    ap.add_argument("--fingerprint", required=True, help="64-hex fingerprint")
    args = ap.parse_args(argv)

    try:
        ok, msg = record_fingerprint(Path(args.path), args.fingerprint)
        if ok:
            print(json.dumps({"ok": True, "message": msg}))
            return 0
        print(json.dumps({"ok": False, "error": msg}))
        return 1
    except ReplayStoreError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
