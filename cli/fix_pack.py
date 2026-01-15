#!/usr/bin/env python3
"""
Fix Pack (E)
- scans Vault exceptions for HARD_FAILs in date or date range
- groups by (fail_code x card_id)
- prints concrete fix suggestions ("what to change")
- optionally writes a fix memo file under vault/manifests/fixpacks/
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VAULT_ROOT = Path("vault")
RUNS_INDEX = VAULT_ROOT / "manifests" / "runs_index.jsonl"


# ---------- time helpers ----------

def parse_ymd(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)

def utc_today_ymd() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def ymd_to_slash(ymd: str) -> str:
    return ymd.replace("-", "/")


# ---------- io helpers ----------

def safe_read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def parse_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


# ---------- card id helpers ----------

def is_valid_card_id(cid: Optional[str]) -> bool:
    if cid is None:
        return False
    c = str(cid).strip().lower()
    return bool(c) and c not in ("unknown", "...", "n/a")

def get_card_ids(exec_doc: Dict[str, Any]) -> Tuple[str, str]:
    run_meta = (exec_doc or {}).get("run", {}) or {}
    sid = str(run_meta.get("strategy_card_id", "unknown"))
    jid = str(run_meta.get("judgment_card_id", "unknown"))
    return sid, jid


# ---------- fix knowledge base ----------

FORBIDDEN_TERMS = [
    "recommend", "buy", "sell", "target", "entry", "exit", "bullish", "bearish",
    "long", "short", "go long", "go short",
]

def suggest_fix(code: str, evidence: Dict[str, Any]) -> List[str]:
    """
    Return concrete, actionable fix steps.
    """
    code = (code or "").strip().upper()
    ev = evidence or {}
    out: List[str] = []

    if code == "CONTEXT_FORBIDDEN_LANGUAGE":
        term = (ev.get("finding", {}) or {}).get("term") or ev.get("term")
        term = term or "unknown_term"
        out.append(f'컨텍스트(또는 카드 메모)에서 금지어 "{term}" 제거/치환')
        out.append('권장 문구 템플릿: "Context snapshot only. No directives."')
        out.append("금지어 리스트(기본): " + ", ".join(FORBIDDEN_TERMS))
        out.append("수정 후: tlog → vscan --strict-context 재실행")

    elif code in ("SCHEMA_REGISTRY_MISSING", "SCHEMA_UNKNOWN", "SCHEMA_VERSION_MISMATCH"):
        out.append("vault/manifests/schema_registry.json 확인/추가/버전 정렬")
        out.append("logger가 쓰는 schema.name/version이 registry와 1:1 매칭되는지 확인")
        out.append("수정 후: vscan 재실행")

    elif code in ("EXECUTION_MISSING", "OUTCOME_MISSING", "INDEX_MISSING"):
        out.append("runs_index.jsonl / executions / outcomes 경로 불일치 확인")
        out.append("부분 write 발생 시: logger 롤백/원자성(atomic) 로직 점검")
        out.append("수정 후: tlog 재실행")

    elif code in ("HASH_MISMATCH", "HASH_MISSING"):
        out.append("VaultBase hash 자동계산 로직 확인")
        out.append("파일을 수동 편집했다면: 재생성(tlog/opatch로 다시 쓰기) 권장")
        out.append("수정 후: vscan 재실행")

    elif code in ("VALIDATION_ERROR", "PYDANTIC_VALIDATION_ERROR"):
        out.append("스키마 필수필드 누락/타입 불일치")
        out.append("exception evidence에서 어떤 field가 깨졌는지 확인 후 입력값 보강")
        out.append("수정 후: 재생성(tlog/opatch)")

    else:
        out.append("해당 fail_code에 대한 자동 템플릿이 없음")
        out.append("exception_report.evidence를 보고 규칙 추가 권장 (rules.py / fix_pack KB)")

    return out


# ---------- scan logic ----------

def within_window(exec_path: str, d_from: datetime, d_to: datetime) -> bool:
    # exec_path contains /executions/YYYY/MM/DD/
    if "/executions/" not in exec_path:
        return False
    try:
        date_part = exec_path.split("/executions/")[1].split("/")[0:3]
        run_date = parse_ymd("-".join(date_part))
    except Exception:
        return False
    return d_from <= run_date <= d_to


def main() -> int:
    ap = argparse.ArgumentParser(description="Fix Pack: HARD_FAIL -> fix suggestions")
    ap.add_argument("--date", help="UTC date YYYY-MM-DD")
    ap.add_argument("--from", dest="from_", help="UTC from YYYY-MM-DD")
    ap.add_argument("--to", help="UTC to YYYY-MM-DD")
    ap.add_argument("--mode", choices=["strategy", "judgment", "both"], default="both")
    ap.add_argument("--include-unknown", action="store_true")
    ap.add_argument("--write-memo", action="store_true", help="Write a fix memo json under vault/manifests/fixpacks/")
    args = ap.parse_args()

    # date window
    if args.from_ or args.to:
        d_from = parse_ymd(args.from_ or args.to)
        d_to = parse_ymd(args.to or args.from_)
    else:
        d = parse_ymd(args.date or utc_today_ymd())
        d_from = d_to = d

    rows = parse_jsonl(RUNS_INDEX)

    # dedupe by run_id (keep last)
    by_run: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        run_id = r.get("run_id")
        exec_path = r.get("exec_path", "")
        if not run_id or not exec_path:
            continue
        if not within_window(exec_path, d_from, d_to):
            continue
        by_run[run_id] = r

    runs = list(by_run.values())

    # collect hard fails grouped by (code, card_id)
    # store examples for evidence
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for r in runs:
        run_id = r["run_id"]
        exec_path = r.get("exec_path", "")
        exec_doc = safe_read_json(Path(exec_path)) or {}
        sid, jid = get_card_ids(exec_doc)

        # determine date_path to look up exception
        # exec_path: .../executions/YYYY/MM/DD/exec_....
        try:
            part = exec_path.split("/executions/")[1].split("/")[0:3]
            date_path = "/".join(part)
        except Exception:
            continue

        # scan exceptions dir for this run_id (today folder)
        ex_dir = VAULT_ROOT / "exceptions" / date_path
        if not ex_dir.exists():
            continue

        ex_files = sorted(ex_dir.glob(f"exception_{run_id}__*.json"))
        if not ex_files:
            continue

        for p in ex_files:
            ex = safe_read_json(p)
            if not ex:
                continue
            if str(ex.get("severity", "")).upper() != "HARD_FAIL":
                continue
            code = str(ex.get("code", "UNKNOWN")).upper()
            evidence = (ex.get("evidence", {}) or {})
            finding = evidence.get("finding", {}) or {}
            term = finding.get("term")

            # pick card(s) per mode
            card_ids: List[str] = []
            if args.mode in ("strategy", "both"):
                if args.include_unknown or is_valid_card_id(sid):
                    card_ids.append(sid)
            if args.mode in ("judgment", "both"):
                if args.include_unknown or is_valid_card_id(jid):
                    card_ids.append(jid)

            for cid in card_ids:
                key = (code, cid)
                g = grouped.setdefault(key, {
                    "count": 0,
                    "example_run_ids": [],
                    "example_exception_paths": [],
                    "evidence_terms": {},
                    "sample_evidence": None,
                })
                g["count"] += 1
                if len(g["example_run_ids"]) < 5:
                    g["example_run_ids"].append(run_id)
                if len(g["example_exception_paths"]) < 5:
                    g["example_exception_paths"].append(str(p))
                if term:
                    g["evidence_terms"][term] = g["evidence_terms"].get(term, 0) + 1
                if g["sample_evidence"] is None:
                    g["sample_evidence"] = evidence

    # print
    window_str = f"{d_from.date()} → {d_to.date()}" if d_from != d_to else f"{d_from.date()}"
    print(f"🧰 Fix Pack — {window_str} (UTC)")
    print(f"HARD_FAIL groups: {len(grouped)}\n")

    if not grouped:
        print("No HARD_FAIL found in this window.")
        return 0

    # sort groups by count desc
    items = sorted(grouped.items(), key=lambda kv: kv[1]["count"], reverse=True)

    memo_obj = {
        "schema": {"name": "fix_pack", "version": "0.1.0"},
        "window": {"from": str(d_from.date()), "to": str(d_to.date())},
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "groups": [],
    }

    for (code, cid), g in items:
        print(f"== {cid}  ×  {code}  (n={g['count']})")
        if g["evidence_terms"]:
            top_terms = sorted(g["evidence_terms"].items(), key=lambda x: x[1], reverse=True)[:3]
            print("   evidence terms:", ", ".join([f"{t}:{n}" for t, n in top_terms]))

        steps = suggest_fix(code, g.get("sample_evidence") or {})
        for s in steps:
            print(" -", s)

        if g["example_exception_paths"]:
            print("   examples:")
            for p in g["example_exception_paths"][:3]:
                print("   -", p)

        print("")

        memo_obj["groups"].append({
            "card_id": cid,
            "code": code,
            "count": g["count"],
            "evidence_terms": g["evidence_terms"],
            "examples": g["example_exception_paths"],
            "suggestions": steps,
        })

    if args.write_memo:
        out_dir = VAULT_ROOT / "manifests" / "fixpacks"
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = f"fixpack_{str(d_from.date())}_{str(d_to.date())}.json"
        out_path = out_dir / fname
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(memo_obj, f, indent=2, ensure_ascii=False)
        print(f"📝 memo written: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

