# Legacy Hospital Migration scale and recovery rehearsal

- generated: `2026-07-21T03:26:03.598042Z`
- validation status: **PASS**
- boundary: generated public-safe rows and temporary SQLite staging; no live hospital DB write

## Scale and recovery

- source rows: **120,000** across 2 systems / 6 tables
- reconciliation: **120,000 = 119,962 accepted + 38 rejected**
- chunk size / committed batches: **2,500 / 48**
- simulated interruption: **TRUE** after 7,500 committed source rows
- completed-run replay: **0 rows processed**; fingerprint stable `TRUE`
- schema drift probe: **blocked before write = TRUE**
- foreign-key violations: **0**
- observed runtime: **0.732s / 163,880 rows/s**
- result fingerprint: `sha256:4472b9beb7f152433c1f0cc1e78b5ceb170ecab2e126695f78631a9b4febd640`

## Reconciliation

| Source | Table | Target | Source | Accepted | Rejected | Accounted | Status |
|---|---|---|---:|---:|---:|---:|---:|
| legacy_a | owners | guardian | 20000 | 19996 | 4 | 20000 | pass |
| legacy_b | customers | guardian | 20000 | 19996 | 4 | 20000 | pass |
| legacy_a | animals | patient | 20000 | 19994 | 6 | 20000 | pass |
| legacy_b | pet_master | patient | 20000 | 19994 | 6 | 20000 | pass |
| legacy_a | charts | encounter | 20000 | 19991 | 9 | 20000 | pass |
| legacy_b | visits | encounter | 20000 | 19991 | 9 | 20000 | pass |

## Rejection classes

`{"duplicate_primary_key": 2, "foreign_key_missing": 20, "required_field_missing": 8, "transform_error": 8}`

## Schema drift evidence

source schema drift in owners; missing columns: owner_name

## Limits

- Generated public-safe rows; no real patient or guardian data.
- SQLite staging validates batch transactions and relational integrity, not MS-SQL or Firebird network behavior.
- Observed throughput is machine-specific and is not a production SLA or live migration claim.
