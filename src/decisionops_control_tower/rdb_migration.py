"""Container integration: synthetic Firebird legacy source to PostgreSQL target."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .migration_case import (
    FieldMapping,
    MigrationContractError,
    TableMapping,
    TargetTableSpec,
    TransformSpec,
    transform_source_row,
)


class RdbMigrationError(RuntimeError):
    """Raised when the container integration cannot preserve its invariants."""


class RdbSchemaDriftError(RdbMigrationError):
    """Raised before target-domain writes when Firebird metadata drifts."""


class _InjectedBatchFailure(RuntimeError):
    pass


class RdbMigrationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities_per_table: int = Field(default=40_000, ge=20, le=250_000)
    batch_size: int = Field(default=2_500, ge=10, le=20_000)
    interrupt_after_batches: int = Field(default=1, ge=1, le=100)
    firebird_host: str = "migration-firebird"
    firebird_port: int = Field(default=3050, ge=1, le=65_535)
    firebird_database: str = "/var/lib/firebird/data/legacy_hospital.fdb"
    firebird_user: str = "SYSDBA"
    firebird_password: str = Field(min_length=1, repr=False)
    postgres_host: str = "migration-postgres"
    postgres_port: int = Field(default=5432, ge=1, le=65_535)
    postgres_database: str = "migration"
    postgres_user: str = "migration"
    postgres_password: str = Field(min_length=1, repr=False)

    @model_validator(mode="after")
    def validate_failure_point(self) -> "RdbMigrationConfig":
        total_batches = (self.entities_per_table * 3 + self.batch_size - 1) // self.batch_size
        if self.interrupt_after_batches >= total_batches:
            raise ValueError("interrupt_after_batches must leave work to resume")
        return self

    @property
    def source_rows(self) -> int:
        return self.entities_per_table * 3


class RdbTableReconciliation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_table: str
    target_table: str
    source_rows: int
    accepted_rows: int
    rejected_rows: int
    checkpoint_rows: int
    status: Literal["pass", "fail"]


class RdbMigrationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["decisionops-rdb-migration-report-v1"] = (
        "decisionops-rdb-migration-report-v1"
    )
    generated_at_utc: str
    status: Literal["pass", "fail"]
    run_id: str
    source_engine: str
    target_engine: str
    source_rows: int
    accepted_rows: int
    rejected_rows: int
    target_counts: dict[str, int]
    reason_counts: dict[str, int]
    reconciliation: list[RdbTableReconciliation]
    committed_batches: int
    resumed_from_source_rows: int
    replay_processed_rows: int
    rollback_verified: bool
    checkpoint_resume_verified: bool
    idempotent_replay: bool
    schema_drift_blocked_before_write: bool
    schema_drift_detail: str
    foreign_key_violations: int
    source_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mapping_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    elapsed_seconds: float
    observed_rows_per_second: float
    limitations: list[str]


TARGET_ORDER = ("guardian", "patient", "encounter")
SOURCE_TO_TARGET = {
    "LEGACY_GUARDIAN": "guardian",
    "LEGACY_PATIENT": "patient",
    "LEGACY_ENCOUNTER": "encounter",
}
SOURCE_COLUMNS = {
    "LEGACY_GUARDIAN": ("SOURCE_ROW_ID", "OWNER_NO", "OWNER_NAME", "PHONE"),
    "LEGACY_PATIENT": (
        "SOURCE_ROW_ID",
        "ANIMAL_NO",
        "OWNER_NO",
        "ANIMAL_NAME",
        "SPECIES_CODE",
        "BIRTH_YMD",
    ),
    "LEGACY_ENCOUNTER": (
        "SOURCE_ROW_ID",
        "CHART_NO",
        "ANIMAL_NO",
        "VISIT_AT",
        "AMOUNT",
    ),
}
TARGET_PRIMARY_KEYS = {
    "guardian": "guardian_id",
    "patient": "patient_id",
    "encounter": "encounter_id",
}
TARGET_COLUMNS = {
    "guardian": ("guardian_id", "full_name", "phone", "source_system"),
    "patient": (
        "patient_id",
        "guardian_id",
        "patient_name",
        "species",
        "birth_date",
        "source_system",
    ),
    "encounter": (
        "encounter_id",
        "patient_id",
        "encounter_date",
        "total_amount",
        "source_system",
    ),
}


def _field(source: str | None, target: str, *transforms: TransformSpec) -> FieldMapping:
    return FieldMapping(source=source, target=target, transforms=list(transforms))


def _transform(operation: str, value: Any = None) -> TransformSpec:
    payload: dict[str, Any] = {"operation": operation}
    if value is not None:
        payload["value"] = value
    return TransformSpec.model_validate(payload)


SOURCE_MAPPINGS = {
    "LEGACY_GUARDIAN": TableMapping(
        source_table="LEGACY_GUARDIAN",
        target_table="guardian",
        fields=[
            _field("owner_no", "guardian_id", _transform("prefix", "FB-G-")),
            _field("owner_name", "full_name", _transform("strip")),
            _field("phone", "phone", _transform("normalize_phone")),
            _field(None, "source_system", _transform("constant", "firebird_demo")),
        ],
    ),
    "LEGACY_PATIENT": TableMapping(
        source_table="LEGACY_PATIENT",
        target_table="patient",
        fields=[
            _field("animal_no", "patient_id", _transform("prefix", "FB-P-")),
            _field("owner_no", "guardian_id", _transform("prefix", "FB-G-")),
            _field("animal_name", "patient_name", _transform("strip")),
            _field(
                "species_code",
                "species",
                _transform("species_map", {"DOG": "canine", "CAT": "feline"}),
            ),
            _field("birth_ymd", "birth_date", _transform("parse_date")),
            _field(None, "source_system", _transform("constant", "firebird_demo")),
        ],
    ),
    "LEGACY_ENCOUNTER": TableMapping(
        source_table="LEGACY_ENCOUNTER",
        target_table="encounter",
        fields=[
            _field("chart_no", "encounter_id", _transform("prefix", "FB-E-")),
            _field("animal_no", "patient_id", _transform("prefix", "FB-P-")),
            _field("visit_at", "encounter_date", _transform("parse_date")),
            _field("amount", "total_amount", _transform("decimal_2", {"minimum": 0})),
            _field(None, "source_system", _transform("constant", "firebird_demo")),
        ],
    ),
}
TARGET_SPECS = {
    "guardian": TargetTableSpec(
        primary_key="guardian_id",
        required_fields=["guardian_id", "full_name", "source_system"],
    ),
    "patient": TargetTableSpec.model_validate(
        {
            "primary_key": "patient_id",
            "required_fields": [
                "patient_id",
                "guardian_id",
                "patient_name",
                "species",
                "birth_date",
                "source_system",
            ],
            "foreign_keys": [
                {
                    "column": "guardian_id",
                    "references_table": "guardian",
                    "references_column": "guardian_id",
                }
            ],
        }
    ),
    "encounter": TargetTableSpec.model_validate(
        {
            "primary_key": "encounter_id",
            "required_fields": [
                "encounter_id",
                "patient_id",
                "encounter_date",
                "total_amount",
                "source_system",
            ],
            "foreign_keys": [
                {
                    "column": "patient_id",
                    "references_table": "patient",
                    "references_column": "patient_id",
                }
            ],
        }
    ),
}


_FIREBIRD_DDL = {
    "LEGACY_GUARDIAN": """
        CREATE TABLE LEGACY_GUARDIAN (
            SOURCE_ROW_ID INTEGER NOT NULL PRIMARY KEY,
            OWNER_NO VARCHAR(32), OWNER_NAME VARCHAR(120), PHONE VARCHAR(40)
        )
    """,
    "LEGACY_PATIENT": """
        CREATE TABLE LEGACY_PATIENT (
            SOURCE_ROW_ID INTEGER NOT NULL PRIMARY KEY,
            ANIMAL_NO VARCHAR(32), OWNER_NO VARCHAR(32), ANIMAL_NAME VARCHAR(120),
            SPECIES_CODE VARCHAR(16), BIRTH_YMD VARCHAR(16)
        )
    """,
    "LEGACY_ENCOUNTER": """
        CREATE TABLE LEGACY_ENCOUNTER (
            SOURCE_ROW_ID INTEGER NOT NULL PRIMARY KEY,
            CHART_NO VARCHAR(32), ANIMAL_NO VARCHAR(32), VISIT_AT VARCHAR(16),
            AMOUNT VARCHAR(32)
        )
    """,
    "LEGACY_GUARDIAN_DRIFT": """
        CREATE TABLE LEGACY_GUARDIAN_DRIFT (
            SOURCE_ROW_ID INTEGER NOT NULL PRIMARY KEY,
            OWNER_NO VARCHAR(32), OWNER_NAME_RENAMED VARCHAR(120), PHONE VARCHAR(40)
        )
    """,
}


_POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS guardian (
    guardian_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    phone TEXT,
    source_system TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS patient (
    patient_id TEXT PRIMARY KEY,
    guardian_id TEXT NOT NULL REFERENCES guardian(guardian_id),
    patient_name TEXT NOT NULL,
    species TEXT NOT NULL CHECK (species IN ('canine', 'feline')),
    birth_date DATE NOT NULL,
    source_system TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS encounter (
    encounter_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patient(patient_id),
    encounter_date DATE NOT NULL,
    total_amount NUMERIC(14, 2) NOT NULL CHECK (total_amount >= 0),
    source_system TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS migration_run (
    run_id TEXT PRIMARY KEY,
    source_fingerprint TEXT NOT NULL,
    mapping_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS migration_checkpoint (
    run_id TEXT NOT NULL REFERENCES migration_run(run_id),
    source_table TEXT NOT NULL,
    target_table TEXT NOT NULL,
    last_source_row INTEGER NOT NULL,
    accepted_rows INTEGER NOT NULL,
    rejected_rows INTEGER NOT NULL,
    committed_batches INTEGER NOT NULL,
    PRIMARY KEY (run_id, source_table)
);
CREATE TABLE IF NOT EXISTS migration_lineage (
    run_id TEXT NOT NULL REFERENCES migration_run(run_id),
    source_table TEXT NOT NULL,
    source_row_id INTEGER NOT NULL,
    source_row_hash TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_primary_key TEXT NOT NULL,
    PRIMARY KEY (run_id, source_table, source_row_id)
);
CREATE TABLE IF NOT EXISTS migration_reject (
    run_id TEXT NOT NULL REFERENCES migration_run(run_id),
    source_table TEXT NOT NULL,
    source_row_id INTEGER NOT NULL,
    source_row_hash TEXT NOT NULL,
    target_table TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    detail TEXT NOT NULL,
    PRIMARY KEY (run_id, source_table, source_row_id)
);
"""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _hash_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def mapping_fingerprint() -> str:
    payload = {
        "contract": "firebird-postgres-v1",
        "mappings": {
            table: mapping.model_dump(mode="json")
            for table, mapping in SOURCE_MAPPINGS.items()
        },
        "targets": {
            table: spec.model_dump(mode="json") for table, spec in TARGET_SPECS.items()
        },
    }
    return _hash_value(payload)


def run_identifier(config: RdbMigrationConfig, source_fingerprint: str) -> str:
    return "rdb-" + _hash_value(
        {
            "entities_per_table": config.entities_per_table,
            "source_fingerprint": source_fingerprint,
            "mapping_fingerprint": mapping_fingerprint(),
        }
    )[:20]


def generate_source_row(source_table: str, index: int) -> tuple[Any, ...]:
    """Generate deterministic synthetic rows with sparse, explainable fault classes."""

    token = f"{index:06d}"
    if source_table == "LEGACY_GUARDIAN":
        owner_no: str | None = token
        owner_name = f" Guardian {token} "
        phone = f"010{index % 10_000:04d}{(index * 7) % 10_000:04d}"
        if index == 5_555:
            phone = "invalid-phone"
        if index == 7_777:
            owner_name = "   "
        if index == 9_999:
            owner_no = f"{9_998:06d}"
        return index, owner_no, owner_name, phone
    if source_table == "LEGACY_PATIENT":
        species = "CAT" if index % 4 == 0 else "DOG"
        if index == 12_345:
            species = "BIRD"
        return (
            index,
            token,
            token,
            f" Pet {token} ",
            species,
            f"{2010 + index % 10:04d}-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
        )
    if source_table == "LEGACY_ENCOUNTER":
        amount = str(20_000 + index % 80_000)
        if index == 23_456:
            amount = "-1"
        return (
            index,
            token,
            token,
            f"2026-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
            amount,
        )
    raise ValueError(f"unsupported source table: {source_table}")


def _connect_firebird(config: RdbMigrationConfig) -> Any:
    from firebird.driver import connect, driver_config

    driver_config.server_defaults.host.value = config.firebird_host
    driver_config.server_defaults.port.value = str(config.firebird_port)
    return connect(
        config.firebird_database,
        user=config.firebird_user,
        password=config.firebird_password,
        charset="UTF8",
    )


def _connect_postgres(config: RdbMigrationConfig) -> Any:
    import psycopg

    return psycopg.connect(
        host=config.postgres_host,
        port=config.postgres_port,
        dbname=config.postgres_database,
        user=config.postgres_user,
        password=config.postgres_password,
        autocommit=True,
    )


def _wait_for_connections(config: RdbMigrationConfig, timeout_seconds: int = 90) -> tuple[Any, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        firebird = postgres = None
        try:
            firebird = _connect_firebird(config)
            postgres = _connect_postgres(config)
            return firebird, postgres
        except Exception as exc:  # pragma: no cover - exercised by container startup
            last_error = exc
            if firebird is not None:
                firebird.close()
            if postgres is not None:
                postgres.close()
            time.sleep(1)
    raise RdbMigrationError(f"database readiness timeout: {last_error}")


def _firebird_tables(connection: Any) -> set[str]:
    cursor = connection.cursor()
    cursor.execute(
        "SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS "
        "WHERE RDB$SYSTEM_FLAG = 0"
    )
    return {str(row[0]).strip().upper() for row in cursor.fetchall()}


def _initialize_firebird(connection: Any) -> None:
    existing = _firebird_tables(connection)
    cursor = connection.cursor()
    for table, statement in _FIREBIRD_DDL.items():
        if table not in existing:
            cursor.execute(statement)
    connection.commit()


def _seed_firebird(connection: Any, config: RdbMigrationConfig) -> dict[str, int]:
    _initialize_firebird(connection)
    counts: dict[str, int] = {}
    cursor = connection.cursor()
    for table, columns in SOURCE_COLUMNS.items():
        cursor.execute(f"SELECT COALESCE(MAX(SOURCE_ROW_ID), 0), COUNT(*) FROM {table}")
        last_id, count = cursor.fetchone()
        last_id, count = int(last_id), int(count)
        if last_id != count or count > config.entities_per_table:
            raise RdbMigrationError(f"unexpected source state in {table}: max={last_id}, count={count}")
        placeholders = ", ".join("?" for _ in columns)
        insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        start = last_id + 1
        while start <= config.entities_per_table:
            end = min(start + config.batch_size - 1, config.entities_per_table)
            cursor.executemany(
                insert_sql,
                [generate_source_row(table, index) for index in range(start, end + 1)],
            )
            connection.commit()
            start = end + 1
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        counts[table] = int(cursor.fetchone()[0])
    return counts


def firebird_columns(connection: Any, table: str) -> tuple[str, ...]:
    cursor = connection.cursor()
    cursor.execute(
        "SELECT TRIM(RDB$FIELD_NAME) FROM RDB$RELATION_FIELDS "
        "WHERE TRIM(RDB$RELATION_NAME) = ? ORDER BY RDB$FIELD_POSITION",
        (table.upper(),),
    )
    return tuple(str(row[0]).strip().upper() for row in cursor.fetchall())


def validate_firebird_schema(
    connection: Any,
    table: str,
    expected_columns: tuple[str, ...],
) -> None:
    actual = set(firebird_columns(connection, table))
    missing = sorted(set(expected_columns) - actual)
    if missing:
        raise RdbSchemaDriftError(
            f"source schema drift in {table}; missing columns: {', '.join(missing)}"
        )


def _initialize_postgres(connection: Any) -> None:
    with connection.cursor() as cursor:
        cursor.execute(_POSTGRES_DDL)


def _fetch_firebird_batch(
    connection: Any,
    table: str,
    last_source_row: int,
    batch_size: int,
) -> list[dict[str, Any]]:
    columns = SOURCE_COLUMNS[table]
    cursor = connection.cursor()
    cursor.execute(
        f"SELECT FIRST {int(batch_size)} {', '.join(columns)} FROM {table} "
        "WHERE SOURCE_ROW_ID > ? ORDER BY SOURCE_ROW_ID",
        (last_source_row,),
    )
    return [
        {column.lower(): value for column, value in zip(columns, row, strict=True)}
        for row in cursor.fetchall()
    ]


def _source_fingerprint(connection: Any) -> str:
    digest = hashlib.sha256(b"firebird-source-v1\n")
    for table, columns in SOURCE_COLUMNS.items():
        cursor = connection.cursor()
        cursor.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY SOURCE_ROW_ID")
        while rows := cursor.fetchmany(5_000):
            for row in rows:
                digest.update(_canonical_json((table, *row)).encode("utf-8"))
                digest.update(b"\n")
    return digest.hexdigest()


def _target_counts(connection: Any) -> dict[str, int]:
    with connection.cursor() as cursor:
        counts: dict[str, int] = {}
        for table in TARGET_ORDER:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = int(cursor.fetchone()[0])
        return counts


def _checkpoint(connection: Any, run_id: str, source_table: str) -> dict[str, int] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT last_source_row, accepted_rows, rejected_rows, committed_batches "
            "FROM migration_checkpoint WHERE run_id = %s AND source_table = %s",
            (run_id, source_table),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return {
        "last_source_row": int(row[0]),
        "accepted_rows": int(row[1]),
        "rejected_rows": int(row[2]),
        "committed_batches": int(row[3]),
    }


def _checkpoint_total(connection: Any, run_id: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(SUM(last_source_row), 0) FROM migration_checkpoint WHERE run_id = %s",
            (run_id,),
        )
        return int(cursor.fetchone()[0])


def _committed_batches(connection: Any, run_id: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(SUM(committed_batches), 0) FROM migration_checkpoint WHERE run_id = %s",
            (run_id,),
        )
        return int(cursor.fetchone()[0])


def _ensure_run(
    connection: Any,
    run_id: str,
    source_fingerprint: str,
    mapping_sha: str,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT run_id, source_fingerprint, mapping_fingerprint FROM migration_run"
        )
        existing = cursor.fetchall()
        incompatible = [
            row
            for row in existing
            if row[0] != run_id
            or row[1] != source_fingerprint
            or row[2] != mapping_sha
        ]
        if incompatible:
            raise RdbMigrationError(
                "target contains a different migration contract; start a fresh Compose stack"
            )
        cursor.execute(
            "INSERT INTO migration_run (run_id, source_fingerprint, mapping_fingerprint, status) "
            "VALUES (%s, %s, %s, 'running') ON CONFLICT (run_id) DO NOTHING",
            (run_id, source_fingerprint, mapping_sha),
        )


def _row_hash(row: dict[str, Any]) -> str:
    return _hash_value(row)


def _validation_error(
    cursor: Any,
    target_table: str,
    target: dict[str, Any],
) -> tuple[str, str] | None:
    spec = TARGET_SPECS[target_table]
    missing = [name for name in spec.required_fields if target.get(name) in (None, "")]
    if missing:
        return "required_field_missing", "missing required fields: " + ", ".join(missing)
    primary_key = TARGET_PRIMARY_KEYS[target_table]
    cursor.execute(
        f"SELECT 1 FROM {target_table} WHERE {primary_key} = %s",
        (target[primary_key],),
    )
    if cursor.fetchone() is not None:
        return "duplicate_primary_key", f"duplicate primary key: {target[primary_key]}"
    for foreign_key in spec.foreign_keys:
        cursor.execute(
            f"SELECT 1 FROM {foreign_key.references_table} "
            f"WHERE {foreign_key.references_column} = %s",
            (target.get(foreign_key.column),),
        )
        if cursor.fetchone() is None:
            return (
                "foreign_key_missing",
                f"{foreign_key.column} has no accepted {foreign_key.references_table} parent",
            )
    return None


def _insert_target(cursor: Any, target_table: str, target: dict[str, Any]) -> None:
    columns = TARGET_COLUMNS[target_table]
    placeholders = ", ".join("%s" for _ in columns)
    cursor.execute(
        f"INSERT INTO {target_table} ({', '.join(columns)}) VALUES ({placeholders})",
        tuple(target[column] for column in columns),
    )


def _process_batch_row(
    cursor: Any,
    run_id: str,
    source_table: str,
    row: dict[str, Any],
) -> Literal["accepted", "rejected"]:
    target_table = SOURCE_TO_TARGET[source_table]
    source_row_id = int(row["source_row_id"])
    source_hash = _row_hash(row)
    mapping_input = {key: value for key, value in row.items() if key != "source_row_id"}
    try:
        target = transform_source_row(mapping_input, SOURCE_MAPPINGS[source_table])
    except MigrationContractError as exc:
        error = ("transform_error", str(exc))
    else:
        error = _validation_error(cursor, target_table, target)
    if error:
        cursor.execute(
            "INSERT INTO migration_reject "
            "(run_id, source_table, source_row_id, source_row_hash, target_table, reason_code, detail) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (run_id, source_table, source_row_id, source_hash, target_table, error[0], error[1]),
        )
        return "rejected"
    _insert_target(cursor, target_table, target)
    cursor.execute(
        "INSERT INTO migration_lineage "
        "(run_id, source_table, source_row_id, source_row_hash, target_table, target_primary_key) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (
            run_id,
            source_table,
            source_row_id,
            source_hash,
            target_table,
            str(target[TARGET_PRIMARY_KEYS[target_table]]),
        ),
    )
    return "accepted"


def _commit_batch(
    connection: Any,
    run_id: str,
    source_table: str,
    rows: list[dict[str, Any]],
    *,
    inject_failure: bool,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    with connection.transaction():
        with connection.cursor() as cursor:
            for offset, row in enumerate(rows, start=1):
                counts[_process_batch_row(cursor, run_id, source_table, row)] += 1
                if inject_failure and offset == min(10, len(rows)):
                    raise _InjectedBatchFailure("simulated mid-batch connection loss")
            cursor.execute(
                "INSERT INTO migration_checkpoint "
                "(run_id, source_table, target_table, last_source_row, accepted_rows, "
                "rejected_rows, committed_batches) VALUES (%s, %s, %s, %s, %s, %s, 1) "
                "ON CONFLICT (run_id, source_table) DO UPDATE SET "
                "last_source_row = EXCLUDED.last_source_row, "
                "accepted_rows = migration_checkpoint.accepted_rows + EXCLUDED.accepted_rows, "
                "rejected_rows = migration_checkpoint.rejected_rows + EXCLUDED.rejected_rows, "
                "committed_batches = migration_checkpoint.committed_batches + 1",
                (
                    run_id,
                    source_table,
                    SOURCE_TO_TARGET[source_table],
                    int(rows[-1]["source_row_id"]),
                    counts["accepted"],
                    counts["rejected"],
                ),
            )
    return counts


def _migration_pass(
    firebird: Any,
    postgres: Any,
    config: RdbMigrationConfig,
    run_id: str,
    *,
    allow_failure: bool,
) -> tuple[int, bool, bool, int]:
    processed = 0
    for source_table in SOURCE_TO_TARGET:
        checkpoint = _checkpoint(postgres, run_id, source_table)
        last_source_row = checkpoint["last_source_row"] if checkpoint else 0
        while last_source_row < config.entities_per_table:
            rows = _fetch_firebird_batch(
                firebird, source_table, last_source_row, config.batch_size
            )
            if not rows:
                raise RdbMigrationError(
                    f"source ended before expected row in {source_table}: {last_source_row}"
                )
            should_fail = (
                allow_failure
                and _committed_batches(postgres, run_id) >= config.interrupt_after_batches
            )
            before_counts = _target_counts(postgres)
            before_checkpoint = _checkpoint_total(postgres, run_id)
            try:
                _commit_batch(
                    postgres,
                    run_id,
                    source_table,
                    rows,
                    inject_failure=should_fail,
                )
            except _InjectedBatchFailure:
                rollback_verified = (
                    _target_counts(postgres) == before_counts
                    and _checkpoint_total(postgres, run_id) == before_checkpoint
                )
                return processed, True, rollback_verified, before_checkpoint
            processed += len(rows)
            last_source_row = int(rows[-1]["source_row_id"])
    return processed, False, False, _checkpoint_total(postgres, run_id)


def _stream_digest(
    connection: Any,
    label: str,
    query: str,
    parameters: tuple[Any, ...] = (),
) -> str:
    digest = hashlib.sha256(label.encode("utf-8"))
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        while rows := cursor.fetchmany(5_000):
            for row in rows:
                digest.update(_canonical_json(tuple(row)).encode("utf-8"))
                digest.update(b"\n")
    return digest.hexdigest()


def _result_fingerprint(connection: Any, run_id: str) -> str:
    components = {
        "guardian": _stream_digest(
            connection,
            "guardian",
            "SELECT guardian_id, full_name, phone, source_system FROM guardian ORDER BY guardian_id",
        ),
        "patient": _stream_digest(
            connection,
            "patient",
            "SELECT patient_id, guardian_id, patient_name, species, birth_date, source_system "
            "FROM patient ORDER BY patient_id",
        ),
        "encounter": _stream_digest(
            connection,
            "encounter",
            "SELECT encounter_id, patient_id, encounter_date, total_amount, source_system "
            "FROM encounter ORDER BY encounter_id",
        ),
        "reject": _stream_digest(
            connection,
            "reject",
            "SELECT source_table, source_row_id, source_row_hash, target_table, reason_code, detail "
            "FROM migration_reject WHERE run_id = %s ORDER BY source_table, source_row_id",
            (run_id,),
        ),
    }
    return _hash_value(components)


def _collect_reconciliation(
    firebird_counts: dict[str, int],
    connection: Any,
    run_id: str,
) -> tuple[list[RdbTableReconciliation], int, int]:
    rows: list[RdbTableReconciliation] = []
    accepted_total = rejected_total = 0
    with connection.cursor() as cursor:
        for source_table, target_table in SOURCE_TO_TARGET.items():
            cursor.execute(
                "SELECT COUNT(*) FROM migration_lineage WHERE run_id = %s AND source_table = %s",
                (run_id, source_table),
            )
            accepted = int(cursor.fetchone()[0])
            cursor.execute(
                "SELECT COUNT(*) FROM migration_reject WHERE run_id = %s AND source_table = %s",
                (run_id, source_table),
            )
            rejected = int(cursor.fetchone()[0])
            checkpoint = _checkpoint(connection, run_id, source_table)
            checkpoint_rows = 0 if checkpoint is None else (
                checkpoint["accepted_rows"] + checkpoint["rejected_rows"]
            )
            source_rows = firebird_counts[source_table]
            passed = source_rows == accepted + rejected == checkpoint_rows
            rows.append(
                RdbTableReconciliation(
                    source_table=source_table,
                    target_table=target_table,
                    source_rows=source_rows,
                    accepted_rows=accepted,
                    rejected_rows=rejected,
                    checkpoint_rows=checkpoint_rows,
                    status="pass" if passed else "fail",
                )
            )
            accepted_total += accepted
            rejected_total += rejected
    return rows, accepted_total, rejected_total


def _reason_counts(connection: Any, run_id: str) -> dict[str, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT reason_code, COUNT(*) FROM migration_reject WHERE run_id = %s "
            "GROUP BY reason_code ORDER BY reason_code",
            (run_id,),
        )
        return {str(reason): int(count) for reason, count in cursor.fetchall()}


def _foreign_key_violations(connection: Any) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM patient p LEFT JOIN guardian g ON g.guardian_id = p.guardian_id "
            " WHERE g.guardian_id IS NULL) + "
            "(SELECT COUNT(*) FROM encounter e LEFT JOIN patient p ON p.patient_id = e.patient_id "
            " WHERE p.patient_id IS NULL)"
        )
        return int(cursor.fetchone()[0])


def _engine_versions(firebird: Any, postgres: Any) -> tuple[str, str]:
    source = f"Firebird {firebird.info.version}"
    with postgres.cursor() as cursor:
        cursor.execute("SHOW server_version")
        target = f"PostgreSQL {cursor.fetchone()[0]}"
    return source, target


def run_rdb_migration(config: RdbMigrationConfig) -> RdbMigrationReport:
    """Execute source seed, migration, failure/recovery, replay, and SQL audits."""

    started = time.monotonic()
    firebird, postgres = _wait_for_connections(config)
    try:
        firebird_counts = _seed_firebird(firebird, config)
        for table, columns in SOURCE_COLUMNS.items():
            validate_firebird_schema(firebird, table, columns)
        _initialize_postgres(postgres)

        domain_before_drift_probe = _target_counts(postgres)
        drift_blocked = False
        drift_detail = ""
        try:
            validate_firebird_schema(
                firebird,
                "LEGACY_GUARDIAN_DRIFT",
                SOURCE_COLUMNS["LEGACY_GUARDIAN"],
            )
        except RdbSchemaDriftError as exc:
            drift_blocked = _target_counts(postgres) == domain_before_drift_probe
            drift_detail = str(exc)

        source_sha = _source_fingerprint(firebird)
        mapping_sha = mapping_fingerprint()
        run_id = run_identifier(config, source_sha)
        _ensure_run(postgres, run_id, source_sha, mapping_sha)
        _, interrupted, rollback_verified, resumed_from = _migration_pass(
            firebird,
            postgres,
            config,
            run_id,
            allow_failure=True,
        )
        if not interrupted:
            raise RdbMigrationError("failure injection did not execute")
    finally:
        firebird.close()
        postgres.close()

    firebird, postgres = _wait_for_connections(config)
    try:
        resumed_processed, _, _, _ = _migration_pass(
            firebird,
            postgres,
            config,
            run_id,
            allow_failure=False,
        )
        result_sha = _result_fingerprint(postgres, run_id)
        replay_processed, _, _, _ = _migration_pass(
            firebird,
            postgres,
            config,
            run_id,
            allow_failure=False,
        )
        replay_sha = _result_fingerprint(postgres, run_id)
        reconciliation, accepted, rejected = _collect_reconciliation(
            firebird_counts, postgres, run_id
        )
        target_counts = _target_counts(postgres)
        foreign_key_violations = _foreign_key_violations(postgres)
        source_engine, target_engine = _engine_versions(firebird, postgres)
        committed_batches = _committed_batches(postgres, run_id)
        checkpoint_resume = resumed_from > 0 and resumed_processed > 0
        idempotent_replay = replay_processed == 0 and result_sha == replay_sha
        status = "pass" if all(
            [
                sum(firebird_counts.values()) == accepted + rejected,
                all(item.status == "pass" for item in reconciliation),
                sum(target_counts.values()) == accepted,
                foreign_key_violations == 0,
                rollback_verified,
                checkpoint_resume,
                idempotent_replay,
                drift_blocked,
            ]
        ) else "fail"
        with postgres.cursor() as cursor:
            cursor.execute(
                "UPDATE migration_run SET status = %s, completed_at = CURRENT_TIMESTAMP WHERE run_id = %s",
                ("completed" if status == "pass" else "failed", run_id),
            )
        elapsed = time.monotonic() - started
        return RdbMigrationReport(
            generated_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            status=status,
            run_id=run_id,
            source_engine=source_engine,
            target_engine=target_engine,
            source_rows=sum(firebird_counts.values()),
            accepted_rows=accepted,
            rejected_rows=rejected,
            target_counts=target_counts,
            reason_counts=_reason_counts(postgres, run_id),
            reconciliation=reconciliation,
            committed_batches=committed_batches,
            resumed_from_source_rows=resumed_from,
            replay_processed_rows=replay_processed,
            rollback_verified=rollback_verified,
            checkpoint_resume_verified=checkpoint_resume,
            idempotent_replay=idempotent_replay,
            schema_drift_blocked_before_write=drift_blocked,
            schema_drift_detail=drift_detail,
            foreign_key_violations=foreign_key_violations,
            source_fingerprint_sha256=source_sha,
            mapping_fingerprint_sha256=mapping_sha,
            result_fingerprint_sha256=result_sha,
            elapsed_seconds=round(elapsed, 6),
            observed_rows_per_second=round(sum(firebird_counts.values()) / elapsed, 3),
            limitations=[
                "Source rows are deterministic synthetic records; no real patient data is used.",
                "This container integration is not evidence of a production hospital cutover.",
                "Observed throughput is machine-specific and is not a production SLA.",
                "CDC, lock contention, backup/WAL recovery, cloud networking, "
                "and PHI controls are out of scope.",
            ],
        )
    finally:
        firebird.close()
        postgres.close()


def render_rdb_migration_report(report: RdbMigrationReport) -> str:
    lines = [
        "# Firebird to PostgreSQL Migration Integration",
        "",
        f"- status: **{report.status.upper()}**",
        f"- run: `{report.run_id}`",
        f"- source: **{report.source_engine}**",
        f"- target: **{report.target_engine}**",
        f"- source rows: **{report.source_rows:,}**",
        f"- accepted/rejected: **{report.accepted_rows:,} / {report.rejected_rows:,}**",
        f"- committed batches: **{report.committed_batches}**",
        f"- resumed from: **{report.resumed_from_source_rows:,} source rows**",
        f"- completed-run replay: **{report.replay_processed_rows} rows processed**",
        f"- transaction rollback verified: **{str(report.rollback_verified).upper()}**",
        f"- checkpoint resume verified: **{str(report.checkpoint_resume_verified).upper()}**",
        f"- schema drift blocked before write: **{str(report.schema_drift_blocked_before_write).upper()}**",
        f"- foreign-key violations: **{report.foreign_key_violations}**",
        "",
        "## Reconciliation",
        "",
        "| Firebird source | PostgreSQL target | Source | Accepted | Rejected | Checkpoint | Status |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for item in report.reconciliation:
        lines.append(
            f"| {item.source_table} | {item.target_table} | {item.source_rows:,} | "
            f"{item.accepted_rows:,} | {item.rejected_rows:,} | "
            f"{item.checkpoint_rows:,} | {item.status} |"
        )
    lines.extend(
        [
            "",
            "## Reject reasons",
            "",
            *[f"- {reason}: **{count:,}**" for reason, count in report.reason_counts.items()],
            "",
            "## Provenance",
            "",
            f"- source SHA-256: `{report.source_fingerprint_sha256}`",
            f"- mapping SHA-256: `{report.mapping_fingerprint_sha256}`",
            f"- result SHA-256: `{report.result_fingerprint_sha256}`",
            f"- elapsed: **{report.elapsed_seconds:.3f}s**",
            f"- observed throughput: **{report.observed_rows_per_second:,.1f} rows/s**",
            f"- drift evidence: `{report.schema_drift_detail}`",
            "",
            "## Limits",
            "",
            *[f"- {item}" for item in report.limitations],
            "",
        ]
    )
    return "\n".join(lines)


def write_rdb_migration_reports(
    report: RdbMigrationReport,
    json_path: Path,
    markdown_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_rdb_migration_report(report), encoding="utf-8")
