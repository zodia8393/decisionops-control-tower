# Firebird to PostgreSQL Migration Integration

- status: **PASS**
- run: `rdb-5e8e08e2142b69b5b9ef`
- source: **Firebird 5.0.4.1812**
- target: **PostgreSQL 17.10**
- source rows: **120,000**
- accepted/rejected: **119,988 / 12**
- committed batches: **48**
- resumed from: **2,500 source rows**
- completed-run replay: **0 rows processed**
- transaction rollback verified: **TRUE**
- checkpoint resume verified: **TRUE**
- schema drift blocked before write: **TRUE**
- foreign-key violations: **0**

## Reconciliation

| Firebird source | PostgreSQL target | Source | Accepted | Rejected | Checkpoint | Status |
|---|---|---:|---:|---:|---:|---|
| LEGACY_GUARDIAN | guardian | 40,000 | 39,997 | 3 | 40,000 | pass |
| LEGACY_PATIENT | patient | 40,000 | 39,996 | 4 | 40,000 | pass |
| LEGACY_ENCOUNTER | encounter | 40,000 | 39,995 | 5 | 40,000 | pass |

## Reject reasons

- duplicate_primary_key: **1**
- foreign_key_missing: **7**
- required_field_missing: **1**
- transform_error: **3**

## Provenance

- source SHA-256: `c6ecf53810d13d69697a7424784990cad680421aa1d5c9da9c503e4811d2ee05`
- mapping SHA-256: `e2ccf88c8e370b0d40c149f04d2cd9e8d933dfbbfbfce803cfb6acaa491ab095`
- result SHA-256: `70b8a585a64812cdf9fe7f980d3251e7371ea9cff4270ada4cbe10d45bc55460`
- elapsed: **30.931s**
- observed throughput: **3,879.6 rows/s**
- drift evidence: `source schema drift in LEGACY_GUARDIAN_DRIFT; missing columns: OWNER_NAME`

## Limits

- Source rows are deterministic synthetic records; no real patient data is used.
- This container integration is not evidence of a production hospital cutover.
- Observed throughput is machine-specific and is not a production SLA.
- CDC, lock contention, backup/WAL recovery, cloud networking, and PHI controls are out of scope.
