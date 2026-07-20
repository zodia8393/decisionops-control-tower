"""Bounded, non-persistent profiling for user-provided CSV and JSON data."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
import re
from typing import Any

import pandas as pd


MAX_CONTENT_BYTES = 1_000_000
MAX_ROWS = 10_000
MAX_COLUMNS = 100
MAX_COLUMN_NAME_LENGTH = 120
SENSITIVE_COLUMN_PATTERN = re.compile(
    r"(^|[_-])(password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|credential|ssn|social[_-]?security|resident[_-]?registration|national[_-]?id|주민등록번호)([_-]|$)",
    re.IGNORECASE,
)


class DatasetAnalysisError(ValueError):
    """Raised when an uploaded dataset violates the public-safe contract."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_filename(filename: str, data_format: str) -> str:
    safe = Path(filename).name.strip() or f"uploaded.{data_format}"
    if len(safe) > 120:
        raise DatasetAnalysisError("filename must be 120 characters or fewer")
    suffix = Path(safe).suffix.lower().lstrip(".")
    if suffix and suffix != data_format:
        raise DatasetAnalysisError("filename extension does not match the declared format")
    return safe


def _parse_json(content: str) -> pd.DataFrame:
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise DatasetAnalysisError("JSON content is invalid") from exc
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        payload = payload["data"]
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise DatasetAnalysisError("JSON must be an object, a list of objects, or an object with a data list")
    if any(
        isinstance(value, (dict, list))
        for item in payload
        for value in item.values()
    ):
        raise DatasetAnalysisError("nested JSON values are not supported; provide flat records")
    return pd.DataFrame(payload)


def _parse_content(content: str, data_format: str) -> pd.DataFrame:
    if not content.strip():
        raise DatasetAnalysisError("dataset content is empty")
    if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
        raise DatasetAnalysisError(f"dataset content exceeds {MAX_CONTENT_BYTES} bytes")
    if data_format == "csv":
        try:
            return pd.read_csv(StringIO(content), nrows=MAX_ROWS + 1)
        except (pd.errors.ParserError, UnicodeError, ValueError) as exc:
            raise DatasetAnalysisError("CSV content could not be parsed") from exc
    if data_format == "json":
        return _parse_json(content)
    raise DatasetAnalysisError("dataset format must be csv or json")


def _validate_shape(frame: pd.DataFrame) -> None:
    if frame.empty:
        raise DatasetAnalysisError("dataset must include at least one data row")
    if len(frame) > MAX_ROWS:
        raise DatasetAnalysisError(f"dataset exceeds the {MAX_ROWS}-row limit")
    if len(frame.columns) > MAX_COLUMNS:
        raise DatasetAnalysisError(f"dataset exceeds the {MAX_COLUMNS}-column limit")
    if len(frame.columns) == 0:
        raise DatasetAnalysisError("dataset must include at least one column")
    long_columns = [str(column) for column in frame.columns if len(str(column)) > MAX_COLUMN_NAME_LENGTH]
    if long_columns:
        raise DatasetAnalysisError(
            f"column names must be {MAX_COLUMN_NAME_LENGTH} characters or fewer"
        )
    sensitive = [str(column) for column in frame.columns if SENSITIVE_COLUMN_PATTERN.search(str(column))]
    if sensitive:
        raise DatasetAnalysisError(
            "potential credential columns are not accepted: " + ", ".join(sensitive[:5])
        )


def _finite_number(value: Any) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else round(number, 6)


def _column_profile(series: pd.Series) -> dict[str, Any]:
    missing_count = int(series.isna().sum())
    profile: dict[str, Any] = {
        "name": str(series.name),
        "dtype": str(series.dtype),
        "missing_count": missing_count,
        "missing_rate": round(missing_count / len(series), 6),
        "unique_count": int(series.nunique(dropna=True)),
    }
    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(series, errors="coerce")
        profile["numeric"] = {
            "min": _finite_number(numeric.min()),
            "max": _finite_number(numeric.max()),
            "mean": _finite_number(numeric.mean()),
            "median": _finite_number(numeric.median()),
        }
    return profile


def analyze_dataset(filename: str, data_format: str, content: str) -> dict[str, Any]:
    """Return a public-safe profile without retaining raw user content."""

    normalized_format = data_format.strip().lower()
    safe_filename = _safe_filename(filename, normalized_format)
    frame = _parse_content(content, normalized_format)
    _validate_shape(frame)
    columns = [_column_profile(frame[column]) for column in frame.columns]
    missing_cells = sum(item["missing_count"] for item in columns)
    numeric_columns = sum("numeric" in item for item in columns)
    fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {
        "contract_version": "decisionops-dataset-profile-v1",
        "filename": safe_filename,
        "format": normalized_format,
        "fingerprint_sha256": fingerprint,
        "generated_at": _utc_now(),
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "numeric_column_count": numeric_columns,
        "missing_cell_count": missing_cells,
        "missing_cell_rate": round(missing_cells / frame.size, 6),
        "columns": columns,
        "storage": "not_persisted",
        "limits": {
            "max_content_bytes": MAX_CONTENT_BYTES,
            "max_rows": MAX_ROWS,
            "max_columns": MAX_COLUMNS,
        },
    }
