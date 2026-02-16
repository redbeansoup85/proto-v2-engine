from __future__ import annotations

from pathlib import Path

import tools.lock4_replay_store as replay_store


def test_replay_store_rejects_path_outside_var_security(tmp_path: Path) -> None:
    fp = "0" * 64
    try:
        replay_store.record_fingerprint(tmp_path / "replay.jsonl", fp)
        assert False, "expected ReplayStoreError"
    except replay_store.ReplayStoreError:
        pass


def test_replay_store_records_and_rejects_duplicate(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    store_dir = repo_root / "var" / "security"
    store_dir.mkdir(parents=True, exist_ok=True)
    store = store_dir / "replay_store_test.jsonl"
    if store.exists():
        store.unlink()

    fp = "a" * 64
    ok1, msg1 = replay_store.record_fingerprint(store, fp)
    assert ok1 is True
    assert msg1 == "recorded"

    ok2, msg2 = replay_store.record_fingerprint(store, fp)
    assert ok2 is False
    assert msg2 == "replay detected"

    store.unlink(missing_ok=True)
