"""Bounded natural-language planner for deterministic tabular analysis."""

from __future__ import annotations

import re
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict

from decisionops_control_tower.analysis_engine import (
    AnalysisPlan,
    ColumnManifest,
    DatasetManifest,
    FilterClause,
    MetricSpec,
    SortSpec,
)
from decisionops_control_tower.data_analysis import summary_row_details


METRIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("correlation", ("상관계수", "상관 분석", "상관관계", "correlation", "corr")),
    (
        "count_distinct",
        ("고유 개수", "고유값 수", "유니크 수", "distinct count", "nunique", "unique count"),
    ),
    ("stddev", ("표준편차", "standard deviation", "stddev", "std")),
    ("median", ("중앙값", "중간값", "median")),
    ("mean", ("평균값", "평균", "average", "avg", "mean")),
    ("share", ("비율", "구성비", "점유율", "percentage", "percent", "share")),
    (
        "sum",
        ("합계", "총합", "총액", "합산", "합쳐", "더해", "합을", "sum", "total"),
    ),
    ("max", ("최고값", "최댓값", "최대", "max", "maximum")),
    ("min", ("최저값", "최솟값", "최소", "min", "minimum")),
    ("count", ("개수", "건수", "몇 개", "count", "row count")),
)
PROFILE_PATTERNS = ("행", "열", "결측", "profile", "schema", "column", "dtype")
SELECT_PATTERNS = ("보여", "목록", "조회", "데이터", "행", "show", "list", "rows")
PROFILE_REQUEST_MESSAGE = "dataset profile request"
CAPABILITY_REQUEST_MESSAGE = "dataset capability request"
OVERVIEW_REQUEST_MESSAGE = "dataset overview request"
ANALYSIS_RESET_REQUEST_MESSAGE = "analysis session reset request"
RESULT_INTERPRETATION_MESSAGE = "previous analysis result interpretation request"
CONVERSATION_REQUEST_MESSAGE = "dataset conversation request"
PROFILE_QUESTION_PATTERNS = (
    re.compile(r"(?:이|그)?\s*데이터(?:는|가|셋은)?\s*(?:어떤|무슨|뭐|무엇)"),
    re.compile(r"(?:데이터|파일)(?:를|을|의)?\s*(?:설명|요약|파악|소개)"),
    re.compile(r"^(?:이|그)?\s*거(?:는|가|야)?\s*(?:뭐|무엇|무슨|설명)"),
    re.compile(r"\b(?:describe|summari[sz]e)\s+(?:this\s+)?(?:data|dataset|file)\b"),
    re.compile(r"\bwhat\s+is\s+(?:this\s+)?(?:data|dataset|file)\b"),
)
CAPABILITY_QUESTION_PATTERNS = (
    re.compile(r"(?:뭘|뭐|무엇을)\s*(?:할|해볼)\s*수\s*있"),
    re.compile(r"(?:할|해볼)\s*수\s*있는\s*(?:데이터\s*)?분석"),
    re.compile(r"(?:어떤|무슨|뭘|무엇을)\s*(?:분석|질문)"),
    re.compile(r"(?:가능한|추천(?:해\s*줄)?)\s*(?:(?:심화|고급|기본)\s*)?(?:분석|질문)"),
    re.compile(r"(?:분석|질문)\s*(?:가능|예시|추천)"),
    re.compile(
        r"(?:다른|추가(?:로)?|더|또)\s*(?:분석|질문)(?:은|을|도)?"
        r"(?:\s*더)?\s*(?:(?:할|해볼)\s*수\s*있는?|추천|알려)?"
    ),
    re.compile(r"(?:다른|추가(?:로)?|더|또)\s*(?:뭐|뭘|무엇을?)\s*(?:볼|보|분석|확인)"),
    re.compile(r"(?:더|또)\s*(?:볼|확인할)\s*(?:거|것|건)\s*(?:없|있)"),
    re.compile(r"(?:어떤|무슨|뭘|무엇을)\s*(?:예측|모델)"),
    re.compile(r"(?:예측|모델)(?:을|이|은|는)?\s*(?:가능|추천|필요|조건|요건)"),
    re.compile(r"(?:예측|모델).*(?:하려면|하기\s*위해).*(?:필요|준비|조건)"),
    re.compile(r"\bwhat\s+can\s+(?:i|we)\s+(?:analy[sz]e|ask)\b"),
    re.compile(r"\bwhat\s+else\s+can\s+(?:i|we)\s+(?:analy[sz]e|ask|look\s+at)\b"),
    re.compile(r"\b(?:more|other|additional|next)\s+(?:analysis|analyses|questions?)\b"),
)
OVERVIEW_QUESTION_PATTERNS = (
    re.compile(r"(?:기본|기초|요약)\s*(?:통계|분석)"),
    re.compile(r"(?:자동|전체)\s*(?:데이터\s*)?(?:분석|eda)"),
    re.compile(r"(?:데이터\s*)?분석\s*(?:을\s*)?시작"),
    re.compile(r"(?:중요한|주요|핵심)\s*(?:특징|내용|인사이트)"),
    re.compile(r"(?:뭐|무엇|어디)가?\s*(?:제일|가장)?\s*(?:눈에\s*띄|특이|두드러)"),
    re.compile(r"(?:눈에\s*띄|특이|두드러).*(?:점|부분|것|거)"),
    re.compile(r"(?:뭘|무엇을?|어디서)\s*(?:먼저|부터)\s*(?:봐|보|확인)"),
    re.compile(r"(?:분포|distribution)\s*(?:를|을)?\s*(?:보여|알려|확인)?"),
    re.compile(r"\b(?:basic|summary)\s+(?:statistics|analysis)\b"),
)
TREND_QUESTION_PATTERN = re.compile(r"(?:추이|트렌드|시계열|trend|over\s+time)")
RELATIONSHIP_QUESTION_PATTERN = re.compile(r"(?:관계|relationship)")
MOST_FREQUENT_PATTERN = re.compile(
    r"(?:가장\s*(?:많은|자주\s*나오는)|최빈|most\s+(?:common|frequent))"
)
ANALYSIS_RESET_QUESTION_PATTERNS = (
    re.compile(
        r"^(?:분석\s*)?(?:조건|필터)\s*(?:을|를)?\s*"
        r"(?:초기화|리셋|reset|전부\s*(?:제거|삭제)|모두\s*(?:제거|삭제))"
    ),
    re.compile(
        r"^(?:원본|전체)\s*(?:데이터)?\s*(?:(?:기준으)?로)?\s*"
        r"(?:돌아가|복원|다시\s*시작)"
    ),
    re.compile(r"^(?:새|새로운)\s*분석(?:으로)?\s*(?:시작|전환)"),
    re.compile(r"^(?:원래|처음)(?:\s*상태)?(?:대)?로(?:\s*(?:돌아가|복원|리셋))?"),
)
EXPLICIT_FOLLOW_UP_PATTERNS = (
    re.compile(r"(?:바꿔|변경해|수정해|이번엔|대신|그중|그\s*결과|그거|그걸|앞선|이전|방금|그대로|이어서)"),
    re.compile(r"(?:만\s*(?:보고|남겨)|필터\s*(?:제거|빼|없애)|조건\s*(?:제거|빼|없애|없이)|전체로)"),
)
RESULT_INTERPRETATION_PATTERNS = (
    re.compile(r"(?:이|그|방금|앞선|이전)?\s*(?:결과|수치|값).*(?:의미|해석|설명|요약|뜻)"),
    re.compile(r"(?:무슨|어떤)\s*(?:의미|뜻)"),
    re.compile(r"왜\s*(?:이런|그런|이|그)?\s*(?:결과|수치|값)"),
    re.compile(r"(?:관계|상관).*(?:강한|약한|큰|작은)\s*편"),
)
MISSING_ROW_PATTERN = re.compile(
    r"(?:결측(?:치|값)?|비어\s*있는|누락(?:값)?|null|missing).*(?:행|데이터).*(?:보여|조회|찾|만)",
    re.I,
)
DERIVED_THRESHOLD_PATTERN = re.compile(
    r"(?:평균|중앙값|합계|최대(?:값)?|최소(?:값)?)\s*(?:보다|이상|이하).*(?:높|낮|크|작|많|적)",
)
PERCENTILE_RANK_PATTERN = re.compile(
    r"(?:상위|하위|top|bottom)\s*\d+(?:\.\d+)?\s*%",
    re.I,
)
CONVERSATION_PATTERNS = (
    re.compile(r"^(?:안녕|안녕하세요|반가워|hello\b|hi\b)"),
    re.compile(r"^(?:고마워|감사(?:해|합니다)?|좋아|알겠어|오케이|okay\b|ok\b)"),
    re.compile(r"^(?:사용법|도움말|도와줘|어떻게\s*(?:써|사용))"),
)
KOREAN_COUNT_WORDS = {
    "한": 1,
    "하나": 1,
    "두": 2,
    "둘": 2,
    "세": 3,
    "셋": 3,
    "네": 4,
    "넷": 4,
    "다섯": 5,
    "여섯": 6,
    "일곱": 7,
    "여덟": 8,
    "아홉": 9,
    "열": 10,
}
COLUMN_ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    ("region", "area", "location", "지역", "지역명", "권역"),
    ("revenue", "sales", "net_sales", "매출", "매출액", "수익"),
    ("cost", "expense", "expenses", "원가", "비용"),
    ("date", "datetime", "event_date", "날짜", "일자", "기준일"),
    ("month", "월"),
    ("status", "state", "상태"),
    ("channel", "채널"),
    ("category", "type", "분류", "유형", "카테고리"),
    ("orders", "order_count", "주문", "주문수", "주문건수"),
    ("quantity", "qty", "수량"),
    ("amount", "금액"),
)
NUMERIC_ONLY_OPERATIONS = frozenset({"sum", "mean", "median", "stddev"})
SUMMARY_LABEL_EXPRESSION = r"(?:합계|총계|소계|subtotal|grand\s+total|total)"
SUMMARY_EXCLUSION_PATTERNS = (
    re.compile(
        rf"{SUMMARY_LABEL_EXPRESSION}"
        rf"(?:\s*(?:,|와|과|및|and)\s*{SUMMARY_LABEL_EXPRESSION})*"
        r"\s*(?:행|rows?)?\s*(?:을|를)?\s*"
        r"(?:제외(?:하고|한|해줘)?|빼고|빼줘|아닌)"
    ),
    re.compile(
        r"(?:excluding?|without)\s+(?:the\s+)?"
        r"(?:grand\s+total|subtotal|total)\s+(?:row|rows)"
    ),
)
SUMMARY_INCLUSION_PATTERNS = (
    re.compile(
        rf"{SUMMARY_LABEL_EXPRESSION}"
        rf"(?:\s*(?:,|와|과|및|and)\s*{SUMMARY_LABEL_EXPRESSION})*"
        r"\s*(?:행|rows?)?\s*(?:도|을|를)?\s*포함(?:해서|하고|해줘)?"
    ),
    re.compile(
        rf"(?:include|including)\s+(?:the\s+)?{SUMMARY_LABEL_EXPRESSION}"
        r"\s+(?:row|rows)"
    ),
)
CATEGORICAL_EXCLUSION_TOKENS = (
    "제외",
    "빼고",
    "빼줘",
    "아닌",
    "not ",
    "exclude ",
    "excluding ",
    "without ",
)


class PlanningOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["planned", "clarification", "not_applicable"]
    message: str
    plan: AnalysisPlan | None = None


def _is_profile_request(question: str) -> bool:
    return any(token in question for token in PROFILE_PATTERNS) or any(
        pattern.search(question) for pattern in PROFILE_QUESTION_PATTERNS
    )


def _is_capability_request(question: str) -> bool:
    return any(pattern.search(question) for pattern in CAPABILITY_QUESTION_PATTERNS)


def _is_overview_request(question: str) -> bool:
    return any(pattern.search(question) for pattern in OVERVIEW_QUESTION_PATTERNS)


def _is_analysis_reset_request(question: str) -> bool:
    return any(pattern.search(question) for pattern in ANALYSIS_RESET_QUESTION_PATTERNS)


def _is_explicit_follow_up(question: str) -> bool:
    return any(pattern.search(question) for pattern in EXPLICIT_FOLLOW_UP_PATTERNS)


def _is_result_interpretation_request(question: str) -> bool:
    return any(pattern.search(question) for pattern in RESULT_INTERPRETATION_PATTERNS)


def _is_conversation_request(question: str) -> bool:
    return any(pattern.search(question) for pattern in CONVERSATION_PATTERNS)


def _bounded_count(value: str, *, default: int = 1) -> int:
    if not value:
        return default
    number = int(value) if value.isdigit() else KOREAN_COUNT_WORDS.get(value, default)
    return max(1, min(number, 200))


def _sort_direction_request(question: str) -> Literal["asc", "desc"] | None:
    normalized = question.casefold()
    if re.search(r"(?:오름차순|낮은\s*순|작은\s*순|적은\s*순|ascending|asc\b)", normalized):
        return "asc"
    if re.search(r"(?:내림차순|높은\s*순|큰\s*순|많은\s*순|descending|desc\b)", normalized):
        return "desc"
    return None


def _alias_group(column_name: str) -> tuple[str, ...] | None:
    normalized = re.sub(r"[\s-]+", "_", column_name.casefold())
    parts = set(normalized.split("_"))
    for group in COLUMN_ALIAS_GROUPS:
        names = {item.casefold() for item in group}
        if normalized in names or parts.intersection(names):
            return group
    return None


def _alias_pattern(alias: str) -> re.Pattern[str]:
    suffix = r"(?=$|[\s,.'\"]|별|마다|기준|은|는|이|가|을|를|의|과|와|로|에서|중|만|도)"
    return re.compile(rf"(?<![A-Za-z0-9_가-힣]){re.escape(alias.casefold())}{suffix}")


def _column_alias_candidates(manifest: DatasetManifest) -> dict[str, list[str]]:
    candidates: dict[str, list[str]] = {}
    for column in manifest.columns:
        group = _alias_group(column.name)
        if group is None:
            continue
        for alias in group:
            candidates.setdefault(alias.casefold(), []).append(column.name)
    return candidates


def _ambiguous_column_aliases(question: str, manifest: DatasetManifest) -> list[str]:
    already_mentioned = {
        column.name
        for column in manifest.columns
        if _column_pattern(column.name).search(question)
    }
    ambiguous: list[str] = []
    for alias, columns in _column_alias_candidates(manifest).items():
        unique = list(dict.fromkeys(columns))
        if len(unique) > 1 and not set(unique).intersection(already_mentioned):
            if _alias_pattern(alias).search(question):
                ambiguous.append(f"{alias}({', '.join(unique)})")
    return ambiguous


def _normalize_column_aliases(question: str, manifest: DatasetManifest) -> str:
    candidates = _column_alias_candidates(manifest)
    already_mentioned = {
        column.name
        for column in manifest.columns
        if _column_pattern(column.name).search(question)
    }
    normalized = question
    for alias in sorted(candidates, key=len, reverse=True):
        columns = list(dict.fromkeys(candidates[alias]))
        if (
            len(columns) != 1
            or columns[0] in already_mentioned
            or alias == columns[0].casefold()
        ):
            continue
        normalized = _alias_pattern(alias).sub(columns[0], normalized)
    return normalized


def _is_summary_inclusion_request(question: str) -> bool:
    return any(pattern.search(question) for pattern in SUMMARY_INCLUSION_PATTERNS)


def _column_expression(name: str) -> str:
    tokens = [token for token in re.split(r"[\s_-]+", name.lower()) if token]
    escaped = r"[\s_-]+".join(re.escape(token) for token in tokens)
    if name.isascii():
        return rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])"
    return escaped


def _column_pattern(name: str) -> re.Pattern[str]:
    return re.compile(_column_expression(name))


def _value_pattern(value: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![A-Za-z0-9_가-힣]){re.escape(value)}"
        rf"(?=$|[\s,.'\"]|을|를|은|는|이|가|인|만|도|와|과)"
    )


def _mentioned_columns(question: str, manifest: DatasetManifest) -> list[str]:
    normalized = question.lower()
    positions: list[tuple[int, str]] = []
    for column in manifest.columns:
        match = _column_pattern(column.name).search(normalized)
        if match:
            positions.append((match.start(), column.name))
    return [name for _, name in sorted(positions)]


def _group_columns(question: str, manifest: DatasetManifest) -> list[str]:
    normalized = question.lower()
    grouped_names: set[str] = set()
    for column in manifest.columns:
        name = _column_expression(column.name)
        patterns = (
            rf"{name}\s*(?:별|마다|기준(?:으로)?)",
            rf"(?:by|per)\s+{name}",
            rf"{name}\s*(?:로|으로)\s*(?:그룹|묶)",
        )
        if any(re.search(pattern, normalized) for pattern in patterns):
            grouped_names.add(column.name)
    for left in manifest.columns:
        for right in manifest.columns:
            if left.name == right.name:
                continue
            coordinated = (
                rf"{_column_expression(left.name)}\s*(?:과|와|및|,)\s*"
                rf"{_column_expression(right.name)}\s*"
                rf"(?:별|마다|기준(?:으로)?|(?:로|으로)\s*(?:그룹|묶))"
            )
            if re.search(coordinated, normalized):
                grouped_names.update((left.name, right.name))
    return [
        name
        for name in _mentioned_columns(normalized, manifest)
        if name in grouped_names
    ]


def _metric_operations(
    question: str,
    manifest: DatasetManifest | None = None,
) -> list[str]:
    normalized = question.lower()
    for pattern in (*SUMMARY_EXCLUSION_PATTERNS, *SUMMARY_INCLUSION_PATTERNS):
        normalized = pattern.sub(" ", normalized)
    if manifest is not None:
        for column in sorted(manifest.columns, key=lambda item: len(item.name), reverse=True):
            normalized = _column_pattern(column.name).sub(" __column__ ", normalized)
    operations: list[str] = []
    matched_spans: list[tuple[int, int]] = []
    for operation, patterns in METRIC_PATTERNS:
        for pattern in patterns:
            expression = (
                rf"(?<![A-Za-z0-9_]){re.escape(pattern)}(?![A-Za-z0-9_])"
                if pattern.isascii()
                else re.escape(pattern)
            )
            match = re.search(expression, normalized)
            if not match:
                continue
            if any(
                match.start() >= start and match.end() <= end
                for start, end in matched_spans
            ):
                continue
            suffix = normalized[match.end() : match.end() + 12]
            if re.match(r"\s*(?:은|는)?\s*(?:말고|대신|에서)", suffix):
                continue
            operations.append(operation)
            matched_spans.append(match.span())
            break
    return operations


def _metric_operation(
    question: str,
    manifest: DatasetManifest | None = None,
) -> str | None:
    operations = _metric_operations(question, manifest)
    return operations[0] if operations else None


def _rank_request(question: str) -> tuple[int, Literal["asc", "desc"]] | None:
    normalized = question.lower()
    count = r"(\d{1,3}|한|하나|두|둘|세|셋|네|넷|다섯|여섯|일곱|여덟|아홉|열)"
    patterns: tuple[tuple[str, Literal["asc", "desc"], int], ...] = (
        (rf"(?:하위|bottom)\s*{count}", "asc", 1),
        (rf"(?:가장\s*)?(?:값이\s*)?(?:낮은|작은|적은)\s*{count}\s*개?", "asc", 1),
        (rf"(?:상위|top)\s*{count}", "desc", 1),
        (rf"(?:가장\s*)?(?:(?:값|건수)이\s*)?(?:높은|큰|많은)\s*{count}\s*개?", "desc", 1),
        (r"(?:제일|가장)\s+.{0,40}?(?:낮은|작은|적은)(?:\s+(?:곳|항목|값|데이터))?", "asc", 0),
        (r"(?:제일|가장)\s+.{0,40}?(?:높은|큰|많은)(?:\s+(?:곳|항목|값|데이터))?", "desc", 0),
    )
    for pattern, direction, group in patterns:
        match = re.search(pattern, normalized)
        if match:
            return _bounded_count(match.group(group) if group else ""), direction
    return None


def _plain_follow_up_limit(question: str) -> int | None:
    match = re.search(
        r"(\d{1,3}|한|하나|두|둘|세|셋|네|넷|다섯|여섯|일곱|여덟|아홉|열)\s*개(?:만)?",
        question.lower(),
    )
    if not match or not any(token in question for token in ("그중", "결과", "만", "보여")):
        return None
    return _bounded_count(match.group(1))


def _numeric_filter(question: str, column: ColumnManifest) -> FilterClause | None:
    if not column.numeric:
        return None
    name = _column_expression(column.name)
    number = r"(-?\d+(?:\.\d+)?)"
    match = re.search(
        rf"{name}\s*(?:이|가)?\s*{number}\s*(이상|이하|초과|미만)",
        question.lower(),
    )
    if match:
        operator = {"이상": "gte", "이하": "lte", "초과": "gt", "미만": "lt"}[match.group(2)]
        value = float(match.group(1))
        return FilterClause(column=column.name, operator=operator, value=value)
    match = re.search(
        rf"{name}\s*(?:이|가)?\s*{number}\s*보다\s*(크거나\s*같은|작거나\s*같은|큰|작은)",
        question.lower(),
    )
    if match:
        operator = {
            "크거나 같은": "gte",
            "작거나 같은": "lte",
            "큰": "gt",
            "작은": "lt",
        }[re.sub(r"\s+", " ", match.group(2))]
        return FilterClause(column=column.name, operator=operator, value=float(match.group(1)))
    match = re.search(
        rf"{number}\s*(이상|이하|초과|미만)(?:인|의)?\s*{name}",
        question.lower(),
    )
    if match:
        operator = {"이상": "gte", "이하": "lte", "초과": "gt", "미만": "lt"}[match.group(2)]
        return FilterClause(column=column.name, operator=operator, value=float(match.group(1)))
    match = re.search(rf"{name}\s*(>=|<=|!=|=|>|<)\s*{number}", question.lower())
    if not match:
        return None
    operator = {">=": "gte", "<=": "lte", "!=": "ne", "=": "eq", ">": "gt", "<": "lt"}[
        match.group(1)
    ]
    return FilterClause(column=column.name, operator=operator, value=float(match.group(2)))


def _numeric_range_bounds(
    question: str,
    column: ColumnManifest,
) -> tuple[float, float] | None:
    if not column.numeric:
        return None
    name = _column_expression(column.name)
    number = r"(-?\d+(?:\.\d+)?)"
    patterns = (
        rf"{name}\s*(?:이|가)?\s*{number}\s*(?:에서|부터|~|～)\s*"
        rf"{number}\s*(?:까지)?\s*(?:사이|범위)?",
        rf"{number}\s*(?:에서|부터|~|～)\s*{number}\s*(?:까지)?\s*"
        rf"(?:사이|범위)?(?:인|의)?\s*{name}",
    )
    match = next(
        (
            candidate
            for pattern in patterns
            if (candidate := re.search(pattern, question.lower()))
        ),
        None,
    )
    if match is None:
        return None
    return float(match.group(1)), float(match.group(2))


def _numeric_range_filters(
    question: str,
    column: ColumnManifest,
) -> list[FilterClause]:
    bounds = _numeric_range_bounds(question, column)
    if bounds is None:
        return []
    lower, upper = bounds
    if lower > upper:
        return []
    return [
        FilterClause(column=column.name, operator="gte", value=lower),
        FilterClause(column=column.name, operator="lte", value=upper),
    ]


def _categorical_filter(
    question: str,
    column: ColumnManifest,
    frame: pd.DataFrame,
) -> FilterClause | None:
    if column.numeric or column.unique_count > 200:
        return None
    normalized = question.lower()
    name = _column_expression(column.name)
    match = re.search(
        rf"{name}\s*(?:은|는|이|가|중|에서|==|=)?\s*['\"]?([^\s,'\"]+)",
        normalized,
    )
    requested = match.group(1) if match else ""
    for suffix in ("인", "만"):
        if requested.endswith(suffix):
            requested = requested[: -len(suffix)]
            break
    values = {str(value).lower(): value for value in frame[column.name].dropna().unique()}
    if requested in values:
        return FilterClause(column=column.name, operator="eq", value=str(values[requested]))
    if any(token in normalized for token in ("만", "인", "같은", "=")):
        mentioned_values = [
            key
            for key in values
            if _value_pattern(key).search(normalized)
        ]
        if len(mentioned_values) == 1:
            return FilterClause(
                column=column.name,
                operator="eq",
                value=str(values[mentioned_values[0]]),
            )
    return None


def _categorical_in_filter(
    question: str,
    column: ColumnManifest,
    frame: pd.DataFrame,
) -> FilterClause | None:
    if column.numeric or column.unique_count > 200:
        return None
    normalized = question.lower()
    if not re.search(r"(?:과|와|및|또는|,|\b또\b)", normalized):
        return None
    values = {str(value).lower(): value for value in frame[column.name].dropna().unique()}
    mentions: list[tuple[int, str]] = []
    for key in values:
        match = _value_pattern(key).search(normalized)
        if match:
            mentions.append((match.start(), key))
    if len(mentions) < 2:
        return None
    requested = [str(values[key]) for _, key in sorted(mentions)]
    return FilterClause(column=column.name, operator="in", value=requested)


def _categorical_exclusion_filters(
    question: str,
    column: ColumnManifest,
    frame: pd.DataFrame,
) -> list[FilterClause]:
    if column.numeric or column.unique_count > 200:
        return []
    normalized = question.lower()
    if not any(token in normalized for token in CATEGORICAL_EXCLUSION_TOKENS):
        return []
    values = {str(value).lower(): value for value in frame[column.name].dropna().unique()}
    return [
        FilterClause(column=column.name, operator="ne", value=str(values[key]))
        for key in values
        if _value_pattern(key).search(normalized)
    ]


def _datetime_filter(
    question: str,
    column: ColumnManifest,
    *,
    allow_implicit_column: bool = False,
) -> FilterClause | None:
    if not column.temporal:
        return None
    name = _column_expression(column.name)
    timestamp = r"(\d{4}-\d{2}-\d{2}(?:[t ]\d{2}:\d{2}(?::\d{2})?(?:z|[+-]\d{2}:?\d{2})?)?)"
    match = re.search(rf"{name}\s*(?:이|가)?\s*{timestamp}\s*(이후|부터|이전|까지)", question.lower())
    if not match:
        match = re.search(
            rf"{timestamp}\s*(이후|부터|이전|까지)(?:인|의)?\s*{name}",
            question.lower(),
        )
    if not match and allow_implicit_column:
        match = re.search(rf"{timestamp}\s*(이후|부터|이전|까지)", question.lower())
    if not match:
        return None
    operator = {"이후": "gte", "부터": "gte", "이전": "lte", "까지": "lte"}[match.group(2)]
    return FilterClause(column=column.name, operator=operator, value=match.group(1))


def _null_filter(question: str, column: ColumnManifest) -> FilterClause | None:
    if not _column_pattern(column.name).search(question.lower()):
        return None
    if any(token in question.lower() for token in ("결측", "비어", "누락", "null", "missing")):
        return FilterClause(column=column.name, operator="is_null")
    return None


def _filters(
    question: str,
    manifest: DatasetManifest,
    frame: pd.DataFrame,
) -> list[FilterClause]:
    items: list[FilterClause] = []
    temporal_columns = [column for column in manifest.columns if column.temporal]
    for column in manifest.columns:
        exclusions = _categorical_exclusion_filters(question, column, frame)
        if exclusions:
            items.extend(exclusions)
            continue
        ranges = _numeric_range_filters(question, column)
        if ranges:
            items.extend(ranges)
            continue
        item = (
            _null_filter(question, column)
            or _numeric_filter(question, column)
            or _datetime_filter(question, column)
            or _categorical_in_filter(question, column, frame)
            or _categorical_filter(question, column, frame)
        )
        if item is not None:
            items.append(item)
    if not any(item.column in {column.name for column in temporal_columns} for item in items) and len(temporal_columns) == 1:
        implicit_date = _datetime_filter(
            question,
            temporal_columns[0],
            allow_implicit_column=True,
        )
        if implicit_date is not None:
            items.append(implicit_date)
    return items


def _missing_row_request_plan(
    question: str,
    manifest: DatasetManifest,
) -> PlanningOutcome | None:
    if not MISSING_ROW_PATTERN.search(question):
        return None
    missing_columns = [
        column for column in manifest.columns if column.missing_count > 0
    ]
    if not missing_columns:
        return PlanningOutcome(status="not_applicable", message=PROFILE_REQUEST_MESSAGE)
    mentioned = set(_mentioned_columns(question, manifest))
    selected = [column for column in missing_columns if column.name in mentioned]
    if not selected and len(missing_columns) == 1:
        selected = missing_columns
    if len(selected) != 1:
        names = ", ".join(column.name for column in missing_columns)
        return PlanningOutcome(
            status="clarification",
            message=(
                f"결측이 있는 컬럼이 여러 개입니다: {names}. "
                "조회할 컬럼명을 하나 지정해 주세요."
            ),
        )
    column = selected[0]
    return PlanningOutcome(
        status="planned",
        message="결측 행 조회 계획을 생성했습니다.",
        plan=AnalysisPlan(
            operation="select",
            filters=[FilterClause(column=column.name, operator="is_null")],
            limit=100,
            rationale=f"{column.name} 컬럼의 결측 행 조회",
        ),
    )


def _with_default_summary_exclusions(
    filters: list[FilterClause],
    frame: pd.DataFrame,
    question: str,
) -> list[FilterClause]:
    """Exclude detected summary rows unless the request selected that value explicitly."""

    if _is_summary_inclusion_request(question):
        return list(filters)
    combined = list(filters)
    existing = {(item.column, item.operator, str(item.value).casefold()) for item in filters}
    _, column_labels = summary_row_details(frame)
    for column, label in column_labels:
        normalized = label.casefold()
        explicitly_selected = any(
            item_column == column
            and operator in {"eq", "in"}
            and value == normalized
            for item_column, operator, value in existing
        )
        if explicitly_selected or (column, "ne", normalized) in existing:
            continue
        combined.append(FilterClause(column=column, operator="ne", value=label))
    return combined


def _metric_column(
    mentioned: list[str],
    groups: list[str],
    manifest: DatasetManifest,
) -> str | None:
    lookup = {column.name: column for column in manifest.columns}
    candidates = [name for name in mentioned if name not in groups]
    numeric = [name for name in candidates if lookup[name].numeric]
    return numeric[-1] if numeric else candidates[-1] if candidates else None


def _aggregate_plan(
    question: str,
    operation: str,
    manifest: DatasetManifest,
    frame: pd.DataFrame,
) -> PlanningOutcome:
    mentioned = _mentioned_columns(question, manifest)
    groups = _group_columns(question, manifest)
    parsed_filters = _filters(question, manifest, frame)
    lookup = {column.name: column for column in manifest.columns}
    filter_columns = {item.column for item in parsed_filters}
    non_filter_mentions = [name for name in mentioned if name not in filter_columns]
    metric_mentions = (
        mentioned
        if operation == "correlation" or not non_filter_mentions
        else non_filter_mentions
    )
    numeric_targets = [
        name
        for name in metric_mentions
        if name not in groups and lookup[name].numeric
    ]
    if operation not in {"correlation", "share", "count"} and len(numeric_targets) > 1:
        return PlanningOutcome(
            status="clarification",
            message=(
                "수치 컬럼이 여러 개 지정되었습니다: "
                + ", ".join(numeric_targets)
                + ". 한 번에 분석할 수치 컬럼 하나를 선택해 주세요."
            ),
        )
    target = _metric_column(metric_mentions, groups, manifest)
    if operation == "share":
        if not groups:
            return PlanningOutcome(
                status="clarification",
                message="비율을 계산할 그룹 컬럼을 ‘status별 비율’처럼 알려주세요.",
            )
        plan = AnalysisPlan(
            operation="aggregate",
            filters=_with_default_summary_exclusions(
                parsed_filters, frame, question
            ),
            group_by=groups,
            metrics=[MetricSpec(operation="share", alias="share_percent")],
            order_by=[SortSpec(column="share_percent", direction="desc")],
            limit=100,
            rationale=f"{', '.join(groups)}별 전체 행 대비 구성비(%)",
        )
        return PlanningOutcome(status="planned", message="구성비 분석 계획을 생성했습니다.", plan=plan)
    if operation == "correlation":
        numeric = [name for name in mentioned if name not in groups and lookup[name].numeric]
        if len(numeric) != 2:
            return PlanningOutcome(
                status="clarification",
                message="상관계수를 계산할 수치 컬럼 2개를 질문에 포함해 주세요.",
            )
        metric = MetricSpec(
            operation="correlation",
            column=numeric[0],
            secondary_column=numeric[1],
            alias="correlation_value",
        )
        plan = AnalysisPlan(
            operation="aggregate",
            filters=_with_default_summary_exclusions(
                parsed_filters,
                frame,
                question,
            ),
            group_by=groups,
            metrics=[metric],
            limit=100 if groups else 1,
            rationale=f"{numeric[0]}과 {numeric[1]} Pearson 상관계수",
        )
        return PlanningOutcome(status="planned", message="상관 분석 계획을 생성했습니다.", plan=plan)
    if operation not in {"count"} and target is None:
        numeric = [column.name for column in manifest.columns if column.numeric]
        if len(numeric) != 1:
            return PlanningOutcome(
                status="clarification",
                message="어느 수치 컬럼을 분석할지 컬럼명을 질문에 포함해 주세요.",
            )
        target = numeric[0]
    if operation in NUMERIC_ONLY_OPERATIONS and target is not None and not lookup[target].numeric:
        return PlanningOutcome(
            status="clarification",
            message=(
                f"{target} 컬럼은 수치형으로 인식되지 않았습니다. "
                "통화기호·퍼센트·천단위 구분자를 정리한 수치 컬럼을 지정해 주세요."
            ),
        )
    alias = "row_count" if operation == "count" and target is None else f"{operation}_value"
    metric = MetricSpec(operation=operation, column=target, alias=alias)
    rank = _rank_request(question)
    sort_direction = _sort_direction_request(question)
    limit = rank[0] if rank else 100
    direction = rank[1] if rank else sort_direction
    order = [SortSpec(column=alias, direction=direction)] if direction else []
    plan = AnalysisPlan(
        operation="aggregate",
        filters=_with_default_summary_exclusions(
            parsed_filters,
            frame,
            question,
        ),
        group_by=groups,
        metrics=[metric],
        order_by=order,
        limit=limit,
        rationale=f"{', '.join(groups) or '전체'} 기준 {operation} 집계",
    )
    return PlanningOutcome(status="planned", message="집계 분석 계획을 생성했습니다.", plan=plan)


def _trend_plan(
    question: str,
    manifest: DatasetManifest,
    frame: pd.DataFrame,
) -> PlanningOutcome:
    lookup = {column.name: column for column in manifest.columns}
    mentioned = _mentioned_columns(question, manifest)
    explicit_groups = _group_columns(question, manifest)
    temporal = [name for name in explicit_groups if lookup[name].temporal]
    if not temporal:
        temporal = [name for name in mentioned if lookup[name].temporal]
    if not temporal:
        temporal = [column.name for column in manifest.columns if column.temporal]
    if len(temporal) != 1:
        return PlanningOutcome(
            status="clarification",
            message="추이를 계산할 날짜 컬럼을 질문에 포함해 주세요.",
        )
    numeric = [name for name in mentioned if lookup[name].numeric]
    if not numeric:
        numeric = [column.name for column in manifest.columns if column.numeric]
    if len(numeric) != 1:
        return PlanningOutcome(
            status="clarification",
            message="추이를 계산할 수치 컬럼을 질문에 포함해 주세요.",
        )
    plan = AnalysisPlan(
        operation="aggregate",
        filters=_with_default_summary_exclusions(
            _filters(question, manifest, frame), frame, question
        ),
        group_by=temporal,
        metrics=[MetricSpec(operation="sum", column=numeric[0], alias="sum_value")],
        order_by=[SortSpec(column=temporal[0], direction="asc")],
        limit=min(manifest.row_count, 200),
        rationale=f"{temporal[0]} 시간 순서별 {numeric[0]} 합계 추이",
    )
    return PlanningOutcome(status="planned", message="시간 추이 분석 계획을 생성했습니다.", plan=plan)


def _most_frequent_plan(
    question: str,
    manifest: DatasetManifest,
    frame: pd.DataFrame,
) -> PlanningOutcome:
    lookup = {column.name: column for column in manifest.columns}
    mentioned = [
        name for name in _mentioned_columns(question, manifest) if not lookup[name].numeric
    ]
    if len(mentioned) != 1:
        return PlanningOutcome(
            status="clarification",
            message="가장 빈번한 값을 찾을 범주 컬럼을 질문에 포함해 주세요.",
        )
    plan = AnalysisPlan(
        operation="aggregate",
        filters=_with_default_summary_exclusions(
            _filters(question, manifest, frame), frame, question
        ),
        group_by=mentioned,
        metrics=[MetricSpec(operation="count", alias="row_count")],
        order_by=[SortSpec(column="row_count", direction="desc")],
        limit=1,
        rationale=f"{mentioned[0]}에서 가장 빈번한 값",
    )
    return PlanningOutcome(status="planned", message="최빈값 분석 계획을 생성했습니다.", plan=plan)


def _select_plan(
    question: str,
    manifest: DatasetManifest,
    frame: pd.DataFrame,
) -> PlanningOutcome:
    mentioned = _mentioned_columns(question, manifest)
    filters = _filters(question, manifest, frame)
    rank = _rank_request(question)
    sort_direction = _sort_direction_request(question)
    if rank:
        filters = _with_default_summary_exclusions(filters, frame, question)
    limit = rank[0] if rank else 100
    order: list[SortSpec] = []
    if rank or sort_direction:
        numeric = [column.name for column in manifest.columns if column.name in mentioned and column.numeric]
        if not numeric:
            return PlanningOutcome(
                status="clarification",
                message="순위나 정렬을 적용할 수치 컬럼명을 질문에 포함해 주세요.",
            )
        order = [
            SortSpec(
                column=numeric[-1],
                direction=rank[1] if rank else sort_direction,
            )
        ]
    select_columns: list[str] = []
    if len(mentioned) >= 2 and not filters and re.search(r"(?:만\s*(?:보여|조회)|only)", question.lower()):
        select_columns = mentioned
    plan = AnalysisPlan(
        operation="select",
        select_columns=select_columns,
        filters=filters,
        order_by=order,
        limit=limit,
        rationale="조건에 맞는 행을 조회하고 요청한 순서와 건수를 적용",
    )
    return PlanningOutcome(status="planned", message="행 조회 계획을 생성했습니다.", plan=plan)


def _is_self_contained_analysis(
    question: str,
    manifest: DatasetManifest,
    frame: pd.DataFrame,
) -> bool:
    """Return whether the question can define a new plan without prior state."""

    mentioned = _mentioned_columns(question, manifest)
    groups = _group_columns(question, manifest)
    lookup = {column.name: column for column in manifest.columns}
    operation = _metric_operation(question, manifest)
    if operation == "correlation" or RELATIONSHIP_QUESTION_PATTERN.search(question):
        return len([name for name in mentioned if lookup[name].numeric]) == 2
    if operation == "share":
        return bool(groups)
    if operation == "count":
        return bool(groups or mentioned)
    if operation is not None:
        return _metric_column(mentioned, groups, manifest) is not None
    if TREND_QUESTION_PATTERN.search(question):
        return bool(
            [name for name in mentioned if lookup[name].temporal]
            and [name for name in mentioned if lookup[name].numeric]
        )
    if MOST_FREQUENT_PATTERN.search(question):
        return len([name for name in mentioned if not lookup[name].numeric]) == 1
    filters = _filters(question, manifest, frame)
    rank = _rank_request(question)
    sort_direction = _sort_direction_request(question)
    if (rank or sort_direction) and any(lookup[name].numeric for name in mentioned):
        return True
    return bool(filters and any(token in question for token in SELECT_PATTERNS))


def _follow_up_plan(
    question: str,
    previous: AnalysisPlan,
    manifest: DatasetManifest,
    frame: pd.DataFrame,
) -> PlanningOutcome | None:
    rank = _rank_request(question)
    plain_limit = _plain_follow_up_limit(question) if rank is None else None
    sort_direction = _sort_direction_request(question)
    operation = _metric_operation(question, manifest)
    groups = _group_columns(question, manifest)
    new_filters = _filters(question, manifest, frame)
    mentioned_columns = _mentioned_columns(question, manifest)
    lookup = {column.name: column for column in manifest.columns}
    retarget_columns = [
        name
        for name in mentioned_columns
        if lookup[name].numeric and name not in groups
    ]
    retarget_request = bool(
        retarget_columns
        and re.search(r"(?:이번엔|대신|대상|지표|컬럼|로\s*(?:해|바꿔|변경))", question)
    )
    include_summary = _is_summary_inclusion_request(question)
    clear_filter_request = any(
        token in question
        for token in (
            "조건 없이",
            "조건 제거",
            "조건 빼",
            "조건 없애",
            "필터 제거",
            "필터 빼",
            "필터 없애",
            "전체로",
        )
    )
    clear_filter_columns = (
        _mentioned_columns(question, manifest) if clear_filter_request else []
    )
    clear_filters = clear_filter_request and not clear_filter_columns
    if not any(
        (
            rank,
            plain_limit,
            sort_direction,
            operation,
            groups,
            new_filters,
            retarget_request,
            clear_filters,
            clear_filter_columns,
            include_summary,
        )
    ):
        return None
    plan = previous.model_copy(deep=True)
    if clear_filters:
        plan.filters = []
    elif clear_filter_columns:
        plan.filters = [
            item for item in plan.filters if item.column not in set(clear_filter_columns)
        ]
    if include_summary:
        _, column_labels = summary_row_details(frame)
        summary_values = {
            (column, label.casefold()) for column, label in column_labels
        }
        plan.filters = [
            item
            for item in plan.filters
            if not (
                item.operator == "ne"
                and (item.column, str(item.value).casefold()) in summary_values
            )
        ]
    if new_filters:
        replaced_columns = {item.column for item in new_filters}
        plan.filters = [
            existing for existing in plan.filters if existing.column not in replaced_columns
        ]
        plan.filters.extend(new_filters)
    if retarget_request and operation is None:
        if plan.operation != "aggregate" or not plan.metrics:
            return PlanningOutcome(
                status="clarification",
                message="수치 컬럼 변경은 기존 집계 결과에서만 지원합니다.",
            )
        if len(retarget_columns) != 1 or plan.metrics[0].operation in {"share", "correlation"}:
            return PlanningOutcome(
                status="clarification",
                message="변경할 수치 컬럼 하나와 집계 방법을 함께 알려주세요.",
            )
        previous_metric = plan.metrics[0]
        plan.metrics = [
            MetricSpec(
                operation=previous_metric.operation,
                column=retarget_columns[0],
                alias=previous_metric.alias,
            )
        ]
    if groups:
        if plan.operation != "aggregate":
            return PlanningOutcome(
                status="clarification",
                message="그룹 기준 변경은 집계 결과에서만 지원합니다.",
            )
        plan.group_by = groups
    if operation is not None:
        if plan.operation != "aggregate" or not plan.metrics:
            return PlanningOutcome(
                status="clarification",
                message="집계 방법 변경은 기존 집계 결과에서만 지원합니다.",
            )
        old_alias = plan.metrics[0].alias
        mentioned = _mentioned_columns(question, manifest)
        explicit_target = _metric_column(
            mentioned,
            groups or plan.group_by,
            manifest,
        )
        target = explicit_target or plan.metrics[0].column
        if operation == "correlation":
            numeric = [
                name
                for name in mentioned
                if next(column for column in manifest.columns if column.name == name).numeric
            ]
            if len(numeric) != 2:
                return PlanningOutcome(
                    status="clarification",
                    message="상관계수를 계산할 수치 컬럼 2개를 질문에 포함해 주세요.",
                )
            metric = MetricSpec(
                operation="correlation",
                column=numeric[0],
                secondary_column=numeric[1],
                alias="correlation_value",
            )
        elif operation == "share":
            if not plan.group_by:
                return PlanningOutcome(
                    status="clarification",
                    message="비율로 바꾸려면 먼저 그룹 기준을 알려주세요.",
                )
            metric = MetricSpec(operation="share", alias="share_percent")
        else:
            if operation != "count" and target is None:
                return PlanningOutcome(
                    status="clarification",
                    message="변경할 집계의 수치 컬럼을 알려주세요.",
                )
            if (
                operation in NUMERIC_ONLY_OPERATIONS
                and target is not None
                and not lookup[target].numeric
            ):
                return PlanningOutcome(
                    status="clarification",
                    message=f"{target} 컬럼은 수치형이 아니어서 {operation} 집계로 바꿀 수 없습니다.",
                )
            metric = MetricSpec(
                operation=operation,
                column=None if operation == "count" and target is None else target,
                alias="row_count" if operation == "count" and target is None else f"{operation}_value",
            )
        plan.metrics = [metric]
        if operation == "share":
            plan.order_by = [SortSpec(column="share_percent", direction="desc")]
        else:
            plan.order_by = [
                SortSpec(
                    column=metric.alias if item.column == old_alias else item.column,
                    direction=item.direction,
                )
                for item in plan.order_by
            ]
    requested_limit = rank[0] if rank else plain_limit
    if requested_limit is not None:
        plan.limit = requested_limit
        direction = rank[1] if rank else (plan.order_by[0].direction if plan.order_by else "desc")
        if plan.operation == "aggregate":
            plan.order_by = [SortSpec(column=plan.metrics[0].alias, direction=direction)]
        elif plan.order_by:
            plan.order_by[0].direction = direction
        else:
            mentioned = _mentioned_columns(question, manifest)
            numeric = [
                column.name
                for column in manifest.columns
                if column.numeric and column.name in mentioned
            ]
            if not numeric:
                return PlanningOutcome(
                    status="clarification",
                    message="순서를 정할 수치 컬럼을 알려주세요.",
                )
            plan.order_by = [SortSpec(column=numeric[-1], direction=direction)]
    if sort_direction is not None:
        if plan.operation == "aggregate":
            plan.order_by = [
                SortSpec(column=plan.metrics[0].alias, direction=sort_direction)
            ]
        elif plan.order_by:
            plan.order_by[0].direction = sort_direction
        else:
            mentioned = _mentioned_columns(question, manifest)
            numeric = [
                column.name
                for column in manifest.columns
                if column.numeric and column.name in mentioned
            ]
            if not numeric:
                return PlanningOutcome(
                    status="clarification",
                    message="정렬할 수치 컬럼을 알려주세요.",
                )
            plan.order_by = [SortSpec(column=numeric[-1], direction=sort_direction)]
    plan.rationale = "이전 검증 plan의 집계·그룹·필터·순위 조건을 제한적으로 수정"
    return PlanningOutcome(status="planned", message="이전 분석 조건을 수정했습니다.", plan=plan)


def plan_analysis(
    question: str,
    manifest: DatasetManifest,
    frame: pd.DataFrame,
    previous_plan: AnalysisPlan | None = None,
) -> PlanningOutcome:
    """Create a bounded plan or ask for clarification without calculating values."""

    normalized = " ".join(question.lower().split())
    if _is_analysis_reset_request(normalized):
        return PlanningOutcome(
            status="not_applicable",
            message=ANALYSIS_RESET_REQUEST_MESSAGE,
        )
    if _is_conversation_request(normalized):
        return PlanningOutcome(
            status="not_applicable",
            message=CONVERSATION_REQUEST_MESSAGE,
        )
    ambiguous_aliases = _ambiguous_column_aliases(normalized, manifest)
    if ambiguous_aliases:
        return PlanningOutcome(
            status="clarification",
            message=(
                "컬럼 별칭이 여러 원본 컬럼과 겹칩니다: "
                + ", ".join(ambiguous_aliases)
                + ". 실제 컬럼명을 사용해 주세요."
            ),
        )
    normalized = _normalize_column_aliases(normalized, manifest)
    reversed_ranges = [
        (column.name, bounds)
        for column in manifest.columns
        if (bounds := _numeric_range_bounds(normalized, column)) is not None
        and bounds[0] > bounds[1]
    ]
    if reversed_ranges:
        column, (lower, upper) = reversed_ranges[0]
        return PlanningOutcome(
            status="clarification",
            message=(
                f"{column} 범위의 시작값 {lower:g}이 종료값 {upper:g}보다 큽니다. "
                "작은 값부터 큰 값 순서로 범위를 다시 지정해 주세요."
            ),
        )
    percentile_rank = PERCENTILE_RANK_PATTERN.search(normalized)
    if percentile_rank:
        percentage = percentile_rank.group(0)
        return PlanningOutcome(
            status="clarification",
            message=(
                f"‘{percentage}’는 행 개수와 백분위 중 어느 의미인지 안전하게 구분해야 합니다. "
                "현재는 ‘상위 10개’처럼 행 개수로 지정해 주세요."
            ),
        )
    if DERIVED_THRESHOLD_PATTERN.search(normalized):
        return PlanningOutcome(
            status="clarification",
            message=(
                "현재는 평균을 먼저 계산한 뒤 그 값과 각 행을 비교하는 파생 조건을 "
                "한 문장으로 실행하지 않습니다. 먼저 평균을 확인한 뒤 숫자 조건으로 "
                "이어 질문해 주세요."
            ),
        )
    numeric_mentions = [
        name
        for name in _mentioned_columns(normalized, manifest)
        if next(column for column in manifest.columns if column.name == name).numeric
    ]
    if (
        len(numeric_mentions) >= 2
        and "비율" in normalized
        and re.search(r"(?:대비|나눈|/)", normalized)
    ):
        return PlanningOutcome(
            status="clarification",
            message=(
                "두 수치 컬럼의 파생 비율은 아직 직접 계산하지 않습니다. "
                "분자·분모와 0으로 나누는 행의 처리 기준을 확인할 수 있는 "
                "파생 컬럼 기능이 필요합니다."
            ),
        )
    missing_rows = _missing_row_request_plan(normalized, manifest)
    if missing_rows is not None:
        return missing_rows
    metric_operations = _metric_operations(normalized, manifest)
    if len(metric_operations) > 1:
        return PlanningOutcome(
            status="clarification",
            message=(
                "집계 방법이 여러 개 지정되었습니다: "
                + ", ".join(metric_operations)
                + ". 먼저 하나를 선택해 주세요."
            ),
        )
    if previous_plan is not None:
        if _is_result_interpretation_request(normalized):
            return PlanningOutcome(
                status="planned",
                message=RESULT_INTERPRETATION_MESSAGE,
                plan=previous_plan.model_copy(deep=True),
            )
        self_contained = _is_self_contained_analysis(normalized, manifest, frame)
        if _is_explicit_follow_up(normalized) or not self_contained:
            follow_up = _follow_up_plan(normalized, previous_plan, manifest, frame)
            if follow_up is not None and (
                follow_up.status == "planned" or not self_contained
            ):
                return follow_up
    operation = metric_operations[0] if metric_operations else None
    if operation is not None:
        return _aggregate_plan(normalized, operation, manifest, frame)
    if RELATIONSHIP_QUESTION_PATTERN.search(normalized):
        return _aggregate_plan(normalized, "correlation", manifest, frame)
    if TREND_QUESTION_PATTERN.search(normalized):
        return _trend_plan(normalized, manifest, frame)
    if MOST_FREQUENT_PATTERN.search(normalized):
        return _most_frequent_plan(normalized, manifest, frame)
    filters = _filters(normalized, manifest, frame)
    rank = _rank_request(normalized)
    sort_direction = _sort_direction_request(normalized)
    if _is_overview_request(normalized) and not filters and not rank:
        return PlanningOutcome(status="not_applicable", message=OVERVIEW_REQUEST_MESSAGE)
    if _is_profile_request(normalized) and not filters and not rank:
        return PlanningOutcome(status="not_applicable", message=PROFILE_REQUEST_MESSAGE)
    if _is_capability_request(normalized) and not filters and not rank:
        return PlanningOutcome(status="not_applicable", message=CAPABILITY_REQUEST_MESSAGE)
    if filters or rank or sort_direction or any(token in normalized for token in SELECT_PATTERNS):
        return _select_plan(normalized, manifest, frame)
    return PlanningOutcome(
        status="clarification",
        message=(
            "요청을 현재 데이터의 실행 가능한 분석으로 해석하지 못했습니다. "
            "‘할 수 있는 분석은?’이라고 묻거나 비교 컬럼·수치·집계 방법을 알려주세요."
        ),
    )
