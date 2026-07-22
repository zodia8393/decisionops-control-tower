# 재현 가이드

## 환경

- Python: 3.10 이상
- Docker Engine + Docker Compose: 실제 Firebird→PostgreSQL integration에 필요
- 산출물 root: `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower`

## 실행

```bash
cd /workspace/prj/personal/data-scientist-career/decisionops-control-tower
pip install -r requirements.txt
scripts/run_all.sh
```

FastAPI server:

```bash
cd /workspace/prj/personal/data-scientist-career/decisionops-control-tower
export OUTPUT_ROOT=/tmp/decisionops-control-tower
scripts/run_server.sh
```

기본 URL:

- Dashboard: `http://127.0.0.1:8093/dashboard`
- Health: `http://127.0.0.1:8093/health`
- OpenAPI docs: `http://127.0.0.1:8093/docs`
- Ops metrics: `http://127.0.0.1:8093/api/ops-metrics`
- Impact policy audit: `http://127.0.0.1:8093/api/impact-policy-audit`
- Reviewer policy robustness: `http://127.0.0.1:8093/api/reviewer-policy-robustness`
- Reviewer action plan: `http://127.0.0.1:8093/api/reviewer-action-plan`
- Reviewer evidence bundles: `http://127.0.0.1:8093/api/reviewer-evidence-bundles`
- Approval audit integrity: `http://127.0.0.1:8093/api/approval-audit-integrity`
- Legacy hospital migration: `http://127.0.0.1:8093/api/migration/case-study`

쓰기 인증 모드:

```bash
cd /workspace/prj/personal/data-scientist-career/decisionops-control-tower
export CONTROL_TOWER_ROLE_TOKENS="viewer:<viewer-credential>,reviewer:<reviewer-credential>,admin:<admin-credential>"
export CONTROL_TOWER_DEPLOYMENT_MODE=hosted
scripts/run_server.sh
```

인증 경계 검증:

```bash
PYTHONPATH=src python3 scripts/verify_private_demo.py --exercise-write
PYTHONPATH=src python3 scripts/verify_private_demo.py --url http://127.0.0.1:8093 --exercise-write
```

Docker smoke:

```bash
scripts/check_docker_ready.py
scripts/verify_docker_deployment.sh
CONTAINER_NAME=decisionops-control-tower-codex-smoke PORT=8095 DOCKER_CLEANUP=1 scripts/verify_docker_deployment.sh
```

인자 없이 실행하면 검증용 container name과 loopback host port를 매번
격리합니다. 기본 ephemeral smoke image도 운영용
`decisionops-control-tower:local`과 분리하며, 성공·실패와 무관하게 smoke
container와 build가 완료된 ephemeral image를 자동 정리합니다.

Compose:

```bash
scripts/verify_compose_deployment.sh
COMPOSE_PROJECT_NAME=decisionops-control-tower-compose-smoke PORT=8094 COMPOSE_CLEANUP=1 scripts/verify_compose_deployment.sh
```

Compose smoke도 기본은 고유 project name·loopback port·ephemeral image를
사용하고 stack, network, build가 완료된 ephemeral image를 자동 정리합니다.
Docker의 shared build cache는 다른 build에 영향을 주지 않도록 prune하지 않습니다.

실제 Firebird→PostgreSQL 120k migration integration:

```bash
scripts/verify_rdb_migration.sh
```

이 명령은 공식 Firebird/PostgreSQL image와 전용 runner를 격리된 Compose stack으로 실행합니다. source/target DB는 tmpfs를 사용하고, 성공·실패와 무관하게 stack을 정리합니다. report는 `build/migration-rdb/firebird_postgres_migration.{json,md}`에 남습니다.

Deployment readiness gate:

```bash
PYTHONPATH=src python3 scripts/write_deployment_readiness.py --output-root /DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower
PYTHONPATH=src python3 scripts/write_deployment_readiness.py --require-auth --require-docker
```

Dashboard/UI와 기본 인증 smoke:

```bash
PYTHONPATH=src python3 scripts/verify_dashboard_ui.py
PYTHONPATH=src python3 scripts/smoke_api.py --auth-smoke
python3 scripts/smoke_public_demo.py
```

Analysis와 migration만 독립 재현:

```bash
PYTHONPATH=src python3 scripts/evaluate_analysis.py --minimum-pass-rate 0.9
PYTHONPATH=src python3 scripts/run_migration_case.py \
  --report-json /tmp/legacy_hospital_migration.json \
  --report-md /tmp/legacy_hospital_migration.md
PYTHONPATH=src python3 scripts/run_migration_rehearsal.py \
  --database /tmp/decisionops-migration-rehearsal.sqlite \
  --report-json /tmp/migration_rehearsal.json \
  --report-md /tmp/migration_rehearsal.md
```

사용자 평가는 현재 release/검증 범위에서 생략하며 `scripts/run_all.sh`의 gate에 포함하지 않습니다.

포트폴리오 캡처 생성:

```bash
python3 scripts/capture_demo_screenshots.py --url http://127.0.0.1:8093
```

`CONTROL_TOWER_ROLE_TOKENS` 설정 후 private demo 인증 smoke:

```bash
PYTHONPATH=src python3 scripts/verify_private_demo.py --exercise-write
```

깨끗한 demo state 재시드:

```bash
PYTHONPATH=src python3 scripts/prepare_demo_state.py
PYTHONPATH=src python3 scripts/prepare_demo_state.py --reset-approval-store
```

`--reset-approval-store`는 기존 `control_tower.sqlite`를 삭제하지 않고 `backups/`로 이동한 뒤 새 pending queue를 초기화한다.

## 검증

```bash
python3 /workspace/prj/personal/data-scientist-career/scripts/validate_weekend_project.py \
  --project /workspace/prj/personal/data-scientist-career/decisionops-control-tower \
  --stage saturday
```

## 성공 기준

- `pytest`가 통과합니다.
- 산출물 root 아래 `reports/run_summary.json` 또는 동등한 실행 요약이 생성됩니다.
- `scripts/smoke_api.py`가 `/health`, `/api/review-queue`, `/api/agent/reviewer-brief`, `/dashboard`, `/openapi.json`를 확인합니다.
- `scripts/smoke_api.py --auth-smoke`가 인증 없는 write 요청을 401로 막고, reviewer token이 인증 경계를 통과하는지 확인합니다.
- `scripts/verify_private_demo.py --exercise-write`가 viewer write 차단, reviewer/admin 승인 기록, history 반영, audit replay, credential 비출력을 확인합니다.
- `scripts/smoke_public_demo.py`가 공개 URL의 HTTP/HTML marker와 write-control 부재를 확인합니다.
- `scripts/verify_dashboard_ui.py`가 한국어 UI, primary CTA, OpenStreetMap tile 기반 후보번호 overlay, AI Reviewer Brief, 좌표 상태, 판단 근거 drawer, 내부 ID 숨김을 확인합니다.
- `scripts/verify_dashboard_ui.py`가 policy audit과 reviewer action plan section도 확인합니다.
- analysis evaluation이 5개 schema의 72개 task(template 40, paraphrase 24, multi-turn 8)에서 plan validity와 DuckDB↔pandas numeric correctness를 검증합니다.
- migration runner가 source 20행 = accepted 11행 + rejected 9행, target PK/FK, reject lineage, fingerprint를 검증합니다.
- scale/recovery runner가 120,000행을 48개 transaction batch로 처리하고 7,500행 checkpoint에서 중단·재개한 뒤 완료 run 재실행 0행과 schema-drift 사전 차단을 검증합니다.
- RDB integration runner가 실제 Firebird 5.0.4 source 120,000행을 PostgreSQL 17 target으로 처리하고, mid-batch rollback·2,500행 checkpoint 재개·0-row replay·actual catalog drift 차단·FK 0건을 검증합니다.
- `/api/migration/case-study`와 Technical dashboard가 같은 `MigrationReport` 계약을 표시합니다.
- `scripts/capture_demo_screenshots.py`가 dashboard, 지도, review queue, OpenAPI 캡처와 manifest를 생성합니다.
- `/api/ops-metrics`가 artifact freshness, queue, auth 상태를 반환합니다.
- `/api/impact-policy-audit`가 unsafe baseline과 guarded policy의 미검증 claim 차단 결과를 반환합니다.
- `/api/impact-policy-audit`가 public `GO`에서도 model-validated estimate만 허용하고, field outcome이 없으면 `unsafe_realized_impact_claim=fail`, `guarded_realized_impact_claim=pass`를 반환합니다.
- `/api/reviewer-policy-robustness`가 36개 deterministic stress row, safety dominance, regret, selection stability를 반환합니다.
- `/api/reviewer-action-plan`이 제한된 검토 용량에서 먼저 볼 local-only 후보를 반환합니다.
- `/api/reviewer-evidence-bundles`가 source age, freshness status, lock status, 64자 SHA-256 fingerprint를 반환합니다.
- `/api/approval-audit-integrity`가 decision hash chain과 queue-state replay 결과를 반환합니다.
- history payload 변조 또는 queue state mismatch test가 integrity `fail`과 deployment blocker를 재현합니다.
- stale/missing/future timestamp bundle은 `needs_more_evidence`로 차단됩니다.
- `scripts/write_monitoring_snapshot.py`가 latest snapshot과 history JSONL을 생성합니다.
- `scripts/write_deployment_readiness.py`가 local/container/hosted/public deploy decision을 JSON/Markdown으로 생성합니다.
- Docker/compose smoke가 image build, container startup, HTTP endpoints, healthcheck를 확인합니다.
- `control_tower.sqlite`가 local approval history store로 생성됩니다.
- `reports/approval_audit_integrity.json`이 chain/replay verdict를 보존합니다.
- 좌표 누락/범위 오류는 `0.0`으로 숨기지 않고 `station_lat/station_lon=null`, `coordinate_status`로 표시됩니다.
- README와 보고서가 실제 실행 결과 기준으로 갱신됩니다.
- 일요일 완료 기준에서는 `--stage sunday` validator와 quality gate를 통과하거나 `docs/research_gap_report.md`에 미달 항목이 남아 있습니다.
