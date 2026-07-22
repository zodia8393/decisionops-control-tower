import base64
from io import BytesIO
from pathlib import Path
import sys

import pandas as pd
import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.analysis_engine import (
    AnalysisContractError,
    AnalysisPlan,
    DatasetManifest,
    FilterClause,
    analyze_with_plan,
    compile_plan,
    materialize_filtered_frame,
)
from decisionops_control_tower.data_analysis import analyze_dataset, load_dataset, profile_dataset


SALES_CSV = """region,category,revenue,orders
Seoul,A,100,2
Seoul,B,80,1
Busan,A,60,3
Busan,B,40,2
Seoul,A,120,4
"""


def manifest() -> DatasetManifest:
    return DatasetManifest.from_profile(analyze_dataset("sales.csv", "csv", SALES_CSV))


def test_manifest_preserves_profile_counts_and_numeric_types():
    dataset = manifest()

    assert dataset.row_count == 5
    assert dataset.column_count == 4
    assert [column.name for column in dataset.columns] == [
        "region",
        "category",
        "revenue",
        "orders",
    ]
    assert next(column for column in dataset.columns if column.name == "revenue").numeric is True


def test_aggregate_plan_matches_independent_pandas_cross_check():
    plan = AnalysisPlan.model_validate(
        {
            "operation": "aggregate",
            "filters": [{"column": "category", "operator": "eq", "value": "A"}],
            "group_by": ["region"],
            "metrics": [
                {"operation": "sum", "column": "revenue", "alias": "revenue_sum"},
                {"operation": "count", "alias": "row_count"},
            ],
            "order_by": [{"column": "revenue_sum", "direction": "desc"}],
            "limit": 10,
            "rationale": "A category revenue by region",
        }
    )

    result = analyze_with_plan("sales.csv", "csv", SALES_CSV, plan)
    expected = (
        pd.read_csv(pd.io.common.StringIO(SALES_CSV))
        .query("category == 'A'")
        .groupby("region", as_index=False)
        .agg(revenue_sum=("revenue", "sum"), row_count=("revenue", "size"))
        .sort_values("revenue_sum", ascending=False)
        .to_dict(orient="records")
    )

    assert result.rows == expected
    assert result.input_row_count == 5
    assert result.denominator_row_count == 3
    assert result.output_row_count == 2
    assert result.numeric_source_of_truth == "duckdb"
    assert result.provenance.parameter_count == 1

    share_plan = AnalysisPlan.model_validate(
        {
            "operation": "aggregate",
            "group_by": ["region"],
            "metrics": [{"operation": "share", "alias": "share_percent"}],
            "order_by": [{"column": "share_percent", "direction": "desc"}],
            "rationale": "region share of all rows",
        }
    )
    share = analyze_with_plan("sales.csv", "csv", SALES_CSV, share_plan)
    assert share.rows == [
        {"region": "Seoul", "share_percent": 60.0},
        {"region": "Busan", "share_percent": 40.0},
    ]
    assert "SUM(COUNT(*)) OVER ()" in share.provenance.sql


def test_select_plan_filters_ranks_and_limits_rows():
    plan = AnalysisPlan.model_validate(
        {
            "operation": "select",
            "select_columns": ["region", "revenue"],
            "filters": [{"column": "revenue", "operator": "gte", "value": 60}],
            "order_by": [{"column": "revenue", "direction": "desc"}],
            "limit": 2,
            "rationale": "show the two largest qualifying revenue rows",
        }
    )

    result = analyze_with_plan("sales.csv", "csv", SALES_CSV, plan)

    assert result.rows == [
        {"region": "Seoul", "revenue": 120},
        {"region": "Seoul", "revenue": 100},
    ]
    assert result.denominator_row_count == 4
    assert result.output_row_count == 2


def test_materialized_frame_preserves_source_lineage_and_parameterized_filters():
    dataset = load_dataset("sales.csv", "csv", SALES_CSV)
    dataset_manifest = DatasetManifest.from_profile(profile_dataset(dataset))

    result = materialize_filtered_frame(
        dataset,
        dataset_manifest,
        columns=["region", "revenue"],
        filters=[FilterClause(column="region", operator="eq", value="Busan")],
    )

    assert result.frame.to_dict(orient="records") == [
        {"__decisionops_source_row__": 2, "region": "Busan", "revenue": 60},
        {"__decisionops_source_row__": 3, "region": "Busan", "revenue": 40},
    ]
    assert result.provenance.parameter_count == 1
    assert "Busan" not in result.provenance.sql


def test_select_plan_serializes_missing_values_as_json_null():
    plan = AnalysisPlan.model_validate(
        {
            "operation": "select",
            "select_columns": ["name", "value"],
            "order_by": [{"column": "name"}],
            "limit": 10,
            "rationale": "preserve missing values without non-finite JSON",
        }
    )

    result = analyze_with_plan("missing.csv", "csv", "name,value\nA,\nB,2\n", plan)

    assert result.rows == [{"name": "A", "value": None}, {"name": "B", "value": 2.0}]


def test_contains_treats_sql_wildcards_as_literal_text():
    content = "name,value\nA_100%,1\nAx100x,2\n"
    plan = AnalysisPlan.model_validate(
        {
            "operation": "select",
            "select_columns": ["name"],
            "filters": [{"column": "name", "operator": "contains", "value": "_100%"}],
            "limit": 10,
            "rationale": "literal wildcard characters",
        }
    )

    result = analyze_with_plan("literal.csv", "csv", content, plan)

    assert result.rows == [{"name": "A_100%"}]


def test_plan_rejects_unknown_column_and_non_numeric_sum():
    unknown = AnalysisPlan.model_validate(
        {
            "operation": "select",
            "select_columns": ["does_not_exist"],
            "limit": 10,
            "rationale": "invalid column should fail",
        }
    )
    non_numeric = AnalysisPlan.model_validate(
        {
            "operation": "aggregate",
            "metrics": [{"operation": "sum", "column": "region", "alias": "bad_sum"}],
            "limit": 10,
            "rationale": "invalid metric should fail",
        }
    )

    with pytest.raises(AnalysisContractError, match="unknown dataset columns"):
        compile_plan(unknown, manifest())
    with pytest.raises(AnalysisContractError, match="requires a numeric column"):
        compile_plan(non_numeric, manifest())


def test_plan_rejects_unsafe_or_ambiguous_contracts():
    with pytest.raises(ValidationError, match="safe ASCII identifier"):
        AnalysisPlan.model_validate(
            {
                "operation": "aggregate",
                "metrics": [
                    {
                        "operation": "sum",
                        "column": "revenue",
                        "alias": 'total"; DROP TABLE uploaded_data; --',
                    }
                ],
                "rationale": "unsafe alias",
            }
        )
    with pytest.raises(ValidationError, match="aggregate plan requires"):
        AnalysisPlan.model_validate(
            {"operation": "aggregate", "rationale": "missing metrics"}
        )
    with pytest.raises(ValidationError, match="does not accept a value"):
        AnalysisPlan.model_validate(
            {
                "operation": "select",
                "filters": [{"column": "revenue", "operator": "is_null", "value": 1}],
                "rationale": "invalid null filter",
            }
        )
    with pytest.raises(ValidationError, match="share does not accept a column"):
        AnalysisPlan.model_validate(
            {
                "operation": "aggregate",
                "group_by": ["region"],
                "metrics": [
                    {"operation": "share", "column": "region", "alias": "share_percent"}
                ],
                "rationale": "share must use the row denominator",
            }
        )


@pytest.mark.parametrize("data_format", ["xlsx", "parquet"])
def test_binary_formats_match_csv_numeric_results(data_format):
    frame = pd.read_csv(pd.io.common.StringIO(SALES_CSV))
    stream = BytesIO()
    if data_format == "xlsx":
        frame.to_excel(stream, index=False, engine="openpyxl")
    else:
        frame.to_parquet(stream, index=False, engine="pyarrow")
    plan = AnalysisPlan.model_validate(
        {
            "operation": "aggregate",
            "group_by": ["region"],
            "metrics": [{"operation": "sum", "column": "revenue", "alias": "total"}],
            "order_by": [{"column": "total", "direction": "desc"}],
            "limit": 10,
            "rationale": "cross-format numeric equivalence",
        }
    )

    result = analyze_with_plan(
        f"sales.{data_format}",
        data_format,
        base64.b64encode(stream.getvalue()).decode("ascii"),
        plan,
        content_encoding="base64",
    )

    assert result.rows == [
        {"region": "Seoul", "total": 300.0},
        {"region": "Busan", "total": 100.0},
    ]


def test_statistical_metrics_match_independent_pandas_results():
    plan = AnalysisPlan.model_validate(
        {
            "operation": "aggregate",
            "metrics": [
                {"operation": "median", "column": "revenue", "alias": "median_revenue"},
                {"operation": "stddev", "column": "orders", "alias": "orders_stddev"},
                {
                    "operation": "correlation",
                    "column": "revenue",
                    "secondary_column": "orders",
                    "alias": "revenue_orders_corr",
                },
            ],
            "limit": 1,
            "rationale": "bounded descriptive statistics",
        }
    )

    result = analyze_with_plan("sales.csv", "csv", SALES_CSV, plan)
    expected = pd.read_csv(pd.io.common.StringIO(SALES_CSV))

    assert result.rows[0]["median_revenue"] == pytest.approx(expected["revenue"].median())
    assert result.rows[0]["orders_stddev"] == pytest.approx(expected["orders"].std())
    assert result.rows[0]["revenue_orders_corr"] == pytest.approx(
        expected["revenue"].corr(expected["orders"])
    )


def test_date_only_filter_includes_the_requested_calendar_day():
    plan = AnalysisPlan.model_validate(
        {
            "operation": "aggregate",
            "filters": [{"column": "event_date", "operator": "lte", "value": "2026-06-03"}],
            "metrics": [{"operation": "sum", "column": "value", "alias": "total"}],
            "rationale": "inclusive date-only upper boundary",
        }
    )

    result = analyze_with_plan(
        "dates.csv",
        "csv",
        "event_date,value\n2026-06-02,1\n2026-06-03,2\n2026-06-04,4\n",
        plan,
    )

    assert result.denominator_row_count == 2
    assert result.rows == [{"total": 3.0}]
