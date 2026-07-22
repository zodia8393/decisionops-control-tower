# Privacy / Publication Gate

2026-07-21 재실행은 tracked public evidence가 3시간 SLA를 넘어 freshness 0/8, public data/claim gate `NO_GO`였다. Source 갱신 뒤 2026-07-22 09:03 KST 실행은 freshness 8/8로 data/claim `GO`다. 이 상태는 SLA에 따라 다시 만료될 수 있고, 실제 deployed Pages는 아직 2026-07-20 legacy snapshot이다.

## 공개 금지

- raw 내부 데이터
- 개인정보와 재식별 가능한 식별자
- SNS 원문, 사용자 ID, profile, 댓글 원문
- 민감 좌표 원본
- token, API key, cookie, `.env` 값

## 공개 허용

- 재현 가능한 코드
- schema contract
- public NY 511 sample의 derived incident surface
- 익명화·집계 feature
- metric, figure, model card, runbook

## Gate Result

| 항목 | 상태 | 근거 |
|---|---|---|
| 내부 데이터 원문 제외 | pass | upstream artifact만 읽고 raw 내부 data 미복사 |
| 개인정보/식별자 제외 | pass | user identifier 없음 |
| SNS 원문 제외 | pass | social source 없음 |
| secret scan | pass | token/API key 값 미포함 |
| unsafe write action | pass | approval POST는 reviewer/admin 역할 credential이 있을 때만 허용되고 local SQLite audit trail에만 기록하며 외부 dispatch/write를 하지 않음 |
| hosted fail-closed auth | pass | hosted mode는 24자 이상 reviewer/admin credential이 없으면 startup 실패하며 runtime에는 credential digest만 보관 |
| public demo isolation | pass | GitHub Pages snapshot은 approval button, write fetch, credential header를 포함하지 않음 |
| request logging | pass | structured log는 request id, method, path, status, duration만 기록하고 token/header 값은 남기지 않음 |
| monitoring snapshot | pass | ops metrics snapshot은 artifact freshness와 queue summary만 남기고 secret/header 값은 포함하지 않음 |
| deployment readiness | pass | deployment gate는 credential 값 없이 auth 설정 여부, role 이름, Docker/buildx 상태, blocker만 기록함 |
| impact policy/claim-scope audit | pass | public GO 뒤에도 model-validated estimate와 field-realized impact를 분리하고, 현장 outcome이 없는 실현 성과 claim을 차단 |
| reviewer policy robustness | pass | derived candidate units와 confidence만 perturb하며 결과를 실현 효과·인과 성과로 공개하지 않음 |
| reviewer action plan | pass | local-only 승인/근거요청 계획이며 외부 dispatch, upstream mutation, public claim을 실행하지 않음 |
| reviewer evidence bundle | pass | fingerprint에는 derived impact/action field만 포함하고 secret·credential을 넣지 않으며 stale/missing/future timestamp를 차단 |
| approval audit integrity | pass | hash payload에는 control decision/reviewer/note/timestamp만 포함하고 credential/header는 제외; chain/replay 실패는 local deploy도 차단 |
| AI reviewer agent | pass | agent brief와 candidate notes는 read-only artifact 요약이며 credential, approval write, field dispatch, 신규 성과 claim을 포함하지 않음 |
| public read-only isolation | pass | allowlist aggregate만 포함하고 write control·credential을 제외 |
| current source data/claim | pass at audit time | 2026-07-22 09:03 KST 실행 evidence freshness 8/8로 `GO`; 3시간 SLA에 따라 동적 재판정 |
| deployed public Pages | stale | 2026-07-20 legacy snapshot이며 current single Copilot source 미반영 |
| hosted write API | blocked | reviewer/admin credential과 target hardening 전까지 `NO_GO` 유지 |

SHA-256 fingerprint는 source content drift 탐지용이며 전자서명이나 외부 origin attestation을 대체하지 않는다.

Approval history chain도 local tamper evidence이며 서명된 외부 anchor나 원격 공증을 대체하지 않는다.
