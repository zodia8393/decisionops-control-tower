from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.data_analysis import DatasetAnalysisError, analyze_dataset


def test_csv_profile_counts_rows_columns_missing_and_numeric_stats():
    payload = analyze_dataset(
        "stations.csv",
        "csv",
        "station,bikes,risk\n시청역,2,0.9\n서울역,,0.8\n",
    )

    bikes = next(item for item in payload["columns"] if item["name"] == "bikes")
    assert payload["row_count"] == 2
    assert payload["column_count"] == 3
    assert payload["missing_cell_count"] == 1
    assert payload["storage"] == "not_persisted"
    assert bikes["missing_count"] == 1
    assert bikes["numeric"]["mean"] == 2


def test_json_profile_accepts_data_record_list():
    payload = analyze_dataset(
        "stations.json",
        "json",
        '{"data":[{"station":"시청역","bikes":2},{"station":"서울역","bikes":4}]}',
    )

    assert payload["row_count"] == 2
    assert payload["numeric_column_count"] == 1


def test_dataset_rejects_credential_like_columns():
    with pytest.raises(DatasetAnalysisError, match="credential columns"):
        analyze_dataset("unsafe.csv", "csv", "station,api_key\n시청역,do-not-store\n")

    with pytest.raises(DatasetAnalysisError, match="credential columns"):
        analyze_dataset("unsafe.csv", "csv", "station,주민등록번호\n시청역,000000-0000000\n")

    with pytest.raises(DatasetAnalysisError, match="credential columns"):
        analyze_dataset("unsafe.csv", "csv", "station,national-id\n시청역,private-id\n")


def test_dataset_rejects_invalid_or_mismatched_input():
    with pytest.raises(DatasetAnalysisError, match="extension"):
        analyze_dataset("stations.json", "csv", "station,bikes\n시청역,2\n")

    with pytest.raises(DatasetAnalysisError, match="JSON content is invalid"):
        analyze_dataset("stations.json", "json", "not-json")

    with pytest.raises(DatasetAnalysisError, match="nested JSON"):
        analyze_dataset("stations.json", "json", '[{"station":{"name":"시청역"}}]')


def test_dataset_rejects_more_than_row_limit():
    content = "value\n" + "\n".join(str(index) for index in range(10_001))

    with pytest.raises(DatasetAnalysisError, match="row limit"):
        analyze_dataset("large.csv", "csv", content)


def test_dataset_rejects_pathological_column_name_and_deep_json():
    long_column = "x" * 121
    with pytest.raises(DatasetAnalysisError, match="column names"):
        analyze_dataset("wide.csv", "csv", f"{long_column}\nvalue\n")

    deeply_nested = "[" * 1_100 + "0" + "]" * 1_100
    with pytest.raises(DatasetAnalysisError):
        analyze_dataset("deep.json", "json", deeply_nested)
