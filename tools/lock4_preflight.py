#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple


class PreflightError(Exception):
    pass


def _find_repo_root(start: Path) -> Optional[Path]:
    current = start.resolve()
    for _ in range(100):
        git_dir = current / ".git"
        if git_dir.exists():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


def _as_int(value: Optional[str], default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _load_keyring(path: Path) -> Tuple[bool, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return False, f"keyring unreadable: {exc}"
    if not isinstance(data, dict):
        return False, "keyring must be a JSON object"
    if "keys" not in data:
        return False, "keyring missing 'keys'"
    if not isinstance(data["keys"], (list, dict)):
        return False, "keyring 'keys' must be list or dict"
    return True, "ok"


def _format_missing(items: List[str]) -> str:
    return ", ".join(items) if items else "none"


def run_preflight(argv: Optional[List[str]] = None) -> Tuple[int, Dict[str, Any], List[str]]:
    ap = argparse.ArgumentParser(description="LOCK-4 preflight (read-only)")
    ap.add_argument("--mode", choices=["warn", "enforce"], default=None)
    ap.add_argument("--clock-skew-seconds", type=int, default=None)
    ap.add_argument("--actor-id", default=None)
    ap.add_argument("--key-id", default=None)
    ap.add_argument("--signing-key-path", default=None)
    ap.add_argument("--keyring-path", default=None)
    ap.add_argument("--replay-db-path", default=None)
    ap.add_argument("--writer", action="store_true")
    ap.add_argument("--verifier", action="store_true")

    args = ap.parse_args(argv)

    mode = args.mode or os.getenv("LOCK4_SIG_MODE") or "warn"
    if mode not in ("warn", "enforce"):
        raise PreflightError("invalid mode; must be warn or enforce")

    clock_skew = args.clock_skew_seconds
    if clock_skew is None:
        clock_skew = _as_int(os.getenv("LOCK4_CLOCK_SKEW_SECONDS"), 300)
    if clock_skew < 0:
        raise PreflightError("clock skew must be >= 0")

    check_writer = args.writer or not args.verifier
    check_verifier = args.verifier or not args.writer

    repo_root = _find_repo_root(Path.cwd())
    repo_root_str = str(repo_root) if repo_root else None

    warnings: List[str] = []
    errors: List[str] = []

    report: Dict[str, Any] = {
        "mode": mode,
        "clock_skew_seconds": clock_skew,
        "writer": {"status": "SKIP", "missing": []},
        "verifier": {"status": "SKIP", "missing": []},
        "paths": {
            "signing_key": None,
            "keyring": None,
            "replay_db": None,
        },
    }

    def add_issue(target: str, msg: str) -> None:
        if mode == "enforce":
            errors.append(msg)
            report[target]["status"] = "FAIL"
        else:
            warnings.append(msg)
            report[target]["status"] = "WARN"

    if check_writer:
        report["writer"]["status"] = "OK"
        missing: List[str] = []

        actor_id = args.actor_id or os.getenv("LOCK4_ACTOR_ID")
        key_id = args.key_id or os.getenv("LOCK4_KEY_ID")
        signing_key_path = args.signing_key_path or os.getenv("LOCK4_SIGNING_KEY_PATH")
        report["paths"]["signing_key"] = signing_key_path

        if not actor_id:
            missing.append("actor_id")
        if not key_id:
            missing.append("key_id")
        if not signing_key_path:
            missing.append("signing_key_path")

        if missing:
            report["writer"]["missing"] = missing
            add_issue("writer", f"writer missing: {_format_missing(missing)}")
        else:
            path = Path(signing_key_path)
            if not path.is_absolute():
                add_issue("writer", "signing key path must be absolute")
            elif not path.exists() or not path.is_file():
                add_issue("writer", "signing key path does not exist or is not a file")
            else:
                if repo_root_str and str(path.resolve()).startswith(repo_root_str + os.sep):
                    add_issue("writer", "signing key path must be outside repo")
                if "/Desktop/meta-os/" in str(path):
                    add_issue("writer", "signing key path must not be under /Desktop/meta-os/")

    if check_verifier:
        report["verifier"]["status"] = "OK"
        missing_v: List[str] = []

        keyring_path = args.keyring_path or os.getenv("LOCK4_KEYRING_PATH")
        replay_db_path = args.replay_db_path or os.getenv("LOCK4_REPLAY_DB_PATH")
        report["paths"]["keyring"] = keyring_path
        report["paths"]["replay_db"] = replay_db_path

        if not keyring_path:
            missing_v.append("keyring_path")
        if mode == "enforce" and not replay_db_path:
            missing_v.append("replay_db_path")
        if missing_v:
            report["verifier"]["missing"] = missing_v
            add_issue("verifier", f"verifier missing: {_format_missing(missing_v)}")
        else:
            if keyring_path:
                kp = Path(keyring_path)
                if not kp.is_absolute():
                    add_issue("verifier", "keyring path must be absolute")
                elif not kp.exists() or not kp.is_file():
                    add_issue("verifier", "keyring path does not exist or is not a file")
                else:
                    ok, msg = _load_keyring(kp)
                    if not ok:
                        add_issue("verifier", msg)
            if replay_db_path:
                rp = Path(replay_db_path)
                if not rp.is_absolute():
                    add_issue("verifier", "replay db path must be absolute")
                else:
                    parent = rp.parent
                    if not parent.exists() or not parent.is_dir():
                        add_issue("verifier", "replay db directory does not exist")

    lines = [
        f"MODE={mode}",
        f"CLOCK_SKEW_SECONDS={clock_skew}",
        f"WRITER={report['writer']['status']} missing={_format_missing(report['writer'].get('missing', []))}",
        f"VERIFIER={report['verifier']['status']} missing={_format_missing(report['verifier'].get('missing', []))}",
        f"PATHS signing_key={report['paths']['signing_key']} keyring={report['paths']['keyring']} replay_db={report['paths']['replay_db']}",
    ]

    if errors:
        return 10, report, lines
    if warnings:
        return 2, report, lines
    return 0, report, lines


def main(argv: Optional[List[str]] = None) -> int:
    try:
        code, _report, lines = run_preflight(argv)
        for line in lines:
            print(line)
        return code
    except PreflightError as exc:
        print(f"ERROR: {exc}")
        return 10
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: unexpected failure: {exc}")
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
