from pathlib import Path
import sys

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.migration_case import MigrationContractError, load_migration_case
import decisionops_control_tower.migration_rehearsal as rehearsal_module
from decisionops_control_tower.migration_rehearsal import (
    MigrationRehearsalConfig,
    render_migration_rehearsal_report,
    run_migration_rehearsal,
)


def test_rehearsal_resumes_from_committed_checkpoint_and_replays_as_noop(tmp_path):
    database = tmp_path / "rehearsal.sqlite"
    config = MigrationRehearsalConfig(
        entities_per_source=40,
        chunk_size=7,
        interrupt_after_batches=2,
    )

    first = run_migration_rehearsal(database, config)
    second = run_migration_rehearsal(database, config)

    assert first.status == "pass"
    assert first.source_rows == 240
    assert first.target_counts == {"guardian": 80, "patient": 80, "encounter": 80}
    assert first.interruption_observed is True
    assert first.resumed_from_source_rows == 14
    assert first.replay_processed_rows == 0
    assert first.idempotent_replay is True
    assert first.result_fingerprint_sha256 == second.result_fingerprint_sha256
    assert second.reused_completed_run is True
    assert database.stat().st_size == second.database_bytes


def test_rehearsal_reconciles_all_four_reject_classes_and_foreign_keys(tmp_path):
    report = run_migration_rehearsal(
        tmp_path / "faults.sqlite",
        MigrationRehearsalConfig(
            entities_per_source=11_000,
            chunk_size=1_000,
            interrupt_after_batches=3,
        ),
    )

    assert report.source_rows == 66_000
    assert report.accepted_rows == 65_980
    assert report.rejected_rows == 20
    assert report.target_counts == {
        "guardian": 21_996,
        "patient": 21_994,
        "encounter": 21_990,
    }
    assert report.reason_counts == {
        "duplicate_primary_key": 2,
        "foreign_key_missing": 10,
        "required_field_missing": 4,
        "transform_error": 4,
    }
    assert all(item.status == "pass" for item in report.reconciliation)
    assert report.foreign_key_violations == 0


def test_rehearsal_blocks_schema_drift_and_incompatible_database_reuse(tmp_path):
    database = tmp_path / "contract.sqlite"
    baseline = MigrationRehearsalConfig(
        entities_per_source=30,
        chunk_size=5,
        interrupt_after_batches=2,
    )
    report = run_migration_rehearsal(database, baseline)

    assert report.schema_drift_blocked_before_write is True
    assert "missing columns: owner_name" in report.schema_drift_detail
    with pytest.raises(MigrationContractError, match="different config or mapping"):
        run_migration_rehearsal(
            database,
            MigrationRehearsalConfig(
                entities_per_source=31,
                chunk_size=5,
                interrupt_after_batches=2,
            ),
        )


def test_rehearsal_config_requires_work_after_interruption():
    with pytest.raises(ValidationError, match="leave at least one batch to resume"):
        MigrationRehearsalConfig(
            entities_per_source=20,
            chunk_size=20,
            interrupt_after_batches=6,
        )


def test_batch_failure_rolls_back_target_rows_and_checkpoint(tmp_path, monkeypatch):
    database = tmp_path / "rollback.sqlite"
    connection = rehearsal_module._connect(database)
    case = load_migration_case()
    mapping = case.sources["legacy_a"].mappings[0]
    original = rehearsal_module._process_row

    def fail_on_third_row(*args, **kwargs):
        if kwargs.get("row_number", args[-1]) == 3:
            raise RuntimeError("simulated mid-batch failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(rehearsal_module, "_process_row", fail_on_third_row)

    with pytest.raises(RuntimeError, match="mid-batch failure"):
        rehearsal_module._commit_batch(
            connection,
            "legacy_a",
            mapping,
            case.canonical_tables["guardian"],
            1,
            5,
        )

    assert connection.execute("SELECT COUNT(*) FROM guardian").fetchone()[0] == 0
    assert (
        connection.execute("SELECT COUNT(*) FROM migration_checkpoint").fetchone()[0]
        == 0
    )
    connection.close()


def test_rehearsal_report_states_synthetic_boundary(tmp_path):
    report = run_migration_rehearsal(
        tmp_path / "report.sqlite",
        MigrationRehearsalConfig(
            entities_per_source=20,
            chunk_size=5,
            interrupt_after_batches=2,
        ),
    )

    markdown = render_migration_rehearsal_report(report)

    assert "temporary SQLite staging; no live hospital DB write" in markdown
    assert "completed-run replay: **0 rows processed**" in markdown
    assert "schema drift probe: **blocked before write = TRUE**" in markdown
