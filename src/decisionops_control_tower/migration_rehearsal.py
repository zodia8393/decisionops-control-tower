"""Synthetic scale, checkpoint, resume, and schema-drift migration rehearsal."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from decisionops_control_tower.migration_case import (
    MigrationCase,
    MigrationContractError,
    Scalar,
    SourceSpec,
    TableMapping,
    TargetTableSpec,
    load_migration_case,
    required_source_columns,
    transform_source_row,
    validate_source_schema,
)


GENERATOR_VERSION = "legacy-hospital-scale-generator-v1"
TARGET_TABLES = ("guardian", "patient", "encounter")


class MigrationRehearsalConfig(BaseModel):
    """Bounded parameters for a reproducible synthetic recovery rehearsal."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["decisionops-migration-rehearsal-v1"] = (
        "decisionops-migration-rehearsal-v1"
    )
    entities_per_source: int = Field(default=20_000, ge=20, le=100_000)
    chunk_size: int = Field(default=2_500, ge=1, le=25_000)
    interrupt_after_batches: int = Field(default=3, ge=1, le=1_000)

    @model_validator(mode="after")
    def validate_interruption_point(self) -> "MigrationRehearsalConfig":
        batches_per_table = (
            self.entities_per_source + self.chunk_size - 1
        ) // self.chunk_size
        total_batches = batches_per_table * 2 * len(TARGET_TABLES)
        if self.interrupt_after_batches >= total_batches:
            raise ValueError("interrupt_after_batches must leave at least one batch to resume")
        return self

    @property
    def source_rows(self) -> int:
        return self.entities_per_source * 2 * len(TARGET_TABLES)


class RehearsalReconciliation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_system: str
    source_table: str
    target_table: str
    source_rows: int
    accepted_rows: int
    rejected_rows: int
    accounted_rows: int
    status: Literal["pass", "fail"]


class MigrationRehearsalReport(BaseModel):
    """Auditable evidence from the scale and recovery rehearsal."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["decisionops-migration-rehearsal-report-v1"] = (
        "decisionops-migration-rehearsal-report-v1"
    )
    generated_at_utc: str
    status: Literal["pass", "fail"]
    config: MigrationRehearsalConfig
    source_systems: int
    source_tables: int
    source_rows: int
    accepted_rows: int
    rejected_rows: int
    target_counts: dict[str, int]
    reason_counts: dict[str, int]
    reconciliation: list[RehearsalReconciliation]
    committed_batches: int
    checkpoint_count: int
    interruption_observed: bool
    resumed_from_source_rows: int
    replay_processed_rows: int
    idempotent_replay: bool
    schema_drift_blocked_before_write: bool
    schema_drift_detail: str
    foreign_key_violations: int
    source_fingerprint_sha256: str
    mapping_fingerprint_sha256: str
    result_fingerprint_sha256: str
    elapsed_seconds: float
    observed_rows_per_second: float
    reused_completed_run: bool
    database_bytes: int
    limitations: list[str]


class _SimulatedInterruption(RuntimeError):
    """Raised after a committed batch to exercise persisted resume state."""


@dataclass(frozen=True)
class _RehearsalEvidence:
    reconciliation: list[RehearsalReconciliation]
    target_counts: dict[str, int]
    reason_counts: dict[str, int]
    accepted_rows: int
    rejected_rows: int
    foreign_key_violations: int
    checkpoint_count: int
    committed_batches: int
    replay_processed_rows: int
    result_fingerprint_before_replay: str
    result_fingerprint_after_replay: str


_DDL = """
CREATE TABLE IF NOT EXISTS migration_meta (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    config_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    interruption_observed INTEGER NOT NULL DEFAULT 0,
    resumed_from_source_rows INTEGER NOT NULL DEFAULT 0,
    elapsed_seconds REAL,
    observed_rows_per_second REAL
);
CREATE TABLE IF NOT EXISTS migration_checkpoint (
    source_system TEXT NOT NULL,
    source_table TEXT NOT NULL,
    target_table TEXT NOT NULL,
    last_row_number INTEGER NOT NULL,
    accepted_rows INTEGER NOT NULL,
    rejected_rows INTEGER NOT NULL,
    committed_batches INTEGER NOT NULL,
    PRIMARY KEY (source_system, source_table)
);
CREATE TABLE IF NOT EXISTS guardian (
    guardian_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    phone TEXT,
    source_system TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    source_row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS patient (
    patient_id TEXT PRIMARY KEY,
    guardian_id TEXT NOT NULL,
    patient_name TEXT NOT NULL,
    species TEXT NOT NULL,
    birth_date TEXT,
    source_system TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    source_row_hash TEXT NOT NULL,
    FOREIGN KEY (guardian_id) REFERENCES guardian(guardian_id)
);
CREATE TABLE IF NOT EXISTS encounter (
    encounter_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    encounter_date TEXT NOT NULL,
    total_amount TEXT NOT NULL,
    source_system TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    source_row_hash TEXT NOT NULL,
    FOREIGN KEY (patient_id) REFERENCES patient(patient_id)
);
CREATE TABLE IF NOT EXISTS reject_lineage (
    source_system TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    source_row_hash TEXT NOT NULL,
    target_table TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    detail TEXT NOT NULL,
    PRIMARY KEY (source_system, source_table, source_row_number)
);
"""

_PK_LOOKUP_SQL = {
    "guardian": "SELECT 1 FROM guardian WHERE guardian_id = ?",
    "patient": "SELECT 1 FROM patient WHERE patient_id = ?",
    "encounter": "SELECT 1 FROM encounter WHERE encounter_id = ?",
}
_ACCEPTED_COUNT_SQL = {
    "guardian": "SELECT COUNT(*) FROM guardian WHERE source_system = ? AND source_table = ?",
    "patient": "SELECT COUNT(*) FROM patient WHERE source_system = ? AND source_table = ?",
    "encounter": "SELECT COUNT(*) FROM encounter WHERE source_system = ? AND source_table = ?",
}
_INSERT_SQL = {
    "guardian": (
        "INSERT INTO guardian "
        "(guardian_id, full_name, phone, source_system, source_table, "
        "source_row_number, source_row_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    ),
    "patient": (
        "INSERT INTO patient "
        "(patient_id, guardian_id, patient_name, species, birth_date, source_system, "
        "source_table, source_row_number, source_row_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    ),
    "encounter": (
        "INSERT INTO encounter "
        "(encounter_id, patient_id, encounter_date, total_amount, source_system, "
        "source_table, source_row_number, source_row_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    ),
}
_SELECT_TARGET_SQL = {
    "guardian": "SELECT * FROM guardian ORDER BY guardian_id",
    "patient": "SELECT * FROM patient ORDER BY patient_id",
    "encounter": "SELECT * FROM encounter ORDER BY encounter_id",
}
_COUNT_TARGET_SQL = {
    "guardian": "SELECT COUNT(*) FROM guardian",
    "patient": "SELECT COUNT(*) FROM patient",
    "encounter": "SELECT COUNT(*) FROM encounter",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _mapping_pairs(
    case: MigrationCase,
) -> list[tuple[str, SourceSpec, TableMapping]]:
    pairs: list[tuple[str, SourceSpec, TableMapping]] = []
    for target_table in case.ordered_target_tables():
        for source_system, source in case.sources.items():
            pairs.extend(
                (source_system, source, mapping)
                for mapping in source.mappings
                if mapping.target_table == target_table
            )
    return pairs


def _source_token(index: int) -> str:
    return f"{index:07d}"


def _source_date(index: int, *, year: int) -> str:
    return (date(year, 1, 1) + timedelta(days=index % 365)).isoformat()


def _legacy_a_row(target_table: str, index: int) -> dict[str, Scalar]:
    token = _source_token(index)
    if target_table == "guardian":
        return {
            "owner_no": token,
            "owner_name": "" if index % 5_000 == 0 else f"Owner A {token}",
            "phone": f"010{index % 100_000_000:08d}",
        }
    if target_table == "patient":
        return {
            "animal_no": token,
            "owner_no": token,
            "animal_name": f"Pet A {token}",
            "species_code": "UNKNOWN" if index % 7_000 == 0 else "DOG",
            "birth_ymd": _source_date(index, year=2018),
        }
    encounter_token = _source_token(index - 1 if index % 11_000 == 0 else index)
    return {
        "chart_no": encounter_token,
        "animal_no": token,
        "visit_at": "invalid-date" if index % 9_000 == 0 else _source_date(index, year=2026),
        "amount": str(1_000 + index % 50_000),
    }


def _legacy_b_row(target_table: str, index: int) -> dict[str, Scalar]:
    token = _source_token(index)
    if target_table == "guardian":
        return {
            "cust_id": token,
            "name": "" if index % 5_000 == 0 else f"Owner B {token}",
            "mobile": f"010{index % 100_000_000:08d}",
        }
    if target_table == "patient":
        return {
            "pet_id": token,
            "cust_id": token,
            "name": f"Pet B {token}",
            "kind": "UNKNOWN" if index % 7_000 == 0 else "feline",
            "dob": _source_date(index, year=2019),
        }
    encounter_token = _source_token(index - 1 if index % 11_000 == 0 else index)
    return {
        "visit_id": encounter_token,
        "pet_id": token,
        "visit_date": "invalid-date" if index % 9_000 == 0 else _source_date(index, year=2026),
        "total_charge": f"{1_000 + index % 50_000:,}",
    }


def _source_row(source_system: str, target_table: str, index: int) -> dict[str, Scalar]:
    if source_system == "legacy_a":
        return _legacy_a_row(target_table, index)
    if source_system == "legacy_b":
        return _legacy_b_row(target_table, index)
    raise MigrationContractError(f"unsupported rehearsal source: {source_system}")


def _validate_generated_schemas(case: MigrationCase) -> None:
    for source_system, _, mapping in _mapping_pairs(case):
        columns = set(_source_row(source_system, mapping.target_table, 1))
        validate_source_schema(mapping, columns)


def _probe_schema_drift(case: MigrationCase) -> tuple[bool, str]:
    mapping = case.sources["legacy_a"].mappings[0]
    columns = set(_source_row("legacy_a", mapping.target_table, 1))
    missing_column = sorted(required_source_columns(mapping))[0]
    columns.remove(missing_column)
    columns.add(f"renamed_{missing_column}")
    try:
        validate_source_schema(mapping, columns)
    except MigrationContractError as exc:
        return True, str(exc)
    return False, "schema drift probe was not blocked"


def _mapping_fingerprint(case: MigrationCase) -> str:
    payload = {
        "canonical_tables": {
            name: spec.model_dump(mode="json")
            for name, spec in case.canonical_tables.items()
        },
        "sources": {
            name: [mapping.model_dump(mode="json") for mapping in source.mappings]
            for name, source in case.sources.items()
        },
    }
    return _hash_value(payload)


def _config_fingerprint(
    config: MigrationRehearsalConfig, mapping_fingerprint: str
) -> str:
    return _hash_value(
        {
            "config": config.model_dump(mode="json"),
            "generator_version": GENERATOR_VERSION,
            "mapping_fingerprint": mapping_fingerprint,
        }
    )


def _connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(_DDL)
    connection.commit()
    return connection


def _ensure_meta(connection: sqlite3.Connection, config_fingerprint: str) -> bool:
    row = connection.execute(
        "SELECT config_fingerprint FROM migration_meta WHERE singleton = 1"
    ).fetchone()
    if row is not None:
        if row["config_fingerprint"] != config_fingerprint:
            raise MigrationContractError(
                "rehearsal database belongs to a different config or mapping"
            )
        return False
    connection.execute(
        "INSERT INTO migration_meta (singleton, config_fingerprint, status) VALUES (1, ?, ?)",
        (config_fingerprint, "running"),
    )
    connection.commit()
    return True


def _checkpoint(
    connection: sqlite3.Connection, source_system: str, mapping: TableMapping
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM migration_checkpoint WHERE source_system = ? AND source_table = ?",
        (source_system, mapping.source_table),
    ).fetchone()


def _exists_primary_key(
    connection: sqlite3.Connection, target_table: str, primary_key: str
) -> bool:
    return connection.execute(
        _PK_LOOKUP_SQL[target_table], (primary_key,)
    ).fetchone() is not None


def _missing_foreign_key(
    connection: sqlite3.Connection,
    target_table: str,
    target: dict[str, Scalar],
) -> str | None:
    if target_table == "patient":
        parent = connection.execute(
            "SELECT 1 FROM guardian WHERE guardian_id = ?", (target["guardian_id"],)
        ).fetchone()
        return None if parent else "guardian_id has no accepted guardian parent"
    if target_table == "encounter":
        parent = connection.execute(
            "SELECT 1 FROM patient WHERE patient_id = ?", (target["patient_id"],)
        ).fetchone()
        return None if parent else "patient_id has no accepted patient parent"
    return None


def _insert_target(
    connection: sqlite3.Connection,
    mapping: TableMapping,
    target: dict[str, Scalar],
    source_system: str,
    row_number: int,
    row_hash: str,
) -> None:
    lineage = (mapping.source_table, row_number, row_hash)
    if mapping.target_table == "guardian":
        values = (
            target["guardian_id"],
            target["full_name"],
            target.get("phone"),
            source_system,
            *lineage,
        )
    elif mapping.target_table == "patient":
        values = (
            target["patient_id"],
            target["guardian_id"],
            target["patient_name"],
            target["species"],
            target.get("birth_date"),
            source_system,
            *lineage,
        )
    else:
        values = (
            target["encounter_id"],
            target["patient_id"],
            target["encounter_date"],
            target["total_amount"],
            source_system,
            *lineage,
        )
    connection.execute(_INSERT_SQL[mapping.target_table], values)


def _insert_reject(
    connection: sqlite3.Connection,
    source_system: str,
    mapping: TableMapping,
    row_number: int,
    row_hash: str,
    reason_code: str,
    detail: str,
) -> None:
    connection.execute(
        "INSERT INTO reject_lineage "
        "(source_system, source_table, source_row_number, source_row_hash, target_table, "
        "reason_code, detail) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            source_system,
            mapping.source_table,
            row_number,
            row_hash,
            mapping.target_table,
            reason_code,
            detail,
        ),
    )


def _process_row(
    connection: sqlite3.Connection,
    source_system: str,
    mapping: TableMapping,
    spec: TargetTableSpec,
    row_number: int,
) -> Literal["accepted", "rejected"]:
    source = _source_row(source_system, mapping.target_table, row_number)
    row_hash = _hash_value(source)
    try:
        target = transform_source_row(source, mapping)
    except MigrationContractError as exc:
        _insert_reject(
            connection,
            source_system,
            mapping,
            row_number,
            row_hash,
            "transform_error",
            str(exc),
        )
        return "rejected"
    missing = [field for field in spec.required_fields if target.get(field) in (None, "")]
    if missing:
        _insert_reject(
            connection,
            source_system,
            mapping,
            row_number,
            row_hash,
            "required_field_missing",
            "missing required fields: " + ", ".join(missing),
        )
        return "rejected"
    primary_key = str(target[spec.primary_key])
    if _exists_primary_key(connection, mapping.target_table, primary_key):
        _insert_reject(
            connection,
            source_system,
            mapping,
            row_number,
            row_hash,
            "duplicate_primary_key",
            f"duplicate primary key: {primary_key}",
        )
        return "rejected"
    foreign_key_error = _missing_foreign_key(connection, mapping.target_table, target)
    if foreign_key_error:
        _insert_reject(
            connection,
            source_system,
            mapping,
            row_number,
            row_hash,
            "foreign_key_missing",
            foreign_key_error,
        )
        return "rejected"
    _insert_target(connection, mapping, target, source_system, row_number, row_hash)
    return "accepted"


def _committed_batches(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT COALESCE(SUM(committed_batches), 0) AS total FROM migration_checkpoint"
    ).fetchone()
    return int(row["total"])


def _mark_interruption(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT COALESCE(SUM(last_row_number), 0) AS total FROM migration_checkpoint"
    ).fetchone()
    resumed_from = int(row["total"])
    connection.execute(
        "UPDATE migration_meta SET interruption_observed = 1, resumed_from_source_rows = ? "
        "WHERE singleton = 1",
        (resumed_from,),
    )
    connection.commit()
    return resumed_from


def _commit_batch(
    connection: sqlite3.Connection,
    source_system: str,
    mapping: TableMapping,
    spec: TargetTableSpec,
    start: int,
    end: int,
) -> int:
    counts: Counter[str] = Counter()
    connection.execute("BEGIN IMMEDIATE")
    try:
        for row_number in range(start, end + 1):
            counts[_process_row(connection, source_system, mapping, spec, row_number)] += 1
        connection.execute(
            "INSERT INTO migration_checkpoint "
            "(source_system, source_table, target_table, last_row_number, accepted_rows, "
            "rejected_rows, committed_batches) VALUES (?, ?, ?, ?, ?, ?, 1) "
            "ON CONFLICT(source_system, source_table) DO UPDATE SET "
            "last_row_number = excluded.last_row_number, "
            "accepted_rows = migration_checkpoint.accepted_rows + excluded.accepted_rows, "
            "rejected_rows = migration_checkpoint.rejected_rows + excluded.rejected_rows, "
            "committed_batches = migration_checkpoint.committed_batches + 1",
            (
                source_system,
                mapping.source_table,
                mapping.target_table,
                end,
                counts["accepted"],
                counts["rejected"],
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return end - start + 1


def _run_batches(
    connection: sqlite3.Connection,
    case: MigrationCase,
    config: MigrationRehearsalConfig,
    *,
    allow_interruption: bool,
) -> int:
    processed = 0
    for source_system, _, mapping in _mapping_pairs(case):
        checkpoint = _checkpoint(connection, source_system, mapping)
        start = int(checkpoint["last_row_number"]) + 1 if checkpoint else 1
        while start <= config.entities_per_source:
            end = min(start + config.chunk_size - 1, config.entities_per_source)
            processed += _commit_batch(
                connection,
                source_system,
                mapping,
                case.canonical_tables[mapping.target_table],
                start,
                end,
            )
            should_interrupt = (
                allow_interruption
                and _committed_batches(connection) >= config.interrupt_after_batches
            )
            if should_interrupt:
                _mark_interruption(connection)
                raise _SimulatedInterruption("simulated process stop after committed batch")
            start = end + 1
    return processed


def _source_fingerprint(case: MigrationCase, config: MigrationRehearsalConfig) -> str:
    digest = hashlib.sha256()
    for source_system, _, mapping in _mapping_pairs(case):
        for row_number in range(1, config.entities_per_source + 1):
            payload = {
                "source_system": source_system,
                "source_table": mapping.source_table,
                "row_number": row_number,
                "row": _source_row(source_system, mapping.target_table, row_number),
            }
            digest.update(_canonical_json(payload).encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest()


def _stream_query_digest(
    connection: sqlite3.Connection, label: str, query: str
) -> str:
    digest = hashlib.sha256(label.encode("utf-8"))
    cursor = connection.execute(query)
    for row in cursor:
        digest.update(_canonical_json(tuple(row)).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _result_fingerprint(connection: sqlite3.Connection) -> str:
    components = {
        table: _stream_query_digest(connection, table, _SELECT_TARGET_SQL[table])
        for table in TARGET_TABLES
    }
    components["reject_lineage"] = _stream_query_digest(
        connection,
        "reject_lineage",
        "SELECT * FROM reject_lineage ORDER BY source_system, source_table, source_row_number",
    )
    return _hash_value(components)


def _target_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(_COUNT_TARGET_SQL[table]).fetchone()[0])
        for table in TARGET_TABLES
    }


def _reason_counts(connection: sqlite3.Connection) -> dict[str, int]:
    rows = connection.execute(
        "SELECT reason_code, COUNT(*) AS count FROM reject_lineage "
        "GROUP BY reason_code ORDER BY reason_code"
    ).fetchall()
    return {str(row["reason_code"]): int(row["count"]) for row in rows}


def _reconciliation(
    connection: sqlite3.Connection,
    case: MigrationCase,
    config: MigrationRehearsalConfig,
) -> list[RehearsalReconciliation]:
    results: list[RehearsalReconciliation] = []
    for source_system, _, mapping in _mapping_pairs(case):
        accepted = int(
            connection.execute(
                _ACCEPTED_COUNT_SQL[mapping.target_table],
                (source_system, mapping.source_table),
            ).fetchone()[0]
        )
        rejected = int(
            connection.execute(
                "SELECT COUNT(*) FROM reject_lineage WHERE source_system = ? AND source_table = ?",
                (source_system, mapping.source_table),
            ).fetchone()[0]
        )
        accounted = accepted + rejected
        results.append(
            RehearsalReconciliation(
                source_system=source_system,
                source_table=mapping.source_table,
                target_table=mapping.target_table,
                source_rows=config.entities_per_source,
                accepted_rows=accepted,
                rejected_rows=rejected,
                accounted_rows=accounted,
                status="pass" if accounted == config.entities_per_source else "fail",
            )
        )
    return results


def _record_performance(
    connection: sqlite3.Connection, source_rows: int, elapsed_seconds: float
) -> None:
    rate = source_rows / elapsed_seconds if elapsed_seconds else 0.0
    connection.execute(
        "UPDATE migration_meta SET status = 'complete', elapsed_seconds = ?, "
        "observed_rows_per_second = ? WHERE singleton = 1",
        (elapsed_seconds, rate),
    )
    connection.commit()


def _execute_with_recovery(
    database_path: Path,
    case: MigrationCase,
    config: MigrationRehearsalConfig,
    config_fingerprint: str,
) -> tuple[sqlite3.Connection, bool]:
    started = time.perf_counter()
    connection = _connect(database_path)
    try:
        fresh_run = _ensure_meta(connection, config_fingerprint)
        meta = connection.execute(
            "SELECT * FROM migration_meta WHERE singleton = 1"
        ).fetchone()
        try:
            _run_batches(
                connection,
                case,
                config,
                allow_interruption=not bool(meta["interruption_observed"]),
            )
        except _SimulatedInterruption:
            connection.close()
            connection = _connect(database_path)
            _ensure_meta(connection, config_fingerprint)
            _run_batches(connection, case, config, allow_interruption=False)
        meta = connection.execute(
            "SELECT status FROM migration_meta WHERE singleton = 1"
        ).fetchone()
        if meta["status"] != "complete":
            elapsed = time.perf_counter() - started
            _record_performance(connection, config.source_rows, elapsed)
        return connection, fresh_run
    except Exception:
        connection.close()
        raise


def _collect_evidence(
    connection: sqlite3.Connection,
    case: MigrationCase,
    config: MigrationRehearsalConfig,
) -> _RehearsalEvidence:
    before_replay = _result_fingerprint(connection)
    replay_processed = _run_batches(connection, case, config, allow_interruption=False)
    after_replay = _result_fingerprint(connection)
    reconciliation = _reconciliation(connection, case, config)
    target_counts = _target_counts(connection)
    reason_counts = _reason_counts(connection)
    foreign_key_violations = len(
        connection.execute("PRAGMA foreign_key_check").fetchall()
    )
    checkpoint_count = int(
        connection.execute("SELECT COUNT(*) FROM migration_checkpoint").fetchone()[0]
    )
    return _RehearsalEvidence(
        reconciliation=reconciliation,
        target_counts=target_counts,
        reason_counts=reason_counts,
        accepted_rows=sum(target_counts.values()),
        rejected_rows=sum(reason_counts.values()),
        foreign_key_violations=foreign_key_violations,
        checkpoint_count=checkpoint_count,
        committed_batches=_committed_batches(connection),
        replay_processed_rows=replay_processed,
        result_fingerprint_before_replay=before_replay,
        result_fingerprint_after_replay=after_replay,
    )


def _evidence_passed(
    evidence: _RehearsalEvidence,
    meta: sqlite3.Row,
    config: MigrationRehearsalConfig,
    drift_blocked: bool,
) -> bool:
    checks = [
        all(item.status == "pass" for item in evidence.reconciliation),
        evidence.accepted_rows + evidence.rejected_rows == config.source_rows,
        evidence.foreign_key_violations == 0,
        bool(meta["interruption_observed"]),
        int(meta["resumed_from_source_rows"]) > 0,
        evidence.replay_processed_rows == 0,
        evidence.result_fingerprint_before_replay
        == evidence.result_fingerprint_after_replay,
        drift_blocked,
    ]
    return all(checks)


def _build_report(
    connection: sqlite3.Connection,
    case: MigrationCase,
    config: MigrationRehearsalConfig,
    evidence: _RehearsalEvidence,
    mapping_fingerprint: str,
    drift_blocked: bool,
    drift_detail: str,
    fresh_run: bool,
) -> MigrationRehearsalReport:
    meta = connection.execute(
        "SELECT * FROM migration_meta WHERE singleton = 1"
    ).fetchone()
    replay_stable = (
        evidence.replay_processed_rows == 0
        and evidence.result_fingerprint_before_replay
        == evidence.result_fingerprint_after_replay
    )
    passed = _evidence_passed(evidence, meta, config, drift_blocked)
    return MigrationRehearsalReport(
        generated_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        status="pass" if passed else "fail",
        config=config,
        source_systems=len(case.sources),
        source_tables=len(_mapping_pairs(case)),
        source_rows=config.source_rows,
        accepted_rows=evidence.accepted_rows,
        rejected_rows=evidence.rejected_rows,
        target_counts=evidence.target_counts,
        reason_counts=evidence.reason_counts,
        reconciliation=evidence.reconciliation,
        committed_batches=evidence.committed_batches,
        checkpoint_count=evidence.checkpoint_count,
        interruption_observed=bool(meta["interruption_observed"]),
        resumed_from_source_rows=int(meta["resumed_from_source_rows"]),
        replay_processed_rows=evidence.replay_processed_rows,
        idempotent_replay=replay_stable,
        schema_drift_blocked_before_write=drift_blocked,
        schema_drift_detail=drift_detail,
        foreign_key_violations=evidence.foreign_key_violations,
        source_fingerprint_sha256=_source_fingerprint(case, config),
        mapping_fingerprint_sha256=mapping_fingerprint,
        result_fingerprint_sha256=evidence.result_fingerprint_after_replay,
        elapsed_seconds=round(float(meta["elapsed_seconds"]), 6),
        observed_rows_per_second=round(float(meta["observed_rows_per_second"]), 2),
        reused_completed_run=not fresh_run,
        database_bytes=0,
        limitations=[
            "Generated public-safe rows; no real patient or guardian data.",
            (
                "SQLite staging validates batch transactions and relational integrity, "
                "not MS-SQL or Firebird network behavior."
            ),
            (
                "Observed throughput is machine-specific and is not a production SLA "
                "or live migration claim."
            ),
        ],
    )


def run_migration_rehearsal(
    database_path: Path,
    config: MigrationRehearsalConfig | None = None,
) -> MigrationRehearsalReport:
    """Run, interrupt, resume, and replay a bounded synthetic migration."""

    config = config or MigrationRehearsalConfig()
    case = load_migration_case()
    _validate_generated_schemas(case)
    drift_blocked, drift_detail = _probe_schema_drift(case)
    mapping_fingerprint = _mapping_fingerprint(case)
    config_fingerprint = _config_fingerprint(config, mapping_fingerprint)
    connection, fresh_run = _execute_with_recovery(
        database_path, case, config, config_fingerprint
    )
    try:
        evidence = _collect_evidence(connection, case, config)
        report = _build_report(
            connection,
            case,
            config,
            evidence,
            mapping_fingerprint,
            drift_blocked,
            drift_detail,
            fresh_run,
        )
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()
    return report.model_copy(update={"database_bytes": database_path.stat().st_size})


def render_migration_rehearsal_report(report: MigrationRehearsalReport) -> str:
    """Render a recruiter-facing report with explicit synthetic boundaries."""

    lines = [
        "# Legacy Hospital Migration scale and recovery rehearsal",
        "",
        f"- generated: `{report.generated_at_utc}`",
        f"- validation status: **{report.status.upper()}**",
        (
            "- boundary: generated public-safe rows and temporary SQLite staging; "
            "no live hospital DB write"
        ),
        "",
        "## Scale and recovery",
        "",
        (
            f"- source rows: **{report.source_rows:,}** across "
            f"{report.source_systems} systems / {report.source_tables} tables"
        ),
        (
            f"- reconciliation: **{report.source_rows:,} = "
            f"{report.accepted_rows:,} accepted + {report.rejected_rows:,} rejected**"
        ),
        (
            f"- chunk size / committed batches: "
            f"**{report.config.chunk_size:,} / {report.committed_batches}**"
        ),
        (
            f"- simulated interruption: **{str(report.interruption_observed).upper()}** "
            f"after {report.resumed_from_source_rows:,} committed source rows"
        ),
        (
            f"- completed-run replay: **{report.replay_processed_rows} rows processed**; "
            f"fingerprint stable `{str(report.idempotent_replay).upper()}`"
        ),
        (
            "- schema drift probe: **blocked before write = "
            f"{str(report.schema_drift_blocked_before_write).upper()}**"
        ),
        f"- foreign-key violations: **{report.foreign_key_violations}**",
        (
            f"- observed runtime: **{report.elapsed_seconds:.3f}s / "
            f"{report.observed_rows_per_second:,.0f} rows/s**"
        ),
        f"- result fingerprint: `sha256:{report.result_fingerprint_sha256}`",
        "",
        "## Reconciliation",
        "",
        "| Source | Table | Target | Source | Accepted | Rejected | Accounted | Status |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in report.reconciliation:
        lines.append(
            f"| {item.source_system} | {item.source_table} | {item.target_table} | "
            f"{item.source_rows} | {item.accepted_rows} | {item.rejected_rows} | "
            f"{item.accounted_rows} | {item.status} |"
        )
    lines.extend(
        [
            "",
            "## Rejection classes",
            "",
            f"`{json.dumps(report.reason_counts, sort_keys=True)}`",
            "",
            "## Schema drift evidence",
            "",
            report.schema_drift_detail,
            "",
            "## Limits",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report.limitations)
    lines.append("")
    return "\n".join(lines)
