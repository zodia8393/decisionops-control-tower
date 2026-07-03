# DecisionOps Control Tower

[![ci](https://github.com/zodia8393/decisionops-control-tower/actions/workflows/ci.yml/badge.svg)](https://github.com/zodia8393/decisionops-control-tower/actions/workflows/ci.yml)

서울 공공자전거 운영 문제를 **예측 점수**에서 끝내지 않고, 지도 기반 후보 조치, 사람 검토 대기열, 승인 기록, 배포 가능 여부 판단까지 연결한 AI/ML product slice입니다.

기존 미국 bike-share benchmark에서 시작해 서울 따릉이 공개데이터 adapter로 확장했고, 실제 운영 문제인 **대여 불가, 반납 포화, 재배치 우선순위**를 reviewer-facing 의사결정 제품으로 구현했습니다.

![DecisionOps Control Tower dashboard](docs/assets/demo/dashboard_overview.png)

## What This Shows

| 평가자가 봐야 할 것 | 구현 증거 |
|---|---|
| Product DS 문제 정의 | 공공자전거 재배치 조치를 `GO/NO_GO`, blocker, review queue로 표현 |
| Applied AI workflow | agentic review/eval 결과를 human approval workflow로 연결 |
| ML output translation | 서울 따릉이 우선순위를 impact card, 후보 이동량, confidence, validation blocker로 변환 |
| Backend/product delivery | FastAPI, OpenAPI, SQLite audit trail, Docker/Compose smoke |
| Responsible deployment | private demo와 public deploy를 분리하고, validation 전 public claim 차단 |
| Portfolio presentation | 실제 dashboard/map/review queue screenshot과 3분 시연 흐름 제공 |

## Product Surfaces

| Surface | 설명 |
|---|---|
| Korean reviewer dashboard | 오늘의 결론, blocker, 지도, impact cards, review queue, approval history |
| Seoul Ddareungi impact cards | 대여소별 권고 action, 예상 완화량, 좌표 상태, 검증 상태 |
| Approval API | `reviewer`/`admin` role token 기반 approve/reject/needs-more-evidence 기록 |
| SQLite audit trail | reviewer decision을 local `control_tower.sqlite`에 보존 |
| Ops metrics | queue, artifact freshness, auth 상태, public deploy decision |
| Deployment gate | local/container/hosted/public `GO`/`NO_GO`를 분리 산출 |

## Demo

| 장면 | 캡처 |
|---|---|
| 서울 따릉이 후보 조치 지도 | <img src="docs/assets/demo/impact_map_section.png" alt="Seoul Ddareungi action map" width="520"> |
| 검토 대기열 | <img src="docs/assets/demo/reviewer_queue.png" alt="Reviewer queue" width="520"> |
| OpenAPI surface | <img src="docs/assets/demo/openapi_docs.png" alt="OpenAPI docs" width="520"> |

시연 흐름은 [docs/demo_package.md](docs/demo_package.md)에 정리했습니다.

## Current State

| 항목 | 상태 |
|---|---|
| CI | GitHub Actions pass |
| Local private demo | `GO` |
| Container demo | `GO` |
| Hosted private demo | credential 설정 전 `NO_GO` |
| Public deploy | upstream readiness와 Seoul validation 전까지 `NO_GO` |
| Review queue | 42건 |
| Impact cards | 12건 |
| Seoul validation | 최소 snapshot 기준 충족 전까지 `NOT_READY` |

`NO_GO`는 실패가 아니라 의도한 guardrail입니다. 서울 따릉이 validation이 충분해지기 전에는 성과 claim을 하지 않고 local review evidence로만 보여줍니다.

## Architecture

```text
Citi Bike benchmark artifacts
Seoul Ddareungi public-data adapter
Agentic DecisionOps Workbench eval/review artifacts
        |
        v
DecisionOps Control Tower
  - control_state.json
  - impact_cards.json/csv
  - review_queue.csv
  - FastAPI + OpenAPI
  - SQLite approval store
  - Korean dashboard
  - deployment readiness gate
```

자세한 설계는 [docs/system_design.md](docs/system_design.md), 한국어 DFD는 [docs/data_flow_diagram.md](docs/data_flow_diagram.md)를 봅니다.

## Quick Start

```bash
cd /workspace/prj/data-scientist-career/decisionops-control-tower
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
scripts/run_all.sh
```

로컬 서버:

```bash
export OUTPUT_ROOT=/tmp/decisionops-control-tower
scripts/run_server.sh
```

주요 URL:

| Surface | URL |
|---|---|
| Dashboard | `http://127.0.0.1:8093/dashboard` |
| Health | `http://127.0.0.1:8093/health` |
| Impact cards | `http://127.0.0.1:8093/api/impact-cards` |
| Ops metrics | `http://127.0.0.1:8093/api/ops-metrics` |
| OpenAPI | `http://127.0.0.1:8093/docs` |

## Private Demo Auth

쓰기 인증을 켜면 approval write는 `reviewer` 또는 `admin` role만 가능합니다. Token 값은 log, report, screenshot에 출력하지 않습니다.

```bash
export CONTROL_TOWER_ROLE_TOKENS="viewer:<viewer-credential>,reviewer:<reviewer-credential>,admin:<admin-credential>"
PYTHONPATH=src scripts/verify_private_demo.py
PYTHONPATH=src scripts/verify_private_demo.py --url http://127.0.0.1:8093
```

Runbook: [docs/private_demo_runbook.md](docs/private_demo_runbook.md)

## Verification

```bash
python3 -m compileall -q src tests scripts
PYTHONPATH=src python3 -m pytest -q
scripts/run_all.sh
PYTHONPATH=src scripts/verify_dashboard_ui.py
PYTHONPATH=src scripts/smoke_api.py --auth-smoke
```

Docker/Compose:

```bash
scripts/check_docker_ready.py
scripts/verify_docker_deployment.sh
scripts/verify_compose_deployment.sh
```

포트폴리오 캡처 재생성:

```bash
scripts/capture_demo_screenshots.py --url http://127.0.0.1:8093
```

## Repository Guide

| 경로 | 내용 |
|---|---|
| [src/decisionops_control_tower](src/decisionops_control_tower) | pipeline, FastAPI app, dashboard renderer, SQLite store |
| [scripts](scripts) | smoke, deployment readiness, Docker verification, screenshot capture |
| [tests](tests) | API, pipeline, dashboard contract, private auth, deployment gate tests |
| [docs/case_study.md](docs/case_study.md) | 문제 정의와 포트폴리오 case study |
| [docs/demo_package.md](docs/demo_package.md) | screenshot 기반 3분 시연 패키지 |
| [docs/reproducibility.md](docs/reproducibility.md) | 재현 명령과 성공 기준 |

## Boundaries

- Approval POST는 local SQLite audit trail에만 기록합니다.
- 실제 자전거 재배치, 외부 dispatch, upstream artifact mutation은 하지 않습니다.
- Public deploy는 upstream readiness와 hosted hardening 전까지 `NO_GO`입니다.
- 좌표 누락 또는 서울 권역 밖 좌표는 `0.0`으로 숨기지 않고 `null`과 `coordinate_status`로 표시합니다.
- `.env`, API key, token 값은 문서와 log에 출력하지 않습니다.
