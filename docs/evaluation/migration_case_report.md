# Legacy Hospital Migration validation case

- generated: `2026-07-21T03:09:58.152970Z`
- case: `legacy-hospital-emr-v1`
- validation status: **PASS**
- outcome: `completed_with_rejects`
- boundary: synthetic versioned extracts; no real patient data or live DB write

## Reconciliation

| Source | Table | Target | Source | Accepted | Rejected | Accounted | Status |
|---|---|---|---:|---:|---:|---:|---:|
| legacy_a | owners | guardian | 3 | 2 | 1 | 3 | pass |
| legacy_b | customers | guardian | 2 | 2 | 0 | 2 | pass |
| legacy_a | animals | patient | 4 | 2 | 2 | 4 | pass |
| legacy_b | pet_master | patient | 3 | 2 | 1 | 3 | pass |
| legacy_a | charts | encounter | 4 | 1 | 3 | 4 | pass |
| legacy_b | visits | encounter | 4 | 2 | 2 | 4 | pass |

## Totals

- source rows: **20**
- accepted canonical rows: **11**
- rejected with lineage: **9**
- rejection reasons: `{"duplicate_primary_key": 1, "foreign_key_missing": 6, "required_field_missing": 1, "transform_error": 1}`
- result fingerprint: `sha256:b9bba63aafc249c75a662823ea4a893c31371175106c611d54cfbe860dfacc8a`

## Reject lineage

| Source row | Target | Reason | Detail |
|---|---|---|---|
| legacy_a.owners#3 | guardian | required_field_missing | missing required fields: full_name |
| legacy_a.animals#3 | patient | foreign_key_missing | guardian_id has no accepted guardian parent |
| legacy_a.animals#4 | patient | foreign_key_missing | guardian_id has no accepted guardian parent |
| legacy_b.pet_master#3 | patient | foreign_key_missing | guardian_id has no accepted guardian parent |
| legacy_a.charts#2 | encounter | transform_error | encounter_date: value is not an ISO date |
| legacy_a.charts#3 | encounter | foreign_key_missing | patient_id has no accepted patient parent |
| legacy_a.charts#4 | encounter | foreign_key_missing | patient_id has no accepted patient parent |
| legacy_b.visits#3 | encounter | duplicate_primary_key | duplicate primary key: B-E10 |
| legacy_b.visits#4 | encounter | foreign_key_missing | patient_id has no accepted patient parent |

## Limits

- Synthetic versioned extracts; no real patient or guardian data.
- Demonstrates mapping correctness and reconciliation, not live MS-SQL/Firebird connectivity.
- Correctness-scale fixture; no production throughput or transaction benchmark claim.
