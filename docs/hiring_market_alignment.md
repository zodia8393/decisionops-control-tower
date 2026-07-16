# Hiring Market Alignment

## 목표 역할

- Data Scientist
- ML/AI Engineer
- Data/Analytics Engineer
- Research Engineer
- Product/Backend Engineer

## 보여줄 역량

| 평가축 | 프로젝트 증거 |
|---|---|
| 문제 정의와 business/product/operation impact | public deploy, demo mode, reviewer backlog를 운영 의사결정으로 정의 |
| Python/data engineering | Stage 1/2 artifacts를 control state와 queue로 통합 |
| 복합 데이터 수집·정제·결합 | bike-share readiness, agent eval, review queue, NY 511 incident surface 결합 |
| 통계·실험·불확실성 | upstream holdout/eval metric과 readiness blocker를 release gate로 사용 |
| ML/AI 모델링 또는 system benchmark | guarded decision agent metric을 product release 조건으로 연결 |
| API/backend/product delivery | FastAPI, OpenAPI docs, chained SQLite approval history, replay verifier, dashboard action, API contract 제공 |
| cloud/deployment/runbook | Dockerfile, `.env.example`, server script, smoke test, deployment readiness gate, public `NO_GO` gate 제공 |
| privacy/security judgment | raw CCTV/token을 제외하고 approval POST를 local SQLite write boundary로 제한 |

## 시장 근거

Applied AI, ML Product, MLE 역할은 모델 자체보다 운영 승인, observability, guardrail, product delivery를 요구한다. 이 프로젝트는 Stage 1/2 분석 결과를 실제 reviewer workflow와 배포 판단으로 연결하는 신호를 만든다.
