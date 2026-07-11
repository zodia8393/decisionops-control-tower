# Research Gap Report

이 문서는 quality gate를 통과하지 못한 항목을 완료 처리하지 않기 위한 추적표입니다.

| Gate | 현재 상태 | 미달 근거 | 다음 작업 |
|---|---|---|---|
| topic candidates >= 5 | pass | Control Tower가 suite capstone으로 선정됨 | 유지 |
| data sources explored >= 3 | pass | Stage 1/2 artifacts와 NY 511 incident surface 사용 | source contract 유지 |
| data sources joined >= 2 or documented exception | pass | bike-share + agentic workbench + incident surface 결합, approval DB persistence 추가 | source contract 유지 |
| leakage-safe validation | pass | 새 모델 split은 없고 upstream holdout + approval workflow regression test로 검증 | production auth 추가 시 테스트 확대 |
| baseline/model/ablation or benchmark | pass | read-only seed 대비 FastAPI/SQLite approval slice로 product-surface ablation 기록 | monitoring surface 확대 |
| uncertainty/robustness/failure audit | pass | 4 stress scenarios × 3 capacities × 3 policies, safety dominance, oracle regret, selection Jaccard, readiness blocker | prospective realized impact는 upstream gate 후 추가 |
| product surface | pass | CLI + FastAPI + OpenAPI + dashboard + SQLite approval history + RBAC-lite writes + structured logs + monitoring snapshot + deployment readiness gate + Docker/compose smoke | hosted demo hardening |
| Seoul impact card | pass | `/api/impact-cards`와 `reports/impact_cards.csv/json`이 추천 action, 후보 이동량, confidence, evidence, blocker를 노출 | Seoul validation READY 후 verified improvement 채우기 |
| Impact policy audit | pass | `reports/impact_policy_audit.csv/json`와 `/api/impact-policy-audit`가 unsafe publish 대비 guarded policy의 unsupported claim 차단을 검증 | public deploy GO 후 verified claim row 분리 |
| Reviewer policy robustness | pass | `/api/reviewer-policy-robustness`와 CSV/JSON이 36-row controlled comparison과 invalid-evidence-first dominance를 재현 | 실제 reviewer feedback으로 utility weight 보정 |
| Reviewer action plan | pass | `reports/reviewer_action_plan.csv/json`와 `/api/reviewer-action-plan`이 검토 용량 제한 하 local-only 우선순위를 제시 | 실제 운영 reviewer feedback 반영 |
| Reviewer evidence contract | pass | `/api/reviewer-evidence-bundles`와 CSV/JSON이 impact/action join, 3시간 SLA, timestamp sad path, SHA-256 content lock을 재현 | 외부 서명/원격 attestation은 hosted hardening에서 검토 |
| AI reviewer agent | pass | `/api/agent/reviewer-brief`, `/api/agent/candidate/{candidate_id}/review-notes`, `reports/agent_reviewer_brief.json`, `reports/agent_candidate_review_notes.json`가 deterministic gate를 source of truth로 둔 read-only 검토 요약을 제공 | LLM planner를 붙일 경우 deterministic fallback regression 유지 |
| privacy publication gate | pass | raw 내부 data/token/write action 미포함 | release artifact scan 유지 |
| CI/tests/smoke | pass | `scripts/run_all.sh`와 pytest 통과 | CI 실행 유지 |
| GitHub/deploy/runbook | pass | Dockerfile, compose, `.env.example`, server script, OpenAPI/ops smoke, private demo auth verifier, deployment readiness gate, docker smoke, compose smoke 존재; public deploy는 upstream readiness 때문에 `NO_GO` | hosted demo 배포 여부 결정 |
| Portfolio case study | pass | `docs/case_study.md`와 `docs/demo_package.md`가 문제, 데이터, 제품 surface, 캡처, 검증, 의사결정 경계를 설명 | 캡처 최신성 유지 |
