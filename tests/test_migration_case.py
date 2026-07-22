from pathlib import Path
import sys
from decimal import Decimal

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.migration_case import (
    MigrationCase,
    MigrationContractError,
    load_migration_case,
    render_migration_report,
    validate_source_schema,
    run_migration_case,
)


def test_legacy_hospital_case_reconciles_every_source_row():
    report = run_migration_case()

    assert report.status == "pass"
    assert report.outcome == "completed_with_rejects"
    assert report.metrics == {
        "source_systems": 2,
        "source_tables": 6,
        "source_rows": 20,
        "accepted_rows": 11,
        "rejected_rows": 9,
        "target_tables": 3,
    }
    assert report.metrics["accepted_rows"] + report.metrics["rejected_rows"] == 20
    assert all(item.status == "pass" for item in report.reconciliation)
    assert all(item.source_rows == item.accounted_rows for item in report.reconciliation)


def test_migration_enforces_pk_fk_required_and_transform_reject_lineage():
    report = run_migration_case()

    assert {table: len(rows) for table, rows in report.accepted_targets.items()} == {
        "guardian": 4,
        "patient": 4,
        "encounter": 3,
    }
    assert report.reason_counts == {
        "duplicate_primary_key": 1,
        "foreign_key_missing": 6,
        "required_field_missing": 1,
        "transform_error": 1,
    }
    assert all(len(item.source_row_hash) == 64 for item in report.rejects)
    assert {item.reason_code for item in report.rejects} == set(report.reason_counts)
    assert len({item.target_primary_key for item in report.lineage}) == len(report.lineage)


def test_migration_normalizes_values_and_preserves_deterministic_fingerprints():
    first = run_migration_case()
    second = run_migration_case()

    guardian = next(
        row for row in first.accepted_targets["guardian"] if row["guardian_id"] == "B-C10"
    )
    encounter = next(
        row for row in first.accepted_targets["encounter"] if row["encounter_id"] == "B-E10"
    )
    assert guardian["full_name"] == "Park"
    assert guardian["phone"] == "010-2222-3333"
    assert encounter["total_amount"] == "80000.00"
    assert first.source_fingerprint_sha256 == second.source_fingerprint_sha256
    assert first.mapping_fingerprint_sha256 == second.mapping_fingerprint_sha256
    assert first.result_fingerprint_sha256 == second.result_fingerprint_sha256
    assert first.idempotency_key == second.idempotency_key


def test_accepted_targets_pass_independent_relational_cross_check():
    targets = run_migration_case().accepted_targets

    for table, primary_key in {
        "guardian": "guardian_id",
        "patient": "patient_id",
        "encounter": "encounter_id",
    }.items():
        values = [row[primary_key] for row in targets[table]]
        assert len(values) == len(set(values))
    guardian_ids = {row["guardian_id"] for row in targets["guardian"]}
    patient_ids = {row["patient_id"] for row in targets["patient"]}
    assert {row["guardian_id"] for row in targets["patient"]} <= guardian_ids
    assert {row["patient_id"] for row in targets["encounter"]} <= patient_ids
    assert sum(Decimal(row["total_amount"]) for row in targets["encounter"]) == Decimal(
        "175000.00"
    )


def test_mapping_change_alters_mapping_and_result_fingerprint():
    baseline = load_migration_case()
    changed = baseline.model_copy(deep=True)
    mapping = changed.sources["legacy_a"].mappings[0]
    mapping.fields[0].transforms[0].value = "CHANGED-"

    first = run_migration_case(baseline)
    second = run_migration_case(changed)

    assert first.mapping_fingerprint_sha256 != second.mapping_fingerprint_sha256
    assert first.result_fingerprint_sha256 != second.result_fingerprint_sha256


def test_fk_topological_order_does_not_depend_on_fixture_key_order():
    payload = load_migration_case().model_dump(mode="json")
    canonical = payload["canonical_tables"]
    payload["canonical_tables"] = {
        "encounter": canonical["encounter"],
        "patient": canonical["patient"],
        "guardian": canonical["guardian"],
    }

    report = run_migration_case(MigrationCase.model_validate(payload))

    assert report.status == "pass"
    assert report.metrics["accepted_rows"] == 11
    assert report.metrics["rejected_rows"] == 9


def test_migration_contract_requires_complete_one_to_one_source_table_coverage():
    unmapped = load_migration_case().model_dump(mode="json")
    unmapped["sources"]["legacy_a"]["tables"]["orphan_table"] = [{"id": "orphan"}]
    with pytest.raises(ValidationError, match="every source table must be mapped exactly once"):
        MigrationCase.model_validate(unmapped)

    duplicate = load_migration_case().model_dump(mode="json")
    duplicate["sources"]["legacy_a"]["mappings"].append(
        duplicate["sources"]["legacy_a"]["mappings"][0]
    )
    with pytest.raises(ValidationError, match="source table must be mapped exactly once"):
        MigrationCase.model_validate(duplicate)


def test_migration_contract_rejects_unmapped_required_target_and_duplicate_fields():
    payload = load_migration_case().model_dump(mode="json")
    payload["sources"]["legacy_a"]["mappings"][0]["fields"] = payload["sources"][
        "legacy_a"
    ]["mappings"][0]["fields"][:1]

    with pytest.raises(ValidationError, match="required target fields are not mapped"):
        MigrationCase.model_validate(payload)

    duplicate = load_migration_case().model_dump(mode="json")
    fields = duplicate["sources"]["legacy_a"]["mappings"][0]["fields"]
    fields[1]["target"] = fields[0]["target"]
    with pytest.raises(ValidationError, match="field mapping targets must be unique"):
        MigrationCase.model_validate(duplicate)


def test_recruiter_report_states_synthetic_boundary():
    report = render_migration_report(run_migration_case())

    assert "Source | Table | Target" in report
    assert "source rows: **20**" in report
    assert "accepted canonical rows: **11**" in report
    assert "synthetic versioned extracts" in report
    assert "no real patient data or live DB write" in report


def test_source_schema_drift_fails_before_row_transformation():
    mapping = load_migration_case().sources["legacy_a"].mappings[0]

    with pytest.raises(MigrationContractError, match="missing columns: owner_name"):
        validate_source_schema(mapping, {"owner_no", "renamed_owner_name", "phone"})
