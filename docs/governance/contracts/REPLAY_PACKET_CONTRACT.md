# REPLAY_PACKET_CONTRACT v1.0 (LOCK-3)

## 목적
Replay Packet은 “결정 재현(decision replay)”을 위해
**입력 스냅샷의 digest + 관련 아티팩트 참조**를 고정한다.
- 실행 환경/외부 어댑터 호출 재현은 LOCK-4에서 다룬다.

## 저장 규약
- 포맷: JSON (단일 파일) 또는 JSONL(여러 패킷). LOCK-3 MVP는 JSON 단일 패킷 권장.
- 스키마: audits/replay_packet.schema.lock3.json 준수
- 외부 절대 경로/URL 금지 (repo-relative path만 허용)

## 필드 정의
schema_version: "lock3/replay_packet@1.0"
packet_id: string
ts: string (RFC3339)

judgment_id: string
approval_record_id: string
execution_run_id: string

inputs_digest: sha256 hex (64)
artifacts: array[{path, kind, digest?}]
- path: repo-relative only (no leading "/", no "://", no "..")
- kind enum: card|policy|contract|log|other
- digest optional sha256

prev_hash: 64 hex
hash: 64 hex

## 불변 규칙 (Fail-Closed)
- 스키마 위반 → FAIL
- artifacts.path 위반(절대경로/URL/.. 포함) → FAIL
- inputs_digest 형식 불일치 → FAIL
