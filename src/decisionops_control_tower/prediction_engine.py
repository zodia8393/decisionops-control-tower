"""CPU-bounded predictive workflows with baseline and leakage gates."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
import math
import re
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_fscore_support,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from decisionops_control_tower.analysis_engine import (
    SOURCE_ROW_COLUMN,
    AnalysisContractError,
    DatasetManifest,
    FilterClause,
    QueryProvenance,
    materialize_filtered_frame,
)
from decisionops_control_tower.data_analysis import LoadedDataset


TaskType = Literal["regression", "classification", "forecasting"]
ModelName = Literal["linear", "random_forest", "gradient_boosting"]

MIN_SUPERVISED_ROWS = 100
MIN_CLASS_ROWS = 20
MIN_FORECAST_ROWS = 60
MAX_EXPLANATION_FEATURES = 8
MAX_EXPLANATION_ROWS = 20
ID_NAME_PATTERN = re.compile(r"(^|[_\s-])(id|uuid|key|index|번호|식별자|코드)($|[_\s-])", re.I)


class PredictionPlan(BaseModel):
    """Closed predictive contract; raw estimator parameters are not accepted."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["decisionops-prediction-plan-v1"] = (
        "decisionops-prediction-plan-v1"
    )
    task: TaskType
    target: str = Field(min_length=1, max_length=120)
    features: list[str] = Field(default_factory=list, max_length=30)
    filters: list[FilterClause] = Field(default_factory=list, max_length=20)
    time_column: str | None = Field(default=None, min_length=1, max_length=120)
    split_strategy: Literal["auto", "random", "chronological"] = "auto"
    validation_size: float = Field(default=0.2, ge=0.1, le=0.3)
    test_size: float = Field(default=0.2, ge=0.1, le=0.3)
    horizon: int = Field(default=7, ge=1, le=30)
    model_candidates: list[ModelName] = Field(default_factory=list, max_length=3)
    confidence_level: float = Field(default=0.9, ge=0.8, le=0.99)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    rationale: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def validate_task_shape(self) -> "PredictionPlan":
        if len(self.features) != len(set(self.features)):
            raise ValueError("prediction features must be unique")
        if self.target in self.features:
            raise ValueError("target cannot also be a feature")
        if self.validation_size + self.test_size > 0.5:
            raise ValueError("validation_size + test_size must not exceed 0.5")
        if self.task == "forecasting":
            if self.time_column is None:
                raise ValueError("forecasting requires time_column")
            if self.split_strategy == "random":
                raise ValueError("forecasting forbids random split")
            if self.features:
                raise ValueError("forecasting v1 uses target history and does not accept exogenous features")
        elif self.split_strategy == "chronological" and self.time_column is None:
            raise ValueError("chronological split requires time_column")
        if self.time_column == self.target or self.time_column in self.features:
            raise ValueError("time_column must differ from target and features")
        allowed = (
            {"linear", "gradient_boosting"}
            if self.task == "forecasting"
            else {"linear", "random_forest"}
        )
        invalid = sorted(set(self.model_candidates).difference(allowed))
        if invalid:
            raise ValueError(
                f"unsupported {self.task} model candidate(s): {', '.join(invalid)}"
            )
        return self


class PredictiveChart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chart_type: Literal["actual_vs_predicted", "forecast", "confusion_matrix"]
    title: str
    data: list[dict[str, Any]] = Field(max_length=500)


class ModelCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: TaskType
    status: Literal["MODEL_READY", "NO_MODEL_GAIN"]
    selected_model: str | None
    primary_metric: str
    baseline: str
    training_rows: int = Field(ge=0)
    validation_rows: int = Field(ge=0)
    test_rows: int = Field(ge=0)
    features_used: list[str]
    features_excluded: list[str]
    seed: int
    intended_use: str
    limitations: list[str]


class PredictionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["decisionops-prediction-result-v1"] = (
        "decisionops-prediction-result-v1"
    )
    dataset: DatasetManifest
    plan: PredictionPlan
    status: Literal["MODEL_READY", "NO_MODEL_GAIN"]
    input_row_count: int = Field(ge=0)
    denominator_row_count: int = Field(ge=0)
    usable_row_count: int = Field(ge=0)
    split_evidence: dict[str, Any]
    baseline: dict[str, Any]
    candidates: list[dict[str, Any]]
    selected_model: str | None
    test_metrics: dict[str, Any] | None
    predictions: list[dict[str, Any]] = Field(max_length=500)
    uncertainty: dict[str, Any] | None
    learning_curve: list[dict[str, Any]]
    error_analysis: dict[str, Any] | None
    feature_importance: list[dict[str, Any]]
    bounded_shap: dict[str, Any] | None
    model_card: ModelCard
    chart: PredictiveChart
    warnings: list[str]
    provenance: QueryProvenance
    numeric_source_of_truth: Literal["scikit-learn+pandas"] = "scikit-learn+pandas"
    storage: Literal["not_persisted"] = "not_persisted"


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_clean(item) for item in value]
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


def _records(frame: pd.DataFrame, limit: int = 500) -> list[dict[str, Any]]:
    return _clean(frame.head(limit).to_dict(orient="records"))


def _validate_columns(plan: PredictionPlan, manifest: DatasetManifest) -> None:
    lookup = {column.name: column for column in manifest.columns}
    requested = [plan.target, *plan.features, *(item.column for item in plan.filters)]
    if plan.time_column:
        requested.append(plan.time_column)
    missing = sorted({name for name in requested if name not in lookup})
    if missing:
        raise AnalysisContractError("unknown dataset columns: " + ", ".join(missing))
    if plan.task in {"regression", "forecasting"} and not lookup[plan.target].numeric:
        raise AnalysisContractError(f"{plan.task} requires a numeric target: {plan.target}")


def _looks_like_id(name: str, series: pd.Series) -> bool:
    present = series.dropna()
    if present.empty:
        return False
    ratio = present.nunique(dropna=True) / len(present)
    if ID_NAME_PATTERN.search(name):
        return ratio >= 0.5
    return ratio >= 0.98 and not pd.api.types.is_numeric_dtype(present)


def _same_as_target(feature: pd.Series, target: pd.Series) -> bool:
    both = feature.notna() & target.notna()
    if not both.any():
        return False
    left = feature.loc[both].astype(str).str.strip()
    right = target.loc[both].astype(str).str.strip()
    return bool((left == right).all())


def _safe_features(
    frame: pd.DataFrame, plan: PredictionPlan, manifest: DatasetManifest
) -> tuple[list[str], list[str], list[str]]:
    reserved = {plan.target, SOURCE_ROW_COLUMN}
    if plan.time_column:
        reserved.add(plan.time_column)
    requested = plan.features or [
        column.name for column in manifest.columns if column.name not in reserved
    ]
    excluded: list[str] = []
    warnings: list[str] = []
    kept: list[str] = []
    for feature in requested:
        if _same_as_target(frame[feature], frame[plan.target]):
            raise AnalysisContractError(
                f"target leakage detected: {feature} duplicates target {plan.target}"
            )
        if _looks_like_id(feature, frame[feature]):
            excluded.append(feature)
            warnings.append(f"고유 식별자 가능성이 높은 feature ‘{feature}’를 자동 제외했습니다.")
            continue
        unique_count = int(frame[feature].nunique(dropna=True))
        if (
            not pd.api.types.is_numeric_dtype(frame[feature])
            and unique_count > min(100, max(20, int(len(frame) * 0.2)))
        ):
            excluded.append(feature)
            warnings.append(
                f"고카디널리티 범주 feature ‘{feature}’({unique_count}개 값)를 CPU/memory 안전을 위해 제외했습니다."
            )
            continue
        if frame[feature].nunique(dropna=True) <= 1:
            excluded.append(feature)
            warnings.append(f"상수 feature ‘{feature}’를 자동 제외했습니다.")
            continue
        kept.append(feature)
    if not kept:
        raise AnalysisContractError("no usable features remain after leakage, ID, and constant gates")
    return kept, excluded, warnings


def _preprocessor(frame: pd.DataFrame, features: list[str]) -> ColumnTransformer:
    numeric = [name for name in features if pd.api.types.is_numeric_dtype(frame[name])]
    categorical = [name for name in features if name not in numeric]
    transformers: list[tuple[str, Any, list[str]]] = []
    if numeric:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric,
            )
        )
    if categorical:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical,
            )
        )
    return ColumnTransformer(transformers, remainder="drop")


def _metric_report(task: TaskType, actual: pd.Series, predicted: np.ndarray, probability: Any = None) -> dict[str, Any]:
    if task == "regression":
        return {
            "mae": float(mean_absolute_error(actual, predicted)),
            "rmse": float(math.sqrt(mean_squared_error(actual, predicted))),
            "r2": float(r2_score(actual, predicted)),
        }
    report: dict[str, Any] = {
        "macro_f1": float(f1_score(actual, predicted, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(actual, predicted)),
    }
    if probability is not None and actual.nunique() == 2:
        classes = sorted(actual.unique().tolist(), key=str)
        binary = (actual == classes[-1]).astype(int)
        report["roc_auc"] = float(roc_auc_score(binary, probability[:, -1]))
    return report


def _better_than_baseline(task: TaskType, candidate: float, baseline: float) -> bool:
    if task == "regression":
        return candidate < baseline - max(abs(baseline) * 0.01, 1e-12)
    return candidate > baseline + max(abs(baseline) * 0.01, 0.001)


def _split_supervised(
    frame: pd.DataFrame, plan: PredictionPlan
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    chronological = plan.split_strategy == "chronological" or (
        plan.split_strategy == "auto" and plan.time_column is not None
    )
    if chronological:
        assert plan.time_column is not None
        ordered = frame.copy()
        ordered[plan.time_column] = pd.to_datetime(ordered[plan.time_column], errors="coerce", utc=True)
        if ordered[plan.time_column].isna().any():
            raise AnalysisContractError("chronological split found invalid or missing time values")
        ordered = ordered.sort_values([plan.time_column, SOURCE_ROW_COLUMN]).reset_index(drop=True)
        unique_times = ordered[plan.time_column].drop_duplicates().sort_values().tolist()
        if len(unique_times) < 5:
            raise AnalysisContractError(
                "chronological split requires at least 5 distinct time values"
            )
        test_time_index = len(unique_times) - max(1, round(len(unique_times) * plan.test_size))
        valid_time_index = test_time_index - max(
            1, round(len(unique_times) * plan.validation_size)
        )
        if valid_time_index <= 0:
            raise AnalysisContractError("chronological split leaves no training time period")
        validation_start = unique_times[valid_time_index]
        test_start = unique_times[test_time_index]
        train = ordered.loc[ordered[plan.time_column] < validation_start]
        valid = ordered.loc[
            (ordered[plan.time_column] >= validation_start)
            & (ordered[plan.time_column] < test_start)
        ]
        test = ordered.loc[ordered[plan.time_column] >= test_start]
        evidence = {
            "strategy": "chronological",
            "shuffled": False,
            "train_end": train[plan.time_column].max(),
            "validation_start": valid[plan.time_column].min(),
            "validation_end": valid[plan.time_column].max(),
            "test_start": test[plan.time_column].min(),
        }
        if not (evidence["train_end"] < evidence["validation_start"] < evidence["test_start"]):
            raise AnalysisContractError("temporal split inversion detected")
        return train, valid, test, _clean(evidence)
    stratify = frame[plan.target] if plan.task == "classification" else None
    train_valid, test = train_test_split(
        frame,
        test_size=plan.test_size,
        random_state=plan.seed,
        stratify=stratify,
    )
    relative_valid = plan.validation_size / (1.0 - plan.test_size)
    stratify_train = train_valid[plan.target] if plan.task == "classification" else None
    train, valid = train_test_split(
        train_valid,
        test_size=relative_valid,
        random_state=plan.seed,
        stratify=stratify_train,
    )
    return train, valid, test, {"strategy": "random", "shuffled": True, "seed": plan.seed}


def _models(task: TaskType, plan: PredictionPlan) -> dict[str, Any]:
    names = plan.model_candidates or ["linear", "random_forest"]
    if task == "regression":
        estimators = {
            "linear": Ridge(alpha=1.0),
            "random_forest": RandomForestRegressor(
                n_estimators=120,
                max_depth=8,
                min_samples_leaf=2,
                random_state=plan.seed,
                n_jobs=1,
            ),
        }
    else:
        estimators = {
            "linear": LogisticRegression(
                max_iter=1000, class_weight="balanced", random_state=plan.seed
            ),
            "random_forest": RandomForestClassifier(
                n_estimators=120,
                max_depth=8,
                min_samples_leaf=2,
                class_weight="balanced",
                random_state=plan.seed,
                n_jobs=1,
            ),
        }
    return {name: estimators[name] for name in names}


def _prediction_values(model: Pipeline, task: TaskType, features: pd.DataFrame) -> tuple[np.ndarray, Any]:
    predicted = model.predict(features)
    probability = model.predict_proba(features) if task == "classification" else None
    return predicted, probability


def _permutation_evidence(
    model: Pipeline,
    task: TaskType,
    features: list[str],
    x_valid: pd.DataFrame,
    y_valid: pd.Series,
    seed: int,
) -> list[dict[str, Any]]:
    scoring = "neg_mean_absolute_error" if task == "regression" else "f1_macro"
    result = permutation_importance(
        model,
        x_valid,
        y_valid,
        scoring=scoring,
        n_repeats=3,
        random_state=seed,
        n_jobs=1,
    )
    evidence = [
        {
            "feature": feature,
            "importance_mean": float(result.importances_mean[index]),
            "importance_std": float(result.importances_std[index]),
        }
        for index, feature in enumerate(features)
    ]
    return sorted(evidence, key=lambda item: (-item["importance_mean"], item["feature"]))


def _baseline_row(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    values: dict[str, Any] = {}
    for feature in features:
        series = frame[feature].dropna()
        if pd.api.types.is_numeric_dtype(frame[feature]):
            values[feature] = float(series.median()) if not series.empty else 0.0
        else:
            modes = series.mode()
            values[feature] = modes.iloc[0] if not modes.empty else ""
    return pd.DataFrame([values], columns=features)


def _bounded_permutation_shap(
    model: Pipeline,
    task: TaskType,
    train: pd.DataFrame,
    explain: pd.DataFrame,
    ordered_features: list[str],
    seed: int,
) -> dict[str, Any]:
    features = ordered_features[:MAX_EXPLANATION_FEATURES]
    model_features = list(getattr(model, "feature_names_in_", ordered_features))
    rows = explain.head(MAX_EXPLANATION_ROWS)
    reference = _baseline_row(train, model_features)
    rng = np.random.default_rng(seed)
    permutations = [rng.permutation(features).tolist() for _ in range(min(8, max(2, len(features))))]
    class_label = None
    if task == "classification":
        classes = list(model.classes_)
        class_label = classes[-1]

    def score(frame: pd.DataFrame) -> float:
        if task == "regression":
            return float(model.predict(frame)[0])
        index = list(model.classes_).index(class_label)
        return float(model.predict_proba(frame)[0, index])

    contributions = {feature: [] for feature in features}
    row_evidence: list[dict[str, Any]] = []
    for source_index, row in rows.iterrows():
        totals = Counter({feature: 0.0 for feature in features})
        for order in permutations:
            current = reference.copy()
            previous = score(current)
            for feature in order:
                current.loc[0, feature] = row[feature]
                updated = score(current)
                totals[feature] += updated - previous
                previous = updated
        row_values = {feature: totals[feature] / len(permutations) for feature in features}
        for feature, value in row_values.items():
            contributions[feature].append(value)
        row_evidence.append(
            {
                "source_row": int(explain.loc[source_index, SOURCE_ROW_COLUMN]),
                "contributions": row_values,
            }
        )
    summary = sorted(
        (
            {"feature": feature, "mean_abs_contribution": float(np.mean(np.abs(values)))}
            for feature, values in contributions.items()
        ),
        key=lambda item: (-item["mean_abs_contribution"], item["feature"]),
    )
    return _clean(
        {
            "method": "bounded_permutation_shapley",
            "explained_output": "prediction" if task == "regression" else f"P({class_label})",
            "feature_limit": MAX_EXPLANATION_FEATURES,
            "row_limit": MAX_EXPLANATION_ROWS,
            "permutations": len(permutations),
            "sample_rows": len(rows),
            "summary": summary,
            "rows": row_evidence,
        }
    )


def _learning_curve(
    estimator: Pipeline,
    task: TaskType,
    train: pd.DataFrame,
    valid: pd.DataFrame,
    features: list[str],
    target: str,
    seed: int,
    chronological: bool,
) -> list[dict[str, Any]]:
    curve: list[dict[str, Any]] = []
    for fraction in (0.4, 0.7, 1.0):
        count = max(20, int(len(train) * fraction))
        if task == "classification" and count < train[target].nunique() * 2:
            continue
        if chronological:
            subset = train.iloc[:count]
        elif fraction < 1.0:
            subset, _ = train_test_split(
                train,
                train_size=count,
                random_state=seed,
                stratify=train[target] if task == "classification" else None,
            )
        else:
            subset = train
        fitted = clone(estimator).fit(subset[features], subset[target])
        predicted, probability = _prediction_values(fitted, task, valid[features])
        metrics = _metric_report(task, valid[target], predicted, probability)
        curve.append({"fraction": fraction, "training_rows": len(subset), "validation_metrics": metrics})
    return _clean(curve)


def _classification_error(actual: pd.Series, predicted: np.ndarray) -> dict[str, Any]:
    labels = sorted(set(actual.tolist()) | set(predicted.tolist()), key=str)
    precision, recall, f1, support = precision_recall_fscore_support(
        actual, predicted, labels=labels, zero_division=0
    )
    return _clean(
        {
            "labels": labels,
            "confusion_matrix": confusion_matrix(actual, predicted, labels=labels).tolist(),
            "per_class": [
                {
                    "class": label,
                    "precision": precision[index],
                    "recall": recall[index],
                    "f1": f1[index],
                    "support": support[index],
                }
                for index, label in enumerate(labels)
            ],
        }
    )


def _conformal_quantile(residuals: np.ndarray, confidence: float) -> float:
    quantile = min(1.0, math.ceil((len(residuals) + 1) * confidence) / len(residuals))
    return float(np.quantile(residuals, quantile, method="higher"))


def _supervised_result(
    dataset: LoadedDataset,
    manifest: DatasetManifest,
    plan: PredictionPlan,
) -> PredictionResult:
    requested = plan.features or [
        column.name
        for column in manifest.columns
        if column.name not in {plan.target, plan.time_column}
    ]
    selected = list(dict.fromkeys([plan.target, *requested, *([plan.time_column] if plan.time_column else [])]))
    materialized = materialize_filtered_frame(dataset, manifest, columns=selected, filters=plan.filters)
    frame = materialized.frame.loc[materialized.frame[plan.target].notna()].copy()
    if len(frame) < MIN_SUPERVISED_ROWS:
        raise AnalysisContractError(
            f"{plan.task} requires at least {MIN_SUPERVISED_ROWS} rows with a target; found {len(frame)}"
        )
    if frame[plan.target].nunique(dropna=True) < 2:
        raise AnalysisContractError("prediction target is constant")
    if plan.task == "regression":
        frame[plan.target] = pd.to_numeric(frame[plan.target], errors="coerce")
        frame = frame.loc[np.isfinite(frame[plan.target])].copy()
        if len(frame) < MIN_SUPERVISED_ROWS:
            raise AnalysisContractError("regression has fewer than 100 valid numeric target rows")
    else:
        counts = frame[plan.target].value_counts()
        if len(counts) < 2:
            raise AnalysisContractError("classification target requires at least two classes")
        if len(counts) > 50:
            raise AnalysisContractError(
                f"classification supports at most 50 classes; found {len(counts)}"
            )
        if int(counts.min()) < MIN_CLASS_ROWS:
            raise AnalysisContractError(
                f"classification requires at least {MIN_CLASS_ROWS} rows per class; smallest class has {int(counts.min())}"
            )
    features, excluded, warnings = _safe_features(frame, plan, manifest)
    train, valid, test, split_evidence = _split_supervised(frame, plan)
    split_evidence.update({"train_rows": len(train), "validation_rows": len(valid), "test_rows": len(test)})
    preprocessor = _preprocessor(train, features)
    if plan.task == "regression":
        baseline_estimator = DummyRegressor(strategy="median")
        baseline_name = "median_dummy"
        primary = "mae"
    else:
        baseline_estimator = DummyClassifier(strategy="most_frequent")
        baseline_name = "most_frequent_dummy"
        primary = "macro_f1"
    baseline_model = Pipeline([("preprocess", clone(preprocessor)), ("model", baseline_estimator)])
    baseline_model.fit(train[features], train[plan.target])
    base_valid_pred, base_valid_prob = _prediction_values(baseline_model, plan.task, valid[features])
    baseline_validation = _metric_report(plan.task, valid[plan.target], base_valid_pred, base_valid_prob)
    candidates: list[dict[str, Any]] = []
    fitted_candidates: dict[str, Pipeline] = {}
    for name, estimator in _models(plan.task, plan).items():
        model = Pipeline([("preprocess", clone(preprocessor)), ("model", estimator)])
        model.fit(train[features], train[plan.target])
        prediction, probability = _prediction_values(model, plan.task, valid[features])
        metrics = _metric_report(plan.task, valid[plan.target], prediction, probability)
        candidates.append({"model": name, "validation_metrics": metrics})
        fitted_candidates[name] = model
    reverse = plan.task == "classification"
    best = sorted(candidates, key=lambda item: item["validation_metrics"][primary], reverse=reverse)[0]
    gain = _better_than_baseline(
        plan.task,
        float(best["validation_metrics"][primary]),
        float(baseline_validation[primary]),
    )
    status: Literal["MODEL_READY", "NO_MODEL_GAIN"] = "MODEL_READY" if gain else "NO_MODEL_GAIN"
    selected_name = str(best["model"]) if gain else None
    baseline_model.fit(pd.concat([train, valid])[features], pd.concat([train, valid])[plan.target])
    base_test_pred, base_test_prob = _prediction_values(baseline_model, plan.task, test[features])
    baseline_test = _metric_report(plan.task, test[plan.target], base_test_pred, base_test_prob)
    baseline = {"model": baseline_name, "validation_metrics": baseline_validation, "test_metrics": baseline_test}
    predictions: list[dict[str, Any]] = []
    test_metrics = None
    uncertainty = None
    learning_curve: list[dict[str, Any]] = []
    error_analysis = None
    importance: list[dict[str, Any]] = []
    shap = None
    chart: PredictiveChart
    if not gain:
        warnings.append("후보 모델이 validation에서 baseline을 1% 이상 개선하지 못해 모델 승격을 차단했습니다.")
        chart = PredictiveChart(chart_type="actual_vs_predicted", title="Baseline test 결과", data=[])
    else:
        selected_validation_model = fitted_candidates[selected_name]
        validation_pred, _ = _prediction_values(selected_validation_model, plan.task, valid[features])
        importance = _permutation_evidence(
            selected_validation_model, plan.task, features, valid[features], valid[plan.target], plan.seed
        )
        ordered = [item["feature"] for item in importance]
        shap = _bounded_permutation_shap(
            selected_validation_model, plan.task, train, valid, ordered, plan.seed
        )
        learning_curve = _learning_curve(
            selected_validation_model,
            plan.task,
            train,
            valid,
            features,
            plan.target,
            plan.seed,
            split_evidence["strategy"] == "chronological",
        )
        final_model = clone(selected_validation_model).fit(
            pd.concat([train, valid])[features], pd.concat([train, valid])[plan.target]
        )
        test_pred, test_probability = _prediction_values(final_model, plan.task, test[features])
        test_metrics = _metric_report(plan.task, test[plan.target], test_pred, test_probability)
        output = pd.DataFrame(
            {
                SOURCE_ROW_COLUMN: test[SOURCE_ROW_COLUMN].astype(int).to_numpy(),
                "actual": test[plan.target].to_numpy(),
                "predicted": test_pred,
            }
        )
        if plan.task == "regression":
            radius = _conformal_quantile(
                np.abs(valid[plan.target].to_numpy(dtype=float) - validation_pred.astype(float)),
                plan.confidence_level,
            )
            output["lower"] = output["predicted"] - radius
            output["upper"] = output["predicted"] + radius
            output["absolute_error"] = np.abs(output["actual"] - output["predicted"])
            uncertainty = {
                "method": "split_conformal_absolute_residual",
                "confidence_level": plan.confidence_level,
                "radius": radius,
                "calibration_rows": len(valid),
            }
            worst = output.sort_values(["absolute_error", SOURCE_ROW_COLUMN], ascending=[False, True]).head(20)
            error_analysis = {
                "mean_signed_error": float((output["predicted"] - output["actual"]).mean()),
                "worst_errors": _records(worst, 20),
            }
            chart_type: Literal["actual_vs_predicted", "confusion_matrix"] = "actual_vs_predicted"
        else:
            confidence = np.max(test_probability, axis=1)
            output["confidence"] = confidence
            output["correct"] = output["actual"] == output["predicted"]
            uncertainty = {
                "method": "predicted_class_probability",
                "mean_confidence": float(np.mean(confidence)),
            }
            warnings.append(
                "분류 confidence는 calibration되지 않은 예측 확률이므로 확정 확률로 해석하지 마세요."
            )
            error_analysis = _classification_error(test[plan.target], test_pred)
            chart_type = "confusion_matrix"
        predictions = _records(output)
        chart = PredictiveChart(
            chart_type=chart_type,
            title="Test actual vs predicted" if plan.task == "regression" else "Test confusion matrix",
            data=(predictions if plan.task == "regression" else error_analysis["per_class"]),
        )
    limitations = [
        "업로드한 데이터 내부 검증 결과이며 외부 환경의 성능을 보장하지 않습니다.",
        "feature 중요도와 SHAP 근사는 인과효과가 아닙니다.",
    ]
    model_card = ModelCard(
        task=plan.task,
        status=status,
        selected_model=selected_name,
        primary_metric=primary,
        baseline=baseline_name,
        training_rows=len(train),
        validation_rows=len(valid),
        test_rows=len(test),
        features_used=features,
        features_excluded=excluded,
        seed=plan.seed,
        intended_use=f"업로드 데이터에서 {plan.target}의 제한된 오프라인 예측 가능성 평가",
        limitations=limitations,
    )
    return PredictionResult(
        dataset=manifest,
        plan=plan,
        status=status,
        input_row_count=len(dataset.frame),
        denominator_row_count=len(materialized.frame),
        usable_row_count=len(frame),
        split_evidence=_clean(split_evidence),
        baseline=_clean(baseline),
        candidates=_clean(candidates),
        selected_model=selected_name,
        test_metrics=_clean(test_metrics),
        predictions=predictions,
        uncertainty=_clean(uncertainty),
        learning_curve=learning_curve,
        error_analysis=_clean(error_analysis),
        feature_importance=_clean(importance),
        bounded_shap=_clean(shap),
        model_card=model_card,
        chart=chart,
        warnings=warnings,
        provenance=materialized.provenance,
    )


def _forecast_features(series: pd.Series) -> pd.DataFrame:
    frame = pd.DataFrame({"target": series.astype(float)})
    for lag in (1, 2, 7):
        frame[f"lag_{lag}"] = frame["target"].shift(lag)
    for window in (3, 7):
        frame[f"rolling_mean_{window}"] = frame["target"].shift(1).rolling(window).mean()
    frame["trend"] = np.arange(len(frame), dtype=float)
    frame["day_of_week"] = frame.index.dayofweek
    frame["month"] = frame.index.month
    return frame.dropna()


def _forecast_metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    denominator = np.abs(actual.to_numpy(dtype=float)) + np.abs(predicted.astype(float))
    smape = np.mean(np.where(denominator == 0, 0.0, 2.0 * np.abs(actual - predicted) / denominator))
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(math.sqrt(mean_squared_error(actual, predicted))),
        "smape": float(smape),
    }


def _forecast_model(name: str, seed: int) -> Any:
    if name == "linear":
        return Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=1.0))])
    return GradientBoostingRegressor(
        n_estimators=100, max_depth=3, min_samples_leaf=2, random_state=seed
    )


def _forecast_result(
    dataset: LoadedDataset,
    manifest: DatasetManifest,
    plan: PredictionPlan,
) -> PredictionResult:
    assert plan.time_column is not None
    materialized = materialize_filtered_frame(
        dataset, manifest, columns=[plan.time_column, plan.target], filters=plan.filters
    )
    raw = materialized.frame.copy()
    raw[plan.time_column] = pd.to_datetime(raw[plan.time_column], errors="coerce", utc=True)
    raw[plan.target] = pd.to_numeric(raw[plan.target], errors="coerce")
    raw = raw.loc[raw[plan.time_column].notna() & np.isfinite(raw[plan.target])]
    raw = raw.sort_values([plan.time_column, SOURCE_ROW_COLUMN])
    series = raw.groupby(plan.time_column, sort=True)[plan.target].mean()
    if len(series) < MIN_FORECAST_ROWS:
        raise AnalysisContractError(
            f"forecasting requires at least {MIN_FORECAST_ROWS} complete time points; found {len(series)}"
        )
    if series.nunique() < 2:
        raise AnalysisContractError("forecast target is constant")
    supervised = _forecast_features(series)
    feature_columns = [column for column in supervised.columns if column != "target"]
    test_count = max(1, round(len(supervised) * plan.test_size))
    valid_count = max(1, round(len(supervised) * plan.validation_size))
    train = supervised.iloc[: -(valid_count + test_count)]
    valid = supervised.iloc[-(valid_count + test_count) : -test_count]
    test = supervised.iloc[-test_count:]
    if len(train) < 30:
        raise AnalysisContractError("forecasting leaves fewer than 30 training periods after lag creation")
    split_evidence = {
        "strategy": "chronological",
        "shuffled": False,
        "train_rows": len(train),
        "validation_rows": len(valid),
        "test_rows": len(test),
        "train_end": train.index.max(),
        "validation_start": valid.index.min(),
        "validation_end": valid.index.max(),
        "test_start": test.index.min(),
    }
    seasonal_period = 7
    baseline_name = "seasonal_naive_lag_7"
    base_valid_pred = valid["lag_7"].to_numpy()
    if mean_absolute_error(valid["target"], valid["lag_1"]) < mean_absolute_error(valid["target"], base_valid_pred):
        baseline_name = "last_value_naive"
        base_valid_pred = valid["lag_1"].to_numpy()
        seasonal_period = 1
    baseline_validation = _forecast_metrics(valid["target"], base_valid_pred)
    candidate_names = plan.model_candidates or ["linear", "gradient_boosting"]
    fitted: dict[str, Any] = {}
    candidates: list[dict[str, Any]] = []
    for name in candidate_names:
        model = _forecast_model(name, plan.seed).fit(train[feature_columns], train["target"])
        prediction = model.predict(valid[feature_columns])
        candidates.append({"model": name, "validation_metrics": _forecast_metrics(valid["target"], prediction)})
        fitted[name] = model
    best = min(candidates, key=lambda item: item["validation_metrics"]["mae"])
    gain = _better_than_baseline("regression", best["validation_metrics"]["mae"], baseline_validation["mae"])
    status: Literal["MODEL_READY", "NO_MODEL_GAIN"] = "MODEL_READY" if gain else "NO_MODEL_GAIN"
    selected_name = str(best["model"]) if gain else None
    combined = pd.concat([train, valid])
    base_test_pred = test[f"lag_{seasonal_period}"].to_numpy()
    baseline_test = _forecast_metrics(test["target"], base_test_pred)
    baseline = {"model": baseline_name, "validation_metrics": baseline_validation, "test_metrics": baseline_test}
    warnings: list[str] = []
    predictions: list[dict[str, Any]] = []
    uncertainty = None
    test_metrics = None
    importance: list[dict[str, Any]] = []
    shap = None
    learning_curve: list[dict[str, Any]] = []
    error_analysis = None
    rolling_validation: list[dict[str, Any]] = []
    cv = TimeSeriesSplit(n_splits=3)
    for fold, (train_index, valid_index) in enumerate(cv.split(combined), start=1):
        fold_train, fold_valid = combined.iloc[train_index], combined.iloc[valid_index]
        model = _forecast_model(str(best["model"]), plan.seed).fit(
            fold_train[feature_columns], fold_train["target"]
        )
        fold_pred = model.predict(fold_valid[feature_columns])
        rolling_validation.append(
            {"fold": fold, "train_rows": len(fold_train), "validation_rows": len(fold_valid), "metrics": _forecast_metrics(fold_valid["target"], fold_pred)}
        )
    if not gain:
        warnings.append("후보 forecast가 validation에서 naive baseline을 1% 이상 개선하지 못해 모델 승격을 차단했습니다.")
        chart = PredictiveChart(chart_type="forecast", title="Naive baseline", data=[])
    else:
        validation_model = fitted[selected_name]
        validation_prediction = validation_model.predict(valid[feature_columns])
        permutation = permutation_importance(
            validation_model,
            valid[feature_columns],
            valid["target"],
            scoring="neg_mean_absolute_error",
            n_repeats=3,
            random_state=plan.seed,
            n_jobs=1,
        )
        importance = sorted(
            [
                {"feature": feature, "importance_mean": float(permutation.importances_mean[index]), "importance_std": float(permutation.importances_std[index])}
                for index, feature in enumerate(feature_columns)
            ],
            key=lambda item: (-item["importance_mean"], item["feature"]),
        )
        explain_train = train.reset_index(drop=False).rename(columns={plan.time_column: "time"})
        explain_valid = valid.reset_index(drop=False).rename(columns={plan.time_column: "time"})
        explain_train[SOURCE_ROW_COLUMN] = np.arange(len(explain_train))
        explain_valid[SOURCE_ROW_COLUMN] = np.arange(len(explain_valid))
        shap = _bounded_permutation_shap(
            validation_model,
            "regression",
            explain_train,
            explain_valid,
            [item["feature"] for item in importance],
            plan.seed,
        )
        final_model = _forecast_model(selected_name, plan.seed).fit(combined[feature_columns], combined["target"])
        test_prediction = final_model.predict(test[feature_columns])
        test_metrics = _forecast_metrics(test["target"], test_prediction)
        radius = _conformal_quantile(
            np.abs(valid["target"].to_numpy() - validation_prediction), plan.confidence_level
        )
        output = pd.DataFrame(
            {
                "time": test.index,
                "actual": test["target"].to_numpy(),
                "predicted": test_prediction,
                "lower": test_prediction - radius,
                "upper": test_prediction + radius,
            }
        )
        output["absolute_error"] = np.abs(output["actual"] - output["predicted"])
        predictions = _records(output)
        uncertainty = {
            "method": "split_conformal_absolute_residual",
            "confidence_level": plan.confidence_level,
            "radius": radius,
            "calibration_rows": len(valid),
        }
        error_analysis = {
            "mean_signed_error": float((output["predicted"] - output["actual"]).mean()),
            "worst_errors": _records(output.sort_values("absolute_error", ascending=False), 20),
        }
        learning_curve = rolling_validation
        history = series.copy()
        inferred = pd.infer_freq(history.index)
        if inferred:
            offset = pd.tseries.frequencies.to_offset(inferred)
        else:
            differences = history.index.to_series().diff().dropna()
            offset = differences.median() if not differences.empty else timedelta(days=1)
            warnings.append("시간 간격을 명확히 추론하지 못해 중앙 간격으로 미래 시점을 생성했습니다.")
        future_rows: list[dict[str, Any]] = []
        recursive_model = _forecast_model(selected_name, plan.seed).fit(supervised[feature_columns], supervised["target"])
        for _ in range(plan.horizon):
            future_time = history.index[-1] + offset
            # Build the final row directly because dropna removes the unknown target row.
            values = {
                "lag_1": history.iloc[-1],
                "lag_2": history.iloc[-2],
                "lag_7": history.iloc[-7],
                "rolling_mean_3": history.iloc[-3:].mean(),
                "rolling_mean_7": history.iloc[-7:].mean(),
                "trend": float(len(history)),
                "day_of_week": future_time.dayofweek,
                "month": future_time.month,
            }
            future_value = float(recursive_model.predict(pd.DataFrame([values], columns=feature_columns))[0])
            history.loc[future_time] = future_value
            future_rows.append(
                {"time": future_time, "predicted": future_value, "lower": future_value - radius, "upper": future_value + radius}
            )
        predictions.extend(_clean(future_rows))
        chart = PredictiveChart(chart_type="forecast", title=f"{plan.target} forecast", data=predictions)
    split_evidence["rolling_origin_validation"] = rolling_validation
    card = ModelCard(
        task="forecasting",
        status=status,
        selected_model=selected_name,
        primary_metric="mae",
        baseline=baseline_name,
        training_rows=len(train),
        validation_rows=len(valid),
        test_rows=len(test),
        features_used=feature_columns,
        features_excluded=[],
        seed=plan.seed,
        intended_use=f"{plan.target}의 {plan.horizon}기간 제한적 단변량 예측",
        limitations=[
            "미래 외생 충격과 구조 변화를 반영하지 않습니다.",
            "재귀 예측이므로 horizon이 길수록 오차가 누적될 수 있습니다.",
        ],
    )
    return PredictionResult(
        dataset=manifest,
        plan=plan,
        status=status,
        input_row_count=len(dataset.frame),
        denominator_row_count=len(materialized.frame),
        usable_row_count=len(series),
        split_evidence=_clean(split_evidence),
        baseline=_clean(baseline),
        candidates=_clean(candidates),
        selected_model=selected_name,
        test_metrics=_clean(test_metrics),
        predictions=predictions,
        uncertainty=_clean(uncertainty),
        learning_curve=_clean(learning_curve),
        error_analysis=_clean(error_analysis),
        feature_importance=_clean(importance),
        bounded_shap=_clean(shap),
        model_card=card,
        chart=chart,
        warnings=warnings,
        provenance=materialized.provenance,
    )


def execute_prediction_plan(
    dataset: LoadedDataset,
    manifest: DatasetManifest,
    plan: PredictionPlan,
) -> PredictionResult:
    """Execute a CPU-bounded predictive plan after deterministic safety gates."""

    _validate_columns(plan, manifest)
    if plan.task == "forecasting":
        return _forecast_result(dataset, manifest, plan)
    return _supervised_result(dataset, manifest, plan)
