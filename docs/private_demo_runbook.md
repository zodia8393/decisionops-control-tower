# Private Demo Runbook

## 목적

`DecisionOps Control Tower`를 공개 배포하지 않고, reviewer/admin 인증이 켜진 상태로 시연하기 위한 절차다. 이 runbook은 token 값을 기록하지 않는다.

## 전제

- Repo: `/workspace/prj/personal/data-scientist-career/decisionops-control-tower`
- 기본 앱 URL: `http://127.0.0.1:8093`
- 기본 output root: `/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower`
- 공개 data/claim 상태는 실행 시점 freshness에 따라 `GO/NO_GO`가 달라진다. 2026-07-21 실행은 freshness 0/8로 `NO_GO`였고, 2026-07-22 09:03 KST 실행은 갱신된 source freshness 8/8로 `GO`다. 실제 Pages는 legacy `STALE`, hosted write는 credential 설정 전까지 `NO_GO`다.

## 1. Credential 설정

역할은 세 가지다.

| Role | 권한 |
|---|---|
| `viewer` | dashboard/API 조회, write 불가 |
| `reviewer` | approval decision 기록 가능 |
| `admin` | approval decision 기록 가능 |

환경 변수 형식:

```bash
export CONTROL_TOWER_ROLE_TOKENS="viewer:<viewer-credential>,reviewer:<reviewer-credential>,admin:<admin-credential>"
export CONTROL_TOWER_DEPLOYMENT_MODE=hosted
```

Hosted mode에서는 reviewer/admin credential이 하나 이상 필요하고 각 credential은 최소 24자여야 한다. Runtime은 원문 credential 대신 SHA-256 digest만 보관한다. Legacy 단일 reviewer token도 지원하지만 role 구분이 보이는 `CONTROL_TOWER_ROLE_TOKENS`를 우선 사용한다.

## 2. 산출물 생성과 기본 검증

```bash
cd /workspace/prj/personal/data-scientist-career/decisionops-control-tower
scripts/run_all.sh
```

성공 기준:

- `81 passed` 이상
- `dashboard ui verification complete`
- `deployment readiness complete`

## 3. Private demo 인증 경계 검증

서버를 띄우기 전 in-process로 검증:

```bash
PYTHONPATH=src scripts/verify_private_demo.py --exercise-write
```

검증 항목:

- `auth_required=True`
- credential 없는 write 요청은 `401`
- `viewer` write 요청은 `403`
- `reviewer` 또는 `admin` write credential은 인증을 통과하고 실제 `needs_more_evidence` 결정을 local SQLite에 기록
- 기록이 approval history와 hash-chain/state replay에 반영되고 integrity `pass`
- queue와 impact card가 비어 있지 않음
- 출력에 credential 값이 포함되지 않음

## 4. 서버 실행

```bash
HOST=127.0.0.1 PORT=8093 scripts/run_server.sh
```

다른 터미널에서 live server 검증:

```bash
PYTHONPATH=src scripts/verify_private_demo.py --url http://127.0.0.1:8093 --exercise-write
curl -fsS http://127.0.0.1:8093/health | python3 -m json.tool
```

시연 URL:

| Surface | URL |
|---|---|
| Dashboard | `http://127.0.0.1:8093/dashboard` |
| OpenAPI | `http://127.0.0.1:8093/docs` |
| Health | `http://127.0.0.1:8093/health` |
| Impact cards | `http://127.0.0.1:8093/api/impact-cards` |
| Ops metrics | `http://127.0.0.1:8093/api/ops-metrics` |

## 5. Docker private demo

```bash
COMPOSE_PROJECT_NAME=decisionops-control-tower PORT=8093 docker compose up --build -d
PYTHONPATH=src scripts/verify_private_demo.py --url http://127.0.0.1:8093
```

현재 shell에서 Docker group이 반영되지 않은 경우:

```bash
sg docker -c 'COMPOSE_PROJECT_NAME=decisionops-control-tower PORT=8093 docker compose up --build -d'
```

중지:

```bash
COMPOSE_PROJECT_NAME=decisionops-control-tower PORT=8093 docker compose down
```

## 6. 실패 대응

| 증상 | 원인 | 조치 |
|---|---|---|
| `auth_required`가 `false` | role token 미설정 | `CONTROL_TOWER_ROLE_TOKENS` 설정 후 재실행 |
| `viewer` write가 `404` | viewer가 write role로 잘못 처리됨 | auth role parser와 `WRITE_ROLES` 테스트 확인 |
| queue가 0건 | upstream artifact 또는 demo fallback 문제 | `scripts/run_all.sh` 재실행, `reports/control_review_queue.csv` 확인 |
| impact card가 0건 | Seoul priority artifact 또는 demo fallback 문제 | `reports/impact_cards.json` 확인 |
| public read-only가 `NO_GO`로 보임 | source stale 또는 fixture 미갱신 | `control_state.json` blocker 확인 후 `refresh_public_demo_inputs.py` 실행 |

## 7. 시연 스크립트

1. Dashboard 첫 화면에서 현재 public data/claim의 동적 `GO/NO_GO`와 hosted write `NO_GO`가 분리된 경계임을 보여준다.
2. 지도에서 서울 따릉이 후보 조치 위치를 보여준다.
3. Impact card에서 권고 action, 좌표 상태, validation blocker를 설명한다.
4. Review queue에서 “무엇을 검토하나”와 “원천 근거 요약”을 보여준다.
5. OpenAPI에서 approval endpoint와 write policy를 보여준다.
6. `verify_private_demo.py` 결과로 인증 경계가 자동 검증됨을 보여준다.
