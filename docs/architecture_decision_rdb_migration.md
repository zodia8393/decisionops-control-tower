# Architecture Decision: Containerized Firebird to PostgreSQL Migration

- 상태: 수용
- 기준일: 2026-07-22 KST
- 범위: Portfolio Release v2의 실제 RDB integration case

## Context

기존 `migration_case.py`는 20-row fixture에서 mapping·reject lineage·PK/FK·fingerprint를 사람이 검토할 수 있게 만들고, `migration_rehearsal.py`는 SQLite에서 120,000-row batch·checkpoint·resume을 재현한다. 두 경로 모두 deterministic correctness evidence로 유효하지만, networked legacy RDB에서 canonical target RDB로 읽고 쓰는 adapter와 실제 transaction rollback은 증명하지 못한다.

채용 공고의 핵심은 문서가 없는 이종 DB 분석, 재사용 가능한 ETL, 대용량 이관의 정합성 검증, 장애 원인 추적, 반복 예외의 일반화다. Portfolio Release v2에서는 이 공백만 별도 integration slice로 보완한다.

## Options

| 옵션 | 장점 | 단점 |
|---|---|---|
| 기존 FastAPI container에 DB driver 추가 | image 하나로 실행 | 웹 제품과 migration runtime의 dependency·failure domain이 결합됨 |
| 기존 SQLite rehearsal을 PostgreSQL로 교체 | 코드 변화가 작음 | legacy source adapter와 실제 schema introspection이 남지 않음 |
| 별도 Compose stack + 전용 runner | 실제 source/target·transaction을 재현하고 기본 demo와 격리 | integration 실행 시간이 늘고 Docker가 필요함 |

## Decision

표준 `compose.yaml`은 유지하고 `compose.migration.yaml`에 세 서비스를 둔다.

1. `migration-firebird`: 공식 `firebirdsql/firebird:5.0.4` image로 synthetic legacy source를 보관한다.
2. `migration-postgres`: 공식 PostgreSQL image로 canonical `guardian → patient → encounter`와 migration metadata를 보관한다.
3. `migration-runner`: Firebird Python driver와 psycopg만 가진 작은 전용 image로 source seed, schema validation, batch ETL, reconciliation report를 수행한다.

runner는 다음 invariant를 강제한다.

- source schema는 Firebird system catalog에서 읽어 versioned mapping의 required column과 비교한다.
- target data와 checkpoint는 같은 PostgreSQL transaction에서 commit한다.
- 첫 committed batch 다음 batch 내부에서 의도적 failure를 발생시키고 target·lineage·reject·checkpoint rollback을 확인한다.
- connection을 닫고 새 connection에서 persisted checkpoint 다음 row부터 재개한다.
- 완료된 같은 run을 replay하면 source 처리 row가 0이고 result fingerprint가 변하지 않는다.
- 모든 source row는 accepted lineage 또는 reject lineage 중 하나로 귀속한다.
- target PK/FK와 source/target/reject count를 독립 SQL로 다시 계산한다.
- drift 전용 Firebird table의 실제 metadata가 contract와 다르면 target domain write 전에 차단한다.

## Component Boundary

```text
Firebird 5 synthetic legacy tables
              │ batched SELECT + metadata introspection
              ▼
 versioned allowlisted mapping / validation
              │
       ┌──────┴──────┐
       ▼             ▼
 canonical row    reject lineage
       └──────┬──────┘
              ▼ one PostgreSQL transaction per batch
 PostgreSQL target + lineage + checkpoint
              │
              ▼
 reconciliation / FK audit / deterministic fingerprint
```

## Acceptance Evidence

- 기본 실행에서 Firebird source row가 실제로 120,000개 생성되고 PostgreSQL로 batch 처리된다.
- injected mid-batch failure 뒤 target과 checkpoint가 함께 rollback되고, 새 connection에서 재개된다.
- `source_rows = accepted_rows + rejected_rows`, checkpoint table별 accounted count와 source count가 일치한다.
- PostgreSQL FK violation은 0이고 completed-run replay 처리량은 0이다.
- 실제 Firebird catalog를 사용한 drift probe가 target domain write 전에 실패한다.
- JSON/Markdown report에 engine version, row count, batch count, fingerprints, reject reason, 관측 elapsed/throughput, 한계가 남는다.

## Consequences and Limits

- 이 사례는 container network와 실제 Firebird/PostgreSQL transaction을 사용하지만 source는 전부 synthetic이다.
- 실제 동물병원 DB, PHI, lock contention, CDC, WAL/backup, cutover/rollback 운영, cloud SLA를 재현하거나 주장하지 않는다.
- 관측 throughput은 실행 machine과 container 상태에 종속되며 production benchmark가 아니다.
- 기본 web demo와 unit suite는 Docker integration에 의존하지 않는다. CI와 release gate에서 별도 integration command로 실행한다.

## References

- [Firebird official Docker image](https://github.com/FirebirdSQL/firebird-docker)
- [firebird-driver 2.0 usage guide](https://firebird-driver.readthedocs.io/en/stable/usage-guide.html)
- [PostgreSQL Docker Official Image documentation](https://github.com/docker-library/docs/tree/master/postgres)
