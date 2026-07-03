# DecisionOps Control Tower

## 결론

Bike-share 운영 ML과 Agentic DecisionOps Workbench의 review/eval 산출물을 하나의 FastAPI/SQLite 기반 control state, reviewer queue, impact card, approval workflow, dashboard로 묶는 Stage 3 capstone product slice를 만들었다.

## 핵심 수치

| 항목 | 값 | 의미 |
|---|---:|---|
| Upstream stages | 2 | bike-share operations ML + agentic review workbench |
| Product surfaces | 15 | FastAPI, OpenAPI docs, control state JSON, review queue CSV, impact cards, SQLite approval store, Korean reviewer dashboard, map/fallback UI, dashboard UI verifier, RBAC-lite writes, auth smoke, structured logs, monitoring snapshot, deployment readiness gate, compose smoke |
| Guarded success | 1.000 | Stage 2 main eval 성공률 |
| Holdout success | 1.000 | Stage 2 adversarial prompt 성공률 |
| Review queue | 42 | reviewer가 승인해야 할 pending decision |
| Impact cards | 12 | 서울 따릉이 우선순위를 검증 상태와 함께 reviewer card로 투영 |
| Incident source | 120 | NY 511 public event sample row 수 |
| Public deploy | NO_GO | bike-share snapshot readiness가 아직 READY가 아님 |

## 무엇을 만들었나

| 구성 | 설명 |
|---|---|
| Control state | Stage 1/2 readiness, prepublish, metric, blocker를 하나의 JSON으로 통합 |
| Review queue | Stage 2 human review queue를 Control Tower approval queue로 변환 |
| Impact cards | 서울 따릉이 추천 action을 후보 이동량, confidence, evidence, blocker로 변환 |
| FastAPI | `/health`, `/api/control-state`, `/api/review-queue`, approval POST, history, ops metrics, OpenAPI docs 제공 |
| SQLite approval store | reviewer decision과 audit history를 `OUTPUT_ROOT/control_tower.sqlite`에 저장 |
| Dashboard | 운영자가 blocker, ops metrics, queue, approval history를 한 화면에서 확인하고 승인 action을 실행 |
| RBAC-lite/logging | `CONTROL_TOWER_ROLE_TOKENS` 설정 시 viewer/reviewer/admin 역할 분리, request log는 JSON으로 출력 |
| Monitoring snapshot | `ops_metrics_snapshot.json`, `ops_metrics_history.jsonl`로 운영 상태를 산출물화 |
| Deployment readiness | local/container/hosted/public deploy 판단을 `deployment_readiness.json`, `deployment_readiness.md`로 분리 |
| Reports | final report, system card, data contract, quality scores 생성 |

## 얻은 인사이트

- Stage 2가 public-ready여도 최종 public deploy는 Stage 1 live readiness가 막을 수 있다.
- Control Tower의 핵심은 모델 성능이 아니라 approval boundary와 blocker visibility다.
- Impact card는 운영 후보를 선명하게 만들지만, Seoul validation이 READY 전이면 성과 claim이 아니라 local review evidence로 제한해야 한다.
- Approval POST는 reviewer/admin 역할이 있을 때만 허용되고, 외부 실행을 호출하지 않고 local SQLite에만 기록한다.

## 방법 선택 이유

| 선택 | 이유 |
|---|---|
| Product slice after seed | upstream artifact contract를 검증한 뒤 API/persistence/dashboard를 붙여 납품 신호를 만들기 위해 |
| Local write boundary | 예측·agent 산출물을 실제 field action으로 오해하지 않도록 하기 위해 |
| Review queue 중심 | 운영 자동화의 안전 경계를 제품 workflow로 표현하기 위해 |
| Impact card 분리 | 추천 action, 후보 효과, blocker를 approval decision 전에 검토하기 위해 |
| API contract artifact | endpoint scope와 write policy가 흔들리지 않게 하기 위해 |

## 대표 시각화

| 산출물 | 확인 위치 |
|---|---|
| Dashboard | `/dashboard` 또는 `dashboard/index.html` |
| Control state | `reports/control_state.json` |
| Review queue | `reports/control_review_queue.csv` |
| Impact cards | `reports/impact_cards.csv`, `reports/impact_cards.json` |
| API contract | `reports/api_contract.json` |
| Approval DB | `control_tower.sqlite` |
| Deployment gate | `reports/deployment_readiness.md` |

설계 문서는 [docs/system_design.md](docs/system_design.md), 데이터 흐름은 [docs/data_flow_diagram.md](docs/data_flow_diagram.md)에서 확인한다.

## 현재 상태

- Stage: Control Tower product slice
- CI/smoke: local `scripts/run_all.sh` pass
- Local private demo: `GO`
- Container demo: `GO`
- Hosted private demo: credentials를 설정하기 전까지 `NO_GO`
- Public deploy: upstream bike-share readiness와 Seoul validation이 READY 전까지 `NO_GO`
- Dashboard: 한국어 reviewer UI, 따릉이 후보 지도, SVG fallback, 난해한 내부 ID 숨김, 판단 근거/검토 기준 drawer 포함
- Impact card: Seoul validation `NOT_READY`면 local review only
- 남은 blocker: upstream bike-share prospective readiness, Seoul validation READY, hosted runtime identity hardening

## 실행 방법

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export OUTPUT_ROOT=/tmp/decisionops-control-tower
scripts/run_all.sh
```

로컬 서버:

```bash
export OUTPUT_ROOT=/tmp/decisionops-control-tower
scripts/run_server.sh
```

확인:

| surface | URL |
|---|---|
| Dashboard | `http://127.0.0.1:8093/dashboard` |
| Health | `http://127.0.0.1:8093/health` |
| Impact cards | `http://127.0.0.1:8093/api/impact-cards` |
| OpenAPI docs | `http://127.0.0.1:8093/docs` |
| Ops metrics | `http://127.0.0.1:8093/api/ops-metrics` |

쓰기 인증을 켜려면:

```bash
export CONTROL_TOWER_ROLE_TOKENS="viewer:<viewer-credential>,reviewer:<reviewer-credential>,admin:<admin-credential>"
scripts/run_server.sh
```

Docker/compose 진단:

```bash
scripts/check_docker_ready.py
scripts/verify_docker_deployment.sh
scripts/verify_compose_deployment.sh
```

대시보드/UI 계약 검증:

```bash
PYTHONPATH=src scripts/verify_dashboard_ui.py
PYTHONPATH=src scripts/smoke_api.py --auth-smoke
```

데모 상태를 다시 만들려면:

```bash
PYTHONPATH=src scripts/prepare_demo_state.py
```

기존 승인 이력을 보존하면서 깨끗한 pending 상태로 시연하려면 SQLite DB를 `backups/`로 이동한 뒤 재시드한다.

```bash
PYTHONPATH=src scripts/prepare_demo_state.py --reset-approval-store
```

8093 포트에서 로컬 장기 실행:

```bash
sg docker -c 'docker rm -f decisionops-control-tower-smoke 2>/dev/null || true'
sg docker -c 'COMPOSE_PROJECT_NAME=decisionops-control-tower PORT=8093 docker compose up --build -d'
curl -fsS http://127.0.0.1:8093/health | python3 -m json.tool
```

중지:

```bash
sg docker -c 'COMPOSE_PROJECT_NAME=decisionops-control-tower PORT=8093 docker compose down'
```

기존 8093 서버를 유지한 채 검증하려면:

```bash
CONTAINER_NAME=decisionops-control-tower-codex-smoke PORT=8095 DOCKER_CLEANUP=1 scripts/verify_docker_deployment.sh
COMPOSE_PROJECT_NAME=decisionops-control-tower-compose-smoke PORT=8094 COMPOSE_CLEANUP=1 scripts/verify_compose_deployment.sh
```

## 산출물 확인 방법

| 보고 싶은 것 | 명령 | 위치 |
|---|---|---|
| Full run | `scripts/run_all.sh` | `reports/`, `dashboard/` |
| Dashboard | `scripts/run_all.sh` | `dashboard/index.html` |
| Dashboard UI verification | `scripts/verify_dashboard_ui.py` | live/TestClient dashboard contract |
| Control state | `scripts/run_all.sh` | `reports/control_state.json` |
| Impact cards | `scripts/run_all.sh` | `reports/impact_cards.csv`, `reports/impact_cards.json` |
| API contract | `scripts/run_all.sh` | `reports/api_contract.json` |
| SQLite approval history | `scripts/run_all.sh` 또는 server | `control_tower.sqlite` |
| Ops monitoring | `scripts/run_all.sh` | `reports/ops_metrics_snapshot.json`, `reports/ops_metrics_history.jsonl` |
| Deployment readiness | `scripts/run_all.sh` | `reports/deployment_readiness.json`, `reports/deployment_readiness.md` |

## 한계

- Approval persistence는 local SQLite이며 token-role 기반 RBAC-lite다. 계정, 세션, 감사자별 권한정책은 아직 별도 identity provider가 아니다.
- Public deploy는 bike-share prospective snapshot readiness가 READY가 될 때까지 `NO_GO`다.
- 지도는 OpenStreetMap iframe을 쓰며, 외부 타일이 차단될 때도 SVG 후보 번호 지도가 남도록 설계했다.
- 좌표가 없거나 서울 권역 밖이면 `station_lat/station_lon`을 `null`로 두고 `coordinate_status`로 명시한다. `0.0`으로 숨기지 않는다.
