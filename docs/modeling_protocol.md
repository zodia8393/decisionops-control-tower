# 모델링 프로토콜

## 목표

이 product slice의 목표는 새 예측 모델이 아니라 Stage 1/2 artifact orchestration과 reviewer approval workflow benchmark다. 핵심 판단은 `demo_mode_ready`, `public_deploy_decision`, reviewer queue backlog, approval persistence다.

## 연구 질문

1. Stage 1 deploy readiness와 Stage 2 prepublish/eval gate를 하나의 release state로 결합할 수 있는가?
2. Agentic review queue를 reviewer approval queue로 변환할 때 unsafe write action을 만들지 않는가?
3. Demo mode와 public deploy를 분리해 과장된 배포 판단을 막는가?
4. Impact card를 public claim으로 바로 공개하는 기준선보다 guarded/capacity policy가 더 안전한가?
5. AI Reviewer Agent가 deterministic gate를 source of truth로 유지하면서 reviewer에게 근거 요약만 제공하는가?

## 분할 원칙

- 모델 train/test split은 없다.
- Upstream evaluation split은 Stage 2 main 60 tasks와 holdout 12 tasks를 그대로 사용한다.
- Control Tower는 run 시점 snapshot을 읽는 integration check와 FastAPI/SQLite workflow smoke로 검증한다.

## 기준선과 모델

| 모델 | 역할 |
|---|---|
| upstream baseline agent | Stage 2 비교 기준 |
| guarded decision agent | Stage 2 decision/eval source |
| control-state rules | Stage 3 release/blocker orchestration |
| unsafe auto-publish policy | 미검증 impact claim 기준선 |
| impact-guarded capacity policy | 검토 용량 제한 하 우선순위 정렬 |
| evidence-gated reviewer agent | health/API/artifact 근거만 요약하는 read-only assistant |

## Ablation

- Stage 2 `baseline_single_agent` vs `guarded_decision_agent`.
- Stage 3 product slice는 API/write persistence가 없는 seed 대비 FastAPI, SQLite history, dashboard approval action을 추가한다.
- Stage 3 impact policy audit은 `unsafe_auto_publish`와 guarded policies를 같은 impact cards로 비교한다.
- Reviewer action plan은 source order와 impact-guarded order를 비교해 제한된 검토 용량에서 먼저 볼 후보를 정한다.
- AI Reviewer Agent는 LLM/agent 없는 기준선 대비 source status, claim-safety rule, evidence refs, candidate notes를 생성하지만 approval write와 `GO/NO_GO` 변경은 하지 않는다.
- Approval POST는 local SQLite에만 기록되며 external dispatch/write는 하지 않는다.

## 평가 지표

- `demo_mode_ready`: Stage 2 prepublish/eval 기반 demo 가능 여부.
- `public_deploy_decision`: bike-share readiness까지 포함한 public deploy 판단.
- `review_queue_items`: reviewer backlog 수.
- `approval_history_rows`: reviewer decision audit trail 수.
- `guarded_success_rate`, `holdout_success_rate`: Stage 2 agent gate.
- `impact_unsupported_claim_units_avoided`: unsafe baseline 대비 guarded policy가 차단한 미검증 claim 단위.
- `reviewer_action_plan_candidate_units`: 상위 검토 계획이 커버하는 후보 이동량.
- `agent_reviewer_brief.mode`: fallback/optional LLM 사용 여부.
- `agent_candidate_review_notes`: 후보별 read-only evidence note 수.

## 불확실성 및 robustness

- Bike-share prospective readiness가 `READY`가 아니면 public deploy는 `NO_GO`다.
- Seoul validation이 `READY`여도 public deploy readiness가 `GO`가 아니면 public claim은 blocked 상태다.
- NY 511 incident sample은 public historical data이며 live dispatch authority가 아니다.
- Approval write path는 local SQLite에 제한하고 upstream artifact와 field action은 변경하지 않는다.
- Agent output은 advisory이며 deterministic gate와 artifact를 덮어쓰지 않는다.

## 오류 감사

- Missing upstream artifact는 empty/default로 처리하지만 blocker에 반영한다.
- Guarded/holdout success가 0.99 미만이면 demo readiness를 차단한다.
- Review queue가 0건이면 product workflow가 비어 있다고 보고 blocker로 둔다.
- Policy audit에서 guarded policy의 unsupported claim 단위가 0이 아니면 public publication gate를 통과하지 못한다.
