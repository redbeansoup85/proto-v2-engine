from __future__ import annotations

import json
from pathlib import Path

import tools.lock4_key_loader as key_loader


def _write_keyring(path: Path) -> None:
    data = {"keys": [{"key_id": "k1", "actor_id": "a1", "public_key_pem": "pem", "alg": "ed25519"}]}
    path.write_text(json.dumps(data), encoding="utf-8")


def test_key_loader_requires_absolute_path(tmp_path: Path) -> None:
    rel = Path("relative.json")
    try:
        key_loader.load_keyring(rel)
        assert False, "expected KeyLoaderError"
    except key_loader.KeyLoaderError:
        pass


def test_key_loader_rejects_repo_path(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    key_path = repo_root / ".tmp_lock4_keyring.json"
    _write_keyring(key_path)
    try:
        key_loader.load_keyring(key_path)
        assert False, "expected KeyLoaderError"
    except key_loader.KeyLoaderError:
        pass
    finally:
        key_path.unlink(missing_ok=True)


def test_key_loader_ok_external_path(tmp_path: Path) -> None:
    key_path = tmp_path / "keyring.json"
    _write_keyring(key_path)
    data, key_count = key_loader.load_keyring(key_path)
    assert key_count == 1
    assert isinstance(data, dict)
