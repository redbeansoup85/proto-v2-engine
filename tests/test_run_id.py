from __future__ import annotations

from tools.run_id import compute_config_sha, make_run_id


def test_make_run_id_format() -> None:
    ts = "2026-02-19T00:00:00Z"
    git_sha = "deadbeef"
    config_sha = "0123456789abcdef"
    assert make_run_id(ts, git_sha, config_sha) == "2026-02-19T00:00:00Z_deadbeef_01234567"


def test_compute_config_sha_deterministic() -> None:
    payload = {"b": 2, "a": 1}
    s1 = compute_config_sha(payload)
    s2 = compute_config_sha({"a": 1, "b": 2})
    assert s1 == s2
