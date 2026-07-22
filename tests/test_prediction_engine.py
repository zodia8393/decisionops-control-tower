from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.analysis_engine import AnalysisContractError, DatasetManifest
from decisionops_control_tower.data_analysis import load_dataset, profile_dataset
from decisionops_control_tower.prediction_engine import PredictionPlan, execute_prediction_plan


def loaded(frame: pd.DataFrame, name: str = "model.csv"):
    content = frame.to_csv(index=False)
    dataset = load_dataset(name, "csv", content)
    return dataset, DatasetManifest.from_profile(profile_dataset(dataset))


def test_prediction_contract_forbids_time_inversion_and_target_feature_overlap():
    with pytest.raises(ValidationError, match="forbids random split"):
        PredictionPlan(
            task="forecasting", target="y", time_column="date", split_strategy="random", rationale="invalid time split"
        )
    with pytest.raises(ValidationError, match="target cannot"):
        PredictionPlan(task="regression", target="y", features=["y"], rationale="direct leakage")
    with pytest.raises(ValidationError, match="does not accept exogenous"):
        PredictionPlan(
            task="forecasting", target="y", time_column="date", features=["x"], rationale="unsupported exogenous"
        )


def test_regression_beats_baseline_and_matches_independent_test_mae():
    rng = np.random.default_rng(42)
    x = np.linspace(0, 20, 180)
    frame = pd.DataFrame(
        {
            "row_id": np.arange(180),
            "x": x,
            "category": np.where(np.arange(180) % 2, "A", "B"),
            "y": 5.0 * x + rng.normal(0, 0.4, 180),
        }
    )
    dataset, manifest = loaded(frame)
    plan = PredictionPlan(
        task="regression",
        target="y",
        features=["row_id", "x", "category"],
        model_candidates=["linear"],
        rationale="predict y with bounded regression",
    )

    result = execute_prediction_plan(dataset, manifest, plan)
    actual = np.array([row["actual"] for row in result.predictions], dtype=float)
    predicted = np.array([row["predicted"] for row in result.predictions], dtype=float)

    assert result.status == "MODEL_READY"
    assert result.selected_model == "linear"
    assert result.test_metrics["mae"] == pytest.approx(float(np.mean(np.abs(actual - predicted))))
    assert "row_id" in result.model_card.features_excluded
    assert result.bounded_shap["method"] == "bounded_permutation_shapley"
    assert result.uncertainty["lower" if False else "method"] == "split_conformal_absolute_residual"
    assert len(result.learning_curve) == 3


def test_classification_reports_confusion_matrix_and_macro_f1():
    rng = np.random.default_rng(7)
    x = rng.normal(size=180)
    frame = pd.DataFrame({"x": x, "noise": rng.normal(size=180), "label": np.where(x > 0, "yes", "no")})
    dataset, manifest = loaded(frame, "classify.csv")
    plan = PredictionPlan(
        task="classification",
        target="label",
        features=["x", "noise"],
        model_candidates=["linear"],
        rationale="classify label",
    )

    result = execute_prediction_plan(dataset, manifest, plan)

    assert result.status == "MODEL_READY"
    assert result.test_metrics["macro_f1"] > 0.9
    assert len(result.error_analysis["confusion_matrix"]) == 2
    assert result.chart.chart_type == "confusion_matrix"


def test_small_sample_constant_target_and_direct_leakage_fail_closed():
    small, small_manifest = loaded(pd.DataFrame({"x": range(50), "y": range(50)}))
    with pytest.raises(AnalysisContractError, match="at least 100"):
        execute_prediction_plan(
            small,
            small_manifest,
            PredictionPlan(task="regression", target="y", features=["x"], rationale="too small"),
        )
    constant, constant_manifest = loaded(pd.DataFrame({"x": range(120), "y": [1] * 120}))
    with pytest.raises(AnalysisContractError, match="constant"):
        execute_prediction_plan(
            constant,
            constant_manifest,
            PredictionPlan(task="regression", target="y", features=["x"], rationale="constant target"),
        )
    leak_frame = pd.DataFrame({"x": range(120), "leaked": np.arange(120) * 2, "y": np.arange(120) * 2})
    leaked, leaked_manifest = loaded(leak_frame)
    with pytest.raises(AnalysisContractError, match="target leakage"):
        execute_prediction_plan(
            leaked,
            leaked_manifest,
            PredictionPlan(task="regression", target="y", features=["x", "leaked"], rationale="leak must fail"),
        )


def test_no_model_gain_is_not_promoted():
    rng = np.random.default_rng(11)
    frame = pd.DataFrame({"x": rng.normal(size=180), "y": rng.normal(size=180)})
    dataset, manifest = loaded(frame)
    result = execute_prediction_plan(
        dataset,
        manifest,
        PredictionPlan(
            task="regression", target="y", features=["x"], model_candidates=["linear"], rationale="random target"
        ),
    )

    assert result.status == "NO_MODEL_GAIN"
    assert result.selected_model is None
    assert result.test_metrics is None
    assert any("baseline" in warning for warning in result.warnings)


def test_forecast_uses_chronological_split_rolling_validation_and_horizon():
    dates = pd.date_range("2025-01-01", periods=140, freq="D")
    values = 20 + np.arange(140) * 0.5 + np.sin(np.arange(140) / 4)
    dataset, manifest = loaded(pd.DataFrame({"date": dates, "value": values}), "forecast.csv")
    plan = PredictionPlan(
        task="forecasting",
        target="value",
        time_column="date",
        horizon=5,
        model_candidates=["linear"],
        rationale="forecast value safely",
    )

    result = execute_prediction_plan(dataset, manifest, plan)

    assert result.split_evidence["strategy"] == "chronological"
    assert result.split_evidence["shuffled"] is False
    assert len(result.split_evidence["rolling_origin_validation"]) == 3
    assert result.status == "MODEL_READY"
    assert len([row for row in result.predictions if "actual" not in row]) == 5
    assert result.chart.chart_type == "forecast"


def test_high_cardinality_category_is_excluded_before_one_hot_expansion():
    rows = 180
    frame = pd.DataFrame(
        {
            "category": [f"category-{index}" for index in range(rows - 30)] + ["shared"] * 30,
            "x": np.arange(rows, dtype=float),
            "y": np.arange(rows, dtype=float) * 2,
        }
    )
    dataset, manifest = loaded(frame, "high-cardinality.csv")
    result = execute_prediction_plan(
        dataset,
        manifest,
        PredictionPlan(
            task="regression",
            target="y",
            features=["category", "x"],
            model_candidates=["linear"],
            rationale="exclude unsafe one-hot expansion",
        ),
    )

    assert "category" in result.model_card.features_excluded
    assert any("고카디널리티" in warning for warning in result.warnings)


def test_chronological_split_keeps_duplicate_timestamps_in_one_partition():
    rows = 160
    frame = pd.DataFrame(
        {
            "date": np.repeat(pd.date_range("2026-01-01", periods=80, freq="D"), 2),
            "x": np.arange(rows, dtype=float),
            "y": np.arange(rows, dtype=float) * 2,
        }
    )
    dataset, manifest = loaded(frame, "chronological.csv")
    result = execute_prediction_plan(
        dataset,
        manifest,
        PredictionPlan(
            task="regression",
            target="y",
            features=["x"],
            time_column="date",
            split_strategy="chronological",
            model_candidates=["linear"],
            rationale="do not split equal timestamps across partitions",
        ),
    )

    assert result.split_evidence["train_end"] < result.split_evidence["validation_start"]
    assert result.split_evidence["validation_end"] < result.split_evidence["test_start"]
