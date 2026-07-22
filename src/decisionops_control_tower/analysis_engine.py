"""Validated contracts and deterministic execution for uploaded tabular data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import math
import re
from typing import Any, Literal

import duckdb
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from decisionops_control_tower.data_analysis import (
    LoadedDataset,
    load_dataset,
    profile_dataset,
)


ANALYSIS_TABLE = "uploaded_data"
SOURCE_ROW_COLUMN = "__decisionops_source_row__"
MAX_RESULT_ROWS = 200
SAFE_ALIAS_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
Scalar = str | int | float | bool | None


class AnalysisContractError(ValueError):
    """Raised when a plan cannot be executed against the supplied dataset."""


class ColumnManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    dtype: str = Field(min_length=1, max_length=80)
    missing_count: int = Field(ge=0)
    missing_rate: float = Field(ge=0.0, le=1.0)
    unique_count: int = Field(ge=0)
    numeric: bool
    temporal: bool = False


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["decisionops-dataset-manifest-v1"] = (
        "decisionops-dataset-manifest-v1"
    )
    filename: str = Field(min_length=1, max_length=120)
    data_format: Literal["csv", "json", "xlsx", "parquet"]
    fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_count: int = Field(ge=1)
    column_count: int = Field(ge=1)
    columns: list[ColumnManifest] = Field(min_length=1, max_length=100)
    storage: Literal["not_persisted"] = "not_persisted"

    @model_validator(mode="after")
    def validate_columns(self) -> "DatasetManifest":
        names = [column.name for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("dataset column names must be unique")
        if self.column_count != len(self.columns):
            raise ValueError("column_count does not match columns")
        return self

    @classmethod
    def from_profile(cls, profile: dict[str, Any]) -> "DatasetManifest":
        columns = [
            {
                "name": item["name"],
                "dtype": item["dtype"],
                "missing_count": item["missing_count"],
                "missing_rate": item["missing_rate"],
                "unique_count": item["unique_count"],
                "numeric": "numeric" in item,
                "temporal": "temporal" in item,
            }
            for item in profile["columns"]
        ]
        return cls(
            filename=profile["filename"],
            data_format=profile["format"],
            fingerprint_sha256=profile["fingerprint_sha256"],
            row_count=profile["row_count"],
            column_count=profile["column_count"],
            columns=columns,
        )


class FilterClause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1, max_length=120)
    operator: Literal[
        "eq", "ne", "gt", "gte", "lt", "lte", "contains", "in", "is_null", "not_null"
    ]
    value: Scalar | list[Scalar] = None

    @model_validator(mode="after")
    def validate_value(self) -> "FilterClause":
        if self.operator in {"is_null", "not_null"}:
            if self.value is not None:
                raise ValueError(f"{self.operator} does not accept a value")
            return self
        if self.operator == "in":
            if not isinstance(self.value, list) or not 1 <= len(self.value) <= 100:
                raise ValueError("in filter requires 1..100 values")
        elif isinstance(self.value, list) or self.value is None:
            raise ValueError(f"{self.operator} requires one scalar value")
        _validate_finite_values(self.value)
        return self


class MetricSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal[
        "count",
        "share",
        "count_distinct",
        "sum",
        "mean",
        "median",
        "stddev",
        "correlation",
        "min",
        "max",
    ]
    column: str | None = Field(default=None, min_length=1, max_length=120)
    secondary_column: str | None = Field(default=None, min_length=1, max_length=120)
    alias: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_metric(self) -> "MetricSpec":
        if not SAFE_ALIAS_PATTERN.fullmatch(self.alias):
            raise ValueError("metric alias must be a safe ASCII identifier")
        if self.operation not in {"count", "share"} and self.column is None:
            raise ValueError(f"{self.operation} requires a column")
        if self.operation == "share" and self.column is not None:
            raise ValueError("share does not accept a column")
        if self.operation == "correlation" and self.secondary_column is None:
            raise ValueError("correlation requires a secondary_column")
        if self.operation != "correlation" and self.secondary_column is not None:
            raise ValueError(f"{self.operation} does not accept a secondary_column")
        return self


class SortSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1, max_length=120)
    direction: Literal["asc", "desc"] = "asc"


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["decisionops-analysis-plan-v1"] = "decisionops-analysis-plan-v1"
    operation: Literal["select", "aggregate"]
    select_columns: list[str] = Field(default_factory=list, max_length=30)
    filters: list[FilterClause] = Field(default_factory=list, max_length=20)
    group_by: list[str] = Field(default_factory=list, max_length=8)
    metrics: list[MetricSpec] = Field(default_factory=list, max_length=12)
    order_by: list[SortSpec] = Field(default_factory=list, max_length=5)
    limit: int = Field(default=100, ge=1, le=MAX_RESULT_ROWS)
    rationale: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def validate_operation(self) -> "AnalysisPlan":
        if self.operation == "select" and (self.group_by or self.metrics):
            raise ValueError("select plan cannot include group_by or metrics")
        if self.operation == "aggregate" and not self.metrics:
            raise ValueError("aggregate plan requires at least one metric")
        aliases = [metric.alias for metric in self.metrics]
        if len(aliases) != len(set(aliases)):
            raise ValueError("metric aliases must be unique")
        return self


class QueryProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: Literal["duckdb"] = "duckdb"
    sql: str
    parameter_count: int = Field(ge=0)
    table: Literal["uploaded_data"] = ANALYSIS_TABLE


class ExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["decisionops-execution-result-v1"] = (
        "decisionops-execution-result-v1"
    )
    dataset: DatasetManifest
    plan: AnalysisPlan
    input_row_count: int = Field(ge=0)
    denominator_row_count: int = Field(ge=0)
    output_row_count: int = Field(ge=0)
    columns: list[str]
    rows: list[dict[str, Any]]
    provenance: QueryProvenance
    numeric_source_of_truth: Literal["duckdb"] = "duckdb"
    storage: Literal["not_persisted"] = "not_persisted"


@dataclass(frozen=True)
class MaterializedDataset:
    """Request-scoped rows selected through the validated DuckDB boundary."""

    frame: pd.DataFrame
    provenance: QueryProvenance


def _validate_finite_values(value: Scalar | list[Scalar]) -> None:
    values = value if isinstance(value, list) else [value]
    for item in values:
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("filter values must be finite")


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _column_lookup(manifest: DatasetManifest) -> dict[str, ColumnManifest]:
    return {column.name: column for column in manifest.columns}


def _require_columns(names: list[str], lookup: dict[str, ColumnManifest]) -> None:
    missing = [name for name in names if name not in lookup]
    if missing:
        raise AnalysisContractError("unknown dataset columns: " + ", ".join(missing))


def _escape_contains(value: Scalar) -> str:
    if not isinstance(value, str):
        raise AnalysisContractError("contains filter requires a string value")
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _compile_filter(item: FilterClause) -> tuple[str, list[Scalar]]:
    column = _quote_identifier(item.column)
    operators = {"eq": "=", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
    if item.operator in operators:
        return f"{column} {operators[item.operator]} ?", [item.value]  # type: ignore[list-item]
    if item.operator == "contains":
        return f"CAST({column} AS VARCHAR) ILIKE ? ESCAPE '\\'", [_escape_contains(item.value)]
    if item.operator == "in":
        values = item.value if isinstance(item.value, list) else []
        return f"{column} IN ({', '.join('?' for _ in values)})", values
    if item.operator == "is_null":
        return f"{column} IS NULL", []
    return f"{column} IS NOT NULL", []


def _compile_where(filters: list[FilterClause]) -> tuple[str, list[Scalar]]:
    if not filters:
        return "", []
    clauses: list[str] = []
    parameters: list[Scalar] = []
    for item in filters:
        sql, values = _compile_filter(item)
        clauses.append(sql)
        parameters.extend(values)
    return " WHERE " + " AND ".join(clauses), parameters


def _metric_sql(metric: MetricSpec, lookup: dict[str, ColumnManifest]) -> str:
    alias = _quote_identifier(metric.alias)
    if metric.operation == "count" and metric.column is None:
        return f"COUNT(*) AS {alias}"
    if metric.operation == "share" and metric.column is None:
        return (
            "ROUND(COUNT(*) * 100.0 / "
            f"NULLIF(SUM(COUNT(*)) OVER (), 0), 2) AS {alias}"
        )
    assert metric.column is not None
    column = lookup[metric.column]
    if metric.operation in {"sum", "mean", "median", "stddev", "correlation"} and not column.numeric:
        raise AnalysisContractError(f"{metric.operation} requires a numeric column: {column.name}")
    if metric.operation == "correlation":
        assert metric.secondary_column is not None
        secondary = lookup[metric.secondary_column]
        if not secondary.numeric:
            raise AnalysisContractError(
                f"correlation requires a numeric column: {secondary.name}"
            )
        return (
            f"CORR({_quote_identifier(column.name)}, "
            f"{_quote_identifier(secondary.name)}) AS {alias}"
        )
    function = {
        "count": "COUNT",
        "count_distinct": "COUNT(DISTINCT",
        "sum": "SUM",
        "mean": "AVG",
        "median": "MEDIAN",
        "stddev": "STDDEV_SAMP",
        "min": "MIN",
        "max": "MAX",
    }[metric.operation]
    expression = f"{function}({_quote_identifier(column.name)})"
    if metric.operation == "count_distinct":
        expression = f"COUNT(DISTINCT {_quote_identifier(column.name)})"
    return f"{expression} AS {alias}"


def _compile_select(plan: AnalysisPlan, lookup: dict[str, ColumnManifest]) -> tuple[str, list[str]]:
    names = plan.select_columns or list(lookup)
    _require_columns(names, lookup)
    selected = ", ".join(_quote_identifier(name) for name in names)
    return selected, names


def _compile_aggregate(plan: AnalysisPlan, lookup: dict[str, ColumnManifest]) -> tuple[str, list[str]]:
    _require_columns(plan.group_by, lookup)
    metric_columns = [
        column
        for metric in plan.metrics
        for column in (metric.column, metric.secondary_column)
        if column is not None
    ]
    _require_columns(metric_columns, lookup)
    if set(plan.group_by).intersection(metric.alias for metric in plan.metrics):
        raise AnalysisContractError("metric aliases cannot duplicate group_by columns")
    parts = [_quote_identifier(name) for name in plan.group_by]
    parts.extend(_metric_sql(metric, lookup) for metric in plan.metrics)
    return ", ".join(parts), plan.group_by + [metric.alias for metric in plan.metrics]


def _compile_order(plan: AnalysisPlan, result_columns: list[str]) -> str:
    requested = [item.column for item in plan.order_by]
    invalid = [column for column in requested if column not in result_columns]
    if invalid:
        raise AnalysisContractError("order_by columns are not in the result: " + ", ".join(invalid))
    if plan.operation == "aggregate":
        tie_breakers = plan.group_by
    else:
        tie_breakers = result_columns
    parts = [
        f"{_quote_identifier(item.column)} {item.direction.upper()}"
        for item in plan.order_by
    ]
    parts.extend(
        f"{_quote_identifier(column)} ASC"
        for column in tie_breakers
        if column not in requested
    )
    if not parts:
        return ""
    return " ORDER BY " + ", ".join(parts)


def compile_plan(plan: AnalysisPlan, manifest: DatasetManifest) -> tuple[str, list[Scalar]]:
    """Compile a validated plan into read-only parameterized DuckDB SQL."""

    lookup = _column_lookup(manifest)
    _require_columns([item.column for item in plan.filters], lookup)
    where_sql, parameters = _compile_where(plan.filters)
    if plan.operation == "select":
        selected, result_columns = _compile_select(plan, lookup)
        group_sql = ""
    else:
        selected, result_columns = _compile_aggregate(plan, lookup)
        group_sql = (
            " GROUP BY " + ", ".join(_quote_identifier(name) for name in plan.group_by)
            if plan.group_by
            else ""
        )
    order_sql = _compile_order(plan, result_columns)
    sql = (
        f"SELECT {selected} FROM {_quote_identifier(ANALYSIS_TABLE)}"
        f"{where_sql}{group_sql}{order_sql} LIMIT {plan.limit}"
    )
    return sql, parameters


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp) and value.tzinfo is not None:
        return value.tz_convert("UTC").isoformat()
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return _json_value(value.item())
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {str(column): _json_value(value) for column, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def execute_plan(
    dataset: LoadedDataset,
    manifest: DatasetManifest,
    plan: AnalysisPlan,
) -> ExecutionResult:
    """Execute one read-only plan and return JSON-safe evidence."""

    if manifest.fingerprint_sha256 != dataset.fingerprint_sha256:
        raise AnalysisContractError("dataset fingerprint does not match the manifest")
    if manifest.row_count != len(dataset.frame):
        raise AnalysisContractError("dataset row count does not match the manifest")
    sql, parameters = compile_plan(plan, manifest)
    where_sql, where_parameters = _compile_where(plan.filters)
    connection = duckdb.connect(database=":memory:")
    try:
        connection.register(ANALYSIS_TABLE, dataset.frame)
        denominator = connection.execute(
            f"SELECT COUNT(*) FROM {_quote_identifier(ANALYSIS_TABLE)}{where_sql}",
            where_parameters,
        ).fetchone()[0]
        result_frame = connection.execute(sql, parameters).fetchdf()
    except duckdb.Error as exc:
        raise AnalysisContractError(f"DuckDB could not execute the validated plan: {exc}") from exc
    finally:
        connection.close()
    return ExecutionResult(
        dataset=manifest,
        plan=plan,
        input_row_count=len(dataset.frame),
        denominator_row_count=int(denominator),
        output_row_count=len(result_frame),
        columns=[str(column) for column in result_frame.columns],
        rows=_rows(result_frame),
        provenance=QueryProvenance(sql=sql, parameter_count=len(parameters)),
    )


def materialize_filtered_frame(
    dataset: LoadedDataset,
    manifest: DatasetManifest,
    *,
    columns: list[str] | None = None,
    filters: list[FilterClause] | None = None,
) -> MaterializedDataset:
    """Materialize validated rows for non-SQL statistics without losing lineage.

    DuckDB remains the source of truth for column selection and filtering.  The
    returned frame is request-scoped and includes a zero-based source-row id so
    downstream statistical and ML results can point back to the uploaded rows.
    """

    if manifest.fingerprint_sha256 != dataset.fingerprint_sha256:
        raise AnalysisContractError("dataset fingerprint does not match the manifest")
    if manifest.row_count != len(dataset.frame):
        raise AnalysisContractError("dataset row count does not match the manifest")
    if SOURCE_ROW_COLUMN in dataset.frame.columns:
        raise AnalysisContractError(
            f"dataset column name is reserved for provenance: {SOURCE_ROW_COLUMN}"
        )
    lookup = _column_lookup(manifest)
    selected_columns = columns or list(lookup)
    active_filters = filters or []
    _require_columns(selected_columns, lookup)
    _require_columns([item.column for item in active_filters], lookup)
    where_sql, parameters = _compile_where(active_filters)
    selected_sql = ", ".join(_quote_identifier(name) for name in selected_columns)
    sql = (
        f"SELECT {_quote_identifier(SOURCE_ROW_COLUMN)}, {selected_sql} FROM ("
        f"SELECT ROW_NUMBER() OVER () - 1 AS {_quote_identifier(SOURCE_ROW_COLUMN)}, * "
        f"FROM {_quote_identifier(ANALYSIS_TABLE)}"
        f") AS {_quote_identifier('source_rows')}{where_sql} "
        f"ORDER BY {_quote_identifier(SOURCE_ROW_COLUMN)} ASC"
    )
    connection = duckdb.connect(database=":memory:")
    try:
        connection.register(ANALYSIS_TABLE, dataset.frame)
        frame = connection.execute(sql, parameters).fetchdf()
    except duckdb.Error as exc:
        raise AnalysisContractError(
            f"DuckDB could not materialize validated rows: {exc}"
        ) from exc
    finally:
        connection.close()
    return MaterializedDataset(
        frame=frame,
        provenance=QueryProvenance(sql=sql, parameter_count=len(parameters)),
    )


def analyze_with_plan(
    filename: str,
    data_format: str,
    content: str,
    plan: AnalysisPlan,
    content_encoding: str = "utf-8",
) -> ExecutionResult:
    """Parse, manifest, and execute one dataset without persistent storage."""

    dataset = load_dataset(filename, data_format, content, content_encoding)
    manifest = DatasetManifest.from_profile(profile_dataset(dataset))
    return execute_plan(dataset, manifest, plan)
