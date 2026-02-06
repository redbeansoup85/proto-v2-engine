from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.audit.observer_hasher import hash_event


HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
ARTIFACT_PATH_RE = re.compile(r"^(?!/)(?!.*://)(?!.*\.\.)([A-Za-z0-9._\-/]+)$")


@dataclass(frozen=True)
class Finding:
    rule_id: str
    file: str
    line: int
    pattern: str
    snippet: str


def _snippet(line: str) -> str:
    return line.strip()[:240]


def _findings_to_lines(findings: List[Finding]) -> List[str]:
    lines = []
    for f in findings:
        lines.append(
            f"FAIL {f.file}:{f.line} rule_id={f.rule_id} pattern={f.pattern} snippet={f.snippet}"
        )
    return lines


def _validate_observer_schema(obj: Dict[str, Any]) -> Optional[str]:
    required = {
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
    }
    allowed = required
    missing = [k for k in required if k not in obj]
    if missing:
        return f"missing required fields {missing}"
    extras = [k for k in obj if k not in allowed]
    if extras:
        return f"unexpected fields {extras}"

    if obj.get("schema_version") != "lock3/observer_event@1.0":
        return "schema_version mismatch"
    if obj.get("status") not in {"started", "ok", "fail", "aborted"}:
        return "status enum mismatch"
    for key in ("event_id", "ts", "judgment_id", "approval_record_id", "execution_run_id"):
        if not isinstance(obj.get(key), str) or not obj.get(key):
            return f"{key} invalid"
    if not isinstance(obj.get("metrics"), dict):
        return "metrics must be object"
    metrics = obj.get("metrics", {})
    allowed_metrics = {"latency_ms", "risk_flags", "notes"}
    extra_metrics = [k for k in metrics if k not in allowed_metrics]
    if extra_metrics:
        return f"metrics unexpected fields {extra_metrics}"
    if "latency_ms" in metrics and (not isinstance(metrics["latency_ms"], int) or metrics["latency_ms"] < 0):
        return "metrics.latency_ms invalid"
    if "risk_flags" in metrics:
        if not isinstance(metrics["risk_flags"], list):
            return "metrics.risk_flags invalid"
        for item in metrics["risk_flags"]:
            if not isinstance(item, str) or not item:
                return "metrics.risk_flags invalid"
    if "notes" in metrics and (not isinstance(metrics["notes"], str) or len(metrics["notes"]) > 500):
        return "metrics.notes invalid"

    for key in ("prev_hash", "hash"):
        if not isinstance(obj.get(key), str) or not HEX64_RE.fullmatch(obj[key]):
            return f"{key} invalid"
    return None


def _validate_replay_schema(obj: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    required = {
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
    }
    allowed = required
    missing = [k for k in required if k not in obj]
    if missing:
        return f"missing required fields {missing}", None
    extras = [k for k in obj if k not in allowed]
    if extras:
        return f"unexpected fields {extras}", None

    if obj.get("schema_version") != "lock3/replay_packet@1.0":
        return "schema_version mismatch", None
    for key in ("packet_id", "ts", "judgment_id", "approval_record_id", "execution_run_id"):
        if not isinstance(obj.get(key), str) or not obj.get(key):
            return f"{key} invalid", None
    if not isinstance(obj.get("inputs_digest"), str) or not HEX64_RE.fullmatch(obj["inputs_digest"]):
        return "inputs_digest invalid", None
    if not isinstance(obj.get("artifacts"), list):
        return "artifacts invalid", None
    for item in obj["artifacts"]:
        if not isinstance(item, dict):
            return "artifacts item invalid", None
        if "path" not in item or "kind" not in item:
            return "artifacts missing required fields", None
        if not isinstance(item["path"], str) or not item["path"]:
            return "artifacts.path invalid", "LOCK3_ARTIFACT_PATH_INVALID"
        if not ARTIFACT_PATH_RE.fullmatch(item["path"]):
            return "artifacts.path invalid", "LOCK3_ARTIFACT_PATH_INVALID"
        if item.get("kind") not in {"card", "policy", "contract", "log", "other"}:
            return "artifacts.kind invalid", None
        if "digest" in item:
            if not isinstance(item["digest"], str) or not HEX64_RE.fullmatch(item["digest"]):
                return "artifacts.digest invalid", None
    for key in ("prev_hash", "hash"):
        if not isinstance(obj.get(key), str) or not HEX64_RE.fullmatch(obj[key]):
            return f"{key} invalid", None
    return None, None


def _load_jsonl(path: Path) -> List[Tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"read error: {exc}") from exc
    lines = text.splitlines()
    return list(enumerate(lines, start=1))


def run_observer_gate(
    *,
    path: Path,
    replay_path: Optional[Path] = None,
) -> Tuple[int, List[Finding]]:
    findings: List[Finding] = []

    try:
        lines = _load_jsonl(path)
    except ValueError as exc:
        findings.append(Finding("LOCK3_PARSE_ERROR", str(path), 1, "read", str(exc)))
        return 1, findings

    prev_hash: Optional[str] = None
    link_map: Dict[str, Tuple[str, str]] = {}

    for lineno, line in lines:
        if line.strip() == "":
            findings.append(Finding("LOCK3_PARSE_ERROR", str(path), lineno, "blank_line", ""))
            continue
        try:
            obj = json.loads(line)
        except Exception as exc:  # noqa: BLE001
            findings.append(Finding("LOCK3_PARSE_ERROR", str(path), lineno, "json", _snippet(line)))
            continue
        if not isinstance(obj, dict):
            findings.append(Finding("LOCK3_SCHEMA_INVALID", str(path), lineno, "type", _snippet(line)))
            continue
        err = _validate_observer_schema(obj)
        if err:
            findings.append(Finding("LOCK3_SCHEMA_INVALID", str(path), lineno, err, _snippet(line)))
            continue

        computed = hash_event(obj["prev_hash"], {k: v for k, v in obj.items()})
        if computed != obj["hash"]:
            findings.append(Finding("LOCK3_CHAIN_BROKEN", str(path), lineno, "hash_mismatch", _snippet(line)))
            continue
        if prev_hash is not None and obj["prev_hash"] != prev_hash:
            findings.append(Finding("LOCK3_CHAIN_BROKEN", str(path), lineno, "prev_hash_mismatch", _snippet(line)))
            continue

        prev_hash = obj["hash"]
        run_id = obj["execution_run_id"]
        current = (obj["judgment_id"], obj["approval_record_id"])
        if run_id in link_map and link_map[run_id] != current:
            findings.append(Finding("LOCK3_LINK_MISMATCH", str(path), lineno, "link", _snippet(line)))
            continue
        link_map[run_id] = current

    if replay_path is not None:
        try:
            replay_text = replay_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            findings.append(Finding("LOCK3_PARSE_ERROR", str(replay_path), 1, "read", str(exc)))
            return 1, findings
        if replay_text.strip() == "":
            findings.append(Finding("LOCK3_PARSE_ERROR", str(replay_path), 1, "blank_line", ""))
            return 1, findings
        try:
            replay_obj = json.loads(replay_text)
        except Exception:  # noqa: BLE001
            findings.append(Finding("LOCK3_PARSE_ERROR", str(replay_path), 1, "json", _snippet(replay_text)))
            return 1, findings
        if isinstance(replay_obj, list):
            replay_items = replay_obj
        else:
            replay_items = [replay_obj]
        for idx, item in enumerate(replay_items, start=1):
            if not isinstance(item, dict):
                findings.append(Finding("LOCK3_SCHEMA_INVALID", str(replay_path), idx, "type", ""))
                continue
            err, rule = _validate_replay_schema(item)
            if err:
                rid = rule or "LOCK3_SCHEMA_INVALID"
                findings.append(Finding(rid, str(replay_path), idx, err, ""))

    if findings:
        return 1, findings
    return 0, []


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="LOCK-3 Observer Gate (Fail-Closed)")
    ap.add_argument("--path", required=True, help="Path to observer event jsonl")
    ap.add_argument("--replay", required=False, help="Optional replay packet json/jsonl")
    args = ap.parse_args(argv)

    code, findings = run_observer_gate(
        path=Path(args.path),
        replay_path=Path(args.replay) if args.replay else None,
    )
    if findings:
        for line in _findings_to_lines(findings):
            print(line)
        summary = {
            "status": "FAIL",
            "gate": "lock3_observer_gate",
            "findings": len(findings),
            "violations": [f.__dict__ for f in findings],
        }
        print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
        return 1

    print(json.dumps({"status": "PASS", "gate": "lock3_observer_gate", "findings": 0}, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
