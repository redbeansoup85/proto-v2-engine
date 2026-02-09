CI 재실행 런북 (LOCK-safe)
로컬 pytest 실행(LOCK): `DATABASE_URL="sqlite+aiosqlite:///test.db" pytest -q`
실수 방지 래퍼: `tools/local/run_pytest.sh -q`
`DATABASE_URL`이 비었거나 `test.db`가 아니면 conftest가 FAIL-CLOSED로 종료한다.
이 동작은 의도된 보호장치이며 완화하지 않는다.

적용 범위: PR checks, governance gates, ruleset-aware workflows
목적: PR 본문/권한 변경이 자동 반영되지 않을 때, 안전하게 CI를 복구

1. 증상

*_gate (pull_request)가 이전 실패 run만 참조

PR_BODY_LEN 값이 과거 값으로 고정

PR body 수정 후에도 gate 실패가 지속

push 이벤트 run은 성공하지만 pull_request run만 실패

2. 원인 요약 (관측 사실)

GitHub Actions의 pull_request 이벤트는
PR body 수정만으로 기존 run을 자동 갱신하지 않을 수 있음

이 경우 gate는 과거 PR body 스냅샷을 기준으로 실행됨

새로운 커밋 없이 PR body만 수정하면:

새로운 run이 생성되지 않음

기존 실패 run이 계속 재사용됨

3. 표준 복구 절차 (권장 · LOCK-safe)
A. 실패한 run 재실행 (최우선)

터미널에서 그대로 실행:

gh run rerun <RUN_ID> --failed

rerun은 새 run을 만드는 것이 아니라

동일 run을 최신 PR body / 환경 기준으로 재평가함

PR body / 권한 / ruleset 변경 사항이 이 시점에 반영됨

⚠️ 주의
PR body 수정만으로는 기존 pull_request run이 갱신되지 않을 수 있다.
rerun은 동일 run을 최신 PR 상태로 다시 평가하는 유일한 안전한 방법이다.

B. rerun 이후 확인 절차

PR checks 화면에서 다음을 확인:

*_gate (pull_request)가 새 로그로 재실행되었는지

PR_BODY_LEN이 최신 body 길이로 갱신되었는지

다음 명령으로 상태 확인 가능:

gh pr checks <PR_NUMBER> --watch

4. 예외 복구 (비권장 · 필요 시)
빈 커밋으로 강제 재트리거

rerun이 불가능하거나 UI 접근이 제한된 경우만 사용

반드시 A-PATCH 규칙 준수

git commit --allow-empty -m "A-PATCH: retrigger pull_request checks (no code change)"
git push

⚠️ 이 방법은 이력 오염 가능성이 있으므로 최후 수단으로만 사용

5. 사용 금지 패턴 (Fail-Closed)

❌ PR body만 수정하고 rerun을 하지 않는 행위

❌ gate 실패 원인을 코드 문제로 오인하여 불필요한 수정 수행

❌ push run 성공을 근거로 pull_request gate를 무시

6. 판단 기준 (운영 체크리스트)

PR body / ruleset / permissions 변경이 있었는가?

YES → rerun 필수

pull_request gate만 실패하는가?

YES → rerun 우선

rerun 이후에도 실패하는가?

YES → gate 로직 또는 ruleset 자체 점검

7. 상태 정의

이 런북이 적용된 경우, 다음 상태를 만족해야 한다:

PR body 변경 → rerun → gate 통과

동일 증상 재발 시 추론 없이 즉시 복구 가능

## POSTMORTEM-lite: CI main-green recovery (LOCKED)

- **Incident**: main push CI failures caused by legacy workflow loading error and prior governance-docs merge with invalid token.
- **Root Causes**:
  1) Legacy `.github/workflows/required-checks-gate.yml` remained and failed at workflow load (0s failure).
  2) Governance docs were merged with `A-PATCH`, violating token policy enforced on push.
- **Resolution**:
  - Removed legacy required-checks workflow (PR #109).
  - Confirmed contract-based required checks as the sole enforcement path.
- **Verification**:
  - All main push checks green at HEAD (proto-v2-engine-ci, contract gate, adapters).
- **Status**: **LOCKED** — main-green restored without weakening governance rules.

> NOTE: Historical red runs prior to LOCK are non-actionable and do not affect current governance state.

### Recommended Operational Steps

1. Before merging any PR touching `docs/governance/**`:
   - Verify token: A-MINOR or A-MAJOR
   - Ensure PR title matches token
2. On PR merge:
   - Observe `proto-v2-engine-ci` and contract-gate runs on main
   - If any check fails, follow LOCK escalation protocol
3. Historical red runs prior to this LOCK are informational only; do not trigger re-runs.
