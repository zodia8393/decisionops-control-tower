from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.analysis_engine import AnalysisPlan, DatasetManifest
from decisionops_control_tower.data_analysis import load_dataset, profile_dataset
from decisionops_control_tower.data_science_planner import plan_data_science


CONTENT = """date,region,revenue,cost,label
2026-01-01,Seoul,100,60,yes
2026-01-02,Seoul,120,70,yes
2026-01-03,Busan,80,55,no
2026-01-04,Busan,90,58,no
"""


@pytest.fixture
def context():
    dataset = load_dataset("sales.csv", "csv", CONTENT)
    return dataset, DatasetManifest.from_profile(profile_dataset(dataset))


@pytest.mark.parametrize(
    ("question", "operation"),
    [
        ("revenue 히스토그램 보여줘", "distribution"),
        ("revenue IQR 이상치 찾아줘", "outliers"),
        ("revenue와 cost Spearman 관계", "relationship"),
        ("region별 revenue 차이 검정", "group_comparison"),
        ("date 기준 revenue 이동평균 3", "time_series"),
    ],
)
def test_routes_explicit_advanced_intents(context, question, operation):
    dataset, manifest = context
    outcome = plan_data_science(question, manifest, dataset.frame)

    assert outcome.status == "planned"
    assert outcome.mode == "advanced"
    assert outcome.advanced_plan.operation == operation


def test_leaves_basic_sql_analysis_untouched(context):
    dataset, manifest = context

    assert plan_data_science("region별 revenue 합계", manifest, dataset.frame).status == "not_applicable"
    assert plan_data_science("revenue와 cost 상관계수", manifest, dataset.frame).status == "not_applicable"


def test_prediction_requirements_question_does_not_start_model_training(context):
    dataset, manifest = context

    outcome = plan_data_science(
        "매출을 예측하려면 뭐가 필요해?",
        manifest,
        dataset.frame,
    )

    assert outcome.status == "not_applicable"
    assert outcome.message == "dataset capability request"
    assert outcome.prediction_plan is None


def test_builds_regression_classification_and_forecast_plans(context):
    dataset, manifest = context
    regression = plan_data_science("revenue 회귀 모델로 예측", manifest, dataset.frame)
    classification = plan_data_science("label 분류 모델", manifest, dataset.frame)
    forecast = plan_data_science("date 기준 revenue 향후 14일 예측", manifest, dataset.frame)

    assert regression.prediction_plan.task == "regression"
    assert regression.prediction_plan.target == "revenue"
    assert classification.prediction_plan.task == "classification"
    assert classification.prediction_plan.target == "label"
    assert forecast.prediction_plan.task == "forecasting"
    assert forecast.prediction_plan.time_column == "date"
    assert forecast.prediction_plan.horizon == 14


def test_clarifies_missing_columns_and_updates_follow_up(context):
    dataset, manifest = context
    unclear = plan_data_science("이상치 찾아줘", manifest, dataset.frame)
    initial = plan_data_science("date 기준 revenue 향후 7일 예측", manifest, dataset.frame)
    changed = plan_data_science(
        "14일로 바꿔줘",
        manifest,
        dataset.frame,
        previous_prediction_plan=initial.prediction_plan,
    )

    assert unclear.status == "clarification"
    assert changed.prediction_plan.horizon == 14


def test_advanced_follow_up_updates_bins(context):
    dataset, manifest = context
    initial = plan_data_science("revenue 히스토그램 보여줘", manifest, dataset.frame)
    changed = plan_data_science(
        "구간을 20으로 바꿔줘",
        manifest,
        dataset.frame,
        previous_advanced_plan=initial.advanced_plan,
    )

    assert changed.advanced_plan.bins == 20


def test_spearman_follow_up_reuses_columns_from_previous_basic_correlation(context):
    dataset, manifest = context
    previous = AnalysisPlan.model_validate(
        {
            "operation": "aggregate",
            "metrics": [
                {
                    "operation": "correlation",
                    "column": "revenue",
                    "secondary_column": "cost",
                    "alias": "correlation_value",
                }
            ],
            "limit": 1,
            "rationale": "previous Pearson correlation",
        }
    )

    outcome = plan_data_science(
        "상관계수 말고 Spearman으로 봐줘",
        manifest,
        dataset.frame,
        previous_analysis_plan=previous,
    )

    assert outcome.status == "planned"
    assert outcome.advanced_plan.operation == "relationship"
    assert outcome.advanced_plan.columns == ["revenue", "cost"]
