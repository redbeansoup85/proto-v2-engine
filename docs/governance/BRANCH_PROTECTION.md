# Branch Protection – LOCK-1 FINAL

## Principles
- **Ruleset = 구조 보호**
- **CI = 검증 (fail-closed)**

## Decisions
- Require status checks: **OFF**
  - Reason: GitHub Actions는 check-runs 중심이며,
    classic status contexts가 비어 있을 경우
    PR이 영구 BLOCKED 상태가 되는 문제가 발생함.
- Validation is enforced exclusively by:
  - required-checks-contract-gate (Single Source of Truth)
  - lock2 / lock3 gates (CI-level enforcement)

## Guarantees
- 검증 실패 시 PR은 CI 단계에서 실패(red)함
- Ruleset은 destructive operation만 차단함
  - branch deletion
  - non-fast-forward push
- status context 불일치로 인한 merge deadlock 재발 방지

## Change Control
- 본 정책 변경은 반드시:
  - A-PATCH 이상 커밋
  - CI green
  - main 브랜치 PR을 통해서만 가능
