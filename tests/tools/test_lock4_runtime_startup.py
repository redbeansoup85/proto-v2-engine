from __future__ import annotations

from types import SimpleNamespace

import infra.api.app as app


def test_resolve_mode_default_warn():
    assert app.resolve_lock4_sig_mode({}) == "warn"


def test_resolve_mode_enforce_without_promote_warn():
    env = {"LOCK4_SIG_MODE": "enforce"}
    assert app.resolve_lock4_sig_mode(env) == "warn"


def test_resolve_mode_enforce_with_promote_enforce():
    env = {"LOCK4_SIG_MODE": "enforce", "LOCK4_PROMOTE_ENFORCE": "1"}
    assert app.resolve_lock4_sig_mode(env) == "enforce"


def test_preflight_enforce_fail_fast(monkeypatch, tmp_path):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=10, stdout="fail", stderr="")

    monkeypatch.setattr(app.subprocess, "run", fake_run)
    code = app.run_lock4_preflight_or_die("enforce", tmp_path)
    assert code == 10


def test_preflight_warn_continues(monkeypatch, tmp_path):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=10, stdout="warn", stderr="")

    monkeypatch.setattr(app.subprocess, "run", fake_run)
    code = app.run_lock4_preflight_or_die("warn", tmp_path)
    assert code == 0
