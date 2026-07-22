"""Versioned holdout-schema evaluation for the deterministic analysis copilot."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
import pandas as pd

from decisionops_control_tower.analysis_engine import (
    AnalysisPlan,
    DatasetManifest,
    ExecutionResult,
    execute_plan,
)
from decisionops_control_tower.analysis_planner import plan_analysis
from decisionops_control_tower.data_analysis import load_dataset, profile_dataset


MIN_ANALYSIS_CASES = 60


def load_analysis_cases(path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    datasets = payload.get("datasets") if isinstance(payload, dict) else None
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(datasets, dict) or not datasets:
        raise ValueError("analysis golden set requires datasets")
    if not isinstance(cases, list) or len(cases) < MIN_ANALYSIS_CASES:
        raise ValueError(f"analysis golden set must contain at least {MIN_ANALYSIS_CASES} cases")
    identifiers: set[str] = set()
    for case in cases:
        required = {"id", "dataset_id", "question", "expected_status"}
        if not isinstance(case, dict) or not required.issubset(case):
            raise ValueError(f"every analysis case requires {sorted(required)}")
        identifier = str(case["id"])
        if identifier in identifiers:
            raise ValueError(f"duplicate analysis case id: {identifier}")
        if case["dataset_id"] not in datasets:
            raise ValueError(f"unknown dataset_id: {case['dataset_id']}")
        if case["expected_status"] == "planned" and "expected_plan" not in case:
            raise ValueError(f"planned case requires expected_plan: {identifier}")
        if case.get("case_type", "template") not in {"template", "paraphrase", "multiturn"}:
            raise ValueError(f"unsupported analysis case_type: {identifier}")
        if case.get("case_type") == "multiturn" and "previous_plan" not in case:
            raise ValueError(f"multiturn case requires previous_plan: {identifier}")
        identifiers.add(identifier)
    return datasets, cases


def analysis_set_identity(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    version = payload.get("version") if isinstance(payload, dict) else None
    if not isinstance(version, str) or not version.strip():
        raise ValueError("analysis golden set requires a non-empty version")
    return {
        "golden_set_version": version,
        "golden_set_sha256": hashlib.sha256(raw).hexdigest(),
    }


def _apply_filters(frame: pd.DataFrame, plan: AnalysisPlan) -> pd.DataFrame:
    mask = pd.Series(True, index=frame.index)
    for item in plan.filters:
        series = frame[item.column]
        if item.operator == "eq":
            current = series.eq(item.value)
        elif item.operator == "ne":
            current = series.ne(item.value)
        elif item.operator == "gt":
            current = series.gt(item.value)
        elif item.operator == "gte":
            current = series.ge(item.value)
        elif item.operator == "lt":
            current = series.lt(item.value)
        elif item.operator == "lte":
            current = series.le(item.value)
        elif item.operator == "contains":
            current = series.astype("string").str.contains(
                str(item.value), case=False, regex=False, na=False
            )
        elif item.operator == "in":
            current = series.isin(item.value if isinstance(item.value, list) else [])
        elif item.operator == "is_null":
            current = series.isna()
        else:
            current = series.notna()
        mask &= current.fillna(False)
    return frame.loc[mask]


def _aggregate(frame: pd.DataFrame, plan: AnalysisPlan) -> pd.DataFrame:
    if plan.group_by:
        grouped = frame.groupby(plan.group_by, dropna=False, sort=False)
        base = grouped.size().reset_index(name="__group_size__")
        for metric in plan.metrics:
            if metric.operation == "count" and metric.column is None:
                values = grouped.size().reset_index(name=metric.alias)
            elif metric.operation == "correlation":
                assert metric.column is not None and metric.secondary_column is not None
                values = grouped.apply(
                    lambda item: item[metric.column].corr(item[metric.secondary_column]),
                    include_groups=False,
                ).reset_index(name=metric.alias)
            else:
                assert metric.column is not None
                series = grouped[metric.column]
                values = {
                    "count": series.count,
                    "count_distinct": series.nunique,
                    "sum": series.sum,
                    "mean": series.mean,
                    "median": series.median,
                    "stddev": series.std,
                    "min": series.min,
                    "max": series.max,
                }[metric.operation]().reset_index(name=metric.alias)
            base = base.merge(values, on=plan.group_by, how="left", validate="one_to_one")
        return base.drop(columns="__group_size__")
    row: dict[str, Any] = {}
    for metric in plan.metrics:
        if metric.operation == "count" and metric.column is None:
            row[metric.alias] = len(frame)
            continue
        assert metric.column is not None
        series = frame[metric.column]
        if metric.operation == "correlation":
            assert metric.secondary_column is not None
            row[metric.alias] = series.corr(frame[metric.secondary_column])
            continue
        row[metric.alias] = {
            "count": series.count,
            "count_distinct": series.nunique,
            "sum": series.sum,
            "mean": series.mean,
            "median": series.median,
            "stddev": series.std,
            "min": series.min,
            "max": series.max,
        }[metric.operation]()
    return pd.DataFrame([row])


def _pandas_oracle(frame: pd.DataFrame, plan: AnalysisPlan) -> tuple[int, pd.DataFrame]:
    filtered = _apply_filters(frame, plan)
    if plan.operation == "select":
        result = filtered.loc[:, plan.select_columns or list(frame.columns)].copy()
    else:
        result = _aggregate(filtered, plan)
    if plan.order_by:
        requested = [item.column for item in plan.order_by]
        tie_breakers = plan.group_by if plan.operation == "aggregate" else list(result.columns)
        extra = [column for column in tie_breakers if column not in requested]
        result = result.sort_values(
            requested + extra,
            ascending=[item.direction == "asc" for item in plan.order_by] + [True] * len(extra),
            na_position="last",
            kind="mergesort",
        )
    return len(filtered), result.head(plan.limit).reset_index(drop=True)


def _normalized_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return _normalized_value(value.item())
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float):
        return round(value, 8)
    return value


def _normalized_rows(rows: list[dict[str, Any]], *, ordered: bool) -> list[dict[str, Any]]:
    normalized = [
        {str(key): _normalized_value(value) for key, value in row.items()}
        for row in rows
    ]
    if ordered:
        return normalized
    return sorted(normalized, key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True))


def _plan_semantics(plan: AnalysisPlan) -> dict[str, Any]:
    payload = plan.model_dump(mode="json")
    payload.pop("contract_version", None)
    payload.pop("rationale", None)
    return payload


def _numeric_match(
    result: ExecutionResult,
    expected_denominator: int,
    expected: pd.DataFrame,
    *,
    ordered: bool,
) -> bool:
    expected_rows = expected.to_dict(orient="records")
    return all(
        [
            result.denominator_row_count == expected_denominator,
            result.output_row_count == len(expected),
            result.columns == [str(column) for column in expected.columns],
            _normalized_rows(result.rows, ordered=ordered)
            == _normalized_rows(expected_rows, ordered=ordered),
        ]
    )


def evaluate_analysis_cases(
    datasets: dict[str, dict[str, Any]],
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Score plan validity, plan semantics, and DuckDB results against pandas."""

    contexts: dict[str, tuple[Any, DatasetManifest]] = {}
    for identifier, spec in datasets.items():
        dataset = load_dataset(spec["filename"], spec.get("format", "csv"), spec["content"])
        contexts[identifier] = (dataset, DatasetManifest.from_profile(profile_dataset(dataset)))

    rows: list[dict[str, Any]] = []
    for case in cases:
        dataset, manifest = contexts[case["dataset_id"]]
        previous_plan = None
        if "previous_plan" in case:
            previous_plan = AnalysisPlan.model_validate(
                {"rationale": "versioned previous plan", **case["previous_plan"]}
            )
        outcome = plan_analysis(
            str(case["question"]),
            manifest,
            dataset.frame,
            previous_plan,
        )
        expected_status = str(case["expected_status"])
        status_pass = outcome.status == expected_status
        schema_valid = outcome.plan is None
        plan_pass = expected_status != "planned"
        numeric_pass = expected_status != "planned"
        if outcome.plan is not None:
            schema_valid = AnalysisPlan.model_validate(outcome.plan.model_dump()).model_dump() == outcome.plan.model_dump()
        if expected_status == "planned" and outcome.plan is not None:
            expected_plan = AnalysisPlan.model_validate(
                {"rationale": "versioned golden expectation", **case["expected_plan"]}
            )
            plan_pass = _plan_semantics(outcome.plan) == _plan_semantics(expected_plan)
            expected_denominator, expected_frame = _pandas_oracle(dataset.frame, expected_plan)
            result = execute_plan(dataset, manifest, outcome.plan)
            numeric_pass = plan_pass and _numeric_match(
                result,
                expected_denominator,
                expected_frame,
                ordered=bool(expected_plan.order_by),
            )
        passed = status_pass and schema_valid and plan_pass and numeric_pass
        rows.append(
            {
                "id": case["id"],
                "dataset_id": case["dataset_id"],
                "question": case["question"],
                "case_type": case.get("case_type", "template"),
                "expected_status": expected_status,
                "actual_status": outcome.status,
                "status_pass": status_pass,
                "plan_schema_valid": schema_valid,
                "plan_semantics_pass": plan_pass,
                "numeric_execution_pass": numeric_pass,
                "passed": passed,
            }
        )
    planned = [row for row in rows if row["expected_status"] == "planned"]
    paraphrase = [row for row in rows if row["case_type"] == "paraphrase"]
    multiturn = [row for row in rows if row["case_type"] == "multiturn"]
    metrics = {
        "dataset_count": len(datasets),
        "case_count": len(rows),
        "planned_case_count": len(planned),
        "end_to_end_pass_rate": round(mean(row["passed"] for row in rows), 6),
        "planning_accuracy": round(mean(row["status_pass"] and row["plan_semantics_pass"] for row in rows), 6),
        "analysis_plan_schema_validity": round(mean(row["plan_schema_valid"] for row in rows), 6),
        "numeric_execution_correctness": round(mean(row["numeric_execution_pass"] for row in planned), 6),
        "paraphrase_case_count": len(paraphrase),
        "paraphrase_pass_rate": round(mean(row["passed"] for row in paraphrase), 6) if paraphrase else 0.0,
        "multiturn_case_count": len(multiturn),
        "multiturn_pass_rate": round(mean(row["passed"] for row in multiturn), 6) if multiturn else 0.0,
    }
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "evaluation_contract": "decisionops-analysis-evaluation-v2",
        "oracle": "independent-pandas-dataframe-operations",
        "metrics": metrics,
        "failures": [row for row in rows if not row["passed"]],
        "cases": rows,
    }


def render_analysis_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# Decision Intelligence Copilot holdout-schema and conversation challenge",
        "",
        f"- generated: `{report['generated_at_utc']}`",
        f"- golden set: `v{report['configuration']['golden_set_version']}` (`sha256:{report['configuration']['golden_set_sha256'][:12]}…`)",
        f"- datasets/cases: **{metrics['dataset_count']} / {metrics['case_count']}**",
        f"- oracle: `{report['oracle']}`",
        "",
        "## Scorecard",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| End-to-end pass rate | {metrics['end_to_end_pass_rate'] * 100:.1f}% |",
        f"| Planning accuracy | {metrics['planning_accuracy'] * 100:.1f}% |",
        f"| AnalysisPlan schema validity | {metrics['analysis_plan_schema_validity'] * 100:.1f}% |",
        f"| Numeric execution correctness | {metrics['numeric_execution_correctness'] * 100:.1f}% |",
        f"| Paraphrase challenge ({metrics['paraphrase_case_count']} cases) | {metrics['paraphrase_pass_rate'] * 100:.1f}% |",
        f"| Multi-turn plan revision ({metrics['multiturn_case_count']} cases) | {metrics['multiturn_pass_rate'] * 100:.1f}% |",
        "",
        "## Failed cases",
        "",
    ]
    failures = report["failures"]
    if not failures:
        lines.append("All holdout-schema cases passed.")
    else:
        lines.extend(["| ID | Expected | Actual | Plan | Numeric |", "|---|---|---|---:|---:|"])
        for row in failures:
            lines.append(
                f"| `{row['id']}` | {row['expected_status']} | {row['actual_status']} | "
                f"{'pass' if row['plan_semantics_pass'] else 'fail'} | "
                f"{'pass' if row['numeric_execution_pass'] else 'fail'} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "이 평가는 planner에 domain별 컬럼명을 hard-code하지 않은 상태에서 versioned holdout schema, "
            "template과 겹치지 않는 paraphrase, 이전 AnalysisPlan을 수정하는 multi-turn case를 함께 사용한다. "
            "수치는 DuckDB 결과를 별도 pandas 연산 oracle과 비교한다. 문항은 프로젝트 내부에서 설계했으므로 "
            "실제 외부 사용자 usability를 대신하지 않는다.",
            "",
        ]
    )
    return "\n".join(lines)
