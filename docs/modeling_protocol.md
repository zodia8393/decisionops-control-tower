# 모델링 프로토콜

## 목표

이 product slice의 목표는 새 예측 모델이 아니라 Stage 1/2 artifact orchestration과 reviewer approval workflow benchmark다. 핵심 판단은 `demo_mode_ready`, `public_deploy_decision`, reviewer queue backlog, approval persistence다.

## 연구 질문

1. Stage 1 deploy readiness와 Stage 2 prepublish/eval gate를 하나의 release state로 결합할 수 있는가?
2. Agentic review queue를 reviewer approval queue로 변환할 때 unsafe write action을 만들지 않는가?
3. Demo mode와 public deploy를 분리해 과장된 배포 판단을 막는가?
4. Impact card를 public claim으로 바로 공개하는 기준선보다 guarded/capacity policy가 더 안전한가?
5. AI Reviewer Agent가 deterministic gate를 source of truth로 유지하면서 reviewer에게 근거 요약만 제공하는가?
6. 오래되거나 timestamp가 잘못된 impact evidence가 reviewer 승인 후보로 재사용되지 않는가?
7. 효과 추정치, confidence, source completeness가 흔들려도 guarded reviewer ordering이 safety-first 기준을 유지하는가?
8. Reviewer decision history 변조나 현재 queue state 불일치를 deterministic하게 탐지하는가?

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
| confidence-weighted guarded policy | invalid evidence를 먼저 제외하고 confidence-adjusted 후보 단위로 정렬 |
| evidence-gated reviewer agent | health/API/artifact 근거만 요약하는 read-only assistant |
| freshness-gated evidence bundle | impact/action join의 최신성·content drift 검증 |
| chained approval audit | 이전 event hash 연결과 queue-state replay로 결정 이력 무결성 검증 |

## Ablation

- Stage 2 `baseline_single_agent` vs `guarded_decision_agent`.
- Stage 3 product slice는 API/write persistence가 없는 seed 대비 FastAPI, SQLite history, dashboard approval action을 추가한다.
- Stage 3 impact policy audit은 `unsafe_auto_publish`와 guarded policies를 같은 impact cards로 비교한다.
- Reviewer action plan은 source order와 impact-guarded order를 비교해 제한된 검토 용량에서 먼저 볼 후보를 정한다.
- Reviewer robustness audit은 4개 deterministic scenario와 capacity 3/6/8에서 source order, impact guarded, confidence-weighted guarded를 비교한다.
- AI Reviewer Agent는 LLM/agent 없는 기준선 대비 source status, claim-safety rule, evidence refs, candidate notes를 생성하지만 approval write와 `GO/NO_GO` 변경은 하지 않는다.
- Approval POST는 local SQLite에만 기록되며 external dispatch/write는 하지 않는다.
- 일반 timestamp history 대비 chained audit은 payload hash와 replay mismatch를 deployment blocker로 승격한다.

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
- `reviewer_evidence_fresh_rows`: 3시간 SLA와 timestamp 계약을 통과한 bundle 수.
- `reviewer_evidence_non_fresh_rows`: stale/missing/future timestamp로 차단된 bundle 수.
- `reviewer_policy_guarded_dominance_rate`: invalid evidence 수를 우선하고 동률에서 confidence-adjusted units를 비교한 safety dominance 비율.
- `reviewer_policy_worst_case_regret_units`: confidence-weighted safe oracle 대비 최대 confidence-adjusted 후보 단위 손실.
- `reviewer_policy_selection_stability`: baseline selection 대비 stress selection의 평균 Jaccard.
- `approval_audit_integrity.status`: event chain과 queue-state replay가 모두 통과했는지 여부.
- `approval_audit_integrity.replay_mismatch_count`: history replay와 현재 queue state가 다른 control 수.

## 불확실성 및 robustness

- Bike-share prospective readiness가 `READY`가 아니면 public read-only snapshot은 `NO_GO`다.
- Seoul validation이 `READY`여도 public snapshot readiness가 `GO`가 아니면 public claim은 blocked 상태다. Hosted write API의 인증 gate는 이 판단과 분리한다.
- NY 511 incident sample은 public historical data이며 live dispatch authority가 아니다.
- Approval write path는 local SQLite에 제한하고 upstream artifact와 field action은 변경하지 않는다.
- Agent output은 advisory이며 deterministic gate와 artifact를 덮어쓰지 않는다.
- Evidence bundle은 timezone-aware ISO-8601 시각과 3시간 SLA를 사용하고, contract version·impact card·action plan canonical JSON을 SHA-256으로 fingerprint한다.
- Robustness scenario는 deterministic controlled comparison이며 prospective realized impact나 causal effect로 해석하지 않는다.

## 오류 감사

- Missing upstream artifact는 empty/default로 처리하지만 blocker에 반영한다.
- Guarded/holdout success가 0.99 미만이면 demo readiness를 차단한다.
- Review queue가 0건이면 product workflow가 비어 있다고 보고 blocker로 둔다.
- Policy audit에서 guarded policy의 unsupported claim 단위가 0이 아니면 public publication gate를 통과하지 못한다.
- Evidence timestamp가 누락·오류·미래 시각이거나 SLA를 초과하면 action plan 결과와 무관하게 `needs_more_evidence`로 강제한다.
- Audit event payload/hash 또는 replay state가 다르면 local/container deployment readiness를 `NO_GO`로 둔다.
