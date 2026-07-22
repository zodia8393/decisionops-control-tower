"""Deterministic synthetic legacy-hospital migration and reconciliation case."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DEFAULT_MIGRATION_CASE_PATH = (
    Path(__file__).with_name("fixtures") / "legacy_hospital_migration.json"
)
Scalar = str | int | float | bool | None


class MigrationContractError(ValueError):
    """Raised when a migration case or transform violates its contract."""


class ForeignKeySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1, max_length=120)
    references_table: str = Field(min_length=1, max_length=120)
    references_column: str = Field(min_length=1, max_length=120)


class TargetTableSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_key: str = Field(min_length=1, max_length=120)
    required_fields: list[str] = Field(min_length=1, max_length=50)
    foreign_keys: list[ForeignKeySpec] = Field(default_factory=list, max_length=20)


class TransformSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal[
        "strip",
        "upper",
        "normalize_phone",
        "prefix",
        "species_map",
        "parse_date",
        "decimal_2",
        "constant",
    ]
    value: str | float | dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_value(self) -> "TransformSpec":
        if self.operation in {"prefix", "constant"} and not isinstance(self.value, str):
            raise ValueError(f"{self.operation} requires a string value")
        if self.operation == "species_map" and not isinstance(self.value, dict):
            raise ValueError("species_map requires an object value")
        return self


class FieldMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str | None = Field(default=None, max_length=120)
    target: str = Field(min_length=1, max_length=120)
    transforms: list[TransformSpec] = Field(default_factory=list, max_length=10)


class TableMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_table: str = Field(min_length=1, max_length=120)
    target_table: str = Field(min_length=1, max_length=120)
    fields: list[FieldMapping] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_targets(self) -> "TableMapping":
        targets = [field.target for field in self.fields]
        if len(targets) != len(set(targets)):
            raise ValueError("field mapping targets must be unique")
        return self


class SourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_engine: str = Field(min_length=3, max_length=120)
    tables: dict[str, list[dict[str, Scalar]]]
    mappings: list[TableMapping] = Field(min_length=1, max_length=30)


class MigrationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["decisionops-migration-case-v1"]
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=500)
    canonical_tables: dict[str, TargetTableSpec]
    sources: dict[str, SourceSpec]
    limitations: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_relations(self) -> "MigrationCase":
        for table, spec in self.canonical_tables.items():
            for foreign_key in spec.foreign_keys:
                parent = self.canonical_tables.get(foreign_key.references_table)
                if parent is None or parent.primary_key != foreign_key.references_column:
                    raise ValueError(f"invalid foreign key in target table: {table}")
        for source_name, source in self.sources.items():
            self._validate_source(source_name, source)
        mapped_targets = {
            mapping.target_table
            for source in self.sources.values()
            for mapping in source.mappings
        }
        if mapped_targets != set(self.canonical_tables):
            raise ValueError("every canonical target table must have a mapping")
        self.ordered_target_tables()
        return self

    def _validate_source(self, source_name: str, source: SourceSpec) -> None:
        mapped_source_tables = [mapping.source_table for mapping in source.mappings]
        if len(mapped_source_tables) != len(set(mapped_source_tables)):
            raise ValueError(f"source table must be mapped exactly once: {source_name}")
        if set(mapped_source_tables) != set(source.tables):
            raise ValueError(f"every source table must be mapped exactly once: {source_name}")
        for mapping in source.mappings:
            rows = source.tables.get(mapping.source_table)
            target = self.canonical_tables.get(mapping.target_table)
            if rows is None or target is None:
                raise ValueError(f"invalid table mapping for source: {source_name}")
            mapped_targets = {field.target for field in mapping.fields}
            if target.primary_key not in mapped_targets:
                raise ValueError(f"primary key is not mapped: {mapping.target_table}")
            if not set(target.required_fields).issubset(mapped_targets):
                raise ValueError(f"required target fields are not mapped: {mapping.target_table}")
            for field in mapping.fields:
                if field.source is not None and any(field.source not in row for row in rows):
                    raise ValueError(f"source field is missing: {mapping.source_table}.{field.source}")

    def ordered_target_tables(self) -> list[str]:
        """Return deterministic FK topological order and reject cyclic targets."""

        pending = list(self.canonical_tables)
        resolved: list[str] = []
        while pending:
            ready = [
                table
                for table in pending
                if {
                    foreign_key.references_table
                    for foreign_key in self.canonical_tables[table].foreign_keys
                }.issubset(resolved)
            ]
            if not ready:
                raise ValueError("canonical target foreign keys contain a cycle")
            for table in ready:
                pending.remove(table)
                resolved.append(table)
        return resolved


class RejectRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_system: str
    source_engine: str
    source_table: str
    source_row_number: int = Field(ge=1)
    source_row_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_table: str
    reason_code: Literal[
        "transform_error",
        "required_field_missing",
        "duplicate_primary_key",
        "foreign_key_missing",
    ]
    detail: str


class LineageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_system: str
    source_table: str
    source_row_number: int = Field(ge=1)
    source_row_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_table: str
    target_primary_key: str


class TableReconciliation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_system: str
    source_table: str
    target_table: str
    source_rows: int = Field(ge=0)
    accepted_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    accounted_rows: int = Field(ge=0)
    status: Literal["pass", "fail"]


class MigrationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["decisionops-migration-report-v1"] = (
        "decisionops-migration-report-v1"
    )
    case_id: str
    title: str
    generated_at_utc: str
    status: Literal["pass", "fail"]
    outcome: Literal["completed", "completed_with_rejects", "failed"]
    source_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mapping_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    metrics: dict[str, int]
    reason_counts: dict[str, int]
    target_checksums: dict[str, str]
    reconciliation: list[TableReconciliation]
    accepted_targets: dict[str, list[dict[str, Scalar]]]
    lineage: list[LineageRecord]
    rejects: list[RejectRecord]
    limitations: list[str]


@dataclass(frozen=True)
class _RowContext:
    source_system: str
    source_engine: str
    source_table: str
    target_table: str
    row_number: int
    row_hash: str


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_migration_case(path: Path = DEFAULT_MIGRATION_CASE_PATH) -> MigrationCase:
    """Load and validate the versioned public-safe migration fixture."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationContractError(f"migration case could not be loaded: {path}") from exc
    return MigrationCase.model_validate(payload)


def required_source_columns(mapping: TableMapping) -> set[str]:
    """Return source columns required by a versioned table mapping."""

    return {field.source for field in mapping.fields if field.source is not None}


def validate_source_schema(mapping: TableMapping, columns: set[str]) -> None:
    """Fail before transformation when required legacy columns drift or disappear."""

    missing = sorted(required_source_columns(mapping) - columns)
    if missing:
        raise MigrationContractError(
            f"source schema drift in {mapping.source_table}; missing columns: "
            + ", ".join(missing)
        )


def _normalize_phone(value: Any) -> str | None:
    if value in (None, ""):
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != 11:
        raise MigrationContractError("phone must contain 11 digits")
    return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"


def _decimal_2(value: Any, config: Any) -> str:
    try:
        number = Decimal(str(value).replace(",", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise MigrationContractError("value is not a decimal") from exc
    minimum = config.get("minimum") if isinstance(config, dict) else None
    if minimum is not None and number < Decimal(str(minimum)):
        raise MigrationContractError(f"decimal is below minimum {minimum}")
    return format(number, ".2f")


def _apply_transform(value: Any, transform: TransformSpec) -> Any:
    operation = transform.operation
    if operation == "constant":
        return transform.value
    if operation == "strip":
        return value.strip() if isinstance(value, str) else value
    if operation == "upper":
        return value.upper() if isinstance(value, str) else value
    if operation == "normalize_phone":
        return _normalize_phone(value)
    if operation == "prefix":
        return None if value is None else f"{transform.value}{value}"
    if operation == "species_map":
        mapping = transform.value if isinstance(transform.value, dict) else {}
        if value not in mapping:
            raise MigrationContractError(f"species mapping is missing: {value}")
        return mapping[value]
    if operation == "parse_date":
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError as exc:
            raise MigrationContractError("value is not an ISO date") from exc
    if operation == "decimal_2":
        return _decimal_2(value, transform.value)
    raise MigrationContractError(f"unsupported transform: {operation}")


def transform_source_row(
    row: dict[str, Scalar], mapping: TableMapping
) -> dict[str, Scalar]:
    """Apply only allowlisted transforms from a validated source mapping."""

    target: dict[str, Scalar] = {}
    for field in mapping.fields:
        value: Any = row.get(field.source) if field.source is not None else None
        for transform in field.transforms:
            try:
                value = _apply_transform(value, transform)
            except MigrationContractError as exc:
                raise MigrationContractError(f"{field.target}: {exc}") from exc
        target[field.target] = value
    return target


def _row_context(
    source_system: str,
    source: SourceSpec,
    mapping: TableMapping,
    row_number: int,
    row: dict[str, Scalar],
) -> _RowContext:
    return _RowContext(
        source_system=source_system,
        source_engine=source.source_engine,
        source_table=mapping.source_table,
        target_table=mapping.target_table,
        row_number=row_number,
        row_hash=_canonical_hash(row),
    )


def _reject(context: _RowContext, reason_code: str, detail: str) -> RejectRecord:
    return RejectRecord(
        source_system=context.source_system,
        source_engine=context.source_engine,
        source_table=context.source_table,
        source_row_number=context.row_number,
        source_row_hash=context.row_hash,
        target_table=context.target_table,
        reason_code=reason_code,
        detail=detail,
    )


def _validation_error(
    row: dict[str, Scalar],
    spec: TargetTableSpec,
    accepted: dict[str, list[dict[str, Scalar]]],
    seen_primary_keys: set[str],
) -> tuple[str, str] | None:
    missing = [field for field in spec.required_fields if row.get(field) in (None, "")]
    if missing:
        return "required_field_missing", "missing required fields: " + ", ".join(missing)
    primary_key = str(row[spec.primary_key])
    if primary_key in seen_primary_keys:
        return "duplicate_primary_key", f"duplicate primary key: {primary_key}"
    for foreign_key in spec.foreign_keys:
        parent_values = {
            str(parent.get(foreign_key.references_column))
            for parent in accepted[foreign_key.references_table]
        }
        if str(row.get(foreign_key.column)) not in parent_values:
            return (
                "foreign_key_missing",
                f"{foreign_key.column} has no accepted {foreign_key.references_table} parent",
            )
    return None


def _process_mapping(
    source_system: str,
    source: SourceSpec,
    mapping: TableMapping,
    spec: TargetTableSpec,
    accepted: dict[str, list[dict[str, Scalar]]],
    seen_primary_keys: set[str],
) -> tuple[list[LineageRecord], list[RejectRecord]]:
    lineage: list[LineageRecord] = []
    rejects: list[RejectRecord] = []
    for row_number, row in enumerate(source.tables[mapping.source_table], start=1):
        context = _row_context(source_system, source, mapping, row_number, row)
        try:
            target = transform_source_row(row, mapping)
        except MigrationContractError as exc:
            rejects.append(_reject(context, "transform_error", str(exc)))
            continue
        error = _validation_error(target, spec, accepted, seen_primary_keys)
        if error:
            rejects.append(_reject(context, error[0], error[1]))
            continue
        primary_key = str(target[spec.primary_key])
        seen_primary_keys.add(primary_key)
        accepted[mapping.target_table].append(target)
        lineage.append(
            LineageRecord(
                source_system=source_system,
                source_table=mapping.source_table,
                source_row_number=row_number,
                source_row_hash=context.row_hash,
                target_table=mapping.target_table,
                target_primary_key=primary_key,
            )
        )
    return lineage, rejects


def _mapping_pairs(case: MigrationCase) -> list[tuple[str, SourceSpec, TableMapping]]:
    pairs: list[tuple[str, SourceSpec, TableMapping]] = []
    for target_table in case.ordered_target_tables():
        for source_system, source in case.sources.items():
            pairs.extend(
                (source_system, source, mapping)
                for mapping in source.mappings
                if mapping.target_table == target_table
            )
    return pairs


def _reconciliation(
    pairs: list[tuple[str, SourceSpec, TableMapping]],
    lineage: list[LineageRecord],
    rejects: list[RejectRecord],
) -> list[TableReconciliation]:
    rows: list[TableReconciliation] = []
    for source_system, source, mapping in pairs:
        source_rows = len(source.tables[mapping.source_table])
        accepted_rows = sum(
            item.source_system == source_system and item.source_table == mapping.source_table
            for item in lineage
        )
        rejected_rows = sum(
            item.source_system == source_system and item.source_table == mapping.source_table
            for item in rejects
        )
        accounted = accepted_rows + rejected_rows
        rows.append(
            TableReconciliation(
                source_system=source_system,
                source_table=mapping.source_table,
                target_table=mapping.target_table,
                source_rows=source_rows,
                accepted_rows=accepted_rows,
                rejected_rows=rejected_rows,
                accounted_rows=accounted,
                status="pass" if accounted == source_rows else "fail",
            )
        )
    return rows


def _mapping_payload(case: MigrationCase) -> dict[str, Any]:
    return {
        "canonical_tables": {
            name: spec.model_dump(mode="json") for name, spec in case.canonical_tables.items()
        },
        "sources": {
            name: [mapping.model_dump(mode="json") for mapping in source.mappings]
            for name, source in case.sources.items()
        },
    }


def run_migration_case(case: MigrationCase | None = None) -> MigrationReport:
    """Run the synthetic mapping with full row accounting and deterministic lineage."""

    case = case or load_migration_case()
    accepted: dict[str, list[dict[str, Scalar]]] = {
        table: [] for table in case.canonical_tables
    }
    lineage: list[LineageRecord] = []
    rejects: list[RejectRecord] = []
    pairs = _mapping_pairs(case)
    for source_system, source, mapping in pairs:
        new_lineage, new_rejects = _process_mapping(
            source_system,
            source,
            mapping,
            case.canonical_tables[mapping.target_table],
            accepted,
            {str(row[case.canonical_tables[mapping.target_table].primary_key]) for row in accepted[mapping.target_table]},
        )
        lineage.extend(new_lineage)
        rejects.extend(new_rejects)
    reconciliation = _reconciliation(pairs, lineage, rejects)
    source_payload = {
        name: {"source_engine": source.source_engine, "tables": source.tables}
        for name, source in case.sources.items()
    }
    source_fingerprint = _canonical_hash(source_payload)
    mapping_fingerprint = _canonical_hash(_mapping_payload(case))
    result_payload = {
        "case_id": case.case_id,
        "accepted_targets": accepted,
        "lineage": [item.model_dump(mode="json") for item in lineage],
        "rejects": [item.model_dump(mode="json") for item in rejects],
        "reconciliation": [item.model_dump(mode="json") for item in reconciliation],
    }
    status = "pass" if all(item.status == "pass" for item in reconciliation) else "fail"
    reason_counts = dict(sorted(Counter(item.reason_code for item in rejects).items()))
    metrics = {
        "source_systems": len(case.sources),
        "source_tables": len(pairs),
        "source_rows": sum(item.source_rows for item in reconciliation),
        "accepted_rows": len(lineage),
        "rejected_rows": len(rejects),
        "target_tables": len(accepted),
    }
    return MigrationReport(
        case_id=case.case_id,
        title=case.title,
        generated_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        status=status,
        outcome=("failed" if status == "fail" else "completed_with_rejects" if rejects else "completed"),
        source_fingerprint_sha256=source_fingerprint,
        mapping_fingerprint_sha256=mapping_fingerprint,
        result_fingerprint_sha256=_canonical_hash(result_payload),
        idempotency_key=_canonical_hash(
            {"source": source_fingerprint, "mapping": mapping_fingerprint}
        ),
        metrics=metrics,
        reason_counts=reason_counts,
        target_checksums={table: _canonical_hash(rows) for table, rows in accepted.items()},
        reconciliation=reconciliation,
        accepted_targets=accepted,
        lineage=lineage,
        rejects=rejects,
        limitations=case.limitations,
    )


def render_migration_report(report: MigrationReport) -> str:
    """Render a concise recruiter-facing report without production overclaim."""

    metrics = report.metrics
    lines = [
        "# Legacy Hospital Migration validation case",
        "",
        f"- generated: `{report.generated_at_utc}`",
        f"- case: `{report.case_id}`",
        f"- validation status: **{report.status.upper()}**",
        f"- outcome: `{report.outcome}`",
        "- boundary: synthetic versioned extracts; no real patient data or live DB write",
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
            "## Totals",
            "",
            f"- source rows: **{metrics['source_rows']}**",
            f"- accepted canonical rows: **{metrics['accepted_rows']}**",
            f"- rejected with lineage: **{metrics['rejected_rows']}**",
            f"- rejection reasons: `{json.dumps(report.reason_counts, sort_keys=True)}`",
            f"- result fingerprint: `sha256:{report.result_fingerprint_sha256}`",
            "",
            "## Reject lineage",
            "",
            "| Source row | Target | Reason | Detail |",
            "|---|---|---|---|",
        ]
    )
    for item in report.rejects:
        lines.append(
            f"| {item.source_system}.{item.source_table}#{item.source_row_number} | "
            f"{item.target_table} | {item.reason_code} | {item.detail} |"
        )
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {item}" for item in report.limitations)
    lines.append("")
    return "\n".join(lines)
