#!/usr/bin/env python3
import json
import hashlib
import sys
from pathlib import Path
from typing import Any, Dict

def _scrub(obj: Any) -> Any:
    """
    Remove volatile fields and path-like values so digests are stable across:
    - different TMP_BASE (/tmp/metaos_ci_XXXX)
    - different runners / absolute paths
    - timestamps / run ids that may leak into artifacts
    """
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            lk = k.lower()

            # drop known volatile keys
            if lk in {
                "ts", "timestamp", "created_at", "createdat", "updated_at", "updatedat",
                "generated_at", "generatedat", "run_id", "runid", "github_run_id",
                "tmp_base", "tmpbase", "base_dir", "basedir"
            }:
                continue

            # drop any *_path keys (plan_path, queue_path, etc.)
            if lk.endswith("_path") or lk.endswith("path"):
                continue

            out[k] = _scrub(v)
        return out

    if isinstance(obj, list):
        return [_scrub(x) for x in obj]

    if isinstance(obj, str):
        # strip absolute tmp paths and other runner paths
        if obj.startswith("/tmp/"):
            return "<TMP_PATH>"
        if "/tmp/" in obj:
            return obj.replace("/tmp/", "<TMP>/")
        if obj.startswith("/home/runner/") or obj.startswith("/Users/"):
            return "<ABS_PATH>"
        return obj

    return obj

def digest_file(path: str) -> str:
    p = Path(path)
    data = p.read_bytes()

    # If it's JSON, canonicalize and scrub volatility
    if p.suffix.lower() == ".json":
        try:
            j = json.loads(data.decode("utf-8"))
            j2 = _scrub(j)
            b = json.dumps(j2, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            return hashlib.sha256(b).hexdigest()
        except Exception:
            # fallback: raw bytes digest
            pass

    return hashlib.sha256(data).hexdigest()

def main():
    if len(sys.argv) != 3:
        print("usage: build_lock_report.py <ci_lock_report.txt> <out.json>", file=sys.stderr)
        raise SystemExit(2)

    report_path = sys.argv[1]
    out_path = sys.argv[2]
    txt = Path(report_path).read_text(encoding="utf-8", errors="replace").splitlines()

    # Parse the CI log lines to find the artifact paths we already print in run_replay_stability.sh outputs.
    # We rely on the same markers that lock_report/verify_lock_report expect.
    fields: Dict[str, str] = {"schema": "metaos_lock_report.v1"}

    # Pull digests directly from log lines when available (preferred)
    for line in txt:
        line = line.strip()
        if line.startswith("same1.digest ="):
            fields["gate_same_digest"] = line.split("=",1)[1].strip()
        if line.startswith("plan.digest.1 ="):
            fields["plan_digest"] = line.split("=",1)[1].strip()
        if line.startswith("queue.digest.1 ="):
            # optional; not always snapshot-locked
            fields["queue_digest"] = line.split("=",1)[1].strip()
        if line.startswith("digest1 =") and "processed" in fields.get("_ctx",""):
            fields["processed_digest"] = line.split("=",1)[1].strip()
        if line.startswith("digest1 =") and "inbox" in fields.get("_ctx",""):
            fields["orch_inbox_digest"] = line.split("=",1)[1].strip()
        if line.startswith("digest1 =") and "orch decision" in fields.get("_ctx",""):
            fields["orch_decision_digest"] = line.split("=",1)[1].strip()
        if line.startswith("digest1 =") and "outbox" in fields.get("_ctx",""):
            fields["outbox_item_digest"] = line.split("=",1)[1].strip()

        # crude context switches
        if line.startswith("[CI] LOCK5"):
            fields["_ctx"] = "processed"
        if line.startswith("[CI] LOCK6"):
            fields["_ctx"] = "inbox"
        if line.startswith("[CI] LOCK7"):
            fields["_ctx"] = "orch decision"
        if line.startswith("[CI] LOCK8"):
            fields["_ctx"] = "outbox"

        if line.startswith("A.policy_sha256 ="):
            fields["policy_sha256"] = line.split("=",1)[1].strip()
        if line.startswith("A.policy_capsule.digest ="):
            fields["policy_capsule_digest"] = line.split("=",1)[1].strip()

    # Remove internal context key
    fields.pop("_ctx", None)

    # If any field missing, fail-closed so we don't silently create partial snapshots
    required = [
        "schema",
        "policy_sha256",
        "policy_capsule_digest",
        "gate_same_digest",
        "plan_digest",
        "processed_digest",
        "orch_inbox_digest",
        "orch_decision_digest",
        "outbox_item_digest",
    ]
    missing = [k for k in required if k not in fields]
    if missing:
        raise SystemExit("FAIL-CLOSED: missing fields in lock report build: " + ", ".join(missing))

    Path(out_path).write_text(json.dumps(fields, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OK: wrote {out_path}")

if __name__ == "__main__":
    main()
