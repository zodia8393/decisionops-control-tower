# 시스템 설계

## Product Surface

실행 surface는 `scripts/run_all.sh`가 제공하는 batch pipeline/CLI, FastAPI server, SQLite approval persistence, chained audit/replay verifier, RBAC-lite write auth, structured JSON request logging, monitoring snapshot, deployment readiness gate, policy audit, reviewer action plan, freshness-gated evidence bundle, AI Reviewer Agent, reviewer dashboard입니다. Public deploy는 upstream readiness가 `GO`가 될 때까지 차단합니다.

AI Reviewer Agent는 `/api/agent/reviewer-brief`와 `/api/agent/candidate/{candidate_id}/review-notes`로 노출되는 read-only reviewer assistant입니다. Agent는 health/API/artifact를 근거로 요약과 다음 action을 만들지만 approval write, 현장 dispatch, `GO/NO_GO` 변경, 신규 효과 수치 생성은 하지 않습니다. LLM 미설정 또는 호출 실패 시 deterministic fallback brief를 반환합니다.

이번 product slice는 서울 따릉이 재배치 추천을 위한 impact card와 policy audit을 추가했습니다. Impact card는 추천 action, 후보 shortage/overflow 완화 단위, baseline 대비 후보 개선량, confidence, evidence, blocker를 reviewer queue 옆에서 보여줍니다. Policy audit은 무검토 공개 기준선과 guarded policy를 비교해 미검증 public claim 단위를 차단합니다.

## Architecture

```text
Stage 1 bike-share artifacts
Stage 2 agentic workbench artifacts
  -> control-state rules
  -> reviewer queue projection
  -> API contract and FastAPI endpoints
  -> SQLite approval store
  -> SHA-256 event chain + deterministic queue-state replay
  -> RBAC-lite write auth and structured logs
  -> ops metrics snapshot/history
  -> deployment readiness gate
  -> dashboard/report

Stage 1 impact simulation artifacts
  -> impact card projection
  -> unsafe-vs-guarded policy audit
  -> reviewer ordering robustness stress test
  -> capacity-ranked reviewer action plan
  -> freshness SLA + SHA-256 evidence bundle lock
  -> reviewer action rationale
  -> approval queue priority
  -> public claim blocker when readiness is NO_GO
```

데이터 흐름도(DFD): [data_flow_diagram.md](data_flow_diagram.md)

## Runtime

- Source root: `/workspace/prj/data-scientist-career/decisionops-control-tower`
- Artifact root: `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower`
- Config/env: `OUTPUT_ROOT`, optional `--bike-root`, optional `--workbench-root`
- Logging/error handling: CLI summary plus blocker list in `reports/control_state.json`
- Server: `scripts/run_server.sh`, default `http://127.0.0.1:8093`
- API docs: `/docs`, `/openapi.json`
- Impact cards: `/api/impact-cards`, `reports/impact_cards.csv`, `reports/impact_cards.json`
- Agent brief: `/api/agent/reviewer-brief`, `/api/agent/candidate/{candidate_id}/review-notes`
- Impact policy audit: `/api/impact-policy-audit`, `reports/impact_policy_audit.csv`, `reports/impact_policy_audit.json`
- Reviewer policy robustness: `/api/reviewer-policy-robustness`, `reports/reviewer_policy_robustness.csv`, `reports/reviewer_policy_robustness.json`
- Reviewer action plan: `/api/reviewer-action-plan`, `reports/reviewer_action_plan.csv`, `reports/reviewer_action_plan.json`
- Reviewer evidence bundles: `/api/reviewer-evidence-bundles`, `reports/reviewer_evidence_bundles.csv`, `reports/reviewer_evidence_bundles.json`
- Approval audit integrity: `/api/approval-audit-integrity`, `reports/approval_audit_integrity.json`
- Write auth: `CONTROL_TOWER_ROLE_TOKENS` set -> approval POST requires `reviewer` or `admin` role via `X-Control-Tower-Token`
- Structured logs: request logs are JSON lines and include request id, method, path, status, duration
- Monitoring artifact: `reports/ops_metrics_snapshot.json` and append-only `reports/ops_metrics_history.jsonl`
- Deployment gate: `reports/deployment_readiness.json` and `reports/deployment_readiness.md` split local/container/hosted/public decisions
- Container packaging: `Dockerfile`, `compose.yaml`, `scripts/check_docker_ready.py`, `scripts/verify_docker_deployment.sh`, `scripts/verify_compose_deployment.sh`
- Deployment/runbook: demo product slice exists; public deploy remains `NO_GO` until upstream readiness and production hardening are complete

## Operations

- Healthcheck: `scripts/run_all.sh` and `GET /health`
- Monitoring/drift: `GET /api/ops-metrics`, `scripts/write_monitoring_snapshot.py`, `scripts/write_deployment_readiness.py`, upstream bike-share snapshot monitor, and Stage 2 eval artifacts
- Refresh cadence: rerun after bike-share readiness changes or Stage 2 review queue changes
- Evidence freshness: timezone-aware source timestamp 기준 3시간 SLA. 초과·누락·미래 시각은 `needs_more_evidence`로 강제
- Evidence integrity: contract version, impact card, action plan canonical JSON의 SHA-256 fingerprint로 content drift 탐지
- Approval integrity: reviewer decision canonical payload를 이전 event hash와 연결하고 마지막 decision을 queue state로 replay; 실패 시 deployment gate 차단
- Write boundary: approval POST writes only to `OUTPUT_ROOT/control_tower.sqlite`; it does not publish, dispatch, or mutate upstream artifacts
