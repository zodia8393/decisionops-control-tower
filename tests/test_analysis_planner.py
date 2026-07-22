from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.analysis_engine import (
    AnalysisPlan,
    DatasetManifest,
    FilterClause,
    execute_plan,
)
from decisionops_control_tower.analysis_planner import plan_analysis
from decisionops_control_tower.data_analysis import load_dataset, profile_dataset


CONTENT = """region,category,revenue,orders
Seoul,A,100,2
Seoul,B,80,1
Busan,A,60,3
Busan,B,40,2
Seoul,A,120,4
"""


@pytest.fixture
def dataset_context():
    dataset = load_dataset("sales.csv", "csv", CONTENT)
    manifest = DatasetManifest.from_profile(profile_dataset(dataset))
    return dataset, manifest


def test_planner_builds_grouped_top_n_aggregation(dataset_context):
    dataset, manifest = dataset_context

    outcome = plan_analysis("region별 revenue 합계 상위 2개", manifest, dataset.frame)
    result = execute_plan(dataset, manifest, outcome.plan)

    assert outcome.status == "planned"
    assert outcome.plan.operation == "aggregate"
    assert outcome.plan.group_by == ["region"]
    assert outcome.plan.metrics[0].operation == "sum"
    assert outcome.plan.limit == 2
    assert result.rows == [
        {"region": "Seoul", "sum_value": 300.0},
        {"region": "Busan", "sum_value": 100.0},
    ]


def test_planner_builds_numeric_and_categorical_filters(dataset_context):
    dataset, manifest = dataset_context

    outcome = plan_analysis(
        "category가 A인 데이터 중 revenue 80 이상인 행을 보여줘",
        manifest,
        dataset.frame,
    )
    result = execute_plan(dataset, manifest, outcome.plan)

    assert outcome.status == "planned"
    assert {(item.column, item.operator) for item in outcome.plan.filters} == {
        ("category", "eq"),
        ("revenue", "gte"),
    }
    assert result.denominator_row_count == 2

    report = load_dataset(
        "report.csv",
        "csv",
        "요일,배출량(g)\n월,100\n일,80\n합계,180\n",
    )
    report_manifest = DatasetManifest.from_profile(profile_dataset(report))
    excluded = plan_analysis(
        "합계 행을 제외하고 배출량(g) 평균",
        report_manifest,
        report.frame,
    )

    assert excluded.status == "planned"
    assert [(item.column, item.operator, item.value) for item in excluded.plan.filters] == [
        ("요일", "ne", "합계")
    ]
    excluded_result = execute_plan(report, report_manifest, excluded.plan)
    assert excluded_result.denominator_row_count == 2
    assert excluded_result.rows == [{"mean_value": 90.0}]

    ranked = plan_analysis(
        "합계 행을 제외하고 배출량(g) 기준 상위 5개 보여줘",
        report_manifest,
        report.frame,
    )
    assert ranked.status == "planned"
    assert ranked.plan.operation == "select"
    assert ranked.plan.filters[0].operator == "ne"
    assert execute_plan(report, report_manifest, ranked.plan).denominator_row_count == 2

    fresh_grouped = plan_analysis(
        "합계 행을 제외하고 요일별 배출량(g) 평균",
        report_manifest,
        report.frame,
        ranked.plan,
    )
    assert fresh_grouped.status == "planned"
    assert fresh_grouped.plan.operation == "aggregate"
    assert fresh_grouped.plan.group_by == ["요일"]
    assert fresh_grouped.plan.metrics[0].operation == "mean"
    assert execute_plan(report, report_manifest, fresh_grouped.plan).denominator_row_count == 2

    implicit = plan_analysis("요일별 건수", report_manifest, report.frame)
    implicit_result = execute_plan(report, report_manifest, implicit.plan)
    assert [(item.column, item.operator, item.value) for item in implicit.plan.filters] == [
        ("요일", "ne", "합계")
    ]
    assert implicit_result.denominator_row_count == 2
    assert implicit_result.output_row_count == 2

    plain_rows = plan_analysis("데이터 보여줘", report_manifest, report.frame)
    assert plain_rows.plan.filters == []

    included = plan_analysis(
        "합계 행도 포함해서 요일별 건수",
        report_manifest,
        report.frame,
    )
    assert included.plan.filters == []
    assert execute_plan(report, report_manifest, included.plan).denominator_row_count == 3

    included_follow_up = plan_analysis(
        "합계 행도 포함해줘",
        report_manifest,
        report.frame,
        implicit.plan,
    )
    assert included_follow_up.plan.filters == []

    multi_summary = load_dataset(
        "multi-summary.csv",
        "csv",
        "구분,value\nA,100\nB,80\n소계,180\n합계,180\n",
    )
    multi_manifest = DatasetManifest.from_profile(profile_dataset(multi_summary))
    multiple = plan_analysis(
        "소계 및 합계 행을 제외하고 value 평균",
        multi_manifest,
        multi_summary.frame,
    )
    assert [item.value for item in multiple.plan.filters] == ["소계", "합계"]
    assert execute_plan(
        multi_summary,
        multi_manifest,
        multiple.plan,
    ).denominator_row_count == 2


def test_planner_requests_column_when_metric_is_ambiguous(dataset_context):
    dataset, manifest = dataset_context

    outcome = plan_analysis("평균을 보여줘", manifest, dataset.frame)

    assert outcome.status == "clarification"
    assert outcome.plan is None
    assert "컬럼명" in outcome.message


def test_planner_modifies_previous_aggregate_limit(dataset_context):
    dataset, manifest = dataset_context
    previous = AnalysisPlan.model_validate(
        {
            "operation": "aggregate",
            "group_by": ["region"],
            "metrics": [{"operation": "sum", "column": "revenue", "alias": "sum_value"}],
            "limit": 100,
            "rationale": "initial aggregation",
        }
    )

    outcome = plan_analysis("그중 상위 1개만", manifest, dataset.frame, previous)

    assert outcome.status == "planned"
    assert outcome.plan.limit == 1
    assert outcome.plan.order_by[0].column == "sum_value"


def test_planner_leaves_profile_request_to_existing_profiler(dataset_context):
    dataset, manifest = dataset_context

    outcome = plan_analysis("이 데이터의 행, 열, 결측을 분석해줘", manifest, dataset.frame)
    natural = plan_analysis("이 데이터는 어떤 데이터지?", manifest, dataset.frame)
    capability = plan_analysis("할수있는 분석은?", manifest, dataset.frame)
    additional_capability = plan_analysis(
        "다른 분석 더 할수있는거는?",
        manifest,
        dataset.frame,
    )
    conversational_capability = plan_analysis("또 뭐 볼 수 있어?", manifest, dataset.frame)
    overview = plan_analysis("기초 통계를 보여줘", manifest, dataset.frame)
    automatic = plan_analysis("업로드 데이터 자동 분석 시작", manifest, dataset.frame)
    reset = plan_analysis("분석 조건 초기화", manifest, dataset.frame)

    assert outcome.status == "not_applicable"
    assert outcome.plan is None
    assert natural.status == "not_applicable"
    assert natural.plan is None
    assert natural.message == "dataset profile request"
    assert capability.status == "not_applicable"
    assert capability.plan is None
    assert capability.message == "dataset capability request"
    assert additional_capability.status == "not_applicable"
    assert additional_capability.message == "dataset capability request"
    assert conversational_capability.status == "not_applicable"
    assert conversational_capability.message == "dataset capability request"
    assert overview.status == "not_applicable"
    assert overview.plan is None
    assert overview.message == "dataset overview request"
    assert automatic.status == "not_applicable"
    assert automatic.plan is None
    assert automatic.message == "dataset overview request"
    assert reset.status == "not_applicable"
    assert reset.plan is None
    assert reset.message == "analysis session reset request"


def test_planner_builds_datetime_filter_and_statistical_metrics():
    content = "event_date,amount,duration\n2026-01-01,10,2\n2026-01-02,20,4\n2026-01-03,30,5\n"
    dataset = load_dataset("events.csv", "csv", content)
    manifest = DatasetManifest.from_profile(profile_dataset(dataset))

    filtered = plan_analysis(
        "event_date 2026-01-02 이후 amount 합계",
        manifest,
        dataset.frame,
    )
    correlation = plan_analysis(
        "amount와 duration 상관계수",
        manifest,
        dataset.frame,
    )

    assert filtered.status == "planned"
    assert filtered.plan.filters[0].column == "event_date"
    assert filtered.plan.filters[0].operator == "gte"
    assert execute_plan(dataset, manifest, filtered.plan).rows == [{"sum_value": 50.0}]
    assert correlation.status == "planned"
    assert correlation.plan.metrics[0].operation == "correlation"
    assert correlation.plan.metrics[0].secondary_column == "duration"
    assert execute_plan(dataset, manifest, correlation.plan).rows[0][
        "correlation_value"
    ] == pytest.approx(dataset.frame["amount"].corr(dataset.frame["duration"]))


def test_planner_handles_humanized_column_names_paraphrases_and_bottom_n():
    content = "service_line,net_sales,wait_minutes\ndental,120,8\nwellness,80,15\ndental,60,4\n"
    dataset = load_dataset("services.csv", "csv", content)
    manifest = DatasetManifest.from_profile(profile_dataset(dataset))

    grouped = plan_analysis(
        "service line마다 net sales를 더해서 가장 높은 2개",
        manifest,
        dataset.frame,
    )
    bottom = plan_analysis(
        "net sales 기준 가장 낮은 2개 목록",
        manifest,
        dataset.frame,
    )

    assert grouped.status == "planned"
    assert grouped.plan.group_by == ["service_line"]
    assert grouped.plan.metrics[0].column == "net_sales"
    assert grouped.plan.order_by[0].direction == "desc"
    assert bottom.status == "planned"
    assert bottom.plan.order_by[0].column == "net_sales"
    assert bottom.plan.order_by[0].direction == "asc"
    assert [row["net_sales"] for row in execute_plan(dataset, manifest, bottom.plan).rows] == [60, 80]

    dated = load_dataset(
        "dated-sales.csv",
        "csv",
        "date,region,revenue,cost\n2026-01-01,서울,100,60\n2026-01-02,서울,130,70\n2026-01-03,부산,80,55\n",
    )
    dated_manifest = DatasetManifest.from_profile(profile_dataset(dated))
    aliased = plan_analysis("지역별 매출 합계", dated_manifest, dated.frame)
    trend = plan_analysis("날짜별 매출 추이 보여줘", dated_manifest, dated.frame)
    relationship = plan_analysis("매출과 비용 관계를 알려줘", dated_manifest, dated.frame)

    assert aliased.plan.group_by == ["region"]
    assert aliased.plan.metrics[0].column == "revenue"
    assert execute_plan(dated, dated_manifest, aliased.plan).rows == [
        {"region": "부산", "sum_value": 80.0},
        {"region": "서울", "sum_value": 230.0},
    ]
    assert trend.plan.group_by == ["date"]
    assert trend.plan.metrics[0].operation == "sum"
    assert trend.plan.order_by[0].column == "date"
    assert relationship.plan.metrics[0].operation == "correlation"

    categories = load_dataset(
        "tickets.csv",
        "csv",
        "status,channel\n완료,web\n완료,app\n대기,web\n완료,web\n",
    )
    category_manifest = DatasetManifest.from_profile(profile_dataset(categories))
    share = plan_analysis("status별 비율 보여줘", category_manifest, categories.frame)
    frequent = plan_analysis("가장 많은 status는?", category_manifest, categories.frame)
    unsupported = plan_analysis("가장 성과 좋은 지역은?", dated_manifest, dated.frame)

    assert execute_plan(categories, category_manifest, share.plan).rows == [
        {"status": "완료", "share_percent": 75.0},
        {"status": "대기", "share_percent": 25.0},
    ]
    assert execute_plan(categories, category_manifest, frequent.plan).rows == [
        {"status": "완료", "row_count": 3}
    ]
    assert unsupported.status == "clarification"

    ambiguous = load_dataset(
        "ambiguous.csv",
        "csv",
        "region,area,revenue\n서울,동부,100\n부산,서부,80\n",
    )
    ambiguous_manifest = DatasetManifest.from_profile(profile_dataset(ambiguous))
    ambiguous_alias = plan_analysis(
        "지역별 매출 합계", ambiguous_manifest, ambiguous.frame
    )
    assert ambiguous_alias.status == "clarification"
    assert "region, area" in ambiguous_alias.message

    market = load_dataset(
        "market.csv",
        "csv",
        "segment,market_share\nA,10\nB,20\n",
    )
    market_manifest = DatasetManifest.from_profile(profile_dataset(market))
    market_mean = plan_analysis("market share 평균", market_manifest, market.frame)
    assert market_mean.plan.metrics[0].operation == "mean"
    assert market_mean.plan.metrics[0].column == "market_share"

    formatted = load_dataset(
        "formatted.csv",
        "csv",
        'month,revenue,rate\n1월,"1,000원",10%\n2월,"1,200원",12%\n',
    )
    formatted_manifest = DatasetManifest.from_profile(profile_dataset(formatted))
    formatted_mean = plan_analysis("월별 revenue 평균", formatted_manifest, formatted.frame)
    assert formatted_mean.status == "clarification"
    assert "수치형으로 인식되지 않았습니다" in formatted_mean.message


def test_planner_handles_natural_comparisons_nulls_and_selected_columns():
    content = "service_line,net_sales,customer_score\ndental,120,5\nwellness,80,\ndental,60,4\n"
    dataset = load_dataset("services.csv", "csv", content)
    manifest = DatasetManifest.from_profile(profile_dataset(dataset))

    compared = plan_analysis(
        "net sales가 80보다 크거나 같은 데이터 목록",
        manifest,
        dataset.frame,
    )
    missing = plan_analysis(
        "customer score가 비어 있는 행을 보여줘",
        manifest,
        dataset.frame,
    )
    selected = plan_analysis(
        "service line과 net sales만 보여줘",
        manifest,
        dataset.frame,
    )

    assert compared.plan.filters[0].column == "net_sales"
    assert compared.plan.filters[0].operator == "gte"
    assert compared.plan.filters[0].value == 80.0
    assert missing.plan.filters[0].operator == "is_null"
    assert selected.plan.select_columns == ["service_line", "net_sales"]


def test_planner_multi_turn_modifies_metric_group_filter_and_rank(dataset_context):
    dataset, manifest = dataset_context
    previous = AnalysisPlan.model_validate(
        {
            "operation": "aggregate",
            "group_by": ["region"],
            "metrics": [{"operation": "sum", "column": "revenue", "alias": "sum_value"}],
            "order_by": [{"column": "sum_value", "direction": "desc"}],
            "limit": 5,
            "rationale": "initial",
        }
    )

    metric = plan_analysis("평균으로 바꿔줘", manifest, dataset.frame, previous)
    retargeted = plan_analysis("orders 평균으로 바꿔줘", manifest, dataset.frame, previous)
    regrouped = plan_analysis("category별로 바꿔줘", manifest, dataset.frame, metric.plan)
    filtered = plan_analysis(
        "category가 A인 것만 보고 하위 1개",
        manifest,
        dataset.frame,
        regrouped.plan,
    )

    assert metric.plan.metrics[0].operation == "mean"
    assert metric.plan.order_by[0].column == "mean_value"
    assert retargeted.plan.metrics[0].operation == "mean"
    assert retargeted.plan.metrics[0].column == "orders"
    assert regrouped.plan.group_by == ["category"]
    assert filtered.plan.filters[0].value == "A"
    assert filtered.plan.limit == 1
    assert filtered.plan.order_by[0].direction == "asc"

    fresh_analysis = plan_analysis(
        "region별 orders 평균",
        manifest,
        dataset.frame,
        filtered.plan,
    )
    assert fresh_analysis.plan.group_by == ["region"]
    assert fresh_analysis.plan.metrics[0].column == "orders"
    assert fresh_analysis.plan.filters == []

    share = plan_analysis("비율로 바꿔줘", manifest, dataset.frame, regrouped.plan)
    assert share.plan.metrics[0].operation == "share"
    assert share.plan.metrics[0].column is None
    assert share.plan.order_by[0].column == "share_percent"
    assert share.plan.order_by[0].direction == "desc"


def test_planner_multi_turn_can_clear_filters_and_use_plain_limit(dataset_context):
    dataset, manifest = dataset_context
    previous = AnalysisPlan.model_validate(
        {
            "operation": "select",
            "filters": [{"column": "category", "operator": "eq", "value": "A"}],
            "order_by": [{"column": "revenue", "direction": "desc"}],
            "limit": 10,
            "rationale": "filtered rows",
        }
    )

    outcome = plan_analysis("조건 없이 전체로 3개만 보여줘", manifest, dataset.frame, previous)

    assert outcome.status == "planned"
    assert outcome.plan.filters == []
    assert outcome.plan.limit == 3

    multiple_filters = previous.model_copy(deep=True)
    multiple_filters.filters.append(
        FilterClause(column="region", operator="eq", value="Seoul")
    )
    selective = plan_analysis(
        "region 필터 제거",
        manifest,
        dataset.frame,
        multiple_filters,
    )
    assert [(item.column, item.value) for item in selective.plan.filters] == [
        ("category", "A")
    ]


def test_planner_understands_conversational_profile_overview_and_capability(dataset_context):
    dataset, manifest = dataset_context

    profile = plan_analysis("이거 뭐야?", manifest, dataset.frame)
    overview = plan_analysis("뭐가 제일 눈에 띄어?", manifest, dataset.frame)
    prediction_guide = plan_analysis("어떤 예측이 가능해?", manifest, dataset.frame)
    open_ended_guide = plan_analysis("뭘 할 수 있어?", manifest, dataset.frame)

    assert profile.status == "not_applicable"
    assert profile.message == "dataset profile request"
    assert overview.status == "not_applicable"
    assert overview.message == "dataset overview request"
    assert prediction_guide.status == "not_applicable"
    assert prediction_guide.message == "dataset capability request"
    assert open_ended_guide.status == "not_applicable"
    assert open_ended_guide.message == "dataset capability request"


def test_planner_understands_natural_sum_sort_rank_and_korean_count(dataset_context):
    dataset, manifest = dataset_context

    grouped = plan_analysis(
        "지역 기준 매출을 합쳐서 큰 순서로 알려줘",
        manifest,
        dataset.frame,
    )
    total_amount = plan_analysis(
        "지역마다 매출 총액 보여줘",
        manifest,
        dataset.frame,
    )
    highest = plan_analysis("제일 매출 높은 곳 알려줘", manifest, dataset.frame)
    top_three = plan_analysis(
        "상위 세 개만",
        manifest,
        dataset.frame,
        grouped.plan,
    )
    ascending = plan_analysis(
        "오름차순으로 정렬해줘",
        manifest,
        dataset.frame,
        top_three.plan,
    )

    assert grouped.status == "planned"
    assert grouped.plan.operation == "aggregate"
    assert grouped.plan.group_by == ["region"]
    assert grouped.plan.metrics[0].operation == "sum"
    assert grouped.plan.order_by[0].direction == "desc"
    assert total_amount.plan.metrics[0].operation == "sum"
    assert highest.plan.operation == "select"
    assert highest.plan.limit == 1
    assert highest.plan.order_by[0].column == "revenue"
    assert highest.plan.order_by[0].direction == "desc"
    assert top_three.plan.limit == 3
    assert ascending.plan.order_by[0].direction == "asc"


def test_planner_reuses_previous_result_for_interpretation_without_guessing(dataset_context):
    dataset, manifest = dataset_context
    previous = plan_analysis(
        "revenue와 orders 상관계수",
        manifest,
        dataset.frame,
    ).plan

    meaning = plan_analysis(
        "그 관계가 강한 편이야?",
        manifest,
        dataset.frame,
        previous,
    )
    why = plan_analysis(
        "왜 이런 결과가 나온 거야?",
        manifest,
        dataset.frame,
        previous,
    )

    assert meaning.status == "planned"
    assert meaning.plan == previous
    assert meaning.message == "previous analysis result interpretation request"
    assert why.status == "planned"
    assert why.plan == previous
    assert why.message == "previous analysis result interpretation request"


def test_planner_blocks_unsupported_derived_threshold_instead_of_silent_wrong_answer(
    dataset_context,
):
    dataset, manifest = dataset_context

    outcome = plan_analysis(
        "매출 평균보다 높은 지역만 보여줘",
        manifest,
        dataset.frame,
    )

    assert outcome.status == "clarification"
    assert outcome.plan is None
    assert "평균을 먼저 계산한 뒤" in outcome.message


def test_planner_handles_missing_row_request_without_misclassifying_it_as_profile():
    complete = load_dataset(
        "complete.csv",
        "csv",
        "region,revenue\nSeoul,100\nBusan,80\n",
    )
    complete_manifest = DatasetManifest.from_profile(profile_dataset(complete))
    none_missing = plan_analysis(
        "결측치가 있는 행만 보여줘",
        complete_manifest,
        complete.frame,
    )

    partial = load_dataset(
        "partial.csv",
        "csv",
        "region,revenue\nSeoul,100\nBusan,\n",
    )
    partial_manifest = DatasetManifest.from_profile(profile_dataset(partial))
    one_missing = plan_analysis(
        "결측치가 있는 행만 보여줘",
        partial_manifest,
        partial.frame,
    )

    assert none_missing.status == "not_applicable"
    assert none_missing.message == "dataset profile request"
    assert one_missing.status == "planned"
    assert one_missing.plan.operation == "select"
    assert one_missing.plan.filters == [
        FilterClause(column="revenue", operator="is_null")
    ]
    assert execute_plan(partial, partial_manifest, one_missing.plan).output_row_count == 1


def test_planner_handles_greeting_help_and_acknowledgement_as_conversation(dataset_context):
    dataset, manifest = dataset_context

    for question in ("안녕", "사용법 알려줘", "고마워"):
        outcome = plan_analysis(question, manifest, dataset.frame)
        assert outcome.status == "not_applicable"
        assert outcome.message == "dataset conversation request"


def test_planner_blocks_ambiguous_percentile_and_multiple_metric_requests(dataset_context):
    dataset, manifest = dataset_context

    percentile = plan_analysis("매출 상위 10% 보여줘", manifest, dataset.frame)
    two_metrics = plan_analysis("매출 합계와 평균 보여줘", manifest, dataset.frame)
    two_targets = plan_analysis("매출과 주문수 평균 보여줘", manifest, dataset.frame)
    correction = plan_analysis("합계 말고 매출 평균", manifest, dataset.frame)

    assert percentile.status == "clarification"
    assert "10%" in percentile.message
    assert two_metrics.status == "clarification"
    assert "집계 방법" in two_metrics.message
    assert two_targets.status == "clarification"
    assert "수치 컬럼" in two_targets.message
    assert correction.status == "planned"
    assert correction.plan.metrics[0].operation == "mean"


def test_planner_grouped_correlation_keeps_all_groups(dataset_context):
    dataset, manifest = dataset_context

    outcome = plan_analysis(
        "region별 revenue와 orders 상관계수",
        manifest,
        dataset.frame,
    )

    assert outcome.status == "planned"
    assert outcome.plan.group_by == ["region"]
    assert outcome.plan.limit == 100


def test_planner_natural_follow_up_retargets_metric_clears_filter_and_resets(dataset_context):
    dataset, manifest = dataset_context
    initial = plan_analysis("region별 revenue 합계", manifest, dataset.frame).plan
    retargeted = plan_analysis("이번엔 orders로 해줘", manifest, dataset.frame, initial)
    filtered = plan_analysis(
        "category가 A인 것만",
        manifest,
        dataset.frame,
        retargeted.plan,
    )
    cleared = plan_analysis("필터 없애줘", manifest, dataset.frame, filtered.plan)
    reset = plan_analysis("원래대로 돌아가", manifest, dataset.frame, cleared.plan)

    assert retargeted.status == "planned"
    assert retargeted.plan.metrics[0].operation == "sum"
    assert retargeted.plan.metrics[0].column == "orders"
    assert filtered.plan.filters[0].column == "category"
    assert cleared.plan.filters == []
    assert reset.status == "not_applicable"
    assert reset.message == "analysis session reset request"


def test_planner_supports_coordinated_groups_multiple_values_and_numeric_ranges(dataset_context):
    dataset, manifest = dataset_context

    coordinated = plan_analysis(
        "지역과 category별 매출 합계",
        manifest,
        dataset.frame,
    )
    multiple_values = plan_analysis(
        "Seoul과 Busan만 보여줘",
        manifest,
        dataset.frame,
    )
    numeric_range = plan_analysis(
        "매출 60에서 100 사이만 보여줘",
        manifest,
        dataset.frame,
    )
    reversed_range = plan_analysis(
        "매출 100에서 60 사이만 보여줘",
        manifest,
        dataset.frame,
    )
    coordinated_phrase = plan_analysis(
        "region과 category로 묶어서 매출 평균",
        manifest,
        dataset.frame,
    )

    assert coordinated.status == "planned"
    assert coordinated.plan.group_by == ["region", "category"]
    assert multiple_values.plan.filters == [
        FilterClause(column="region", operator="in", value=["Seoul", "Busan"])
    ]
    assert execute_plan(dataset, manifest, multiple_values.plan).denominator_row_count == 5
    assert numeric_range.plan.filters == [
        FilterClause(column="revenue", operator="gte", value=60.0),
        FilterClause(column="revenue", operator="lte", value=100.0),
    ]
    assert reversed_range.status == "clarification"
    assert "시작값 100" in reversed_range.message
    assert coordinated_phrase.plan.group_by == ["region", "category"]


def test_planner_clarifies_row_level_ratio_instead_of_misreading_it_as_group_share(
    dataset_context,
):
    dataset, manifest = dataset_context

    outcome = plan_analysis(
        "매출 대비 주문수 비율 보여줘",
        manifest,
        dataset.frame,
    )

    assert outcome.status == "clarification"
    assert "파생 비율" in outcome.message


def test_planner_understands_open_ended_capability_question(dataset_context):
    dataset, manifest = dataset_context

    outcome = plan_analysis("뭘 할 수 있어?", manifest, dataset.frame)

    assert outcome.status == "not_applicable"
    assert outcome.message == "dataset capability request"


def test_planner_does_not_split_distinct_count_into_two_metrics(dataset_context):
    dataset, manifest = dataset_context

    korean = plan_analysis("category 고유 개수", manifest, dataset.frame)
    english = plan_analysis("category distinct count", manifest, dataset.frame)

    assert korean.status == "planned"
    assert korean.plan.metrics[0].operation == "count_distinct"
    assert english.status == "planned"
    assert english.plan.metrics[0].operation == "count_distinct"
