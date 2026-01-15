from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault.schemas_py.registry import validate_schema

FORBIDDEN_KEYS_IN_EXEC = (
    "auto_execute",
    "autoTrade",
    "autotrade",
    "auto_execute_enabled",
)

FORBIDDEN_TERMS_IN_CONTEXT_TEXT = (
    "buy",
    "sell",
    "recommend",
    "target",
    "entry",
    "exit",
    "bullish",
    "bearish",
)

@dataclass
class Finding:
    severity: str   # "HARD_FAIL" | "WARNING"
    code: str
    message: str
    evidence: Dict[str, Any]

def _deep_contains_key(obj: Any, forbidden_keys: Tuple[str, ...]) -> Optional[str]:
    """
    dict/list 내부를 순회하며 금지 키가 존재하는지 검사.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k in forbidden_keys:
                return k
            hit = _deep_contains_key(v, forbidden_keys)
            if hit:
                return hit
    elif isinstance(obj, list):
        for it in obj:
            hit = _deep_contains_key(it, forbidden_keys)
            if hit:
                return hit
    return None

def _deep_contains_term(obj: Any, forbidden_terms: Tuple[str, ...]) -> Optional[str]:
    """
    문자열화하여 금지 단어가 섞였는지 검사(컨텍스트에서만 사용).
    """
    text = str(obj).lower()
    for t in forbidden_terms:
        if t in text:
            return t
    return None

def validate_run_documents(
    exec_doc: Dict[str, Any],
    outcome_doc: Dict[str, Any],
    context_doc: Optional[Dict[str, Any]] = None,
) -> List[Finding]:
    findings: List[Finding] = []

    # R1) schema registry 일치 (각 문서)
    for name, doc in [("execution_log", exec_doc), ("outcome_record", outcome_doc)]:
        schema = doc.get("schema", {})
        if not validate_schema(schema):
            findings.append(Finding(
                severity="HARD_FAIL",
                code="SCHEMA_MISMATCH",
                message=f"{name} schema not allowed or version mismatch",
                evidence={"schema": schema, "doc": name}
            ))

    if context_doc is not None:
        schema = context_doc.get("schema", {})
        if not validate_schema(schema):
            findings.append(Finding(
                severity="HARD_FAIL",
                code="SCHEMA_MISMATCH",
                message="context_snapshot schema not allowed or version mismatch",
                evidence={"schema": schema, "doc": "context_snapshot"}
            ))

    # R2) execution에 자동실행 흔적 키 금지
    hit_key = _deep_contains_key(exec_doc, FORBIDDEN_KEYS_IN_EXEC)
    if hit_key:
        findings.append(Finding(
            severity="HARD_FAIL",
            code="AUTO_EXECUTE_FORBIDDEN",
            message="Forbidden automation key detected in execution log",
            evidence={"key": hit_key}
        ))

    # R3) execution.run.run_id, outcome.run_id 정합성
    run_id_exec = exec_doc.get("id") or exec_doc.get("run", {}).get("run_id")
    run_id_out = outcome_doc.get("run_id") or outcome_doc.get("id")
    if run_id_exec and run_id_out and str(run_id_exec) != str(run_id_out):
        findings.append(Finding(
            severity="HARD_FAIL",
            code="RUN_ID_MISMATCH",
            message="ExecutionLog and OutcomeRecord run_id mismatch",
            evidence={"execution_run_id": run_id_exec, "outcome_run_id": run_id_out}
        ))

    # R4) context_snapshot 금칙어 검사 (context 존재 시)
    if context_doc is not None:
        # v0.1: tags/notes 중심 검사 (Pydantic에서도 막지만, raw json도 대비)
        tags = context_doc.get("tags", {})
        notes = context_doc.get("notes", "")
        term = _deep_contains_term({"tags": tags, "notes": notes}, FORBIDDEN_TERMS_IN_CONTEXT_TEXT)
        if term:
            findings.append(Finding(
                severity="HARD_FAIL",
                code="CONTEXT_FORBIDDEN_LANGUAGE",
                message="Forbidden directional/recommendation language detected in context_snapshot",
                evidence={"term": term}
            ))

    # R5) 최소 필수 필드 존재성 (warning 레벨로)
    if "run" not in exec_doc:
        findings.append(Finding(
            severity="WARNING",
            code="MISSING_RUN_BLOCK",
            message="execution_log missing 'run' block",
            evidence={}
        ))
    if "instrument" not in exec_doc:
        findings.append(Finding(
            severity="WARNING",
            code="MISSING_INSTRUMENT",
            message="execution_log missing instrument",
            evidence={}
        ))

    return findings

