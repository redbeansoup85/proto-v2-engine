# LOCK-3 INPUT PATHS (v1.0)

## 목적
LOCK-3는 Observer / Replay 입력 스트림을 고정된 경로로 운영한다.
모든 입력은 append-only이며, 누락/파싱 오류/체인 불일치 시 Fail-Closed 한다.

---

## 경로 표

| Stream | Path | 생성 주체 |
|---|---|---|
| Observer events | `var/observer/events.jsonl` | runtime observer hook |
| Replay packets | `var/replay/packets.jsonl` | 승인 후 replayer |
| Audit chain | `var/audit/lock3_chain.jsonl` | lock3 gate |

---

## 규칙 (Fail-Closed)
- 파일 미존재 → FAIL
- blank line / parse error → FAIL
- 체인 불일치(prev_hash/hash) → FAIL
- execution_run_id 링크 불일치 → FAIL

---

## 생성/운영 원칙
- Observer events는 실행 관측 레코드만 기록한다.
- Replay packets는 승인 이후에만 생성된다.
- 모든 기록은 append-only이며 삭제/덮어쓰기 금지.
