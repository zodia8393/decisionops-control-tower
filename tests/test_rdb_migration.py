from pathlib import Path
import sys
import json

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.rdb_migration import (
    RdbMigrationConfig,
    RdbMigrationReport,
    generate_source_row,
    mapping_fingerprint,
    render_rdb_migration_report,
    run_identifier,
)


def _config(**changes):
    payload = {
        "entities_per_table": 40,
        "batch_size": 10,
        "interrupt_after_batches": 1,
        "firebird_password": "local-test",
        "postgres_password": "local-test",
    }
    payload.update(changes)
    return RdbMigrationConfig(**payload)


def test_config_requires_remaining_work_after_failure():
    with pytest.raises(ValidationError, match="leave work to resume"):
        _config(interrupt_after_batches=12)


def test_source_generator_is_deterministic_and_faults_are_sparse():
    assert generate_source_row("LEGACY_GUARDIAN", 1) == generate_source_row(
        "LEGACY_GUARDIAN", 1
    )
    assert generate_source_row("LEGACY_GUARDIAN", 5_555)[3] == "invalid-phone"
    assert generate_source_row("LEGACY_GUARDIAN", 9_999)[1] == "009998"
    assert generate_source_row("LEGACY_PATIENT", 12_345)[4] == "BIRD"
    assert generate_source_row("LEGACY_ENCOUNTER", 23_456)[4] == "-1"


def test_mapping_and_run_identifiers_are_deterministic_and_config_sensitive():
    source = "a" * 64
    first = _config()
    second = _config(entities_per_table=41)

    assert len(mapping_fingerprint()) == 64
    assert run_identifier(first, source) == run_identifier(first, source)
    assert run_identifier(first, source) != run_identifier(second, source)


def test_report_renderer_exposes_reconciliation_and_honest_boundary():
    report = RdbMigrationReport.model_validate(
        {
            "generated_at_utc": "2026-07-22T00:00:00Z",
            "status": "pass",
            "run_id": "rdb-test",
            "source_engine": "Firebird 5.0.4",
            "target_engine": "PostgreSQL 17",
            "source_rows": 120_000,
            "accepted_rows": 119_990,
            "rejected_rows": 10,
            "target_counts": {"guardian": 39_997, "patient": 39_997, "encounter": 39_996},
            "reason_counts": {"foreign_key_missing": 5},
            "reconciliation": [
                {
                    "source_table": "LEGACY_GUARDIAN",
                    "target_table": "guardian",
                    "source_rows": 40_000,
                    "accepted_rows": 39_997,
                    "rejected_rows": 3,
                    "checkpoint_rows": 40_000,
                    "status": "pass",
                }
            ],
            "committed_batches": 48,
            "resumed_from_source_rows": 2_500,
            "replay_processed_rows": 0,
            "rollback_verified": True,
            "checkpoint_resume_verified": True,
            "idempotent_replay": True,
            "schema_drift_blocked_before_write": True,
            "schema_drift_detail": "missing OWNER_NAME",
            "foreign_key_violations": 0,
            "source_fingerprint_sha256": "a" * 64,
            "mapping_fingerprint_sha256": "b" * 64,
            "result_fingerprint_sha256": "c" * 64,
            "elapsed_seconds": 12.5,
            "observed_rows_per_second": 9_600,
            "limitations": [
                "Source rows are deterministic synthetic records; no real patient data is used."
            ],
        }
    )

    markdown = render_rdb_migration_report(report)

    assert "120,000" in markdown
    assert "completed-run replay: **0 rows processed**" in markdown
    assert "transaction rollback verified: **TRUE**" in markdown
    assert "no real patient data" in markdown


def test_checked_in_integration_report_preserves_release_invariants():
    payload = json.loads(
        (ROOT / "docs/evaluation/firebird_postgres_migration.json").read_text(
            encoding="utf-8"
        )
    )
    report = RdbMigrationReport.model_validate(payload)

    assert report.status == "pass"
    assert report.source_rows == 120_000
    assert report.source_rows == report.accepted_rows + report.rejected_rows
    assert sum(report.target_counts.values()) == report.accepted_rows
    assert all(item.status == "pass" for item in report.reconciliation)
    assert report.rollback_verified is True
    assert report.checkpoint_resume_verified is True
    assert report.replay_processed_rows == 0
    assert report.schema_drift_blocked_before_write is True
    assert report.foreign_key_violations == 0
