from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.app import create_app


def client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            output_root=tmp_path,
            bike_root=tmp_path / "missing-bike",
            workbench_root=tmp_path / "missing-workbench",
        )
    )


def dataset_payload(frame: pd.DataFrame) -> dict:
    return {
        "filename": "science.csv",
        "format": "csv",
        "content": frame.to_csv(index=False),
        "content_encoding": "utf-8",
    }


def test_chat_routes_advanced_analysis_and_preserves_follow_up_plan(tmp_path):
    api = client(tmp_path)
    frame = pd.DataFrame({"x": np.arange(40), "y": np.arange(40) * 2})
    first = api.post(
        "/api/chat",
        json={"question": "x 히스토그램 보여줘", "dataset": dataset_payload(frame)},
    )

    assert first.status_code == 200
    payload = first.json()
    assert payload["mode"] == "deterministic-advanced-analysis"
    assert payload["advanced_analysis"]["plan"]["operation"] == "distribution"
    assert payload["advanced_analysis"]["provenance"]["engine"] == "duckdb"

    changed = api.post(
        "/api/chat",
        json={
            "question": "구간을 20으로 바꿔줘",
            "dataset": dataset_payload(frame),
            "previous_advanced_plan": payload["advanced_analysis"]["plan"],
        },
    )
    assert changed.status_code == 200
    assert changed.json()["advanced_analysis"]["plan"]["bins"] == 20


def test_chat_prediction_returns_baseline_model_card_and_explanations(tmp_path):
    api = client(tmp_path)
    rng = np.random.default_rng(42)
    x = np.linspace(0, 10, 160)
    frame = pd.DataFrame({"x": x, "y": x * 3 + rng.normal(0, 0.2, len(x))})
    response = api.post(
        "/api/chat",
        json={"question": "y 회귀 모델로 예측", "dataset": dataset_payload(frame)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "deterministic-prediction"
    assert payload["prediction"]["status"] == "MODEL_READY"
    assert payload["prediction"]["baseline"]["model"] == "median_dummy"
    assert payload["prediction"]["model_card"]["test_rows"] > 0
    assert payload["prediction"]["bounded_shap"]["method"] == "bounded_permutation_shapley"


def test_direct_advanced_and_prediction_endpoints_are_typed_and_fail_closed(tmp_path):
    api = client(tmp_path)
    frame = pd.DataFrame({"x": np.arange(20), "y": np.arange(20) * 2})
    advanced = api.post(
        "/api/data/advanced",
        json={
            "dataset": dataset_payload(frame),
            "plan": {
                "operation": "relationship",
                "columns": ["x", "y"],
                "rationale": "direct typed relationship",
            },
        },
    )
    assert advanced.status_code == 200
    assert advanced.json()["statistics"]["pearson_r"] == pytest.approx(1.0)

    too_small = api.post(
        "/api/data/predict",
        json={
            "dataset": dataset_payload(frame),
            "plan": {
                "task": "regression",
                "target": "y",
                "features": ["x"],
                "rationale": "must reject small sample",
            },
        },
    )
    assert too_small.status_code == 422
    assert "at least 100" in too_small.json()["detail"]


def test_basic_analysis_route_still_uses_original_analysis_plan(tmp_path):
    api = client(tmp_path)
    frame = pd.DataFrame({"region": ["A", "A", "B"], "revenue": [10, 20, 5]})
    response = api.post(
        "/api/chat",
        json={"question": "region별 revenue 합계", "dataset": dataset_payload(frame)},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "deterministic-analysis"


def test_capability_guide_recommends_advanced_and_prediction_only_when_safe(tmp_path):
    api = client(tmp_path)
    dates = pd.date_range("2025-01-01", periods=120, freq="D")
    frame = pd.DataFrame(
        {"date": dates, "region": np.where(np.arange(120) % 2, "A", "B"), "x": np.arange(120), "y": np.arange(120) * 2}
    )
    response = api.post(
        "/api/chat",
        json={"question": "가능한 심화 분석과 예측은?", "dataset": dataset_payload(frame)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "deterministic-capabilities"
    assert "히스토그램" in payload["answer"]
    assert "IQR 이상치" in payload["answer"]
    assert "향후 7일 예측" in payload["answer"]
