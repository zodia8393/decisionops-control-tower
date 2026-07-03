# 재현 가이드

## 환경

- Python: 3.10 이상
- 산출물 root: `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower`

## 실행

```bash
cd /workspace/prj/data-scientist-career/decisionops-control-tower
pip install -r requirements.txt
scripts/run_all.sh
```

FastAPI server:

```bash
cd /workspace/prj/data-scientist-career/decisionops-control-tower
export OUTPUT_ROOT=/tmp/decisionops-control-tower
scripts/run_server.sh
```

기본 URL:

- Dashboard: `http://127.0.0.1:8093/dashboard`
- Health: `http://127.0.0.1:8093/health`
- OpenAPI docs: `http://127.0.0.1:8093/docs`
- Ops metrics: `http://127.0.0.1:8093/api/ops-metrics`

쓰기 인증 모드:

```bash
cd /workspace/prj/data-scientist-career/decisionops-control-tower
export CONTROL_TOWER_ROLE_TOKENS="viewer:<viewer-credential>,reviewer:<reviewer-credential>,admin:<admin-credential>"
scripts/run_server.sh
```

Docker smoke:

```bash
scripts/check_docker_ready.py
scripts/verify_docker_deployment.sh
CONTAINER_NAME=decisionops-control-tower-codex-smoke PORT=8095 DOCKER_CLEANUP=1 scripts/verify_docker_deployment.sh
```

Compose:

```bash
scripts/verify_compose_deployment.sh
COMPOSE_PROJECT_NAME=decisionops-control-tower-compose-smoke PORT=8094 COMPOSE_CLEANUP=1 scripts/verify_compose_deployment.sh
```

Deployment readiness gate:

```bash
PYTHONPATH=src python3 scripts/write_deployment_readiness.py --output-root /DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower
PYTHONPATH=src python3 scripts/write_deployment_readiness.py --require-auth --require-docker
```

Dashboard/UI와 인증 smoke:

```bash
PYTHONPATH=src python3 scripts/verify_dashboard_ui.py
PYTHONPATH=src python3 scripts/smoke_api.py --auth-smoke
```

깨끗한 demo state 재시드:

```bash
PYTHONPATH=src python3 scripts/prepare_demo_state.py
PYTHONPATH=src python3 scripts/prepare_demo_state.py --reset-approval-store
```

`--reset-approval-store`는 기존 `control_tower.sqlite`를 삭제하지 않고 `backups/`로 이동한 뒤 새 pending queue를 초기화한다.

## 검증

```bash
python3 /workspace/prj/data-scientist-career/scripts/validate_weekend_project.py \
  --project /workspace/prj/data-scientist-career/decisionops-control-tower \
  --stage saturday
```

## 성공 기준

- `pytest`가 통과합니다.
- 산출물 root 아래 `reports/run_summary.json` 또는 동등한 실행 요약이 생성됩니다.
- `scripts/smoke_api.py`가 `/health`, `/api/review-queue`, `/dashboard`, `/openapi.json`를 확인합니다.
- `scripts/smoke_api.py --auth-smoke`가 인증 없는 write 요청을 401로 막고, reviewer token이 인증 경계를 통과하는지 확인합니다.
- `scripts/verify_dashboard_ui.py`가 한국어 UI, primary CTA, 지도 iframe/SVG fallback, 좌표 상태, 판단 근거 drawer, 내부 ID 숨김을 확인합니다.
- `/api/ops-metrics`가 artifact freshness, queue, auth 상태를 반환합니다.
- `scripts/write_monitoring_snapshot.py`가 latest snapshot과 history JSONL을 생성합니다.
- `scripts/write_deployment_readiness.py`가 local/container/hosted/public deploy decision을 JSON/Markdown으로 생성합니다.
- Docker/compose smoke가 image build, container startup, HTTP endpoints, healthcheck를 확인합니다.
- `control_tower.sqlite`가 local approval history store로 생성됩니다.
- 좌표 누락/범위 오류는 `0.0`으로 숨기지 않고 `station_lat/station_lon=null`, `coordinate_status`로 표시됩니다.
- README와 보고서가 실제 실행 결과 기준으로 갱신됩니다.
- 일요일 완료 기준에서는 `--stage sunday` validator와 quality gate를 통과하거나 `docs/research_gap_report.md`에 미달 항목이 남아 있습니다.
