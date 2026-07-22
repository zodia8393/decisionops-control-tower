# Portfolio Release v2 Goal

- 시작: 2026-07-22 KST
- 상태: release candidate 완료 · draft PR/Pages publication 완료
- 외부 배포: 2026-07-22 18:06 KST · read-only Pages LIVE

## Objective

Decision Intelligence Copilot을 신입~1년차 데이터 마이그레이션·Data Engineer 지원용 portfolio release로 완성한다. 첫 화면과 README의 주장을 migration-first로 정리하고, 실제 containerized Firebird→PostgreSQL integration과 장애·재개·대사 증거를 추가한다.

## Success Criteria

1. 한 명령으로 Firebird source, PostgreSQL target, migration runner가 실행되고 120,000 source row의 전수 대사·FK audit·reject lineage·fingerprint report가 생성된다.
2. mid-batch transaction failure가 target/checkpoint에 남지 않고 새 connection의 persisted checkpoint에서 재개되며, completed replay는 0 row다.
3. README, recruiter demo, interview guide가 같은 수치와 한계를 사용하고 실제 운영 병원 migration 경험으로 오해할 표현이 없다.
4. targeted test, 전체 pytest, analysis/data-science/migration/RAG gate, Docker integration, browser smoke가 모두 통과한다.
5. 기존 사용자 변경을 보존하고 secret·대형 artifact·runtime DB를 Git 대상에 포함하지 않는다.

## Work Breakdown

| 단계 | 상태 | 산출물 |
|---|---|---|
| repository/migration boundary audit | 완료 | dirty-state 및 기존 20-row/120k 경계 확인 |
| RDB architecture decision | 완료 | `architecture_decision_rdb_migration.md` |
| Firebird→PostgreSQL integration | 완료 | 120,000 = 119,988 + 12; rollback/resume/replay/drift/FK PASS |
| migration-first hiring package | 완료 | README, demo package, interview guide, release manifest |
| release verification | 완료 | 204 tests, run_all, RDB integration, browser, clean archive PASS |
| publication | 완료 | branch `agent/portfolio-release-v2`, draft PR #11, Pages read-only smoke PASS |

## Guardrails

- 실제 환자 데이터와 외부 DB credential을 사용하지 않는다.
- standard web demo runtime과 migration integration dependency를 분리한다.
- 사용자 평가는 이번 goal의 acceptance gate에 포함하지 않는다.
- external GitHub push와 Pages 배포는 2026-07-22 사용자 승인 후 수행했다.

## Completion Evidence

- 실제 RDB: Firebird 5.0.4.1812 → PostgreSQL 17.10, 48 batches
- 전수 대사: 120,000 source = 119,988 accepted + 12 rejected
- recovery: mid-batch rollback verified, 2,500 checkpoint resume, replay 0
- integrity: actual catalog drift blocked, FK violation 0, source/mapping/result SHA-256
- automated suite: 204 pytest, Analysis 72/72, Data Science 22/22, RAG 36/36
- browser: 14 captures, desktop/mobile overflow false, console/page errors 0
- clean archive: runtime/cache/secret 제외 별도 directory에서 204 pytest 재통과
- publication: commit `f5ce604`, PR checks 3/3 PASS, Pages HTTP 200/read-only smoke PASS
- policy restore: 배포에 사용한 임시 exact-branch 허용을 제거하고 `github-pages` 환경을 `main`-only로 복구
