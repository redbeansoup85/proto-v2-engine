#!/usr/bin/env python3
import json
import hashlib
import sys
from pathlib import Path
from typing import Any, Dict, Optional

def _scrub(obj: Any) -> Any:
    """Remove volatile fields & normalize path-like values for stable digests."""
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            lk = k.lower()

            # Drop volatile keys
            if lk in {
                "ts","timestamp","created_at","createdat","updated_at","updatedat",
                "generated_at","generatedat","run_id","runid","github_run_id",
                "tmp_base","tmpbase","base_dir","basedir",
            }:
                continue

            if lk in {"record_hash","prev_hash","payload_hash"}:
                continue

            # Drop path-ish keys entirely
            if lk.endswith("_path") or lk.endswith("path"):
                continue

            out[k] = _scrub(v)
        return out

    if isinstance(obj, list):
        return [_scrub(x) for x in obj]

    if isinstance(obj, str):
        # normalize temp/abs paths wherever they appear
        if obj.startswith("/tmp/"):
            return "<TMP_PATH>"
        if "/tmp/" in obj:
            return obj.replace("/tmp/", "<TMP>/")
        if obj.startswith("/home/runner/") or obj.startswith("/Users/"):
            return "<ABS_PATH>"
        return obj

    return obj


def digest_json_file(path: str) -> str:
    p = Path(path)
    data = p.read_text(encoding="utf-8")
    j = json.loads(data)
    j2 = _scrub(j)
    b = json.dumps(j2, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def _parse_value(line: str) -> str:
    return line.split("=", 1)[1].strip()


def main():
    if len(sys.argv) != 3:
        print("usage: build_lock_report.py <ci_lock_report.txt> <out.json>", file=sys.stderr)
        raise SystemExit(2)

    report_path = sys.argv[1]
    out_path = sys.argv[2]
    lines = Path(report_path).read_text(encoding="utf-8", errors="replace").splitlines()

    fields: Dict[str, Any] = {"schema": "metaos_lock_report.v1"}

    # Stable values already printed by CI
    for line in lines:
        s = line.strip()
        if s.startswith("A.policy_sha256 ="):
            fields["policy_sha256"] = _parse_value(s)
        if s.startswith("A.policy_capsule.digest ="):
            fields["policy_capsule_digest"] = _parse_value(s)

    # Artifact paths
    paths: Dict[str, Optional[str]] = {
        "gate_same": None,
        "plan": None,
        "queue": None,
        "processed": None,
        "inbox": None,
        "decision": None,
        "outbox_item": None,
    }

    for line in lines:
        s = line.strip()

        # gate_same (allow flexible path)
        if "gate_same_1.json" in s and s.startswith("OK: wrote"):
            parts = s.split("OK: wrote", 1)
            if len(parts) == 2:
                paths["gate_same"] = parts[1].strip()

        if s.startswith("plan1 ="):
            paths["plan"] = _parse_value(s)

        if s.startswith("queue1="):
            paths["queue"] = _parse_value(s)

        if s.startswith("processed1 ="):
            paths["processed"] = _parse_value(s)

        if s.startswith("inbox1 ="):
            paths["inbox"] = _parse_value(s)

        if s.startswith("dec1 ="):
            paths["decision"] = _parse_value(s)

        if s.startswith("item1 ="):
            paths["outbox_item"] = _parse_value(s)

    # Fail-closed if any expected artifact path missing
    missing_paths = [k for k, v in paths.items() if v is None]
    if missing_paths:
        raise SystemExit("FAIL-CLOSED: missing artifact paths in CI log: " + ", ".join(missing_paths))

    # Compute scrubbed digests
    fields["gate_same_digest"] = digest_json_file(paths["gate_same"])       # type: ignore[arg-type]
    fields["plan_digest"] = digest_json_file(paths["plan"])                 # type: ignore[arg-type]
    fields["queue_digest"] = digest_json_file(paths["queue"])               # type: ignore[arg-type]
    fields["processed_digest"] = digest_json_file(paths["processed"])       # type: ignore[arg-type]
    fields["orch_inbox_digest"] = digest_json_file(paths["inbox"])          # type: ignore[arg-type]
    fields["orch_decision_digest"] = digest_json_file(paths["decision"])    # type: ignore[arg-type]
    fields["outbox_item_digest"] = digest_json_file(paths["outbox_item"])   # type: ignore[arg-type]

    required = [
        "schema",
        "policy_sha256",
        "policy_capsule_digest",
        "gate_same_digest",
        "plan_digest",
        "queue_digest",
        "processed_digest",
        "orch_inbox_digest",
        "orch_decision_digest",
        "outbox_item_digest",
    ]

    missing = [k for k in required if k not in fields]
    if missing:
        raise SystemExit("FAIL-CLOSED: missing fields in lock report build: " + ", ".join(missing))

    Path(out_path).write_text(
        json.dumps(fields, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"OK: wrote {out_path}")


if __name__ == "__main__":
    main()
