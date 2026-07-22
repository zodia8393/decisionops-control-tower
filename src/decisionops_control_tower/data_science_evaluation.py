"""Versioned golden evaluation with independent statistical and metric oracles."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import (
    balanced_accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from decisionops_control_tower.advanced_analytics import (
    AdvancedAnalysisPlan,
    AdvancedAnalysisResult,
    execute_advanced_plan,
)
from decisionops_control_tower.analysis_engine import AnalysisContractError, DatasetManifest
from decisionops_control_tower.data_analysis import load_dataset, profile_dataset
from decisionops_control_tower.data_science_planner import plan_data_science
from decisionops_control_tower.prediction_engine import (
    PredictionPlan,
    PredictionResult,
    execute_prediction_plan,
)


MIN_DATA_SCIENCE_CASES = 20


def load_data_science_cases(path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    datasets = payload.get("datasets") if isinstance(payload, dict) else None
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(datasets, dict) or not datasets:
        raise ValueError("data-science golden set requires datasets")
    if not isinstance(cases, list) or len(cases) < MIN_DATA_SCIENCE_CASES:
        raise ValueError(
            f"data-science golden set must contain at least {MIN_DATA_SCIENCE_CASES} cases"
        )
    identifiers: set[str] = set()
    for case in cases:
        required = {"id", "dataset_id", "question", "expected_status"}
        if not isinstance(case, dict) or not required.issubset(case):
            raise ValueError(f"every data-science case requires {sorted(required)}")
        identifier = str(case["id"])
        if identifier in identifiers:
            raise ValueError(f"duplicate data-science case id: {identifier}")
        if case["dataset_id"] not in datasets:
            raise ValueError(f"unknown dataset_id: {case['dataset_id']}")
        identifiers.add(identifier)
    return datasets, cases


def data_science_set_identity(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    version = payload.get("version") if isinstance(payload, dict) else None
    if not isinstance(version, str) or not version.strip():
        raise ValueError("data-science golden set requires a non-empty version")
    return {
        "golden_set_version": version,
        "golden_set_sha256": hashlib.sha256(raw).hexdigest(),
    }


def _generated_frame(spec: dict[str, Any]) -> pd.DataFrame:
    kind = str(spec["kind"])
    rows = int(spec.get("rows", 0))
    seed = int(spec.get("seed", 42))
    rng = np.random.default_rng(seed)
    if kind == "regression_signal":
        x = np.linspace(0, 20, rows)
        return pd.DataFrame(
            {
                "row_id": np.arange(rows),
                "x": x,
                "category": np.where(np.arange(rows) % 2, "A", "B"),
                "y": 5.0 * x + rng.normal(0, 0.4, rows),
            }
        )
    if kind == "classification_signal":
        x = rng.normal(size=rows)
        return pd.DataFrame(
            {"x": x, "noise": rng.normal(size=rows), "label": np.where(x > 0, "yes", "no")}
        )
    if kind == "forecast_signal":
        positions = np.arange(rows)
        return pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=rows, freq="D"),
                "value": 20 + positions * 0.5 + np.sin(positions / 4),
            }
        )
    if kind == "random_target":
        return pd.DataFrame({"x": rng.normal(size=rows), "y": rng.normal(size=rows)})
    if kind == "small":
        return pd.DataFrame({"x": np.arange(rows), "y": np.arange(rows) * 2})
    if kind == "constant":
        return pd.DataFrame({"x": np.arange(rows), "y": np.ones(rows)})
    if kind == "leak":
        target = np.arange(rows) * 2
        return pd.DataFrame({"x": np.arange(rows), "leaked": target, "y": target})
    if kind == "imbalanced":
        minority = 10
        return pd.DataFrame(
            {
                "x": rng.normal(size=rows),
                "label": ["minority"] * minority + ["majority"] * (rows - minority),
            }
        )
    raise ValueError(f"unsupported generated dataset kind: {kind}")


def _dataset_from_spec(identifier: str, spec: dict[str, Any]):
    if spec.get("kind") == "csv":
        content = str(spec["content"])
        filename = str(spec.get("filename", f"{identifier}.csv"))
    else:
        content = _generated_frame(spec).to_csv(index=False)
        filename = f"{identifier}.csv"
    dataset = load_dataset(filename, "csv", content)
    return dataset, DatasetManifest.from_profile(profile_dataset(dataset))


def _subset_match(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _subset_match(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _subset_match(left, right) for left, right in zip(actual, expected, strict=True)
        )
    return actual == expected


def _filtered(frame: pd.DataFrame, plan: AdvancedAnalysisPlan) -> pd.DataFrame:
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
        elif item.operator == "in":
            current = series.isin(item.value)
        elif item.operator == "contains":
            current = series.astype("string").str.contains(str(item.value), case=False, regex=False)
        elif item.operator == "is_null":
            current = series.isna()
        else:
            current = series.notna()
        mask &= current.fillna(False)
    return frame.loc[mask].copy()


def _close(left: Any, right: Any, tolerance: float = 1e-8) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return bool(np.isclose(float(left), float(right), rtol=tolerance, atol=tolerance))


def _advanced_oracle(frame: pd.DataFrame, result: AdvancedAnalysisResult) -> bool:
    plan = result.plan
    filtered = _filtered(frame, plan)
    if result.denominator_row_count != len(filtered):
        return False
    if plan.operation in {"distribution", "outliers"}:
        values = pd.to_numeric(filtered[plan.columns[0]], errors="coerce").dropna().astype(float)
        if result.valid_row_count != len(values):
            return False
        q1, median, q3 = values.quantile([0.25, 0.5, 0.75]).tolist()
        if plan.operation == "distribution":
            return all(
                [
                    _close(result.statistics["mean"], values.mean()),
                    _close(result.statistics["median"], median),
                    _close(result.statistics["stddev"], values.std(ddof=1)),
                    sum(item["count"] for item in result.chart.data) == len(values),
                ]
            )
        iqr = q3 - q1
        lower, upper = q1 - plan.iqr_multiplier * iqr, q3 + plan.iqr_multiplier * iqr
        count = int(((values < lower) | (values > upper)).sum())
        return all(
            [
                _close(result.statistics["lower_bound"], lower),
                _close(result.statistics["upper_bound"], upper),
                result.statistics["outlier_count"] == count,
            ]
        )
    if plan.operation == "relationship":
        pair = filtered[plan.columns].apply(pd.to_numeric, errors="coerce").dropna()
        pearson = stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
        spearman = stats.spearmanr(pair.iloc[:, 0], pair.iloc[:, 1])
        return all(
            [
                result.valid_row_count == len(pair),
                _close(result.statistics["pearson_r"], pearson.statistic),
                _close(result.statistics["pearson_p_value"], pearson.pvalue),
                _close(result.statistics["spearman_rho"], spearman.statistic),
            ]
        )
    if plan.operation == "group_comparison":
        assert plan.group_by is not None
        valid = filtered[[plan.group_by, plan.columns[0]]].dropna()
        groups = [group[plan.columns[0]].astype(float) for _, group in valid.groupby(plan.group_by, sort=True)]
        test_name = result.statistics["test"]
        if test_name == "welch_t_test":
            test = stats.ttest_ind(groups[0], groups[1], equal_var=False)
        elif test_name == "mann_whitney_u":
            test = stats.mannwhitneyu(groups[0], groups[1], alternative="two-sided")
        elif test_name == "one_way_anova":
            test = stats.f_oneway(*groups)
        else:
            test = stats.kruskal(*groups)
        return all(
            [
                result.valid_row_count == len(valid),
                _close(result.statistics["statistic"], test.statistic),
                _close(result.statistics["p_value"], test.pvalue),
                [row["count"] for row in result.rows] == [len(group) for group in groups],
            ]
        )
    assert plan.time_column is not None
    valid = filtered[[plan.time_column, plan.columns[0]]].copy()
    valid[plan.time_column] = pd.to_datetime(valid[plan.time_column], errors="coerce", utc=True)
    valid[plan.columns[0]] = pd.to_numeric(valid[plan.columns[0]], errors="coerce")
    valid = valid.dropna().sort_values(plan.time_column)
    frequency = {"daily": "D", "weekly": "W", "monthly": "MS"}.get(plan.frequency)
    if frequency:
        series = valid.set_index(plan.time_column)[plan.columns[0]].resample(frequency).agg(plan.aggregation).dropna()
    else:
        series = valid.groupby(plan.time_column)[plan.columns[0]].agg(plan.aggregation)
    trend = stats.linregress(np.arange(len(series)), series.to_numpy(dtype=float))
    return all(
        [
            result.valid_row_count == len(valid),
            result.statistics["period_count"] == len(series),
            _close(result.statistics["mean"], series.mean()),
            _close(result.statistics["trend_slope_per_period"], trend.slope),
        ]
    )


def _prediction_oracle(result: PredictionResult) -> bool:
    primary = "mae" if result.plan.task in {"regression", "forecasting"} else "macro_f1"
    baseline_value = float(result.baseline["validation_metrics"][primary])
    candidate_values = [float(item["validation_metrics"][primary]) for item in result.candidates]
    best = min(candidate_values) if primary == "mae" else max(candidate_values)
    gain = best < baseline_value - max(abs(baseline_value) * 0.01, 1e-12) if primary == "mae" else best > baseline_value + max(abs(baseline_value) * 0.01, 0.001)
    if (result.status == "MODEL_READY") != gain:
        return False
    split = result.split_evidence
    if sum(int(split[key]) for key in ("train_rows", "validation_rows", "test_rows")) <= 0:
        return False
    if result.status == "NO_MODEL_GAIN":
        return result.selected_model is None and result.test_metrics is None
    test_rows = [row for row in result.predictions if row.get("actual") is not None]
    if len(test_rows) != int(split["test_rows"]):
        return False
    actual = pd.Series([row["actual"] for row in test_rows])
    predicted = np.asarray([row["predicted"] for row in test_rows])
    if result.plan.task in {"regression", "forecasting"}:
        metrics = {
            "mae": mean_absolute_error(actual.astype(float), predicted.astype(float)),
            "rmse": math.sqrt(mean_squared_error(actual.astype(float), predicted.astype(float))),
        }
        if result.plan.task == "regression":
            metrics["r2"] = r2_score(actual.astype(float), predicted.astype(float))
    else:
        metrics = {
            "macro_f1": f1_score(actual, predicted, average="macro", zero_division=0),
            "balanced_accuracy": balanced_accuracy_score(actual, predicted),
        }
    metric_match = all(_close(result.test_metrics[key], value) for key, value in metrics.items())
    explanation_ok = bool(
        result.bounded_shap
        and result.bounded_shap.get("method") == "bounded_permutation_shapley"
        and result.feature_importance
    )
    horizon_ok = True
    if result.plan.task == "forecasting":
        future = [row for row in result.predictions if row.get("actual") is None]
        horizon_ok = len(future) == result.plan.horizon and split.get("shuffled") is False
    return metric_match and explanation_ok and horizon_ok


def evaluate_data_science_cases(
    datasets: dict[str, dict[str, Any]], cases: list[dict[str, Any]]
) -> dict[str, Any]:
    contexts = {identifier: _dataset_from_spec(identifier, spec) for identifier, spec in datasets.items()}
    rows: list[dict[str, Any]] = []
    for case in cases:
        dataset, manifest = contexts[case["dataset_id"]]
        previous = (
            PredictionPlan.model_validate(case["previous_prediction_plan"])
            if case.get("previous_prediction_plan")
            else None
        )
        outcome = plan_data_science(
            str(case["question"]), manifest, dataset.frame, previous_prediction_plan=previous
        )
        status_pass = outcome.status == case["expected_status"]
        mode_pass = case.get("expected_mode") in {None, outcome.mode}
        plan = outcome.advanced_plan or outcome.prediction_plan
        schema_valid = True
        if outcome.advanced_plan is not None:
            schema_valid = AdvancedAnalysisPlan.model_validate(
                outcome.advanced_plan.model_dump()
            ) == outcome.advanced_plan
        if outcome.prediction_plan is not None:
            schema_valid = PredictionPlan.model_validate(
                outcome.prediction_plan.model_dump()
            ) == outcome.prediction_plan
        plan_pass = _subset_match(plan.model_dump(mode="json"), case.get("expected_plan", {})) if plan else not case.get("expected_plan")
        oracle_pass = case["expected_status"] != "planned"
        gate_pass = case.get("expected_error") is None
        result_status = None
        error = None
        if outcome.status == "planned" and plan is not None:
            try:
                if outcome.advanced_plan is not None:
                    result = execute_advanced_plan(dataset, manifest, outcome.advanced_plan)
                    oracle_pass = _advanced_oracle(dataset.frame, result)
                else:
                    assert outcome.prediction_plan is not None
                    result = execute_prediction_plan(dataset, manifest, outcome.prediction_plan)
                    result_status = result.status
                    oracle_pass = _prediction_oracle(result)
                    expected_excluded = case.get("expected_excluded_feature")
                    if expected_excluded:
                        gate_pass = expected_excluded in result.model_card.features_excluded
                if case.get("expected_error"):
                    gate_pass = False
                if case.get("expected_result_status"):
                    gate_pass = gate_pass and result_status == case["expected_result_status"]
            except AnalysisContractError as exc:
                error = str(exc)
                expected_error = case.get("expected_error")
                gate_pass = bool(expected_error and str(expected_error) in error)
                oracle_pass = gate_pass
        passed = status_pass and mode_pass and schema_valid and plan_pass and oracle_pass and gate_pass
        rows.append(
            {
                "id": case["id"],
                "dataset_id": case["dataset_id"],
                "expected_status": case["expected_status"],
                "actual_status": outcome.status,
                "mode": outcome.mode,
                "status_pass": status_pass,
                "mode_pass": mode_pass,
                "plan_schema_valid": schema_valid,
                "plan_semantics_pass": plan_pass,
                "independent_oracle_pass": oracle_pass,
                "safety_gate_pass": gate_pass,
                "result_status": result_status,
                "error": error,
                "passed": passed,
            }
        )
    planned = [row for row in rows if row["expected_status"] == "planned"]
    metrics = {
        "dataset_count": len(datasets),
        "case_count": len(rows),
        "end_to_end_pass_rate": round(mean(row["passed"] for row in rows), 6),
        "plan_schema_validity": round(mean(row["plan_schema_valid"] for row in rows), 6),
        "plan_semantics_accuracy": round(mean(row["plan_semantics_pass"] for row in rows), 6),
        "independent_oracle_match_rate": round(mean(row["independent_oracle_pass"] for row in planned), 6),
        "safety_gate_pass_rate": round(mean(row["safety_gate_pass"] for row in planned), 6),
    }
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "evaluation_contract": "decisionops-data-science-evaluation-v1",
        "oracle": "independent-pandas-scipy-sklearn-metric-recalculation",
        "metrics": metrics,
        "failures": [row for row in rows if not row["passed"]],
        "cases": rows,
    }


def render_data_science_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# Data Science Copilot golden evaluation",
        "",
        f"- generated: `{report['generated_at_utc']}`",
        f"- golden set: `v{report['configuration']['golden_set_version']}` (`sha256:{report['configuration']['golden_set_sha256'][:12]}…`)",
        f"- datasets/cases: **{metrics['dataset_count']} / {metrics['case_count']}**",
        f"- oracle: `{report['oracle']}`",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| End-to-end pass rate | {metrics['end_to_end_pass_rate'] * 100:.1f}% |",
        f"| Typed plan schema validity | {metrics['plan_schema_validity'] * 100:.1f}% |",
        f"| Plan semantics accuracy | {metrics['plan_semantics_accuracy'] * 100:.1f}% |",
        f"| Independent numeric/metric oracle | {metrics['independent_oracle_match_rate'] * 100:.1f}% |",
        f"| Safety gate pass rate | {metrics['safety_gate_pass_rate'] * 100:.1f}% |",
        "",
        "## Failed cases",
        "",
    ]
    if not report["failures"]:
        lines.append("All data-science golden cases passed.")
    else:
        lines.extend(["| ID | Status | Plan | Oracle | Gate |", "|---|---:|---:|---:|---:|"])
        for row in report["failures"]:
            lines.append(
                f"| `{row['id']}` | {row['status_pass']} | {row['plan_semantics_pass']} | "
                f"{row['independent_oracle_pass']} | {row['safety_gate_pass']} |"
            )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "이 평가는 versioned synthetic/fixture data에서 typed plan, 계산 결과, baseline gate를 재현한다. "
            "사용자 평가는 이번 목표에서 제외되어 있으며 이 자동 평가는 실제 업무 usability를 대신하지 않는다.",
            "",
        ]
    )
    return "\n".join(lines)
