# Case Study: 서울 공공자전거 DecisionOps Control Tower

## 한 줄 요약

기존 미국 bike-share benchmark에서 시작해 서울 따릉이 공개데이터 adapter로 확장하고, 대여 불가·반납 포화·재배치 우선순위를 지도, 검토 대기열, impact card, 승인 기록으로 연결한 운영 의사결정 제품이다.

## 문제

공공자전거 운영에서 단순 예측 점수만으로는 실제 조치가 어렵다. 운영자는 다음 질문을 동시에 봐야 한다.

- 어느 대여소가 대여 불가 또는 반납 포화 위험이 높은가?
- 지금 권고가 검증된 개선 효과인지, 아직 검증 전 후보인지 구분되는가?
- 자동 실행해도 되는가, 아니면 사람이 승인해야 하는가?
- 공개 배포나 외부 공유가 가능한 상태인가?

이 프로젝트는 예측 모델을 하나 더 만드는 대신, 예측·검증·agentic review 결과를 제품 workflow로 묶는 데 초점을 둔다.

## 데이터와 확장 구조

| 축 | 역할 | 현재 상태 |
|---|---|---|
| Citi Bike benchmark | station-level readiness와 prospective validation 기준선 | 2주 검증 snapshot 축적 중 |
| 서울 따릉이 공개데이터 | 한국 공공자전거 adapter와 실시간성 inventory snapshot | 정거장 약 2,700개 단위 수집 |
| Agentic DecisionOps Workbench | guarded decision agent, eval metric, human review queue | guarded/holdout success gate |
| Control Tower SQLite | reviewer decision audit trail | local write boundary |

핵심 설계는 adapter 구조다. 미국 benchmark는 방법론 기준선으로 두고, 서울 따릉이는 같은 control surface에 연결되는 국내 운영 데이터로 투영한다.

## 제품으로 만든 것

| Surface | 사용자가 보는 것 | 포트폴리오 신호 |
|---|---|---|
| 한국어 dashboard | 오늘의 결론, 차단 사유, 검토 대기열, 지도 | 제품 감각과 운영 이해 |
| 지도 | 따릉이 후보 조치 위치와 fallback 번호 지도 | 좌표 기반 의사결정 |
| Impact card | 권고 action, 후보 이동량, confidence, public-claim blocker | ML output의 business translation |
| Policy audit | unsafe publish와 guarded policy 비교 | 미검증 성과 claim 차단 |
| Policy robustness | 4 scenarios × 3 capacities × 3 policies | uncertainty 하 reviewer ranking 안정성 |
| Action plan | 검토자가 먼저 볼 후보와 local-only 판단 | 제한된 검토 용량 반영 |
| Evidence bundle | source age, freshness SLA, SHA-256 lock | stale/content drift 근거 차단 |
| Audit integrity | chained decision hash와 queue-state replay | 승인 이력 변조·불일치 탐지 |
| Review queue | 사람이 무엇을 검토해야 하는지 설명 | human-in-the-loop workflow |
| Approval API | reviewer/admin token 기반 approve/reject/needs_more_evidence | 안전한 write boundary |
| Deployment readiness | local/container/hosted/public `GO`/`NO_GO` 분리 | 배포 판단과 책임 경계 |

시연용 캡처와 3분 설명 흐름은 [demo_package.md](demo_package.md)에 정리했다.

## 현재 검증 결과

| 항목 | 상태 |
|---|---|
| Local private demo | `GO` |
| Container demo | `GO` |
| Hosted private demo | 인증 credential 설정 전 `NO_GO` |
| Public read-only snapshot | `GO` · 2026-07-20 12:25 KST aggregate |
| Hosted write API | credential/target hardening 전까지 `NO_GO` |
| Review queue | 54건 |
| Impact cards | 12건 |
| Policy audit | 8개 policy/capacity row |
| Policy robustness | 36개 comparison, safety dominance 100%, worst-case regret 0.0 |
| Reviewer action plan | 8건 |
| Reviewer evidence bundles | 8건, freshness/hash 계약 |
| Approval audit integrity | `PASS`, hash chain + state replay |
| CI | GitHub Actions 통과 |

서울 따릉이 validation과 evidence freshness가 `READY`여서 public read-only snapshot은 `GO`다. 다만 impact card는 실현 효과나 인과 성과가 아니라 reviewer-facing 후보 단위이며, hosted write API는 계속 별도 `NO_GO` gate다.

## 왜 식상하지 않은가

많은 DS 포트폴리오는 “데이터 수집 - 모델 학습 - 점수 출력”에서 끝난다. 이 프로젝트는 그 다음 단계인 운영 승인, 공개 배포 gate, 검토자 설명, audit trail을 제품 표면으로 만든다. 따라서 전통 DS뿐 아니라 AI/ML Product DS, Applied AI, ML Engineer 역할에 맞는 증거를 제공한다.

## 의사결정 경계

- Approval POST는 local SQLite에만 기록하며 각 event를 SHA-256 chain으로 연결한다.
- Decision history를 replay한 state가 현재 queue와 다르면 deployment gate를 차단한다.
- 외부 현장 조치, 실제 자전거 재배치, upstream artifact mutation은 하지 않는다.
- token 값과 `.env` 값은 report, dashboard, log에 출력하지 않는다.
- public read-only snapshot과 hosted write API를 분리하며, 후자는 credential과 target hardening 전까지 `NO_GO`다.

## 다음 마일스톤

| 마일스톤 | 완료 조건 |
|---|---|
| Private demo hardening | `CONTROL_TOWER_ROLE_TOKENS` 설정 후 `scripts/verify_private_demo.py` 통과 |
| Public snapshot refresh | 최신 aggregate, 3시간 SLA, public fixture 교차검증 통과 |
| Portfolio package | README, case study, demo package, DFD, runbook, screenshots가 한 흐름으로 연결 |
| Public claim update | public deploy `GO` 후 verified improvement와 한계 갱신 |
