# Meta OS v1.0 — SYSTEM FLOW (Prelude → Judgment → Gates → Delivery)

Version: v1.0.0  
Status: LOCKED  
Date: 2026-01-06  
Tag: v1.0.0  

---

## 0. Purpose

이 문서는 Meta OS v1.0의 **엔드-투-엔드 흐름**을 “한 번에” 이해시키기 위한 문서다.

- v1.0에서 **무엇이 입력되고**
- 어떤 아티팩트가 생성되며
- **어디서 인간 책임이 개입되고**
- 최종적으로 무엇이 “전달되지만 실행되지 않는지”
를 명시한다.

---

## 1. One-Page Mental Model

Meta OS v1.0은 다음을 수행한다:

- **관측을 받아**
- **판단/정렬 결과물을 만들고**
- **인간이 책임을 수락하면**
- **인간이 실행을 승인할 수는 있지만**
- **시스템은 끝까지 실행하지 않는다**
- 실행은 외부 실행기가 수행한다

---

## 2. System Flow Diagram (텍스트 도식)

### 2.1 전체 파이프라인

[Prelude / Observation]
  └─ (Input Layer: raw/signal/context)
        ↓
[Engine / Judgment-Preparation]
  └─ EngineOutput (judgment artifact / receipt 형태)
        ↓
[Gate 1: Responsibility Acceptance]
  └─ ResponsibilityAcceptance (human accountability object)
        ↓
[Gate 2: Execution Authorization]
  └─ ExecutionAuthorizationRequest (bounded, timeboxed, non-executing)
        ↓
[Delivery Plan Build]
  └─ DeliveryPlan (action-free routing plan)
        ↓
[Queue / Pending]
  └─ logs/queues/<channel>/pending/<plan_id>.json
        ↓
[Queue Consumer]
  └─ logs/queues/<channel>/processed/<safe_plan_id>.json
        ↓
[STOP]
  └─ action_executed=false (always)
  └─ executor is external (out of scope)

---

## 3. Boundary Clarification (무엇이 어디까지인가)

### 3.1 Prelude (Observation Zone)

**역할**
- 외부 신호/센서/ML 함수값(가능)을 “판단 이전 상태”로 수용
- raw + signal 분리
- source/channel/context를 명시

**산출물 (대표)**
- Prelude output JSON (예: out_prelude_stub.json 등)

**특징**
- 책임 없음
- 실행 없음
- “판단 이전”을 유지하는 계약 영역

---

### 3.2 Engine (Judgment-Preparation Zone)

**역할**
- Prelude 입력을 받아 의미 구조로 정렬
- 최소한의 판단 결과(혹은 판단 준비 결과) 아티팩트 생성

**산출물**
- EngineOutput / Receipt류 아티팩트
- 이후 DeliveryPlan이 참조하는 근거(SSoT)

**특징**
- 실행 없음
- “이 상황을 무엇으로 볼 것인가”의 구조화를 담당

---

## 4. Gates (v1.0 핵심 구조)

### 4.1 Gate 1 — Responsibility Acceptance

**목적**
- 인간이 “이 판단 결과에 대한 책임을 수락한다”를 명시

**산출물**
- ResponsibilityAcceptance

**필수 필드**
- decision=ACCEPT
- actor_id / actor_role
- judgment_ref (judgment artifact에 대한 참조)
- ts (ISO)

**의미**
- Gate 1은 실행이 아니다
- 책임 객체(감사/추적/통제 목적)다

---

### 4.2 Gate 2 — Execution Authorization

**목적**
- 책임을 수락한 인간이 “제한된 범위에서 실행을 승인한다”를 명시

**산출물**
- ExecutionAuthorizationRequest

**필수 구성**
- responsibility (accepted)
- scope (domain/asset/actions/target 등)
- limit (max_notional, max_order_count 등)
- timebox (valid_from/until)
- judgment_ref

**불변 조건 (v1.0 LOCK)**
- auto_action MUST remain false
- Meta OS는 이 요청을 실행하지 않는다

---

## 5. Delivery Artifacts (실행 없는 전달)

### 5.1 DeliveryPlan (Action-free)

**생성 시점**
- receipt 기반으로 plan 생성
- (execution channel일 경우) receipt.meta.execution_request_path 강제

**목적**
- 어디로 전달할지(채널/라우팅)를 명시
- 실행은 포함하지 않는다

**대표 필드**
- plan_id / ts_iso / channel
- receipt_path / receipt_hash
- policy_version / policy_sha256
- evidence_* ids
- recommended_actions (참고용)

---

### 5.2 Queue Item

**저장 위치**
- logs/queues/<channel>/pending/<plan_id>.json

**특징**
- “실행 요청”이 아니라 “전달 계획 아티팩트”
- execution channel은 Gate 2 없으면 생성 불가(또는 실패)

---

### 5.3 Queue Consumer (Processed Artifact)

**저장 위치**
- logs/queues/<channel>/processed/<safe_plan_id>.json

**확정 필드**
- status=PROCESSED
- action_executed=false
- delivery_status.mode=ARTIFACT_ONLY
- forwarded_to_orchestrator=false (기본)
- execution_request_path (있을 수 있으나 실행하지 않음)

---

## 6. Execution Channels (v1.0에서 특별 취급)

### 6.1 실행 채널 정의

- trading
- ops_exec
- automation
- live

### 6.2 실행 채널의 조건

- receipt.meta.execution_request_path MUST exist
- execution_request는 validate되어야 한다:
  - responsibility.is_accepted() == True
  - auto_action == False
  - scope/limit/timebox/judgment_ref 필수

---

## 7. What v1.0 Explicitly Does NOT Do

- 자동 주문 실행
- 외부 API 호출로 행위 수행
- 무인 실행 / 자율 에이전트
- 승인 없이 실행
- Gate 우회

---

## 8. Summary (한 문장)

Meta OS v1.0은  
**“판단 아티팩트를 만들고, 인간이 책임과 실행승인을 명시할 수는 있지만, 시스템은 끝까지 실행하지 않는 구조”**로 잠금되었다.

— End of Meta OS v1.0 System Flow —
