import base64
from io import BytesIO
from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.data_analysis import (
    DatasetAnalysisError,
    analyze_dataset,
    load_dataset,
)


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
    assert payload["duplicate_row_count"] == 0
    assert payload["duplicate_row_rate"] == 0
    assert bikes["missing_count"] == 1
    assert bikes["numeric"]["count"] == 1
    assert bikes["numeric"]["min"] == 2
    assert bikes["numeric"]["q1"] == 2
    assert bikes["numeric"]["mean"] == 2
    assert bikes["numeric"]["median"] == 2
    assert bikes["numeric"]["q3"] == 2
    assert bikes["numeric"]["max"] == 2
    assert bikes["numeric"]["stddev"] is None

    duplicate = analyze_dataset(
        "duplicates.csv",
        "csv",
        "group,value\nA,1\nA,1\n",
    )
    assert duplicate["duplicate_row_count"] == 1
    assert duplicate["duplicate_row_rate"] == 0.5


def test_json_profile_accepts_data_record_list():
    payload = analyze_dataset(
        "stations.json",
        "json",
        '{"data":[{"station":"시청역","bikes":2},{"station":"서울역","bikes":4}]}',
    )

    assert payload["row_count"] == 2
    assert payload["numeric_column_count"] == 1

    repaired = analyze_dataset(
        "recoverable.json",
        "json",
        '[{"":1," value ":2,"Value":3}]',
    )
    assert [column["name"] for column in repaired["columns"]] == [
        "column_1",
        "value",
        "Value_2",
    ]
    assert repaired["column_name_normalization"]["change_count"] == 3


def test_iso_datetime_column_is_typed_and_profiled():
    payload = analyze_dataset(
        "events.csv",
        "csv",
        "event_date,value\n2026-01-01,10\n2026-01-03,20\n",
    )

    event_date = next(item for item in payload["columns"] if item["name"] == "event_date")
    assert event_date["dtype"].startswith("datetime64")
    assert event_date["temporal"]["min"].startswith("2026-01-01")
    assert event_date["temporal"]["max"].startswith("2026-01-03")


def test_date_only_values_preserve_calendar_midnight_without_timezone_shift():
    dataset = load_dataset(
        "dates.csv",
        "csv",
        "event_date,value\n2026-06-02,1\n2026-06-03,2\n",
    )

    assert str(dataset.frame["event_date"].dtype).startswith("datetime64")
    assert dataset.frame["event_date"].dt.tz is None
    assert dataset.frame["event_date"].dt.hour.tolist() == [0, 0]


def test_dataset_rejects_credential_like_columns():
    with pytest.raises(DatasetAnalysisError, match="credential columns"):
        analyze_dataset("unsafe.csv", "csv", "station,api_key\n시청역,do-not-store\n")

    with pytest.raises(DatasetAnalysisError, match="credential columns"):
        analyze_dataset("unsafe.csv", "csv", "station,주민등록번호\n시청역,000000-0000000\n")

    with pytest.raises(DatasetAnalysisError, match="credential columns"):
        analyze_dataset("unsafe.csv", "csv", "station,national-id\n시청역,private-id\n")

    with pytest.raises(DatasetAnalysisError, match="credential columns"):
        analyze_dataset("unsafe.csv", "csv", "station, API KEY \n시청역,do-not-store\n")

    hidden_after_truncation = "x" * 120 + "_api_key"
    with pytest.raises(DatasetAnalysisError, match="credential columns"):
        analyze_dataset(
            "unsafe.csv",
            "csv",
            f"station,{hidden_after_truncation}\n시청역,do-not-store\n",
        )


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


def test_dataset_repairs_long_column_name_but_rejects_deep_json():
    long_column = "x" * 121
    payload = analyze_dataset("wide.csv", "csv", f"{long_column}\nvalue\n")

    assert payload["columns"][0]["name"] == "x" * 120
    assert payload["column_name_normalization"]["changes"][0]["reasons"] == [
        "truncated"
    ]

    deeply_nested = "[" * 1_100 + "0" + "]" * 1_100
    with pytest.raises(DatasetAnalysisError):
        analyze_dataset("deep.json", "json", deeply_nested)


def test_dataset_repairs_blank_whitespace_placeholder_duplicate_and_case_headers():
    dataset = load_dataset(
        "recoverable.csv",
        "csv",
        ", value ,Value,Unnamed: 3,column_1\nA,1,2,3,4\n",
    )
    profile = analyze_dataset(
        "recoverable.csv",
        "csv",
        ", value ,Value,Unnamed: 3,column_1\nA,1,2,3,4\n",
    )

    assert dataset.frame.columns.tolist() == [
        "column_1",
        "value",
        "Value_2",
        "column_4",
        "column_1_2",
    ]
    assert dataset.frame.iloc[0].tolist() == ["A", 1, 2, 3, 4]
    normalization = profile["column_name_normalization"]
    assert normalization["applied"] is True
    assert normalization["change_count"] == 5
    assert normalization["changes"][0] == {
        "position": 1,
        "original": "",
        "normalized": "column_1",
        "reasons": ["empty"],
    }
    assert normalization["changes"][2]["reasons"] == ["case_collision"]
    assert normalization["changes"][3]["reasons"] == ["placeholder_replaced"]
    assert normalization["changes"][4]["reasons"] == ["duplicate"]

    report = analyze_dataset(
        "daily-report.csv",
        "csv",
        (
            "2024년 01월 요일별 종합배출내역\n"
            "\n"
            "요일,일수,배출량(g),일평균배출량(g),배출횟수,일평균배출횟수\n"
            "월,5,13219184975,2643836995,7520254,1504050\n"
            "합계,31,74589175678,,44820738,\n"
        ),
    )
    assert report["row_count"] == 2
    assert [column["name"] for column in report["columns"]] == [
        "요일",
        "일수",
        "배출량(g)",
        "일평균배출량(g)",
        "배출횟수",
        "일평균배출횟수",
    ]
    assert report["numeric_column_count"] == 5
    assert report["missing_cell_count"] == 2
    assert report["table_structure_normalization"] == {
        "applied": True,
        "header_row": 3,
        "preamble_rows_removed": 2,
        "blank_rows_removed": 0,
        "detected_title": "2024년 01월 요일별 종합배출내역",
    }


@pytest.mark.parametrize("data_format", ["xlsx", "parquet"])
def test_binary_tabular_profiles_use_base64_without_persisting_content(data_format):
    frame = pd.DataFrame(
        [["Seoul", 100], ["Busan", 60], ["Seoul", 120]],
        columns=[None, 2026]
        if data_format == "xlsx"
        else ["Unnamed: 0", " revenue "],
    )
    stream = BytesIO()
    if data_format == "xlsx":
        frame.to_excel(stream, index=False, engine="openpyxl")
    else:
        frame.to_parquet(stream, index=False, engine="pyarrow")
    content = base64.b64encode(stream.getvalue()).decode("ascii")

    payload = analyze_dataset(
        f"sales.{data_format}",
        data_format,
        content,
        content_encoding="base64",
    )

    assert payload["row_count"] == 3
    assert payload["numeric_column_count"] == 1
    assert payload["format"] == data_format
    assert payload["storage"] == "not_persisted"
    assert "content" not in payload
    expected_columns = ["column_1", "2026"] if data_format == "xlsx" else ["column_1", "revenue"]
    assert [column["name"] for column in payload["columns"]] == expected_columns
    assert payload["column_name_normalization"]["change_count"] == 2


def test_binary_tabular_rejects_invalid_encoding_and_payload():
    with pytest.raises(DatasetAnalysisError, match="requires base64"):
        analyze_dataset("sales.xlsx", "xlsx", "not-an-xlsx")
    with pytest.raises(DatasetAnalysisError, match="base64 dataset content is invalid"):
        analyze_dataset(
            "sales.parquet",
            "parquet",
            "not-base64!",
            content_encoding="base64",
        )
