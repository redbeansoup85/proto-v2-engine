#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tools.audit.observer_hasher import hash_event as _hash_event  # <-- tests use this


@dataclass(frozen=True)
class Finding:
    rule_id: str
    file: str
    line: int
    pattern: str
    snippet: str


# ---------------- helpers ----------------

def _snippet(s: str, limit: int = 240) -> str:
    s = s.strip("\n")
    if len(s) <= limit:
        return s
    return s[:limit] + "…"


def _load_jsonl(path: Path) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            out.append((idx, line.rstrip("\n")))
    return out


def hash_event(prev_hash: str, obj: dict) -> str:
    """
    MUST match tests:
    tests import hash_event from tools.audit.observer_hasher.
    Also tests compute hash on an object that does NOT yet include 'hash'.
    """
    if not isinstance(obj, dict):
        raise ValueError("obj must be dict")
    data = dict(obj)
    data.pop("hash", None)
    return _hash_event(prev_hash, data)


# ---------------- schema ----------------

_ALLOWED_STATUS = {"started", "ok", "fail"}
_ALLOWED_METRIC_KEYS = {"latency_ms"}


def _validate_observer_schema(obj: dict) -> Optional[str]:
    required = [
        "schema_version",
        "event_id",
        "ts",
        "judgment_id",
        "approval_record_id",
        "execution_run_id",
        "status",
        "metrics",
        "prev_hash",
        "hash",
    ]
    for k in required:
        if k not in obj:
            return f"missing_key:{k}"

    for k in [
        "schema_version",
        "event_id",
        "ts",
        "judgment_id",
        "approval_record_id",
        "execution_run_id",
        "prev_hash",
        "hash",
    ]:
        if not isinstance(obj[k], str) or obj[k] == "":
            return f"invalid:{k}"

    if obj["status"] not in _ALLOWED_STATUS:
        return "invalid:status"

    if not isinstance(obj["metrics"], dict):
        return "invalid:metrics"

    for mk, mv in obj["metrics"].items():
        if mk not in _ALLOWED_METRIC_KEYS:
            return f"invalid:metric_key:{mk}"
        if not isinstance(mv, (int, float)):
            return f"invalid:metric_value:{mk}"

    return None


def _is_safe_relpath(p: str) -> bool:
    if p.startswith("/") or p.startswith("~"):
        return False
    if ".." in Path(p).parts:
        return False
    return True


def _validate_replay_schema(item: dict) -> Tuple[Optional[str], Optional[str]]:
    required = [
        "schema_version",
        "packet_id",
        "ts",
        "judgment_id",
        "approval_record_id",
        "execution_run_id",
        "inputs_digest",
        "artifacts",
        "prev_hash",
        "hash",
    ]
    for k in required:
        if k not in item:
            return f"missing_key:{k}", "LOCK3_SCHEMA_INVALID"

    if not isinstance(item["artifacts"], list):
        return "invalid:artifacts", "LOCK3_SCHEMA_INVALID"

    for idx, a in enumerate(item["artifacts"], start=1):
        if not isinstance(a, dict):
            return f"invalid:artifact:{idx}", "LOCK3_SCHEMA_INVALID"
        if "path" not in a or "kind" not in a:
            return f"missing_key:artifact:{idx}", "LOCK3_SCHEMA_INVALID"
        if not isinstance(a["path"], str) or a["path"] == "":
            return f"invalid:artifact_path:{idx}", "LOCK3_SCHEMA_INVALID"
        if not _is_safe_relpath(a["path"]):
            return (
                f"artifact_path_traversal:{a['path']}",
                "LOCK3_ARTIFACT_PATH_INVALID",
            )

    return None, None


# ---------------- core gate ----------------

def run_observer_gate(
    *,
    path: Path,
    replay_path: Optional[Path] = None,
) -> Tuple[int, List[Finding]]:
    findings: List[Finding] = []

    if not path.exists():
        findings.append(Finding("LOCK3_PARSE_ERROR", str(path), 1, "missing_file", ""))
        return 1, findings

    try:
        lines = _load_jsonl(path)
    except Exception as exc:  # noqa: BLE001
        findings.append(Finding("LOCK3_PARSE_ERROR", str(path), 1, "read", str(exc)))
        return 1, findings

    prev_hash_seen: Optional[str] = None
    link_map: Dict[str, Tuple[str, str]] = {}

    for lineno, line in lines:
        if line.strip() == "":
            continue

        try:
            obj = json.loads(line)
        except Exception:  # noqa: BLE001
            findings.append(Finding("LOCK3_PARSE_ERROR", str(path), lineno, "json", _snippet(line)))
            continue

        if not isinstance(obj, dict):
            findings.append(Finding("LOCK3_SCHEMA_INVALID", str(path), lineno, "type", ""))
            continue

        err = _validate_observer_schema(obj)
        if err:
            findings.append(Finding("LOCK3_SCHEMA_INVALID", str(path), lineno, err, _snippet(line)))
            continue

        computed = hash_event(obj["prev_hash"], obj)
        if computed != obj["hash"]:
            findings.append(Finding("LOCK3_CHAIN_BROKEN", str(path), lineno, "hash_mismatch", ""))
            continue

        if prev_hash_seen is not None and obj["prev_hash"] != prev_hash_seen:
            findings.append(Finding("LOCK3_CHAIN_BROKEN", str(path), lineno, "prev_hash_mismatch", ""))
            continue

        prev_hash_seen = obj["hash"]

        run_id = obj["execution_run_id"]
        link = (obj["judgment_id"], obj["approval_record_id"])
        if run_id in link_map and link_map[run_id] != link:
            findings.append(Finding("LOCK3_LINK_MISMATCH", str(path), lineno, "link", ""))
            continue
        link_map[run_id] = link

    # replay checks (fail-closed)
    if replay_path is not None:
        if not replay_path.exists():
            findings.append(Finding("LOCK3_PARSE_ERROR", str(replay_path), 1, "missing_file", ""))
            return 1, findings

        # Empty replay file is valid (0 packets)
        try:
            if replay_path.stat().st_size == 0:
                replay_obj = []
            else:
                replay_obj = None
        except Exception as exc:  # noqa: BLE001
            findings.append(Finding("LOCK3_PARSE_ERROR", str(replay_path), 1, "stat", str(exc)))
            return 1, findings

        if replay_obj is None:
            try:
                replay_obj = json.loads(replay_path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                findings.append(Finding("LOCK3_PARSE_ERROR", str(replay_path), 1, "json", str(exc)))
                return 1, findings

        items = replay_obj if isinstance(replay_obj, list) else [replay_obj]
        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                findings.append(Finding("LOCK3_SCHEMA_INVALID", str(replay_path), idx, "type", ""))
                continue
            err, rid = _validate_replay_schema(item)
            if err:
                findings.append(Finding(rid or "LOCK3_SCHEMA_INVALID", str(replay_path), idx, err, ""))

    if findings:
        return 1, findings
    return 0, []


# ---------------- CLI envelope v1 ----------------

def _emit_gate_findings_v1(gate: str, status: str, findings: List[Finding]) -> None:
    payload = {
        "gate": gate,
        "version": "v1",
        "status": status,
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": "ERROR",
                "file": f.file,
                "line": f.line,
                "message": f.pattern or "violation",
                "evidence": f.snippet,
            }
            for f in findings
        ],
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="LOCK-3 Observer Gate (Fail-Closed)")
    ap.add_argument("--path", action="append", required=True, help="Path to observer event jsonl")
    ap.add_argument("--replay", required=False, help="Optional replay packet json")
    args = ap.parse_args(argv)

    all_findings: List[Finding] = []
    code = 0
    for p in args.path:
        rc, fs = run_observer_gate(
            path=Path(p),
            replay_path=Path(args.replay) if args.replay else None,
        )
        if rc != 0:
            code = 1
        all_findings.extend(fs)

    if code != 0:
        _emit_gate_findings_v1("lock3_observer_gate", "FAIL", all_findings)
        return 1

    _emit_gate_findings_v1("lock3_observer_gate", "PASS", [])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
