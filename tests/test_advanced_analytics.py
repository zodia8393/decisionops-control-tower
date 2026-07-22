from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.advanced_analytics import (
    AdvancedAnalysisPlan,
    execute_advanced_plan,
)
from decisionops_control_tower.analysis_engine import AnalysisContractError, DatasetManifest
from decisionops_control_tower.data_analysis import load_dataset, profile_dataset


CSV = """date,group,x,y
2026-01-01,A,1,2
2026-01-02,A,2,4
2026-01-03,A,3,5
2026-01-04,B,4,8
2026-01-05,B,5,11
2026-01-06,B,6,12
2026-01-07,B,100,20
"""


def subject():
    dataset = load_dataset("advanced.csv", "csv", CSV)
    return dataset, DatasetManifest.from_profile(profile_dataset(dataset))


def run(plan: dict):
    dataset, manifest = subject()
    return execute_advanced_plan(dataset, manifest, AdvancedAnalysisPlan.model_validate(plan))


def test_contract_rejects_ambiguous_shapes_and_extra_fields():
    with pytest.raises(ValidationError, match="requires exactly 2"):
        AdvancedAnalysisPlan.model_validate(
            {"operation": "relationship", "columns": ["x"], "rationale": "bad relationship"}
        )
    with pytest.raises(ValidationError, match="requires group_by"):
        AdvancedAnalysisPlan.model_validate(
            {"operation": "group_comparison", "columns": ["x"], "rationale": "missing group"}
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        AdvancedAnalysisPlan.model_validate(
            {"operation": "distribution", "columns": ["x"], "rationale": "closed plan", "sql": "DROP TABLE x"}
        )


def test_distribution_matches_independent_numpy_scipy_oracle():
    result = run(
        {"operation": "distribution", "columns": ["x"], "bins": 5, "rationale": "profile x distribution"}
    )
    values = pd.read_csv(pd.io.common.StringIO(CSV))["x"].to_numpy(dtype=float)

    assert result.statistics["mean"] == pytest.approx(float(values.mean()))
    assert result.statistics["median"] == pytest.approx(float(np.median(values)))
    assert result.statistics["skewness"] == pytest.approx(float(stats.skew(values, bias=False)))
    assert sum(item["count"] for item in result.chart.data) == len(values)
    assert result.numeric_source_of_truth == "scipy+pandas"


def test_iqr_outliers_return_source_lineage_and_bounds():
    result = run(
        {"operation": "outliers", "columns": ["x"], "iqr_multiplier": 1.5, "rationale": "find x outliers"}
    )

    assert result.statistics["outlier_count"] == 1
    assert result.rows[0]["__decisionops_source_row__"] == 6
    assert result.rows[0]["x"] == 100


def test_relationship_matches_scipy_and_rejects_constant_input():
    result = run(
        {"operation": "relationship", "columns": ["x", "y"], "rationale": "measure x y relationship"}
    )
    frame = pd.read_csv(pd.io.common.StringIO(CSV))
    expected = stats.pearsonr(frame["x"], frame["y"])

    assert result.statistics["pearson_r"] == pytest.approx(float(expected.statistic))
    assert result.valid_row_count == 7
    constant = load_dataset("constant.csv", "csv", "x,y\n1,2\n1,3\n1,4\n")
    manifest = DatasetManifest.from_profile(profile_dataset(constant))
    plan = AdvancedAnalysisPlan(
        operation="relationship", columns=["x", "y"], rationale="constant must fail"
    )
    with pytest.raises(AnalysisContractError, match="non-constant"):
        execute_advanced_plan(constant, manifest, plan)


def test_group_comparison_reports_test_effect_and_confidence_intervals():
    result = run(
        {
            "operation": "group_comparison",
            "columns": ["y"],
            "group_by": "group",
            "test_method": "parametric",
            "rationale": "compare group means",
        }
    )

    assert result.statistics["test"] == "welch_t_test"
    assert result.statistics["effect_size_name"] == "cohen_d"
    assert result.statistics["p_value"] is not None
    assert [row["group"] for row in result.rows] == ["A", "B"]
    assert all(row["ci_lower"] < row["mean"] < row["ci_upper"] for row in result.rows)


def test_time_series_is_sorted_and_rolling_values_match_pandas_oracle():
    result = run(
        {
            "operation": "time_series",
            "columns": ["y"],
            "time_column": "date",
            "rolling_window": 3,
            "rationale": "explore y over time",
        }
    )
    expected = pd.read_csv(pd.io.common.StringIO(CSV))["y"].rolling(3, min_periods=1).mean()

    assert [row["rolling_value"] for row in result.rows] == pytest.approx(expected.tolist())
    assert result.statistics["period_count"] == 7
    assert result.chart.chart_type == "line"


def test_unknown_and_non_numeric_columns_fail_closed():
    with pytest.raises(AnalysisContractError, match="unknown dataset columns"):
        run({"operation": "distribution", "columns": ["missing"], "rationale": "unknown column"})
    with pytest.raises(AnalysisContractError, match="numeric value columns"):
        run({"operation": "distribution", "columns": ["group"], "rationale": "wrong dtype"})
