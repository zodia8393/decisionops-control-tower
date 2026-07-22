# Architecture Decision: Legacy Hospital Migration Case

- 상태: 수용
- 기준일: 2026-07-21 KST
- 범위: recruiter-facing synthetic migration case

## Context

Decision Intelligence Copilot은 임의 schema의 단일 dataset을 분석할 수 있지만, source schema를 target domain으로 옮기는 ETL·reconciliation 증거는 제공하지 않는다. 데이터 마이그레이션 직무에서 필요한 핵심 신호는 자연어 분석보다 source-target mapping, reject lineage, 무결성 검증, 재실행 결정성이다.

실제 병원 DB, 개인정보, MS-SQL/Firebird 접속정보는 프로젝트에 포함할 수 없다. 따라서 운영 migration을 했다고 주장하지 않고, 서로 다른 두 병원 legacy extract를 canonical EMR domain으로 옮기는 versioned synthetic case를 재현한다.

## Options

| 옵션 | 장점 | 단점 |
|---|---|---|
| 자연어 planner에 migration 명령 추가 | 기존 chat surface 재사용 | 분석 plan과 mutation-oriented migration contract가 섞임 |
| 별도 migration repo 생성 | 독립성이 높음 | 단일 제품 목표가 다시 분산됨 |
| Control Tower 내부 deterministic case pipeline | 기존 validation·provenance·dashboard 재사용, 경계 명확 | 실제 DB adapter 성능을 증명하지 못함 |

## Decision

Control Tower 안에 read-only `Legacy Hospital Migration` case pipeline을 둔다.

1. package fixture는 두 source system의 synthetic extract, canonical target schema, versioned field mapping을 함께 보존한다.
2. mapping은 allowlisted transform만 실행하며 arbitrary Python expression을 허용하지 않는다.
3. target table 순서는 `guardian → patient → encounter`로 고정하고 PK, required field, FK를 deterministic하게 검증한다.
4. 모든 source row는 accepted 또는 rejected 중 정확히 하나로 귀속하며 source system/table/row number를 lineage로 남긴다.
5. reconciliation은 source·accepted·rejected count, target checksum, source/mapping/result SHA-256을 기록한다.
6. 같은 fixture를 재실행하면 timestamp를 제외한 result fingerprint가 같아야 한다.
7. API와 dashboard는 같은 report builder를 호출하며 외부 DB write를 수행하지 않는다.

## Component Boundary

```text
versioned synthetic extracts + mapping contract
                  │
                  ▼
        contract/schema validation
                  │
                  ▼
       allowlisted field transforms
                  │
                  ▼
 required → PK uniqueness → FK validation
          │                   │
          ▼                   ▼
 accepted canonical rows   reject lineage
          └─────────┬─────────┘
                    ▼
 reconciliation + deterministic fingerprints
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
 read-only API          technical dashboard
```

## Acceptance Evidence

- 모든 source row가 count reconciliation을 통과한다.
- accepted target의 PK는 table별 unique이고 모든 FK는 accepted parent를 참조한다.
- 의도한 invalid row는 reason code와 source row lineage를 가진다.
- 동일 input의 두 번 실행에서 result fingerprint가 같다.
- source/mapping 변조 시 fingerprint 또는 결과가 달라진다.
- report에 실제 운영 DB migration, 대용량 처리, production outcome을 주장하지 않는다.

## Scale and recovery follow-up

20-row fixture는 mapping과 reject correctness를 사람이 검토할 수 있게 유지한다. 대용량·재시작 가능성은 같은 fixture를 단순 복제해 부풀리지 않고 별도 synthetic rehearsal로 검증한다.

- 두 legacy mapping을 사용해 총 120,000 source rows를 generator로 생성한다.
- target은 temporary SQLite staging DB이며 chunk마다 data와 checkpoint를 한 transaction으로 commit한다.
- 정해진 batch 직후 의도적으로 중단하고 새 connection에서 persisted checkpoint부터 재개한다.
- 완료된 run을 다시 실행했을 때 처리 row 0, target count·fingerprint 불변이어야 한다.
- required source column rename probe는 staging schema 생성과 target write 전에 실패해야 한다.
- 처리시간·rows/sec는 실행 환경 관측값으로만 보고하고 production SLA로 해석하지 않는다.

## Consequences and Limits

- 이 case는 mapping·validation·reconciliation 설계 역량을 증명하지만 MS-SQL/Firebird network adapter나 production transaction을 증명하지 않는다.
- 20-row fixture는 correctness case이고 120k rehearsal은 synthetic scale/recovery 증거다. 어느 쪽도 실제 network·lock·transaction-log·운영 부하를 재현하지 않는다.
- 기존 upload analysis는 session-only 단일 dataset을 유지하며 migration case와 contract를 공유하지 않는다.
