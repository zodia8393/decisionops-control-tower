# 데이터 계약

## 목적

`DecisionOps Control Tower` pipeline과 FastAPI service가 Stage 1/2 산출물을 읽어 control state, review queue, API contract, dashboard, policy audit, reviewer action plan, AI reviewer brief, approval history로 변환하는 계약을 기록한다.

## 원천

| 원천 | 역할 | 공개성 |
|---|---|---|
| Bike-share station readiness | public deploy blocker와 snapshot readiness | upstream public/derived artifact |
| Bike-share station priority/inventory | 운영 ML decision surface | upstream public/derived artifact |
| Seoul Ddareungi priority/validation | impact card 후보 action과 validation guardrail | Seoul Open Data derived artifact |
| Agentic DecisionOps eval metrics | guarded/holdout success와 invalid action gate | generated artifact |
| Agentic review queue | reviewer approval workload | generated artifact |
| NY 511 incident surface | incident evidence와 publication guardrail | public open-data sample |

## 라이선스 및 사용 조건

- Bike-share와 Agentic Workbench 산출물은 이전 portfolio project의 derived artifact다.
- NY 511 incident surface는 public open-data sample에서 파생된 decision surface다.
- Control Tower는 원천 raw data를 재배포하지 않고, review/product decision artifact만 생성한다.

## 결합 방식

원천 간 raw row join은 하지 않는다. Stage 1/2 산출물을 run-level control state로 결합하고, Stage 2 review queue row를 Control Tower approval queue row로 projection한다. Seoul Ddareungi priority row는 `impact_cards`로 projection하며, validation summary와 public deploy readiness가 모두 준비되지 않으면 public-claim blocker를 붙인다.

`impact_policy_audit`는 무검토 공개 기준선과 guarded policy를 같은 후보 단위로 비교한다. `reviewer_action_plan`은 영향 우선 정렬, 누적 후보 단위, confidence threshold, public-claim state를 reviewer가 바로 처리할 action row로 투영한다.

`agent_reviewer_brief`와 `agent_candidate_review_notes`는 health/API/artifact에서 읽은 source status, claim-safety rule, evidence refs, 다음 검토 action만 저장한다. Agent artifact는 approval write, field dispatch, public deploy 판단, 신규 효과 추정을 하지 않는다.

## 분석 단위

- Control state: pipeline run 1회당 1개 JSON.
- Review queue: Stage 2 `queue_id` 또는 `task_id` 단위 pending decision.
- Impact cards: Seoul station priority 단위 후보 action, 후보 이동량, evidence, validation blocker.
- Impact policy audit: unsafe publish, guarded all-review, source-order capacity, impact-guarded capacity의 public-claim 위반 비교.
- Reviewer action plan: 검토 용량이 제한될 때 먼저 볼 후보, 누적 후보 단위, local-only 승인/근거요청 판단.
- AI reviewer brief: run 단위 source status, claim-safety lock, top risks, next actions, limitations.
- Candidate review notes: 상위 impact card 후보별 evidence refs, local-only next actions, public-claim blocker.
- Dashboard: run 시점의 blocker, metric, queue snapshot.
- Approval history: reviewer가 API/dashboard에서 남긴 local decision audit trail.
- Ops metrics: artifact freshness, queue summary, auth enabled flag, configured role names, runtime uptime.
- Deployment readiness: local private demo, container demo, hosted private demo, public deploy의 분리된 GO/NO_GO 판단.
- Target: `demo_mode_ready`, `public_deploy_decision`, reviewer approval backlog.

## 저장 정책

| 구분 | 위치 | Git 포함 여부 |
|---|---|---|
| raw upstream data | upstream project artifact roots | 제외 |
| processed control surface | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/` | 제외 |
| impact cards | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/impact_cards.*` | 제외 |
| impact policy audit | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/impact_policy_audit.*` | 제외 |
| reviewer action plan | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/reviewer_action_plan.*` | 제외 |
| agent reviewer brief | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/agent_reviewer_brief.json` | 제외 |
| candidate review notes | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/agent_candidate_review_notes.json` | 제외 |
| reports | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/` | 제외 |
| dashboard | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/dashboard/` | 제외 |
| approval SQLite | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/control_tower.sqlite` | 제외 |
| deployment readiness | `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower/reports/deployment_readiness.*` | 제외 |

## 누수 위험

- 이 product slice는 새 모델 학습 split이 아니라 upstream artifact orchestration과 approval workflow다.
- Public deploy 판단은 upstream readiness를 그대로 반영하고 임의로 `GO`로 바꾸지 않는다.
- Impact card의 후보 단위는 public deploy readiness 전 production 성과가 아니라 reviewer evidence이며, Seoul validation 또는 public deploy readiness가 부족하면 public claim을 차단한다.
- Policy audit은 unsafe baseline의 미검증 claim 단위를 명시하고 guarded policy가 이를 0으로 낮추는지 검증한다.
- Review queue approval write action은 `CONTROL_TOWER_ROLE_TOKENS`가 설정되면 reviewer/admin 역할 credential을 요구하고, local SQLite에만 기록하며 upstream artifact, 외부 시스템, field action을 변경하지 않는다.
- AI Reviewer Agent는 read-only이며 `GO/NO_GO`, public claim safety, 숫자 원천을 deterministic artifact에서 가져오고 새 claim을 만들지 않는다.
- Structured request log는 secret/header value 없이 request metadata만 남긴다.
- Monitoring snapshot은 latest JSON과 append-only JSONL history를 reports 아래에 남긴다.
- Deployment readiness gate는 credential 값 없이 auth configured 여부, role 이름, Docker/buildx 상태, public deploy blocker만 기록한다.
- 내부 데이터, 개인정보, raw CCTV, token, `.env` 값은 Control Tower source와 artifact에 복사하지 않는다.
