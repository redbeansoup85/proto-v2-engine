# JUDGMENT → APPROVAL → RECORD Contract (LOCK-2)

## 목적
- 실행(execution)은 **승인(approval) 이벤트**를 유일한 트리거로만 발생할 수 있다.
- 모든 승인은 **Record(immutable audit chain)** 로 남는다.
- 본 계약은 "설명 가능, 실행 불가" 원칙과 충돌하지 않는다. (외부 실행은 별도 LOCK에서만 허용)

## 규정
### R1. Approval is the sole execution trigger
- 승인 이벤트가 없으면 어떤 execution endpoint / executor / external side effect도 호출될 수 없다.

### R2. Approval must be recorded (append-only)
- 승인 이벤트는 audit chain(JSONL)에 append-only로 기록되어야 한다.
- 체인은 hash_prev로 연결되며 첫 이벤트는 GENESIS를 사용한다.

### R3. Fail-Closed
- 게이트/스캔/검증 중 하나라도 실패하면 CI는 실패해야 한다.

## 산출물 (Implementation Artifacts)
- `tools/gates/lock2_gate.py` : 승인-기반 실행 트리거 강제 게이트 (fail-closed)
- `tools/gates/static_scan.py` : 외부 실행 단서(HTTP/SHELL/TRADE) 정적 스캔
- `audits/audit_schema.lock2.json` : audit event schema
- `tests/gates/test_lock2_gate.py`, `tests/gates/test_static_scan.py` : fail-closed 테스트

## 비고
- DB/ORM의 `execute()`는 외부 실행이 아니며 LOCK-2 금지 대상이 아니다.
