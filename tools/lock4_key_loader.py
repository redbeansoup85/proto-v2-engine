#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple


class KeyLoaderError(RuntimeError):
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


def _load_keyring(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise KeyLoaderError(f"keyring unreadable: {exc}") from exc

    if not isinstance(data, dict):
        raise KeyLoaderError("keyring must be a JSON object")
    if "keys" not in data:
        raise KeyLoaderError("keyring missing 'keys'")
    if not isinstance(data["keys"], (list, dict)):
        raise KeyLoaderError("keyring 'keys' must be list or dict")
    return data


def _validate_path(path: Path, repo_root: Path | None) -> None:
    if not path.is_absolute():
        raise KeyLoaderError("keyring path must be absolute")
    if not path.exists() or not path.is_file():
        raise KeyLoaderError("keyring path does not exist or is not a file")
    if repo_root is not None:
        repo_root_str = str(repo_root.resolve())
        if str(path.resolve()).startswith(repo_root_str + os.sep):
            raise KeyLoaderError("keyring path must be outside repo")
    if "/Desktop/meta-os/" in str(path):
        raise KeyLoaderError("keyring path must not be under /Desktop/meta-os/")


def load_keyring(path: Path) -> Tuple[Dict[str, Any], int]:
    repo_root = _find_repo_root(Path.cwd())
    _validate_path(path, repo_root)
    data = _load_keyring(path)
    key_count = len(data["keys"]) if isinstance(data["keys"], list) else 0
    return data, key_count


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LOCK-4 keyring loader (read-only)")
    ap.add_argument("--keyring-path", default=None)
    args = ap.parse_args(argv)

    keyring_path = args.keyring_path or os.getenv("LOCK4_KEYRING_PATH")
    if not keyring_path:
        print("ERROR: keyring path missing")
        return 1

    try:
        data, key_count = load_keyring(Path(keyring_path))
        print(
            json.dumps(
                {
                    "ok": True,
                    "keyring_path": keyring_path,
                    "keys_count": key_count,
                    "keys_type": "list" if isinstance(data.get("keys"), list) else "dict",
                }
            )
        )
        return 0
    except KeyLoaderError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "keyring_path": keyring_path}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
