# OBSERVER_EVENT_CONTRACT v1.0 (LOCK-3)

## 목적
Observer Event는 **승인(Approval) → 실행(Execution) → 관측(Observer)**의 연결을
감사 가능하게 고정하기 위한 **append-only 이벤트 레코드**다.
- Fail-Closed: 필드 누락/스키마 위반/체인 불일치/링크 불일치 → 무조건 실패
- 외부 실행을 재현하지 않는다(LOCK-3는 decision replay 전용). LOCK-4에서 확장.

## 스코프
- 저장 포맷: JSON Lines (jsonl)
- 체인: SHA-256 hash chain (prev_hash → hash)
- 스키마: audits/observer_event.schema.lock3.json 준수
- 저장 위치: var/audit/lock3_chain.jsonl (기본)

## 필드 정의
schema_version: string
- 고정 값: "lock3/observer_event@1.0"

event_id: string
ts: string (RFC3339)
judgment_id: string
approval_record_id: string
execution_run_id: string

status: string (enum)
- started | ok | fail | aborted

metrics: object
- additionalProperties=false
- allowlist만 허용:
  - latency_ms: integer (>=0)
  - risk_flags: array[string]
  - notes: string (max 500)

prev_hash: string (64 hex)
hash: string (64 hex)

## 해시 규칙
canonical_json = JSON dump with sorted keys, compact separators, ensure_ascii=false
hash_input = prev_hash + "\n" + canonical_json_without_hash_fields
hash = sha256(hash_input).hexdigest()

## 불변 규칙 (Fail-Closed)
- 스키마 위반 → FAIL
- prev_hash/hash 체인 불일치 → FAIL
- 링크 불일치(judgment_id/approval_record_id/execution_run_id) → FAIL
- 파싱 실패/라인 깨짐 → FAIL

## 출력/로그
Gate는 findings를 다음 필드로 출력한다:
- rule_id, file, line, pattern, snippet
