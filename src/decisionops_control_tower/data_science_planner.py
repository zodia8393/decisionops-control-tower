"""Natural-language routing into closed advanced and predictive contracts."""

from __future__ import annotations

import re
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict

from decisionops_control_tower.advanced_analytics import AdvancedAnalysisPlan
from decisionops_control_tower.analysis_engine import AnalysisPlan, DatasetManifest
from decisionops_control_tower.analysis_planner import (
    _ambiguous_column_aliases,
    _filters,
    _group_columns,
    _mentioned_columns,
    _normalize_column_aliases,
    _with_default_summary_exclusions,
)
from decisionops_control_tower.prediction_engine import PredictionPlan


PREDICTION_PATTERN = re.compile(
    r"(?:예측|forecast|predict|prediction|분류\s*모델|classification|회귀\s*모델|regression)",
    re.I,
)
FORECAST_PATTERN = re.compile(
    r"(?:시계열\s*예측|미래|향후|forecast|다음\s*\d+|\d+\s*(?:일|주|개월|기간)\s*(?:뒤|예측))",
    re.I,
)
CLASSIFICATION_PATTERN = re.compile(r"(?:분류|classification|classify|확률\s*예측)", re.I)
REGRESSION_PATTERN = re.compile(r"(?:회귀|regression)", re.I)
PREDICTION_GUIDANCE_PATTERN = re.compile(
    r"(?:하려면|하기\s*위해|무엇이?\s*필요|뭐가?\s*필요|필요한\s*(?:데이터|조건|요건)|"
    r"(?:조건|요건|준비).*(?:알려|설명)|how\s+to|requirements?)",
    re.I,
)
ADVANCED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("outliers", re.compile(r"(?:이상치|outliers?|IQR|box\s*plot|박스\s*플롯)", re.I)),
    (
        "group_comparison",
        re.compile(
            r"(?:유의한?\s*차이|차이\s*검정|가설\s*검정|t[- ]?test|anova|mann[- ]?whitney|kruskal|효과\s*크기|effect\s*size|그룹\s*비교)",
            re.I,
        ),
    ),
    (
        "relationship",
        re.compile(
            r"(?:pearson|spearman|산점도|scatter|회귀선|선형\s*관계|r\s*제곱|r[- ]?squared|상관.*p[- ]?value)",
            re.I,
        ),
    ),
    (
        "time_series",
        re.compile(
            r"(?:이동\s*평균|rolling|변화율|증감|resampl|일별로\s*재집계|주별로\s*재집계|월별로\s*재집계|추세\s*기울기|시계열\s*탐색)",
            re.I,
        ),
    ),
    (
        "distribution",
        re.compile(r"(?:히스토그램|histogram|왜도|첨도|정규성|분포\s*(?:분석|확인|보여))", re.I),
    ),
)


class DataSciencePlanningOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["planned", "clarification", "not_applicable"]
    mode: Literal["advanced", "prediction"] | None = None
    message: str
    advanced_plan: AdvancedAnalysisPlan | None = None
    prediction_plan: PredictionPlan | None = None


def _clarify(message: str, mode: Literal["advanced", "prediction"]) -> DataSciencePlanningOutcome:
    return DataSciencePlanningOutcome(status="clarification", mode=mode, message=message)


def _horizon(question: str, default: int = 7) -> int:
    match = re.search(r"(?:향후|다음)?\s*(\d{1,2})\s*(?:일|주|개월|기간|step)", question, re.I)
    return max(1, min(int(match.group(1)), 30)) if match else default


def _confidence(question: str, default: float = 0.95) -> float:
    match = re.search(r"(8\d|9\d(?:\.\d+)?)\s*%\s*(?:신뢰|confidence)?", question, re.I)
    return float(match.group(1)) / 100.0 if match else default


def _target_column(
    question: str, mentioned: list[str], manifest: DatasetManifest, task: str
) -> str | None:
    lowered = question.casefold()
    positions: list[tuple[int, str]] = []
    intent = PREDICTION_PATTERN.search(lowered)
    intent_position = intent.start() if intent else len(lowered)
    for name in mentioned:
        position = lowered.find(name.casefold())
        if 0 <= position <= intent_position:
            positions.append((position, name))
    if positions:
        return sorted(positions)[-1][1]
    candidates = [
        column.name
        for column in manifest.columns
        if (task != "regression" or column.numeric) and not column.temporal
    ]
    return candidates[0] if len(candidates) == 1 else None


def _prediction_follow_up(
    question: str,
    previous: PredictionPlan,
    manifest: DatasetManifest,
) -> DataSciencePlanningOutcome | None:
    normalized = question.casefold()
    if not re.search(r"(?:바꿔|변경|수정|제외|빼|추가|더|기간|horizon|feature|변수)", normalized):
        return None
    updates: dict[str, object] = {}
    horizon_match = re.search(r"(\d{1,2})\s*(?:일|기간|step)", normalized)
    if horizon_match and previous.task == "forecasting":
        updates["horizon"] = max(1, min(int(horizon_match.group(1)), 30))
    mentioned = _mentioned_columns(_normalize_column_aliases(normalized, manifest), manifest)
    if mentioned and previous.task != "forecasting":
        features = list(previous.features)
        if re.search(r"(?:제외|빼|remove)", normalized):
            features = [name for name in features if name not in mentioned]
        elif re.search(r"(?:추가|넣|add)", normalized):
            features.extend(name for name in mentioned if name != previous.target and name not in features)
        updates["features"] = features
    if not updates:
        return _clarify("변경할 horizon 또는 feature 컬럼을 명시해 주세요.", "prediction")
    plan = PredictionPlan.model_validate({**previous.model_dump(), **updates})
    return DataSciencePlanningOutcome(
        status="planned", mode="prediction", message="이전 예측 계획의 조건을 수정했습니다.", prediction_plan=plan
    )


def _advanced_follow_up(
    question: str, previous: AdvancedAnalysisPlan
) -> DataSciencePlanningOutcome | None:
    normalized = question.casefold()
    updates: dict[str, object] = {}
    if previous.operation == "distribution":
        bins = re.search(r"(?:bin|구간)\s*(?:을|를)?\s*(\d{1,2})", normalized)
        if bins:
            updates["bins"] = max(5, min(int(bins.group(1)), 50))
    if previous.operation == "time_series":
        window = re.search(r"(?:이동\s*평균|rolling|window)\s*(\d{1,2})", normalized)
        if window:
            updates["rolling_window"] = max(2, min(int(window.group(1)), 90))
    confidence = re.search(r"(8\d|9\d(?:\.\d+)?)\s*%", normalized)
    if confidence:
        updates["confidence_level"] = float(confidence.group(1)) / 100.0
    if not updates:
        return None
    plan = AdvancedAnalysisPlan.model_validate({**previous.model_dump(), **updates})
    return DataSciencePlanningOutcome(
        status="planned", mode="advanced", message="이전 심화 분석 계획의 조건을 수정했습니다.", advanced_plan=plan
    )


def _plan_prediction(
    question: str,
    manifest: DatasetManifest,
    frame: pd.DataFrame,
) -> DataSciencePlanningOutcome:
    ambiguous = _ambiguous_column_aliases(question, manifest)
    if ambiguous:
        return _clarify("컬럼 별칭이 모호합니다: " + ", ".join(ambiguous), "prediction")
    mentioned = _mentioned_columns(question, manifest)
    lookup = {column.name: column for column in manifest.columns}
    forecast = bool(FORECAST_PATTERN.search(question))
    if forecast:
        task = "forecasting"
    elif CLASSIFICATION_PATTERN.search(question):
        task = "classification"
    elif REGRESSION_PATTERN.search(question):
        task = "regression"
    else:
        explicit = mentioned[-1] if mentioned else None
        task = "regression" if explicit and lookup[explicit].numeric else "classification"
    target = _target_column(question, mentioned, manifest, task)
    if target is None:
        return _clarify("예측할 target 컬럼을 질문에 포함해 주세요.", "prediction")
    time_column = None
    if task == "forecasting":
        temporal = [name for name in mentioned if lookup[name].temporal]
        if not temporal:
            temporal = [column.name for column in manifest.columns if column.temporal]
        if len(temporal) != 1:
            return _clarify("forecast에 사용할 시간 컬럼을 하나 명시해 주세요.", "prediction")
        time_column = temporal[0]
    features = [
        name
        for name in mentioned
        if name not in {target, time_column}
    ]
    filters = _with_default_summary_exclusions(
        _filters(question, manifest, frame), frame, question
    )
    plan = PredictionPlan(
        task=task,
        target=target,
        features=[] if task == "forecasting" else features,
        filters=filters,
        time_column=time_column,
        split_strategy="chronological" if task == "forecasting" else "auto",
        horizon=_horizon(question),
        confidence_level=_confidence(question, 0.9),
        rationale=f"{target} {task} 요청을 baseline 비교가 있는 제한된 예측 계획으로 변환",
    )
    return DataSciencePlanningOutcome(
        status="planned", mode="prediction", message="검증 가능한 예측 계획을 생성했습니다.", prediction_plan=plan
    )


def _advanced_operation(question: str) -> str | None:
    for operation, pattern in ADVANCED_PATTERNS:
        if pattern.search(question):
            return operation
    return None


def _plan_advanced(
    question: str,
    manifest: DatasetManifest,
    frame: pd.DataFrame,
    operation: str,
    previous_analysis_plan: AnalysisPlan | None = None,
) -> DataSciencePlanningOutcome:
    ambiguous = _ambiguous_column_aliases(question, manifest)
    if ambiguous:
        return _clarify("컬럼 별칭이 모호합니다: " + ", ".join(ambiguous), "advanced")
    mentioned = _mentioned_columns(question, manifest)
    lookup = {column.name: column for column in manifest.columns}
    numeric = [name for name in mentioned if lookup[name].numeric]
    if (
        operation == "relationship"
        and len(numeric) < 2
        and previous_analysis_plan is not None
        and previous_analysis_plan.operation == "aggregate"
        and previous_analysis_plan.metrics
        and previous_analysis_plan.metrics[0].operation == "correlation"
    ):
        previous_metric = previous_analysis_plan.metrics[0]
        inherited = [previous_metric.column, previous_metric.secondary_column]
        numeric = [
            name
            for name in inherited
            if name is not None and name in lookup and lookup[name].numeric
        ]
    group_by = None
    time_column = None
    if operation == "relationship":
        if len(numeric) != 2:
            return _clarify("관계를 분석할 수치 컬럼 두 개를 명시해 주세요.", "advanced")
        columns = numeric
    else:
        if len(numeric) != 1:
            return _clarify("심화 분석에 사용할 수치 컬럼 하나를 명시해 주세요.", "advanced")
        columns = numeric
    if operation == "group_comparison":
        groups = _group_columns(question, manifest)
        if not groups:
            groups = [name for name in mentioned if not lookup[name].numeric and not lookup[name].temporal]
        if len(groups) != 1:
            return _clarify("비교할 group 컬럼 하나를 ‘컬럼별’ 형식으로 명시해 주세요.", "advanced")
        group_by = groups[0]
    if operation == "time_series":
        temporal = [name for name in mentioned if lookup[name].temporal]
        if not temporal:
            temporal = [column.name for column in manifest.columns if column.temporal]
        if len(temporal) != 1:
            return _clarify("시계열 탐색에 사용할 시간 컬럼 하나를 명시해 주세요.", "advanced")
        time_column = temporal[0]
    method: Literal["auto", "parametric", "nonparametric"] = "auto"
    if re.search(r"(?:mann|kruskal|비모수|nonparametric)", question, re.I):
        method = "nonparametric"
    elif re.search(r"(?:t[- ]?test|anova|모수|parametric)", question, re.I):
        method = "parametric"
    frequency: Literal["raw", "daily", "weekly", "monthly"] = "raw"
    if re.search(r"(?:일별|daily)", question, re.I):
        frequency = "daily"
    elif re.search(r"(?:주별|weekly)", question, re.I):
        frequency = "weekly"
    elif re.search(r"(?:월별|monthly)", question, re.I):
        frequency = "monthly"
    window = re.search(r"(?:이동\s*평균|rolling|window)\s*(\d{1,2})", question, re.I)
    bins = re.search(r"(?:bin|구간)\s*(?:을|를)?\s*(\d{1,2})", question, re.I)
    plan = AdvancedAnalysisPlan(
        operation=operation,
        columns=columns,
        filters=_with_default_summary_exclusions(
            _filters(question, manifest, frame), frame, question
        ),
        group_by=group_by,
        time_column=time_column,
        test_method=method,
        confidence_level=_confidence(question),
        bins=max(5, min(int(bins.group(1)), 50)) if bins else 10,
        rolling_window=max(2, min(int(window.group(1)), 90)) if window else 3,
        frequency=frequency,
        rationale=f"{operation} 심화 분석 요청을 제한된 통계 계획으로 변환",
    )
    return DataSciencePlanningOutcome(
        status="planned", mode="advanced", message="검증 가능한 심화 분석 계획을 생성했습니다.", advanced_plan=plan
    )


def plan_data_science(
    question: str,
    manifest: DatasetManifest,
    frame: pd.DataFrame,
    previous_advanced_plan: AdvancedAnalysisPlan | None = None,
    previous_prediction_plan: PredictionPlan | None = None,
    previous_analysis_plan: AnalysisPlan | None = None,
) -> DataSciencePlanningOutcome:
    """Route only explicit advanced/predictive intent; leave basic SQL questions untouched."""

    normalized = _normalize_column_aliases(question.strip().casefold(), manifest)
    if PREDICTION_PATTERN.search(normalized) and PREDICTION_GUIDANCE_PATTERN.search(normalized):
        return DataSciencePlanningOutcome(
            status="not_applicable", message="dataset capability request"
        )
    if (
        not _mentioned_columns(normalized, manifest)
        and re.search(r"(?:가능한|할\s*수\s*있는|어떤|무슨|추천)", normalized)
        and re.search(r"(?:분석|예측|모델)", normalized)
    ):
        return DataSciencePlanningOutcome(
            status="not_applicable", message="dataset capability request"
        )
    if previous_prediction_plan is not None:
        follow_up = _prediction_follow_up(normalized, previous_prediction_plan, manifest)
        if follow_up is not None:
            return follow_up
    if previous_advanced_plan is not None:
        follow_up = _advanced_follow_up(normalized, previous_advanced_plan)
        if follow_up is not None:
            return follow_up
    if PREDICTION_PATTERN.search(normalized):
        return _plan_prediction(normalized, manifest, frame)
    operation = _advanced_operation(normalized)
    if operation is not None:
        return _plan_advanced(
            normalized,
            manifest,
            frame,
            operation,
            previous_analysis_plan,
        )
    return DataSciencePlanningOutcome(
        status="not_applicable", message="not an explicit advanced or predictive request"
    )
