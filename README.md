# DecisionOps Control Tower

[![ci](https://github.com/zodia8393/decisionops-control-tower/actions/workflows/ci.yml/badge.svg)](https://github.com/zodia8393/decisionops-control-tower/actions/workflows/ci.yml)

## 결론

서울 공공자전거 운영 문제를 예측 점수에서 끝내지 않고, 지도 기반 후보 조치, 사람 검토 대기열, 승인 기록, 배포 가능 여부 판단까지 연결한 AI/ML product slice입니다.

현재 결론은 명확합니다. Local/private demo는 `GO`지만 public deploy와 성과 claim은 upstream readiness가 끝날 때까지 `NO_GO`입니다.

## 무엇을 만들었나

| Surface | 구현 증거 | 의사결정 |
|---|---|---|
| Reviewer dashboard | 지도, impact cards, policy audit, action plan | 먼저 검토할 후보 선택 |
| Policy robustness | 4 stress scenarios × 3 capacities × 3 policies | 안전 우선 ranking 안정성 확인 |
| AI Reviewer Agent | evidence-locked reviewer brief, candidate review notes | 근거 기반 검토 요약 |
| Evidence bundles | source age, 3-hour SLA, SHA-256 fingerprint | stale 근거 차단·content drift 식별 |
| Approval API | role token 기반 approve/reject/needs-more-evidence | local audit 기록 |
| SQLite audit trail | `control_tower.sqlite` | 결정 이력 보존 |
| Deployment gate | local/container/hosted/public 분리 | 공개 여부 `GO/NO_GO` |

## 핵심 수치

| 항목 | 값 | 의미 |
|---|---:|---|
| Impact cards | 12 | 서울 따릉이 후보 조치 수 |
| Candidate units | 803 | 검토 대상 후보 이동량 |
| Unsupported claim avoided | 803 | 공개 claim으로 쓰지 않고 차단한 단위 |
| Reviewer action plan | 8 | 검토자가 먼저 볼 local-only 계획 |
| Agent review notes | 8 | 상위 후보별 evidence-locked 검토 메모 |
| Fresh evidence bundles | 8/8 | 최신성·content lock 계약을 통과한 심의 패킷 |
| Robustness comparisons | 36 | 효과 jitter·confidence stress·source dropout 포함 |
| Guarded safety dominance | 100% | invalid evidence를 먼저 줄이고 동률에서 조정 단위 비교 |
| Review queue | 54 | 승인/반려/근거 요청 대기 건수 |
| Public deploy | `NO_GO` | 외부 공개 차단 상태 |

## 얻은 인사이트

운영 제품에서 중요한 것은 높은 점수보다 “지금 공개해도 되는가”입니다. 이 프로젝트는 후보 효과 단위를 계산하면서도, 검증 전 수치를 대외 성과로 말하지 못하게 막습니다.

무검토 공개 기준선은 803단위의 unsupported claim을 만들 수 있습니다. Guarded policy는 같은 후보를 local reviewer evidence로만 보존합니다.

검증 상태가 `READY`여도 근거가 오래되면 같은 판단을 재사용하면 안 됩니다. 각 심의 패킷은 관측 시각과 3시간 SLA를 확인하고, source content가 달라지면 SHA-256 fingerprint도 바뀝니다.

Reviewer ranking도 단일 입력값에 고정하면 취약합니다. 4개 stress scenario에서 guarded policy는 source order보다 invalid evidence를 우선 줄였고, 안전성이 같을 때 confidence-adjusted 후보 단위를 유지하거나 높였습니다.

## 방법 선택 이유

| 선택 | 이유 | 대안 |
|---|---|
| FastAPI | reviewer workflow를 바로 실행 | notebook-only 분석 |
| SQLite | local audit trail을 간단히 보존 | 외부 DB 선행 |
| Policy audit | 성과 claim 위험을 수치화 | 설명문만 작성 |
| Deterministic stress test | 용량·효과·confidence·source 누락에 대한 ranking 안정성 측정 | 단일 best-case 순위 |
| Action plan | 제한된 검토 시간을 반영 | 전체 queue 나열 |
| Freshness + fingerprint | 오래되거나 바뀐 근거를 식별 | artifact 존재 여부만 확인 |
| `NO_GO` gate | 공개 배포와 demo를 분리 | 단일 ready flag |

## 대표 시각화

![DecisionOps Control Tower dashboard](docs/assets/demo/dashboard_overview.png)

| 장면 | 캡처 |
|---|---|
| 서울 따릉이 후보 조치 지도 | <img src="docs/assets/demo/impact_map_section.png" alt="Seoul Ddareungi action map" width="520"> |
| 검토 대기열 | <img src="docs/assets/demo/reviewer_queue.png" alt="Reviewer queue" width="520"> |
| OpenAPI surface | <img src="docs/assets/demo/openapi_docs.png" alt="OpenAPI docs" width="520"> |

시연 흐름은 [docs/demo_package.md](docs/demo_package.md)에 정리했습니다.

## 현재 상태

| 항목 | 상태 | 의미 |
|---|---|---|
| Local private demo | `GO` | reviewer walkthrough 가능 |
| Container demo | `GO` | Docker smoke 가능 |
| Hosted private demo | `NO_GO` | write auth 미설정 |
| Public deploy | `NO_GO` | upstream readiness 대기 |
| Seoul validation | `READY` | 후보 검토 가능 |
| Public claim | `blocked` | 외부 성과 주장 금지 |

`NO_GO`는 실패가 아니라 의도한 guardrail입니다.

## 실행 방법

```bash
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
| Policy audit | `http://127.0.0.1:8093/api/impact-policy-audit` |
| Policy robustness | `http://127.0.0.1:8093/api/reviewer-policy-robustness` |
| Action plan | `http://127.0.0.1:8093/api/reviewer-action-plan` |
| Evidence bundles | `http://127.0.0.1:8093/api/reviewer-evidence-bundles` |
| AI reviewer brief | `http://127.0.0.1:8093/api/agent/reviewer-brief` |
| Candidate review notes | `http://127.0.0.1:8093/api/agent/candidate/{candidate_id}/review-notes` |
| Ops metrics | `http://127.0.0.1:8093/api/ops-metrics` |
| OpenAPI | `http://127.0.0.1:8093/docs` |

## 산출물 확인 방법

| 산출물 | 경로 | 의미 |
|---|---|---|
| Control state | `reports/control_state.json` | 배포 판단과 blocker |
| Impact cards | `reports/impact_cards.json` | 따릉이 후보 조치 |
| Policy audit | `reports/impact_policy_audit.json` | 공개 claim 차단 검증 |
| Policy robustness | `reports/reviewer_policy_robustness.json` | 36-row controlled stress comparison |
| Action plan | `reports/reviewer_action_plan.json` | 검토 우선순위 |
| Evidence bundles | `reports/reviewer_evidence_bundles.json` | 최신성·fingerprint가 잠긴 심의 근거 |
| Agent brief | `reports/agent_reviewer_brief.json` | read-only 검토 요약 |
| Candidate notes | `reports/agent_candidate_review_notes.json` | 후보별 evidence lock |
| Dashboard | `dashboard/index.html` | reviewer 화면 |
| Quality gate | `reports/quality_gate_scores.csv` | portfolio quality score |

기본 산출물 root는 `OUTPUT_ROOT`로 바꿀 수 있습니다.

## Private Demo Auth

쓰기 인증을 켜면 approval write는 `reviewer` 또는 `admin` role만 가능합니다. Token 값은 log, report, screenshot에 출력하지 않습니다.

```bash
export CONTROL_TOWER_ROLE_TOKENS="viewer:<viewer-credential>,reviewer:<reviewer-credential>,admin:<admin-credential>"
PYTHONPATH=src scripts/verify_private_demo.py
PYTHONPATH=src scripts/verify_private_demo.py --url http://127.0.0.1:8093
```

Runbook: [docs/private_demo_runbook.md](docs/private_demo_runbook.md)

## AI Reviewer Agent

LLM은 source of truth가 아니라 reviewer assistant입니다. `/api/agent/reviewer-brief`는 health/API/artifact를 근거로 현재 상태, claim risk, 다음 검토 action을 요약하지만, `GO/NO_GO`와 수치는 deterministic pipeline과 policy gate에서 가져옵니다.

기본값은 credential 없이 동작하는 `fallback` mode입니다. 선택적으로 `CONTROL_TOWER_LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `CONTROL_TOWER_LLM_MODEL`을 설정하면 LLM 요약을 시도하되, 실패하거나 미설정이면 fallback brief를 반환합니다. Token 값은 log, report, screenshot에 출력하지 않습니다.

## 검증

```bash
python3 -m compileall -q src tests scripts
PYTHONPATH=src python3 -m pytest -q
scripts/run_all.sh
PYTHONPATH=src scripts/verify_dashboard_ui.py
curl -fsS http://127.0.0.1:8093/api/agent/reviewer-brief
PYTHONPATH=src scripts/smoke_api.py --auth-smoke
```

Docker/Compose:

```bash
scripts/check_docker_ready.py
scripts/verify_docker_deployment.sh
scripts/verify_compose_deployment.sh
```

포트폴리오 캡처:

```bash
scripts/capture_demo_screenshots.py --url http://127.0.0.1:8093
```

## 구조

| 경로 | 내용 |
|---|---|
| [src/decisionops_control_tower](src/decisionops_control_tower) | pipeline, FastAPI app, dashboard renderer, SQLite store |
| [scripts](scripts) | smoke, deployment readiness, Docker verification, screenshot capture |
| [tests](tests) | API, pipeline, dashboard contract, private auth, deployment gate tests |
| [docs/case_study.md](docs/case_study.md) | 문제 정의와 포트폴리오 case study |
| [docs/demo_package.md](docs/demo_package.md) | screenshot 기반 3분 시연 패키지 |
| [docs/reproducibility.md](docs/reproducibility.md) | 재현 명령과 성공 기준 |

## 한계

- Approval POST는 local SQLite audit trail에만 기록합니다.
- 실제 자전거 재배치, 외부 dispatch, upstream artifact mutation은 하지 않습니다.
- Public deploy는 upstream readiness와 hosted hardening 전까지 `NO_GO`입니다.
- Evidence fingerprint는 source drift 탐지용이며 전자서명이나 외부 공증을 대체하지 않습니다.
- Robustness audit은 reviewer ordering stress test이며 실현 효과나 인과효과 추정치가 아닙니다.
- 좌표 누락 또는 서울 권역 밖 좌표는 `0.0`으로 숨기지 않고 `null`과 `coordinate_status`로 표시합니다.
- `.env`, API key, token 값은 문서와 log에 출력하지 않습니다.
