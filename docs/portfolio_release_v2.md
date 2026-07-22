# Portfolio Release v2

- 상태: **DEPLOYED RELEASE CANDIDATE · DRAFT PR**
- 기준일: 2026-07-22 KST
- 대상: 신입~1년차 Data Migration / Data Engineer
- publication: **PAGES LIVE · PR #11 OPEN**

## Recruiter Summary

이 프로젝트는 서로 다른 legacy schema를 canonical domain으로 옮기고, 모든 source row의 성공·실패 상태를 대사하며, 장애 뒤 안전하게 재개하는 migration-first data product다. 실제 Firebird와 PostgreSQL container를 연결하지만 데이터는 공개 가능한 synthetic record만 사용한다. 같은 화면에서 이관 전후 extract를 업로드해 자연어 분석·통계·예측을 수행할 수 있다.

## Primary Evidence

| 평가 신호 | 구현 | 검증 결과 |
|---|---|---|
| 이종 DB | Firebird 5.0.4 source → PostgreSQL 17.10 target | actual container network PASS |
| source-target mapping | `guardian → patient → encounter`, allowlisted transforms | mapping SHA-256 고정 |
| 전수 대사 | accepted/reject lineage + table checkpoint | **120,000 = 119,988 + 12** |
| transaction atomicity | target·lineage/reject·checkpoint same transaction | injected mid-batch rollback PASS |
| 장애 재개 | persisted checkpoint + new DB connections | **2,500 rows부터 resume** |
| 재실행 안전성 | completed-run checkpoint/fingerprint | replay **0 rows** |
| schema drift | Firebird system catalog introspection | target write 전 BLOCKED |
| target 무결성 | PostgreSQL PK/FK + independent SQL audit | FK violation **0** |
| 작은 correctness case | 2개 synthetic legacy style, 6 tables | **20 = 11 + 9** |
| DB-free recovery regression | SQLite 120k rehearsal | **119,962 + 38**, 7,500 resume |
| 대화형 데이터 분석 | typed plan + DuckDB/SciPy/sklearn | Analysis **72/72**, DS **22/22** |
| 전체 regression | unit/API/auth/RAG/UI/migration | **204 passed** |
| browser QA | desktop/mobile scripted flow | overflow 0, console/page error 0 |

## One-command Reproduction

```bash
scripts/verify_rdb_migration.sh
```

이 명령은 Firebird/PostgreSQL/runner를 tmpfs-backed Compose stack으로 실행하고 `build/migration-rdb/firebird_postgres_migration.{json,md}`를 만든다. 성공·실패와 무관하게 container·network·volume을 정리한다.

전체 application gate:

```bash
OUTPUT_ROOT=/tmp/decisionops-portfolio-release-v2 scripts/run_all.sh
python3 scripts/capture_demo_screenshots.py --url http://127.0.0.1:8093
```

## Release Verification

| Gate | Result |
|---|---|
| compileall | PASS |
| full pytest | **204 passed in 13.06s** |
| clean archive pytest | **204 passed in 13.13s** |
| Analysis evaluation | **72/72**, plan/numeric 100% |
| Data Science evaluation | **22/22**, oracle/gates 100% |
| RAG evaluation | **36/36**, recall@3 100% |
| 20-row migration | **11 accepted + 9 rejected** |
| SQLite 120k recovery | **119,962 + 38**, replay 0, drift blocked |
| RDB 120k integration | **119,988 + 12**, rollback/resume/replay/drift/FK PASS |
| API/auth/UI/deployment command | PASS |
| Browser captures | 14 captures, overflow false, console/page errors 0 |
| Clean candidate archive | 6.6MB, runtime/cache/secret 제외 후 별도 directory 검증 PASS |

## Hiring Package

- [README](../README.md): migration-first problem, metrics, one-command run
- [RDB architecture decision](architecture_decision_rdb_migration.md): boundaries and trade-offs
- [Actual RDB report](evaluation/firebird_postgres_migration.md): reconciliation and provenance
- [Demo package](demo_package.md): 5-minute walkthrough order
- [Interview guide](migration_interview_guide.md): expected questions and honest answers
- [Migration Lab screenshot](assets/demo/migration_lab.png): actual RDB + correctness + recovery layers

## Claim Boundary

증명한 것은 synthetic container에서의 adapter, metadata validation, transaction rollback, checkpoint resume, replay, reconciliation, PK/FK audit다. 실제 동물병원 DB, PHI, production cutover, CDC, lock contention, backup/WAL recovery, cloud HA, production SLA는 증명하지 않았다. 관측 3,879.6 rows/s는 현재 machine의 단일 실행값이다.

사용자 평가는 이번 release 범위와 pass/fail gate에서 생략했다.

## Publication Result

- release branch: `agent/portfolio-release-v2`
- release commit: `f5ce604bf1fec68f0ce0feeff02a9d40f598647d`
- draft PR: [#11](https://github.com/zodia8393/decisionops-control-tower/pull/11)
- CI: `ci`, `private-demo-smoke`, `migration-rdb` 모두 PASS
- Pages: [LIVE / READ-ONLY](https://zodia8393.github.io/decisionops-control-tower/)
- deployed smoke: HTTP 200, required marker 13개, forbidden marker 7개 계약 PASS

Pages의 최신 product UI 배포와 snapshot 내부 운영 근거의 최신성은 별도 상태다. 배포된 recorded source는 freshness SLA를 넘어 운영 data/claim gate가 `NO_GO`이며, 이 fail-closed 상태를 UI와 README에 그대로 공개한다. `main` 병합은 draft PR review 이후 별도 결정한다.
