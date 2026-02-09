# GATEKIT TEMPLATE TAG CONTRACT v1.0

## 목적
모든 워크플로우(`.github/workflows/*-gate.yml`)가 **템플릿 태그를 선언**하고,
선언된 템플릿과 **드리프트(차이) 0** 상태를 항상 유지하도록 강제한다.

---

## 1) 태그 규격 (Template Tag)

### Key
- `gatekit_template`

### Format
- `# gatekit_template: <template_key>`

### Placement
- 워크플로우 파일 상단 **5줄 이내**에 반드시 존재해야 한다.
- 권장: **첫 줄**

### Fail-Closed
- 태그가 없으면: FAIL
- `<template_key>`가 비어있으면: FAIL

---

## 2) 템플릿 경로 규칙 (Template Resolution)

템플릿 루트(기본):
- `gatekit/templates`

템플릿 파일명 규칙(v1.0):
- `<template_key>.yml`
- 예: `# gatekit_template: lock2-gate`  -> `gatekit/templates/lock2-gate.yml`

### Fail-Closed
- 템플릿 파일이 없으면: FAIL

---

## 3) 드리프트 규칙 (Drift = 0)

v1.0은 **완전 동일성**을 요구한다.

### 동일성 정의(v1.0)
- 워크플로우 파일 전체 내용(text)이 템플릿 파일 전체 내용(text)과 **완전히 동일**해야 한다.
- 차이가 1글자라도 존재하면: FAIL

### Fail-Closed
- 드리프트 발생 시: FAIL (diff 요약 출력)

---

## 4) 변경 정책

- 템플릿 변경이 필요하면:
  1) `gatekit/templates/<template_key>.yml`을 변경한다.
  2) 동일 변경을 `.github/workflows/<template_key>.yml`에 반영한다.
  3) PR에서 drift gate가 PASS되는지 확인한다.

(선택) 향후 v1.1+에서 "재생성 스크립트"를 표준화할 수 있다.
