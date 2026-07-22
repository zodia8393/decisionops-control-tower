# Migration Interview Guide

## 30초 소개

“문서가 부족한 legacy DB를 canonical domain으로 옮길 때 필요한 mapping, validation, reject lineage, batch recovery를 한 제품에서 재현했습니다. 실제 Firebird 5.0.4 container에 120,000개 synthetic row를 만들고 PostgreSQL 17.10으로 이관했습니다. 모든 source row를 accepted 또는 rejected로 대사하고, batch 중간 failure가 data와 checkpoint를 함께 rollback하는지 확인한 뒤 새 connection에서 재개합니다. 완료 replay는 0건이고 FK violation은 0건입니다. 실제 병원 데이터나 운영 cutover 경험을 주장하는 프로젝트는 아닙니다.”

## 5분 시연

### 1. 문제와 계약 — 45초

- source: Firebird `LEGACY_GUARDIAN`, `LEGACY_PATIENT`, `LEGACY_ENCOUNTER`
- target: PostgreSQL `guardian → patient → encounter`
- contract: versioned field mapping, allowlisted transform, required/PK/FK validation
- invariant: `source = accepted lineage + reject lineage`

보여줄 파일: [`src/decisionops_control_tower/rdb_migration.py`](../src/decisionops_control_tower/rdb_migration.py). 면접에서는 source mapping과 `_commit_batch`만 펼친다.

### 2. 실제 RDB 실행 결과 — 60초

- Firebird 5.0.4.1812 → PostgreSQL 17.10
- 120,000 source = 119,988 accepted + 12 rejected
- target: guardian 39,997 / patient 39,996 / encounter 39,995
- reject: duplicate PK 1 / missing FK 7 / required 1 / transform 3
- 독립 PostgreSQL FK audit: 0

보여줄 파일: [integration report](evaluation/firebird_postgres_migration.md)

### 3. 장애와 재개 — 75초

1. 첫 2,500-row batch를 data+checkpoint 한 transaction으로 commit한다.
2. 다음 batch에서 10개 row를 처리한 직후 의도적으로 exception을 발생시킨다.
3. transaction이 target, lineage/reject, checkpoint를 모두 rollback했는지 이전 count와 비교한다.
4. Firebird/PostgreSQL connection을 닫고 새 connection을 연다.
5. PostgreSQL checkpoint의 2,500 다음 row부터 처리한다.
6. 완료 후 같은 run을 replay해 0 row와 동일 result fingerprint를 확인한다.

핵심 답변: “checkpoint만 별도 commit하면 data와 위치가 어긋날 수 있어 같은 target transaction에 넣었습니다.”

### 4. Drift와 정합성 — 45초

- Firebird `RDB$RELATION_FIELDS`에서 실제 column metadata를 읽는다.
- `OWNER_NAME`이 `OWNER_NAME_RENAMED`로 바뀐 drift table은 mapping 전에 차단한다.
- raw patient row는 reject table에 저장하지 않고 SHA-256과 source key, reason만 남긴다.
- PostgreSQL PK/FK constraint와 별도 reconciliation query를 둘 다 사용한다.

### 5. 제품 확장 — 75초

- 작은 20-row fixture: 사람이 mapping/reject를 review하기 위한 correctness case
- SQLite 120k rehearsal: DB 없이 빠르게 recovery logic을 regression하는 test double
- 실제 RDB 120k integration: network adapter, catalog, PostgreSQL transaction 확인
- Analysis Copilot: 이관 전후 extract를 올려 품질·분포·집계·통계·예측을 후속 대화로 검토

## 자주 받을 질문

### 왜 Firebird와 PostgreSQL인가?

지원 공고의 legacy Firebird와 canonical PostgreSQL 조합을 직접 재현하면서도 실제 병원 credential이나 PHI 없이 공개할 수 있기 때문이다. adapter는 분리되어 MS-SQL source를 추가할 때 mapping/executor contract는 재사용한다.

### 왜 invalid row를 버리지 않았나?

silent drop은 source/target count를 맞출 수 없고 운영팀이 원인을 추적할 수 없다. 각 source row를 accepted lineage 또는 reject lineage 중 정확히 하나로 귀속하고 reason code와 row hash를 남겼다.

### `ON CONFLICT DO NOTHING`만 쓰면 안 되나?

중복과 정상 replay를 구분할 수 없고, FK·transform·required 오류의 원인이 사라진다. 완료 replay는 checkpoint/run fingerprint로 no-op 처리하고, 데이터 오류는 명시적 reason으로 reject한다.

### checkpoint가 target과 다른 transaction이면 어떤 문제가 생기나?

data만 commit되면 재개 시 duplicate가 발생하고, checkpoint만 commit되면 source row가 누락된다. 따라서 batch target write, lineage/reject, checkpoint를 한 PostgreSQL transaction으로 묶었다.

### schema drift는 어떻게 막았나?

첫 target domain write 전에 Firebird system catalog의 실제 column set을 versioned mapping의 required source column과 비교한다. missing column이 있으면 runner가 종료되고 target row count는 변하지 않는다.

### 3,879.6 rows/s가 운영 성능인가?

아니다. local container와 synthetic row에서 한 번 관측한 수치다. production 성능 결론에는 network latency, index/trigger, lock, DB size, concurrent workload, backup/replication 조건을 고정한 반복 benchmark가 필요하다.

### 실무로 가려면 무엇이 더 필요한가?

- source snapshot/CDC와 cutover window 설계
- PII/PHI masking, encryption, access audit
- retry/backoff, metrics/alert, dead-letter 운영 workflow
- backup·restore rehearsal와 rollback runbook
- mapping version 배포·승인·rollback
- production-like load/lock benchmark

## 주장 경계

말해도 되는 것:

- 실제 Firebird/PostgreSQL container와 DB transaction을 사용했다.
- 120k synthetic source를 전수 대사했다.
- failure/rollback/reconnect/resume/replay/drift를 자동 검증했다.

말하면 안 되는 것:

- 실제 동물병원 데이터를 이관했다.
- production cutover 또는 무중단 migration을 수행했다.
- 관측 throughput이 운영 SLA를 만족한다.
- PHI security, cloud HA, CDC를 구현했다.

## 실행

```bash
scripts/verify_rdb_migration.sh
```

성공 기준은 report `status=pass`, source 120,000 전수 대사, rollback/resume/replay/drift `true`, FK violation 0이다.
