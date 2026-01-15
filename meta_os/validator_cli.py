from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Optional

from meta_os.validators.vault_io import (
    VAULT_ROOT,
    utc_now,
    read_json,
    write_json_atomic,
    find_latest_complete_run,
    exception_output_path,
    schema_registry_path,
)
from meta_os.validators.rules import validate_run_documents

from vault.schemas_py.exception import ExceptionReport


def load_schema_registry_or_fail() -> Dict[str, Any]:
    p = schema_registry_path()
    if not p.exists():
        raise RuntimeError(f"schema_registry.json not found at {p}")
    return read_json(p)


def scan_run(run_id: str, strict_context: bool) -> int:
    """
    Returns exit code:
      0 = OK (no hard fail)
      2 = HARD_FAIL detected (exception report written)
      3 = operational error (missing files, etc.)
    """
    _ = load_schema_registry_or_fail()  # 존재 확인

    entry = find_latest_complete_run(run_id)
    if not entry:
        print(f"[ERROR] run_id not found in runs_index: {run_id}")
        return 3

    exec_path = Path(entry.get("exec_path", ""))
    outcome_path = Path(entry.get("outcome_path", ""))

    if not exec_path.exists():
        print(f"[ERROR] execution file missing: {exec_path}")
        return 3
    if not outcome_path.exists():
        print(f"[ERROR] outcome file missing: {outcome_path}")
        return 3

    exec_doc = read_json(exec_path)
    outcome_doc = read_json(outcome_path)

    # context resolve (optional)
    context_doc: Optional[Dict[str, Any]] = None
    context_id = None
    try:
        context_id = exec_doc.get("run", {}).get("context_id")
    except Exception:
        context_id = None

    if context_id:
        ctx_root = VAULT_ROOT / "contexts"
        if ctx_root.exists():
            matches = list(ctx_root.rglob(f"context_{context_id}.json"))
            if matches:
                context_doc = read_json(matches[0])
            elif strict_context:
                print(f"[ERROR] strict_context enabled but context not found: {context_id}")
                return 3
        elif strict_context:
            print(f"[ERROR] strict_context enabled but contexts/ folder missing")
            return 3

    findings = validate_run_documents(exec_doc, outcome_doc, context_doc=context_doc)

    hard_fails = [f for f in findings if f.severity == "HARD_FAIL"]
    warnings = [f for f in findings if f.severity == "WARNING"]

    if warnings:
        print("[WARNINGS]")
        for w in warnings:
            print(f" - {w.code}: {w.message}")

    if not hard_fails:
        print(f"[OK] run_id={run_id} passed (no hard fails)")
        return 0

    # exception_report 기록
    now = utc_now()
    hf = hard_fails[0]

    report = ExceptionReport(
        id=f"exception_{run_id}__{hf.code}",
        ts=now,
        producer={"system": "meta_os", "module": "validator", "instance": "meta-1"},
        run_id=run_id,
        severity="HARD_FAIL",
        code=hf.code,
        message=hf.message,
        evidence={
            "exec_path": str(exec_path),
            "outcome_path": str(outcome_path),
            "context_id": context_id,
            "finding": hf.evidence,
            "all_hard_fails": [{"code": f.code, "message": f.message, "evidence": f.evidence} for f in hard_fails],
            "warnings": [{"code": f.code, "message": f.message, "evidence": f.evidence} for f in warnings],
        },
    )

    out_path = exception_output_path(run_id, hf.code, now)
    write_json_atomic(out_path, report.model_dump(mode="json"))

    print(f"[HARD_FAIL] run_id={run_id} code={hf.code}")
    print(f"  -> exception_report written: {out_path}")
    return 2


def main():
    parser = argparse.ArgumentParser(prog="meta_validator", description="Meta OS Read-only Validator (v0.1)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="scan a run_id from Vault and emit exception_report on hard fail")
    scan.add_argument("--run-id", required=True)
    scan.add_argument("--strict-context", action="store_true", help="fail if context_id is present but context file missing")

    args = parser.parse_args()

    if args.cmd == "scan":
        code = scan_run(args.run_id, strict_context=args.strict_context)
        raise SystemExit(code)


if __name__ == "__main__":
    main()
