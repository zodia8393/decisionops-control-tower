"""Typed, evidence-grounded advanced statistics for uploaded tabular data."""

from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy import stats

from decisionops_control_tower.analysis_engine import (
    SOURCE_ROW_COLUMN,
    AnalysisContractError,
    DatasetManifest,
    FilterClause,
    QueryProvenance,
    materialize_filtered_frame,
)
from decisionops_control_tower.data_analysis import LoadedDataset


AdvancedOperation = Literal[
    "distribution", "outliers", "group_comparison", "relationship", "time_series"
]


class AdvancedAnalysisPlan(BaseModel):
    """A closed contract for calculations that are intentionally outside SQL v1."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["decisionops-advanced-analysis-plan-v1"] = (
        "decisionops-advanced-analysis-plan-v1"
    )
    operation: AdvancedOperation
    columns: list[str] = Field(min_length=1, max_length=2)
    filters: list[FilterClause] = Field(default_factory=list, max_length=20)
    group_by: str | None = Field(default=None, min_length=1, max_length=120)
    time_column: str | None = Field(default=None, min_length=1, max_length=120)
    test_method: Literal["auto", "parametric", "nonparametric"] = "auto"
    confidence_level: float = Field(default=0.95, ge=0.8, le=0.99)
    bins: int = Field(default=10, ge=5, le=50)
    iqr_multiplier: float = Field(default=1.5, ge=0.5, le=5.0)
    rolling_window: int = Field(default=3, ge=2, le=90)
    aggregation: Literal["mean", "sum", "median"] = "mean"
    frequency: Literal["raw", "daily", "weekly", "monthly"] = "raw"
    rationale: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def validate_operation_shape(self) -> "AdvancedAnalysisPlan":
        if len(self.columns) != len(set(self.columns)):
            raise ValueError("advanced analysis columns must be unique")
        expected = 2 if self.operation == "relationship" else 1
        if len(self.columns) != expected:
            raise ValueError(f"{self.operation} requires exactly {expected} value column(s)")
        if self.operation == "group_comparison" and self.group_by is None:
            raise ValueError("group_comparison requires group_by")
        if self.operation != "group_comparison" and self.group_by is not None:
            raise ValueError(f"{self.operation} does not accept group_by")
        if self.operation == "time_series" and self.time_column is None:
            raise ValueError("time_series requires time_column")
        if self.operation != "time_series" and self.time_column is not None:
            raise ValueError(f"{self.operation} does not accept time_column")
        return self


class ChartSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chart_type: Literal["histogram", "box", "bar", "scatter", "line"]
    title: str
    x_label: str
    y_label: str
    data: list[dict[str, Any]] = Field(max_length=500)


class AdvancedAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["decisionops-advanced-analysis-result-v1"] = (
        "decisionops-advanced-analysis-result-v1"
    )
    dataset: DatasetManifest
    plan: AdvancedAnalysisPlan
    input_row_count: int = Field(ge=0)
    denominator_row_count: int = Field(ge=0)
    valid_row_count: int = Field(ge=0)
    statistics: dict[str, Any]
    rows: list[dict[str, Any]] = Field(max_length=200)
    chart: ChartSpec
    warnings: list[str]
    assumptions: list[str]
    provenance: QueryProvenance
    numeric_source_of_truth: Literal["scipy+pandas"] = "scipy+pandas"
    storage: Literal["not_persisted"] = "not_persisted"


def _manifest_lookup(manifest: DatasetManifest) -> dict[str, Any]:
    return {column.name: column for column in manifest.columns}


def _validate_plan_columns(plan: AdvancedAnalysisPlan, manifest: DatasetManifest) -> None:
    lookup = _manifest_lookup(manifest)
    required = list(plan.columns)
    required.extend(item.column for item in plan.filters)
    if plan.group_by:
        required.append(plan.group_by)
    if plan.time_column:
        required.append(plan.time_column)
    missing = sorted({name for name in required if name not in lookup})
    if missing:
        raise AnalysisContractError("unknown dataset columns: " + ", ".join(missing))
    non_numeric = [name for name in plan.columns if not lookup[name].numeric]
    if non_numeric:
        raise AnalysisContractError(
            "advanced analysis requires numeric value columns: " + ", ".join(non_numeric)
        )
    if plan.group_by and plan.group_by in plan.columns:
        raise AnalysisContractError("group_by must differ from the value column")
    if plan.time_column and plan.time_column in plan.columns:
        raise AnalysisContractError("time_column must differ from the value column")


def _finite(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _records(frame: pd.DataFrame, *, limit: int = 200) -> list[dict[str, Any]]:
    return [
        {str(column): _finite(value) for column, value in row.items()}
        for row in frame.head(limit).to_dict(orient="records")
    ]


def _valid_numeric(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    result = frame.copy()
    result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.loc[np.isfinite(result[column])].copy()


def _distribution(
    frame: pd.DataFrame, plan: AdvancedAnalysisPlan
) -> tuple[dict[str, Any], list[dict[str, Any]], ChartSpec, list[str], list[str], int]:
    column = plan.columns[0]
    valid = _valid_numeric(frame, column)
    if len(valid) < 3:
        raise AnalysisContractError("distribution requires at least 3 valid numeric rows")
    values = valid[column].astype(float)
    quantiles = values.quantile([0.25, 0.5, 0.75])
    counts, edges = np.histogram(values.to_numpy(), bins=plan.bins)
    histogram = [
        {
            "bin_start": float(edges[index]),
            "bin_end": float(edges[index + 1]),
            "count": int(count),
        }
        for index, count in enumerate(counts)
    ]
    normality_p = None
    if 8 <= len(values) <= 5000 and values.nunique() > 1:
        normality_p = float(stats.normaltest(values).pvalue)
    statistics = {
        "count": int(len(values)),
        "mean": float(values.mean()),
        "stddev": float(values.std(ddof=1)),
        "min": float(values.min()),
        "q1": float(quantiles.loc[0.25]),
        "median": float(quantiles.loc[0.5]),
        "q3": float(quantiles.loc[0.75]),
        "max": float(values.max()),
        "skewness": float(stats.skew(values, bias=False)),
        "excess_kurtosis": float(stats.kurtosis(values, fisher=True, bias=False)),
        "normality_p_value": normality_p,
    }
    warnings = []
    if normality_p is not None and normality_p < 0.05:
        warnings.append("정규성 검정 p-value가 0.05 미만이므로 정규분포 가정에 주의해야 합니다.")
    chart = ChartSpec(
        chart_type="histogram",
        title=f"{column} 분포",
        x_label=column,
        y_label="빈도",
        data=histogram,
    )
    return statistics, histogram, chart, warnings, ["결측·비수치 값은 분포 분모에서 제외했습니다."], len(valid)


def _outliers(
    frame: pd.DataFrame, plan: AdvancedAnalysisPlan
) -> tuple[dict[str, Any], list[dict[str, Any]], ChartSpec, list[str], list[str], int]:
    column = plan.columns[0]
    valid = _valid_numeric(frame, column)
    if len(valid) < 4:
        raise AnalysisContractError("outlier analysis requires at least 4 valid numeric rows")
    values = valid[column].astype(float)
    q1, median, q3 = values.quantile([0.25, 0.5, 0.75]).tolist()
    iqr = float(q3 - q1)
    lower = float(q1 - plan.iqr_multiplier * iqr)
    upper = float(q3 + plan.iqr_multiplier * iqr)
    mask = (values < lower) | (values > upper)
    outliers = valid.loc[mask, [SOURCE_ROW_COLUMN, column]].copy()
    outliers["distance_from_median"] = (outliers[column] - median).abs()
    outliers = outliers.sort_values(
        ["distance_from_median", SOURCE_ROW_COLUMN], ascending=[False, True]
    )
    rows = _records(outliers)
    statistics = {
        "count": int(len(values)),
        "q1": float(q1),
        "median": float(median),
        "q3": float(q3),
        "iqr": iqr,
        "lower_bound": lower,
        "upper_bound": upper,
        "outlier_count": int(mask.sum()),
        "outlier_rate": float(mask.mean()),
    }
    chart = ChartSpec(
        chart_type="box",
        title=f"{column} IQR 이상치",
        x_label=column,
        y_label="값",
        data=[statistics],
    )
    warning = [] if iqr > 0 else ["IQR이 0이어서 중앙값과 다른 값이 모두 이상치로 표시될 수 있습니다."]
    assumptions = [
        f"Tukey IQR 규칙({plan.iqr_multiplier:g} × IQR)을 사용했으며 이상치는 오류를 의미하지 않습니다."
    ]
    return statistics, rows, chart, warning, assumptions, len(valid)


def _relationship(
    frame: pd.DataFrame, plan: AdvancedAnalysisPlan
) -> tuple[dict[str, Any], list[dict[str, Any]], ChartSpec, list[str], list[str], int]:
    x_column, y_column = plan.columns
    valid = frame[[SOURCE_ROW_COLUMN, x_column, y_column]].copy()
    valid[x_column] = pd.to_numeric(valid[x_column], errors="coerce")
    valid[y_column] = pd.to_numeric(valid[y_column], errors="coerce")
    valid = valid.loc[np.isfinite(valid[x_column]) & np.isfinite(valid[y_column])]
    if len(valid) < 3:
        raise AnalysisContractError("relationship analysis requires at least 3 complete pairs")
    if valid[x_column].nunique() < 2 or valid[y_column].nunique() < 2:
        raise AnalysisContractError("relationship analysis requires non-constant columns")
    pearson = stats.pearsonr(valid[x_column], valid[y_column])
    spearman = stats.spearmanr(valid[x_column], valid[y_column])
    regression = stats.linregress(valid[x_column], valid[y_column])
    statistics = {
        "pair_count": int(len(valid)),
        "pearson_r": float(pearson.statistic),
        "pearson_p_value": float(pearson.pvalue),
        "spearman_rho": float(spearman.statistic),
        "spearman_p_value": float(spearman.pvalue),
        "linear_slope": float(regression.slope),
        "linear_intercept": float(regression.intercept),
        "linear_r_squared": float(regression.rvalue**2),
        "slope_standard_error": float(regression.stderr),
    }
    rows = _records(valid.sort_values([x_column, SOURCE_ROW_COLUMN]))
    chart = ChartSpec(
        chart_type="scatter",
        title=f"{x_column}와 {y_column} 관계",
        x_label=x_column,
        y_label=y_column,
        data=rows,
    )
    warnings = []
    if len(valid) < 30:
        warnings.append("완전한 관측쌍이 30개 미만이므로 상관계수와 p-value가 불안정할 수 있습니다.")
    assumptions = ["상관과 선형회귀는 인과관계를 입증하지 않습니다."]
    return statistics, rows, chart, warnings, assumptions, len(valid)


def _normal_enough(values: pd.Series) -> bool:
    if len(values) < 3:
        return False
    sample = values if len(values) <= 5000 else values.sample(5000, random_state=42)
    return bool(stats.shapiro(sample).pvalue >= 0.05)


def _group_comparison(
    frame: pd.DataFrame, plan: AdvancedAnalysisPlan
) -> tuple[dict[str, Any], list[dict[str, Any]], ChartSpec, list[str], list[str], int]:
    value_column = plan.columns[0]
    assert plan.group_by is not None
    valid = frame[[SOURCE_ROW_COLUMN, plan.group_by, value_column]].copy()
    valid[value_column] = pd.to_numeric(valid[value_column], errors="coerce")
    valid = valid.loc[valid[plan.group_by].notna() & np.isfinite(valid[value_column])]
    groups = [group[value_column].astype(float) for _, group in valid.groupby(plan.group_by, sort=True)]
    labels = [str(label) for label, _ in valid.groupby(plan.group_by, sort=True)]
    if not 2 <= len(groups) <= 50:
        raise AnalysisContractError("group comparison requires 2..50 non-empty groups")
    alpha = 1.0 - plan.confidence_level
    rows: list[dict[str, Any]] = []
    for label, values in zip(labels, groups, strict=True):
        count = len(values)
        sem = float(stats.sem(values)) if count >= 2 else None
        margin = (
            float(stats.t.ppf(1.0 - alpha / 2.0, count - 1) * sem)
            if sem is not None and math.isfinite(sem)
            else None
        )
        mean = float(values.mean())
        rows.append(
            {
                "group": label,
                "count": count,
                "mean": mean,
                "median": float(values.median()),
                "stddev": float(values.std(ddof=1)) if count >= 2 else None,
                "ci_lower": mean - margin if margin is not None else None,
                "ci_upper": mean + margin if margin is not None else None,
            }
        )
    all_normal = all(_normal_enough(values) for values in groups)
    use_parametric = plan.test_method == "parametric" or (
        plan.test_method == "auto" and all_normal
    )
    test_name: str
    effect_name: str
    effect_value: float | None
    if len(groups) == 2:
        if use_parametric:
            test = stats.ttest_ind(groups[0], groups[1], equal_var=False)
            test_name = "welch_t_test"
        else:
            test = stats.mannwhitneyu(groups[0], groups[1], alternative="two-sided")
            test_name = "mann_whitney_u"
        variance = (
            ((len(groups[0]) - 1) * groups[0].var(ddof=1) + (len(groups[1]) - 1) * groups[1].var(ddof=1))
            / max(len(groups[0]) + len(groups[1]) - 2, 1)
        )
        effect_value = (
            float((groups[0].mean() - groups[1].mean()) / math.sqrt(variance))
            if variance > 0
            else None
        )
        effect_name = "cohen_d"
    else:
        if use_parametric:
            test = stats.f_oneway(*groups)
            test_name = "one_way_anova"
        else:
            test = stats.kruskal(*groups)
            test_name = "kruskal_wallis"
        grand_mean = valid[value_column].mean()
        between = sum(len(values) * float(values.mean() - grand_mean) ** 2 for values in groups)
        total = float(((valid[value_column] - grand_mean) ** 2).sum())
        effect_value = float(between / total) if total > 0 else None
        effect_name = "eta_squared"
    statistics = {
        "group_count": len(groups),
        "test": test_name,
        "statistic": float(test.statistic),
        "p_value": float(test.pvalue),
        "confidence_level": plan.confidence_level,
        "effect_size_name": effect_name,
        "effect_size": effect_value,
        "normality_supported": all_normal,
    }
    warnings = []
    if min(len(group) for group in groups) < 5:
        warnings.append("표본이 5개 미만인 그룹이 있어 검정력과 신뢰구간이 불안정합니다.")
    assumptions = [
        "각 행은 서로 독립인 관측으로 가정했습니다.",
        "p-value와 함께 효과크기와 그룹별 신뢰구간을 확인해야 합니다.",
    ]
    chart = ChartSpec(
        chart_type="bar",
        title=f"{plan.group_by}별 {value_column} 비교",
        x_label=plan.group_by,
        y_label=value_column,
        data=rows,
    )
    return statistics, rows, chart, warnings, assumptions, len(valid)


def _time_series(
    frame: pd.DataFrame, plan: AdvancedAnalysisPlan
) -> tuple[dict[str, Any], list[dict[str, Any]], ChartSpec, list[str], list[str], int]:
    value_column = plan.columns[0]
    assert plan.time_column is not None
    valid = frame[[SOURCE_ROW_COLUMN, plan.time_column, value_column]].copy()
    valid[plan.time_column] = pd.to_datetime(valid[plan.time_column], errors="coerce", utc=True)
    valid[value_column] = pd.to_numeric(valid[value_column], errors="coerce")
    valid = valid.loc[valid[plan.time_column].notna() & np.isfinite(valid[value_column])]
    if len(valid) < 3:
        raise AnalysisContractError("time-series analysis requires at least 3 complete time/value rows")
    valid = valid.sort_values([plan.time_column, SOURCE_ROW_COLUMN])
    aggregation = {"mean": "mean", "sum": "sum", "median": "median"}[plan.aggregation]
    if plan.frequency == "raw":
        series = valid.groupby(plan.time_column, sort=True)[value_column].agg(aggregation)
    else:
        frequency = {"daily": "D", "weekly": "W", "monthly": "MS"}[plan.frequency]
        series = (
            valid.set_index(plan.time_column)[value_column]
            .resample(frequency)
            .agg(aggregation)
            .dropna()
        )
    if len(series) < 3:
        raise AnalysisContractError("time-series aggregation leaves fewer than 3 periods")
    result = series.rename("value").reset_index()
    result["rolling_value"] = result["value"].rolling(plan.rolling_window, min_periods=1).mean()
    result["change"] = result["value"].diff()
    result["change_rate"] = result["value"].pct_change().replace([np.inf, -np.inf], np.nan)
    trend = stats.linregress(np.arange(len(result), dtype=float), result["value"].astype(float))
    statistics = {
        "period_count": int(len(result)),
        "start": result[plan.time_column].iloc[0].isoformat(),
        "end": result[plan.time_column].iloc[-1].isoformat(),
        "mean": float(result["value"].mean()),
        "trend_slope_per_period": float(trend.slope),
        "trend_r_squared": float(trend.rvalue**2),
        "first_value": float(result["value"].iloc[0]),
        "last_value": float(result["value"].iloc[-1]),
        "total_change": float(result["value"].iloc[-1] - result["value"].iloc[0]),
    }
    warnings = []
    chart_frame = result
    if len(result) > 500:
        positions = np.linspace(0, len(result) - 1, 500, dtype=int)
        chart_frame = result.iloc[np.unique(positions)]
        warnings.append("차트는 가독성을 위해 전체 기간에서 균등하게 500개 시점만 표시합니다.")
    rows = _records(chart_frame, limit=500)
    chart = ChartSpec(
        chart_type="line",
        title=f"{value_column} 시계열",
        x_label=plan.time_column,
        y_label=value_column,
        data=rows,
    )
    assumptions = [
        "추세 기울기는 집계된 기간 순서 기준이며 계절성이나 인과효과를 의미하지 않습니다.",
        f"이동평균 window는 {plan.rolling_window}개 기간입니다.",
    ]
    return statistics, rows, chart, warnings, assumptions, len(valid)


def execute_advanced_plan(
    dataset: LoadedDataset,
    manifest: DatasetManifest,
    plan: AdvancedAnalysisPlan,
) -> AdvancedAnalysisResult:
    """Execute one closed advanced-analysis plan with row and SQL evidence."""

    _validate_plan_columns(plan, manifest)
    selected = list(plan.columns)
    if plan.group_by:
        selected.append(plan.group_by)
    if plan.time_column:
        selected.append(plan.time_column)
    materialized = materialize_filtered_frame(
        dataset,
        manifest,
        columns=list(dict.fromkeys(selected)),
        filters=plan.filters,
    )
    executors = {
        "distribution": _distribution,
        "outliers": _outliers,
        "group_comparison": _group_comparison,
        "relationship": _relationship,
        "time_series": _time_series,
    }
    statistics, rows, chart, warnings, assumptions, valid_count = executors[plan.operation](
        materialized.frame, plan
    )
    excluded = len(materialized.frame) - valid_count
    if excluded:
        warnings.insert(0, f"결측·변환 불가 값이 있는 {excluded}개 행을 계산 분모에서 제외했습니다.")
    return AdvancedAnalysisResult(
        dataset=manifest,
        plan=plan,
        input_row_count=len(dataset.frame),
        denominator_row_count=len(materialized.frame),
        valid_row_count=valid_count,
        statistics={key: _finite(value) for key, value in statistics.items()},
        rows=rows,
        chart=chart,
        warnings=warnings,
        assumptions=assumptions,
        provenance=materialized.provenance,
    )
