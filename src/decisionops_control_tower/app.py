"""FastAPI product surface for DecisionOps Control Tower."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Literal
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
import pandas as pd
from pydantic import BaseModel, Field

from decisionops_control_tower.agent import build_candidate_review_notes, build_reviewer_brief
from decisionops_control_tower.advanced_analytics import (
    AdvancedAnalysisPlan,
    AdvancedAnalysisResult,
    execute_advanced_plan,
)
from decisionops_control_tower.analysis_engine import (
    AnalysisContractError,
    AnalysisPlan,
    DatasetManifest,
    ExecutionResult,
    execute_plan,
)
from decisionops_control_tower.analysis_planner import (
    ANALYSIS_RESET_REQUEST_MESSAGE,
    CAPABILITY_REQUEST_MESSAGE,
    CONVERSATION_REQUEST_MESSAGE,
    OVERVIEW_REQUEST_MESSAGE,
    PROFILE_REQUEST_MESSAGE,
    RESULT_INTERPRETATION_MESSAGE,
    PlanningOutcome,
    plan_analysis,
)
from decisionops_control_tower.data_analysis import (
    DatasetAnalysisError,
    SUMMARY_ROW_LABELS,
    analyze_dataset,
    load_dataset,
    profile_dataset,
    summary_row_details,
)
from decisionops_control_tower.copilot_dashboard import (
    load_product_evidence,
    render_copilot_dashboard,
)
from decisionops_control_tower.data_science_planner import (
    DataSciencePlanningOutcome,
    plan_data_science,
)
from decisionops_control_tower.migration_case import run_migration_case
from decisionops_control_tower.pipeline import (
    DEFAULT_BIKE_ROOT,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_WORKBENCH_ROOT,
    run,
)
from decisionops_control_tower.prediction_engine import (
    PredictionPlan,
    PredictionResult,
    execute_prediction_plan,
)
from decisionops_control_tower.rag import (
    RagService,
    RagUnavailableError,
    build_recorded_chat,
    requires_guarded_chat,
)
from decisionops_control_tower.store import (
    database_path,
    initialize_store,
    list_history,
    list_queue,
    queue_summary,
    record_decision,
    verify_audit_integrity,
)


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject", "needs_more_evidence"]
    reviewer: str = Field(default="ops_reviewer", min_length=1, max_length=80)
    note: str = Field(default="", max_length=1000)


class DatasetInput(BaseModel):
    filename: str = Field(min_length=1, max_length=120)
    format: Literal["csv", "json", "xlsx", "parquet"]
    content: str = Field(min_length=1, max_length=1_400_000)
    content_encoding: Literal["utf-8", "base64"] = "utf-8"


class ChatHistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=8)
    dataset: DatasetInput | None = None
    history: list[ChatHistoryTurn] = Field(default_factory=list, max_length=12)
    previous_analysis_plan: AnalysisPlan | None = None
    previous_advanced_plan: AdvancedAnalysisPlan | None = None
    previous_prediction_plan: PredictionPlan | None = None


class DatasetQueryRequest(BaseModel):
    dataset: DatasetInput
    plan: AnalysisPlan


class AdvancedAnalysisRequest(BaseModel):
    dataset: DatasetInput
    plan: AdvancedAnalysisPlan


class PredictionRequest(BaseModel):
    dataset: DatasetInput
    plan: PredictionPlan


def _dataset_citation(profile: dict[str, Any], *, section: str) -> dict[str, Any]:
    fingerprint = str(profile["fingerprint_sha256"])
    return {
        "source_id": f"dataset:{fingerprint[:24]}",
        "source_type": "dataset",
        "title": f"업로드 데이터 분석 · {profile['filename']}",
        "repository": "session-only",
        "path": "#uploaded-dataset",
        "section": section,
        "observed_at": profile["generated_at"],
        "content_hash": fingerprint,
        "freshness_status": "session",
        "excerpt": (
            f"{profile['row_count']}행 × {profile['column_count']}열, "
            f"결측 {profile['missing_cell_count']}개; 원본은 저장하지 않음"
        ),
        "url": "#uploaded-dataset",
        "retrieval_score": 1.0,
    }


def _display_analysis_value(value: Any) -> str:
    if value is None:
        return "계산 불가"
    if isinstance(value, bool):
        return "참" if value else "거짓"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if not math.isfinite(value):
            return "계산 불가"
        if value != 0 and abs(value) < 0.0001:
            return f"{value:.3e}"
        return f"{value:,.6f}".rstrip("0").rstrip(".")
    return str(value)


def _analysis_result_insight(result: ExecutionResult) -> str:
    if result.output_row_count == 0:
        return "현재 조건에 맞는 행은 없습니다."
    plan = result.plan
    if plan.operation == "aggregate" and plan.metrics:
        metric = plan.metrics[0]
        alias = metric.alias
        operation_labels = {
            "count": "건수",
            "share": "비율",
            "count_distinct": "고유값 수",
            "sum": "합계",
            "mean": "평균",
            "median": "중앙값",
            "stddev": "표준편차",
            "min": "최솟값",
            "max": "최댓값",
        }
        if metric.operation == "correlation" and result.rows:
            numeric_rows = [
                row
                for row in result.rows
                if isinstance(row.get(alias), (int, float))
                and math.isfinite(float(row[alias]))
            ]
            if plan.group_by:
                if not numeric_rows:
                    return "그룹별 유효한 관측쌍에서 상관계수를 계산할 수 없었습니다."
                strongest = max(numeric_rows, key=lambda row: abs(float(row[alias])))
                group = ", ".join(
                    f"{name}={strongest.get(name)}" for name in plan.group_by
                )
                coefficient = float(strongest[alias])
                return (
                    f"{', '.join(plan.group_by)}별 {metric.column}–"
                    f"{metric.secondary_column} Pearson 상관계수: "
                    f"절댓값이 가장 큰 그룹은 {group} "
                    f"(r={_display_analysis_value(coefficient)})이며, "
                    f"유효한 결과는 {len(numeric_rows)}개 그룹입니다."
                )
            value = result.rows[0].get(alias)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                return "유효한 관측쌍에서 상관계수를 계산할 수 없었습니다."
            coefficient = float(value)
            magnitude = abs(coefficient)
            strength = (
                "강한"
                if magnitude >= 0.7
                else "중간 정도의"
                if magnitude >= 0.4
                else "약한"
                if magnitude >= 0.2
                else "매우 약한"
            )
            direction = "양의" if coefficient > 0 else "음의" if coefficient < 0 else "없는"
            return (
                f"{metric.column}–{metric.secondary_column} Pearson 상관계수: "
                f"{_display_analysis_value(coefficient)}. {strength} {direction} 선형 관계가 관찰됩니다."
            )
        label = operation_labels.get(metric.operation, metric.operation)
        target = metric.column or "행"
        if not plan.group_by and result.rows:
            return f"{target} {label}: {_display_analysis_value(result.rows[0].get(alias))}."
        numeric_rows = [
            row
            for row in result.rows
            if isinstance(row.get(alias), (int, float))
            and math.isfinite(float(row[alias]))
        ]
        if numeric_rows:
            highest = max(numeric_rows, key=lambda row: float(row[alias]))
            lowest = min(numeric_rows, key=lambda row: float(row[alias]))

            def group_name(row: dict[str, Any]) -> str:
                return ", ".join(f"{name}={row.get(name)}" for name in plan.group_by)

            high_text = (
                f"{group_name(highest)} "
                f"({_display_analysis_value(highest.get(alias))})"
            )
            if highest is lowest or highest.get(alias) == lowest.get(alias):
                return (
                    f"{', '.join(plan.group_by)}별 {target} {label}: "
                    f"{len(numeric_rows)}개 그룹이 모두 "
                    f"{_display_analysis_value(highest.get(alias))}로 같습니다."
                )
            low_text = (
                f"{group_name(lowest)} "
                f"({_display_analysis_value(lowest.get(alias))})"
            )
            return (
                f"{', '.join(plan.group_by)}별 {target} {label}: 최고 {high_text}, "
                f"최저 {low_text}."
            )
    if plan.operation == "select" and plan.order_by and result.rows:
        sort = plan.order_by[0]
        first = result.rows[0]
        manifest_lookup = {column.name: column for column in result.dataset.columns}
        descriptor_columns = [column for column in result.columns if column != sort.column]
        descriptor_columns.sort(
            key=lambda name: (
                bool(manifest_lookup[name].numeric),
                bool(manifest_lookup[name].temporal),
                result.columns.index(name),
            )
        )
        descriptors = [
            f"{column}={first.get(column)}"
            for column in descriptor_columns
        ][:2]
        rank_label = "상위" if sort.direction == "desc" else "하위"
        subject = ", ".join(descriptors) or "첫 번째 행"
        return (
            f"{sort.column} 기준 {rank_label} 첫 행: {subject}; "
            f"{sort.column}={_display_analysis_value(first.get(sort.column))}."
        )
    return (
        f"현재 조건에 맞는 {result.denominator_row_count}행 중 "
        f"{result.output_row_count}행을 확인했습니다."
    )


def _advanced_result_insight(result: AdvancedAnalysisResult) -> str:
    stats = result.statistics
    column = result.plan.columns[0]
    if result.plan.operation == "distribution":
        return (
            f"{column} 분포: 평균 {_display_analysis_value(stats.get('mean'))}, "
            f"중앙값 {_display_analysis_value(stats.get('median'))}, "
            f"표준편차 {_display_analysis_value(stats.get('stddev'))}."
        )
    if result.plan.operation == "outliers":
        return (
            f"{column} IQR 기준 이상치는 {stats.get('outlier_count', 0)}개"
            f"({_display_analysis_value(float(stats.get('outlier_rate', 0)) * 100)}%)이며, "
            f"정상 범위는 {_display_analysis_value(stats.get('lower_bound'))}~"
            f"{_display_analysis_value(stats.get('upper_bound'))}입니다."
        )
    if result.plan.operation == "relationship":
        second = result.plan.columns[1]
        return (
            f"{column}–{second} 관계: Pearson r={_display_analysis_value(stats.get('pearson_r'))}, "
            f"Spearman ρ={_display_analysis_value(stats.get('spearman_rho'))}, "
            f"완전한 관측쌍 {stats.get('pair_count', result.valid_row_count)}개."
        )
    if result.plan.operation == "group_comparison":
        p_value = stats.get("p_value")
        significance = (
            "0.05 미만"
            if isinstance(p_value, (int, float)) and float(p_value) < 0.05
            else "0.05 이상"
        )
        return (
            f"{result.plan.group_by}별 {column} 비교: {stats.get('test')} "
            f"p-value={_display_analysis_value(p_value)}({significance}), "
            f"{stats.get('effect_size_name')}={_display_analysis_value(stats.get('effect_size'))}."
        )
    return (
        f"{column} 시계열: 첫 값 {_display_analysis_value(stats.get('first_value'))}에서 "
        f"마지막 값 {_display_analysis_value(stats.get('last_value'))}으로, "
        f"총 변화 {_display_analysis_value(stats.get('total_change'))}."
    )


def _dataset_profile_chat_payload(
    question: str,
    profile: dict[str, Any],
    outcome: PlanningOutcome,
    history_turns: int,
) -> dict[str, Any]:
    citation = _dataset_citation(profile, section="dataset profile")
    columns = [
        str(item.get("name"))
        for item in profile.get("columns", [])
        if isinstance(item, dict) and item.get("name")
    ]
    shown_columns = ", ".join(columns[:8])
    if len(columns) > 8:
        shown_columns += f" 외 {len(columns) - 8}개"
    structure = profile.get("table_structure_normalization", {})
    title = structure.get("detected_title") if isinstance(structure, dict) else None
    subject = f"‘{title}’ 표" if title else f"{profile.get('filename')}"
    header_note = ""
    if isinstance(structure, dict) and int(structure.get("header_row", 1)) > 1:
        header_note = (
            f" 원본 {structure['header_row']}행을 실제 header로 감지해 "
            f"앞의 {structure.get('preamble_rows_removed', 0)}행을 분석 대상에서 제외했습니다."
        )
    missing_columns = sorted(
        (
            (str(item.get("name")), int(item.get("missing_count", 0)))
            for item in profile.get("columns", [])
            if isinstance(item, dict) and int(item.get("missing_count", 0)) > 0
        ),
        key=lambda item: (-item[1], item[0]),
    )
    missing_note = ""
    if missing_columns:
        missing_note = " 결측이 있는 컬럼은 " + ", ".join(
            f"{name} {count}개" for name, count in missing_columns[:5]
        ) + "입니다."
    answer = (
        f"업로드한 파일은 {subject}로 보입니다.{header_note} "
        f"현재 분석 대상은 {profile.get('row_count')}행 × {profile.get('column_count')}열이며, "
        f"컬럼은 {shown_columns or '확인되지 않음'}입니다. "
        f"수치형 컬럼은 {profile.get('numeric_column_count')}개, 전체 결측 셀은 "
        f"{profile.get('missing_cell_count')}개입니다.{missing_note} [1]"
    )
    missing_rows_requested = bool(
        re.search(
            r"(?:결측|비어\s*있는|누락|null|missing).*(?:행|데이터)",
            question,
            re.I,
        )
    )
    next_action = "비교 기준과 수치 컬럼을 지정해 집계·필터·순위 질문을 이어가세요."
    if missing_rows_requested and int(profile.get("missing_cell_count", 0)) == 0:
        answer = (
            f"현재 {profile.get('row_count')}행 × {profile.get('column_count')}열 전체에서 "
            "결측 셀이 0개이므로 결측치가 있는 행도 0개입니다. [1]"
        )
        next_action = "결측 처리는 필요하지 않습니다. 중복·분포·이상치 등 다른 품질 점검을 이어가세요."
    return {
        "question": question,
        "status": "ANSWER",
        "mode": "deterministic-profile",
        "answer": answer,
        "risk": "설명은 파일 제목·header·기술 통계를 바탕으로 하며 업무 의미를 임의로 추정하지 않습니다.",
        "next_action": next_action,
        "claims": [{"text": answer, "citation_ids": [citation["source_id"]]}],
        "citations": [citation],
        "retrieval": {
            "strategy": "deterministic-dataset-profile",
            "vector_store": "not_used_for_dataset_profile",
            "returned_evidence": 1,
        },
        "dataset_profile": profile,
        "planning": outcome.model_dump(mode="json"),
        "conversation": {
            "context_used": False,
            "history_turns_received": history_turns,
            "user_turns_used": 0,
            "scope": "current_dataset_profile",
        },
        "safety": {
            "read_only": True,
            "unsafe_request_detected": False,
            "unsafe_context_detected": False,
            "deterministic_gate_is_source_of_truth": True,
        },
        "llm": {"provider": "deterministic-profiler", "status": "not_called"},
    }


def _preferred_numeric_columns(profile: dict[str, Any]) -> list[dict[str, Any]]:
    numeric = [
        item
        for item in profile.get("columns", [])
        if isinstance(item, dict) and isinstance(item.get("numeric"), dict)
    ]
    primary_hints = ("배출량", "금액", "amount", "revenue", "sales", "value")
    secondary_hints = ("횟수", "건수", "count", "orders", "duration")

    def priority(item: dict[str, Any]) -> tuple[int, int]:
        name = str(item.get("name", "")).casefold()
        if any(token in name for token in primary_hints):
            return 0, numeric.index(item)
        if any(token in name for token in secondary_hints):
            return 1, numeric.index(item)
        return 2, numeric.index(item)

    return sorted(numeric, key=priority)


def _preferred_categorical_columns(profile: dict[str, Any]) -> list[dict[str, Any]]:
    columns = [item for item in profile.get("columns", []) if isinstance(item, dict)]
    categorical = [
        item
        for item in columns
        if "numeric" not in item
        and "temporal" not in item
        and 1 < int(item.get("unique_count", 0)) <= 50
    ]
    row_count = max(1, int(profile.get("row_count", 1)))
    categorical.sort(
        key=lambda item: int(int(item.get("unique_count", 0)) / row_count >= 0.8)
    )
    return categorical


def _coordinate_particle(value: str) -> str:
    stripped = value.rstrip()
    if not stripped:
        return "와"
    last = stripped[-1]
    if "가" <= last <= "힣":
        return "과" if (ord(last) - ord("가")) % 28 else "와"
    if last in ")]}":
        return "과"
    return "와"


def _capability_examples(
    profile: dict[str, Any],
    *,
    summary_labels: list[str],
) -> list[tuple[str, str]]:
    numeric = _preferred_numeric_columns(profile)
    categorical = _preferred_categorical_columns(profile)
    prefix = f"{' 및 '.join(summary_labels)} 행을 제외하고 " if summary_labels else ""
    examples: list[tuple[str, str]] = []
    primary = str(numeric[0]["name"]) if numeric else None
    category = str(categorical[0]["name"]) if categorical else None

    if primary:
        examples.append(("순위", f"{prefix}{primary} 기준 상위 5개 보여줘"))
    if primary and category:
        examples.append(("그룹 비교", f"{prefix}{category}별 {primary} 평균"))
    if len(numeric) >= 2:
        secondary_candidates = [
            item
            for item in numeric[1:]
            if any(
                token in str(item["name"]).casefold()
                for token in ("횟수", "건수", "count", "orders")
            )
        ]
        secondary = str((secondary_candidates or numeric[1:])[0]["name"])
        examples.append(
            ("관계", f"{prefix}{primary}{_coordinate_particle(primary)} {secondary} 상관계수")
        )
    if category:
        examples.append(("빈도", f"{prefix}{category}별 건수"))
    examples.append(("품질", "이 데이터의 행, 열, 결측을 분석해줘"))
    return examples[:5]


def _additional_capability_examples(
    profile: dict[str, Any],
    *,
    summary_labels: list[str],
) -> list[tuple[str, str]]:
    numeric = _preferred_numeric_columns(profile)
    categorical = _preferred_categorical_columns(profile)
    prefix = f"{' 및 '.join(summary_labels)} 행을 제외하고 " if summary_labels else ""
    examples: list[tuple[str, str]] = []
    primary = str(numeric[0]["name"]) if numeric else None
    category = str(categorical[0]["name"]) if categorical else None
    count_hints = ("횟수", "건수", "count", "orders", "duration")
    count_like = [
        str(item["name"])
        for item in numeric[1:]
        if any(token in str(item["name"]).casefold() for token in count_hints)
    ]
    secondary = (
        count_like[0]
        if count_like
        else (str(numeric[1]["name"]) if len(numeric) >= 2 else primary)
    )

    if primary:
        examples.append(("중앙값", f"{prefix}{primary} 중앙값"))
        examples.append(("변동성", f"{prefix}{primary} 표준편차"))
    if secondary:
        examples.append(("하위 순위", f"{prefix}{secondary} 기준 하위 5개 보여줘"))
    if category and secondary:
        examples.append(("다른 그룹 비교", f"{prefix}{category}별 {secondary} 평균"))

    numeric_names = [str(item["name"]) for item in numeric]
    original_relationship = {primary, secondary}
    alternate_left: str | None = None
    alternate_right: str | None = None
    for index, left in enumerate(numeric_names):
        for right in numeric_names[index + 1 :]:
            pair = {left, right}
            expanded_mentions = {
                candidate
                for selected in pair
                for candidate in numeric_names
                if candidate.casefold() in selected.casefold()
            }
            if pair != original_relationship and expanded_mentions == pair:
                alternate_left, alternate_right = left, right
                break
        if alternate_left:
            break
    if alternate_left and alternate_right and alternate_left != alternate_right:
        examples.append(
            (
                "다른 관계",
                f"{prefix}{alternate_left}{_coordinate_particle(alternate_left)} "
                f"{alternate_right} 상관계수",
            )
        )
    if primary and category:
        examples.append(("그룹 합계", f"{prefix}{category}별 {primary} 합계"))
    if primary:
        examples.append(("최솟값", f"{prefix}{primary} 최소"))
        examples.append(("최댓값", f"{prefix}{primary} 최대"))

    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for label, prompt in examples:
        key = _capability_question_key(prompt)
        if key not in seen:
            unique.append((label, prompt))
            seen.add(key)
    return unique


def _data_science_capability_examples(
    profile: dict[str, Any],
    *,
    summary_labels: list[str],
) -> list[tuple[str, str]]:
    numeric = _preferred_numeric_columns(profile)
    categorical = _preferred_categorical_columns(profile)
    temporal = [
        item
        for item in profile.get("columns", [])
        if isinstance(item, dict) and isinstance(item.get("temporal"), dict)
    ]
    prefix = f"{' 및 '.join(summary_labels)} 행을 제외하고 " if summary_labels else ""
    examples: list[tuple[str, str]] = []
    primary = str(numeric[0]["name"]) if numeric else None
    if primary:
        examples.extend(
            [
                ("분포", f"{prefix}{primary} 히스토그램으로 분포 분석"),
                ("이상치", f"{prefix}{primary} IQR 이상치 찾아줘"),
            ]
        )
    if len(numeric) >= 2:
        examples.append(
            (
                "심화 관계",
                f"{prefix}{numeric[0]['name']}와 {numeric[1]['name']} Spearman 관계",
            )
        )
    if primary and categorical:
        examples.append(
            ("차이 검정", f"{prefix}{categorical[0]['name']}별 {primary} 차이 검정")
        )
    row_count = int(profile.get("row_count", 0))
    if primary and temporal and row_count >= 60:
        examples.append(
            (
                "Forecast",
                f"{temporal[0]['name']} 기준 {primary} 향후 7일 예측",
            )
        )
    elif len(numeric) >= 2 and row_count >= 100:
        examples.append(("회귀 예측", f"{primary} 회귀 모델로 예측"))
    return examples[:5]


def _prediction_requirements_note(profile: dict[str, Any]) -> str:
    row_count = int(profile.get("row_count", 0))
    temporal = [
        str(item.get("name"))
        for item in profile.get("columns", [])
        if isinstance(item, dict) and "temporal" in item
    ]
    readiness = (
        f"현재 {row_count}행이므로 supervised 예측의 최소 100행에 미달합니다."
        if row_count < 100
        else "현재 행수는 supervised 예측의 100행 1차 기준을 통과하지만 target 유효값과 누수 검증이 추가로 필요합니다."
    )
    forecast = (
        f" Forecast는 시간 컬럼({', '.join(temporal[:3])})과 최소 60개 완전한 시점이 필요합니다."
        if temporal
        else " Forecast는 시간 컬럼과 최소 60개 완전한 시점이 필요합니다."
    )
    return (
        "예측 실행 기준은 회귀·분류 target 유효값 최소 100행, 분류는 class별 최소 20행입니다. "
        f"{readiness}{forecast}"
    )


def _capability_question_key(question: str) -> str:
    return re.sub(r"[\W_]+", "", question.casefold(), flags=re.UNICODE)


def _is_additional_capability_request(question: str) -> bool:
    normalized = " ".join(question.casefold().split())
    return bool(
        re.search(r"(?:다른|추가|더|또|그\s*외|이외|다음)", normalized)
        or re.search(r"\b(?:else|more|other|additional|next)\b", normalized)
    )


def _conversation_capability_examples(
    question: str,
    profile: dict[str, Any],
    *,
    summary_labels: list[str],
    history: list[dict[str, str]],
) -> tuple[list[tuple[str, str]], int, bool]:
    primary = _capability_examples(profile, summary_labels=summary_labels)
    additional = _additional_capability_examples(profile, summary_labels=summary_labels)
    data_science = _data_science_capability_examples(
        profile, summary_labels=summary_labels
    )
    additional_requested = _is_additional_capability_request(question)
    data_science_requested = bool(
        re.search(r"(?:심화|고급|예측|모델|forecast|prediction)", question, re.I)
    )
    if data_science_requested:
        candidates = data_science + additional + primary
    else:
        candidates = additional + data_science + primary if additional_requested else primary + additional + data_science
    used = {
        _capability_question_key(str(turn.get("content", "")))
        for turn in history
        if turn.get("role") == "user"
    }
    examples: list[tuple[str, str]] = []
    seen: set[str] = set()
    excluded = 0
    for label, prompt in candidates:
        key = _capability_question_key(prompt)
        if key in seen:
            continue
        seen.add(key)
        if key in used:
            excluded += 1
            continue
        examples.append((label, prompt))
        if len(examples) == 5:
            break
    return examples, excluded, additional_requested


def _overview_number(value: Any) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else round(number, 6)


def _overview_statistics(
    profile: dict[str, Any],
    frame: pd.DataFrame,
    summary_column_labels: list[tuple[str, str]],
) -> dict[str, Any]:
    columns = [
        "column",
        "count",
        "missing",
        "min",
        "q1",
        "mean",
        "median",
        "q3",
        "max",
        "stddev",
    ]
    summary_mask = pd.Series(False, index=frame.index, dtype=bool)
    for column, label in summary_column_labels:
        normalized = frame[column].astype("string").str.strip().str.casefold()
        summary_mask |= normalized.eq(label.casefold()).fillna(False)
    statistics_frame = frame.loc[~summary_mask]
    rows: list[dict[str, Any]] = []
    for item in profile.get("columns", []):
        numeric = item.get("numeric") if isinstance(item, dict) else None
        if not isinstance(numeric, dict):
            continue
        values = pd.to_numeric(statistics_frame[item["name"]], errors="coerce")
        rows.append(
            {
                "column": item.get("name"),
                "count": int(values.count()),
                "missing": int(values.isna().sum()),
                "min": _overview_number(values.min()),
                "q1": _overview_number(values.quantile(0.25)),
                "mean": _overview_number(values.mean()),
                "median": _overview_number(values.median()),
                "q3": _overview_number(values.quantile(0.75)),
                "max": _overview_number(values.max()),
                "stddev": _overview_number(values.std()),
            }
        )
    return {
        "numeric_source_of_truth": "pandas-profile",
        "input_row_count": int(len(frame)),
        "denominator_row_count": int(len(statistics_frame)),
        "excluded_summary_row_count": int(summary_mask.sum()),
        "columns": columns,
        "rows": rows[:8],
        "total_numeric_columns": len(rows),
        "truncated": len(rows) > 8,
    }


def _dataset_overview_chat_payload(
    question: str,
    profile: dict[str, Any],
    outcome: PlanningOutcome,
    frame: Any,
    history_turns: int,
) -> dict[str, Any]:
    citation = _dataset_citation(profile, section="automatic dataset overview")
    profile_answer = _dataset_profile_chat_payload(
        question,
        profile,
        outcome,
        history_turns,
    )["answer"].removesuffix(" [1]")
    summary_rows, summary_column_labels = summary_row_details(frame)
    summary_labels = list(dict.fromkeys(label for _, label in summary_column_labels))
    examples = _capability_examples(profile, summary_labels=summary_labels)
    statistics = _overview_statistics(profile, frame, summary_column_labels)
    answer = (
        f"{profile_answer} 업로드 직후 품질 점검과 수치형 컬럼 "
        f"{statistics['total_numeric_columns']}개의 기초 통계를 계산했습니다. "
        f"중복 행은 {profile.get('duplicate_row_count', 0)}개입니다. [1]"
    )
    risk = "업무 의미나 인과관계는 추정하지 않고 구조·품질·기술 통계만 자동 계산했습니다."
    if summary_rows:
        risk = (
            f"합계·총계 성격의 행 {summary_rows}개({', '.join(summary_labels)})를 감지했습니다. "
            "원본에는 유지하고 후속 집계·순위에서 기본 제외합니다."
        )
    return {
        "question": question,
        "status": "ANSWER",
        "mode": "deterministic-overview",
        "answer": answer,
        "risk": risk,
        "next_action": "추천 분석을 선택하거나 원하는 비교 기준·수치·조건을 자연어로 입력하세요.",
        "claims": [{"text": answer, "citation_ids": [citation["source_id"]]}],
        "citations": [citation],
        "retrieval": {
            "strategy": "deterministic-dataset-onboarding",
            "vector_store": "not_used_for_dataset_overview",
            "returned_evidence": 1,
        },
        "dataset_profile": profile,
        "overview": {
            "auto_generated": True,
            "statistics": statistics,
            "quality": {
                "missing_cell_count": profile.get("missing_cell_count", 0),
                "duplicate_row_count": profile.get("duplicate_row_count", 0),
                "summary_row_count": summary_rows,
            },
        },
        "suggested_questions": [
            {"label": label, "question": suggested_question}
            for label, suggested_question in examples
        ],
        "planning": outcome.model_dump(mode="json"),
        "conversation": {
            "context_used": False,
            "history_turns_received": history_turns,
            "user_turns_used": 0,
            "scope": "automatic_dataset_onboarding",
        },
        "safety": {
            "read_only": True,
            "unsafe_request_detected": False,
            "unsafe_context_detected": False,
            "deterministic_gate_is_source_of_truth": True,
        },
        "llm": {"provider": "deterministic-profiler", "status": "not_called"},
    }


def _dataset_capability_chat_payload(
    question: str,
    profile: dict[str, Any],
    outcome: PlanningOutcome,
    frame: Any,
    history: list[dict[str, str]],
) -> dict[str, Any]:
    citation = _dataset_citation(profile, section="dataset analysis capabilities")
    summary_rows, summary_column_labels = summary_row_details(frame)
    summary_labels = list(dict.fromkeys(label for _, label in summary_column_labels))
    examples, excluded, additional_requested = _conversation_capability_examples(
        question,
        profile,
        summary_labels=summary_labels,
        history=history,
    )
    example_text = "\n".join(f"• {label}: {prompt}" for label, prompt in examples)
    guide_label = "추가 분석" if additional_requested or excluded else "다음 분석"
    history_note = (
        f" 이 채팅에서 이미 사용한 추천 {excluded}개는 제외했습니다."
        if excluded
        else ""
    )
    prediction_requested = bool(
        re.search(r"(?:예측|모델|forecast|prediction|regression|classification)", question, re.I)
    )
    requirements_note = _prediction_requirements_note(profile) if prediction_requested else ""
    if examples:
        answer = (
            f"{requirements_note}{chr(10) if requirements_note else ''}"
            f"현재 {profile.get('row_count')}행 × {profile.get('column_count')}열 기준으로 "
            f"{guide_label}을 바로 실행할 수 있습니다.{history_note}\n{example_text} [1]"
        )
        next_action = f"먼저 ‘{examples[0][1]}’처럼 질문하거나 추천 버튼을 선택하세요."
    else:
        answer = (
            f"{requirements_note}{chr(10) if requirements_note else ''}"
            f"현재 {profile.get('row_count')}행 × {profile.get('column_count')}열에서 지원하는 "
            f"추천 분석은 이 채팅에서 모두 사용했습니다.{history_note} [1]"
        )
        next_action = "원하는 컬럼과 집계 방법·필터 조건을 직접 입력하거나 분석 조건을 초기화하세요."
    if summary_rows:
        label_text = ", ".join(summary_labels)
        risk = (
            f"합계·총계 성격의 행 {summary_rows}개({label_text})가 감지되었습니다. "
            "집계·순위에서는 해당 행을 기본 제외해 이중 집계를 피합니다. "
            "원하면 ‘합계 행도 포함해서’라고 명시할 수 있습니다."
        )
    else:
        risk = "추천 질문은 현재 감지된 컬럼과 지원하는 deterministic 연산 범위에서만 생성했습니다."
    return {
        "question": question,
        "status": "ANSWER",
        "mode": "deterministic-capabilities",
        "answer": answer,
        "risk": risk,
        "next_action": next_action,
        "claims": [{"text": answer, "citation_ids": [citation["source_id"]]}],
        "citations": [citation],
        "retrieval": {
            "strategy": "dataset-schema-capability-guide",
            "vector_store": "not_used_for_capability_guide",
            "returned_evidence": 1,
        },
        "dataset_profile": profile,
        "suggested_questions": [
            {"label": label, "question": suggested_question}
            for label, suggested_question in examples
        ],
        "planning": outcome.model_dump(mode="json"),
        "conversation": {
            "context_used": bool(history),
            "history_turns_received": len(history),
            "user_turns_used": sum(turn.get("role") == "user" for turn in history),
            "scope": "current_dataset_capabilities",
        },
        "safety": {
            "read_only": True,
            "unsafe_request_detected": False,
            "unsafe_context_detected": False,
            "deterministic_gate_is_source_of_truth": True,
        },
        "llm": {"provider": "deterministic-profiler", "status": "not_called"},
    }


def _dataset_conversation_chat_payload(
    question: str,
    profile: dict[str, Any],
    outcome: PlanningOutcome,
    frame: pd.DataFrame,
    history_turns: int,
) -> dict[str, Any]:
    citation = _dataset_citation(profile, section="connected dataset conversation")
    _, summary_column_labels = summary_row_details(frame)
    summary_labels = list(dict.fromkeys(label for _, label in summary_column_labels))
    examples = _capability_examples(profile, summary_labels=summary_labels)[:4]
    normalized = question.casefold()
    if re.match(r"^(?:안녕|안녕하세요|반가워|hello\b|hi\b)", normalized):
        answer = (
            f"안녕하세요. 현재 대화에는 {profile['filename']} 파일이 연결되어 있습니다. "
            "데이터 설명, 집계, 필터, 순위, 통계나 예측 조건을 편하게 물어보세요. [1]"
        )
    elif re.match(r"^(?:고마워|감사|좋아|알겠어|오케이|okay\b|ok\b)", normalized):
        answer = (
            f"좋습니다. {profile['filename']}은 그대로 유지되고 있으니 원하는 조건을 이어서 "
            "계속 질문하면 됩니다. [1]"
        )
    else:
        answer = (
            "같은 파일에서 ‘지역별 매출 합계’처럼 새 분석을 요청하거나, 결과 뒤에 "
            "‘평균으로 바꿔줘’, ‘web만 봐줘’, ‘그 결과가 무슨 의미야?’처럼 이어서 물어보세요. [1]"
        )
    return {
        "question": question,
        "status": "ANSWER",
        "mode": "dataset-conversation",
        "answer": answer,
        "risk": "숫자와 분석 결과는 대화 문장이 아니라 검증된 plan과 계산 engine에서 가져옵니다.",
        "next_action": "아래 예시를 선택하거나 원하는 분석을 자연어로 입력하세요.",
        "claims": [{"text": answer, "citation_ids": [citation["source_id"]]}],
        "citations": [citation],
        "retrieval": {"strategy": "connected-dataset-conversation", "returned_evidence": 1},
        "dataset_profile": profile,
        "suggested_questions": [
            {"label": label, "question": prompt} for label, prompt in examples
        ],
        "planning": outcome.model_dump(mode="json"),
        "conversation": {
            "context_used": bool(history_turns),
            "history_turns_received": history_turns,
            "scope": "current_dataset_conversation",
        },
        "safety": {
            "read_only": True,
            "deterministic_gate_is_source_of_truth": True,
        },
        "llm": {"provider": "deterministic-conversation", "status": "not_called"},
    }


def _analysis_chat_payload(
    question: str,
    profile: dict[str, Any],
    outcome: PlanningOutcome,
    result: ExecutionResult,
    history_turns: int,
    context_used: bool,
) -> dict[str, Any]:
    citation = _dataset_citation(profile, section="validated analysis result")
    insight = _analysis_result_insight(result)
    if outcome.message == RESULT_INTERPRETATION_MESSAGE and re.search(r"^\s*왜", question):
        insight = (
            "업로드 데이터만으로 원인을 단정할 수는 없습니다. "
            f"현재 관찰되는 차이는 다음과 같습니다. {insight}"
        )
    summary_labels = list(
        dict.fromkeys(
            str(item.value)
            for item in result.plan.filters
            if item.operator == "ne"
            and str(item.value).strip().casefold() in SUMMARY_ROW_LABELS
        )
    )
    observation = ""
    if (
        result.plan.operation == "aggregate"
        and len(result.plan.group_by) == 1
        and len(result.plan.metrics) == 1
        and result.plan.metrics[0].operation == "count"
        and len(result.rows) > 1
    ):
        alias = result.plan.metrics[0].alias
        values = [row.get(alias) for row in result.rows]
        if values and len(set(values)) == 1:
            observation = (
                f" {result.plan.group_by[0]}별 {len(result.rows)}개 그룹은 "
                f"모두 {values[0]}건입니다."
            )
    summary_note = ""
    if summary_labels:
        summary_note = (
            f" 감지한 summary row({', '.join(summary_labels)})는 "
            "분모에서 제외했습니다."
        )
    execution_note = (
        "같은 검증 계획을 다시 계산해 확인했습니다. "
        if outcome.message == RESULT_INTERPRETATION_MESSAGE
        else ""
    )
    answer = (
        f"{insight} {execution_note}전체 {result.input_row_count}행 중 "
        f"{result.denominator_row_count}행을 계산에 사용했고 결과는 {result.output_row_count}행입니다."
        f"{summary_note}{observation} [1]"
    )
    risk = "결과는 현재 업로드한 데이터와 사용자가 확인한 분석 조건에만 해당합니다."
    next_action = (
        "현재 분석 조건은 이 채팅에 유지됩니다. 표의 행수·분모와 SQL을 확인한 뒤 "
        "필터·그룹·수치 컬럼·집계 방법을 이어서 수정하세요."
    )
    if summary_labels:
        risk = (
            f"원본 {result.input_row_count}행은 유지하고 summary row만 분석 분모에서 제외했습니다. "
            "실행 SQL과 AnalysisPlan에서 제외 조건을 확인할 수 있으며, "
            "원하면 ‘합계 행도 포함해서’라고 명시할 수 있습니다."
        )
    if observation:
        next_action = (
            "모든 그룹이 1건이면 식별자 수준 집계라 비교 정보가 적습니다. "
            "요일처럼 반복되는 범주로 바꿔 질문해 보세요."
        )
    if result.plan.metrics and result.plan.metrics[0].operation == "correlation":
        risk = (
            "상관계수는 두 수치의 선형 동행 정도이며 인과관계를 뜻하지 않습니다. "
            "표본 수, 이상치와 산점도를 함께 확인해야 합니다."
        )
        next_action = (
            "비선형·순위 관계도 확인하려면 같은 두 컬럼으로 Spearman 관계 분석을 요청하세요."
        )
    return {
        "question": question,
        "status": "ANSWER",
        "mode": "deterministic-analysis",
        "answer": answer,
        "risk": risk,
        "next_action": next_action,
        "claims": [{"text": answer, "citation_ids": [citation["source_id"]]}],
        "citations": [citation],
        "retrieval": {
            "strategy": "validated-analysis-plan+duckdb",
            "vector_store": "not_used_for_numeric_analysis",
            "returned_evidence": 1,
        },
        "dataset_profile": profile,
        "analysis": result.model_dump(mode="json"),
        "planning": outcome.model_dump(mode="json"),
        "conversation": {
            "context_used": context_used,
            "history_turns_received": history_turns,
            "user_turns_used": 1 if context_used else 0,
            "scope": "previous_validated_analysis_plan" if context_used else "current_question_only",
        },
        "safety": {
            "read_only": True,
            "unsafe_request_detected": False,
            "unsafe_context_detected": False,
            "deterministic_gate_is_source_of_truth": True,
        },
        "llm": {"provider": "deterministic-planner", "status": "not_called"},
    }


def _advanced_chat_payload(
    question: str,
    profile: dict[str, Any],
    outcome: DataSciencePlanningOutcome,
    result: AdvancedAnalysisResult,
    history_turns: int,
) -> dict[str, Any]:
    citation = _dataset_citation(profile, section="validated advanced analysis")
    operation_labels = {
        "distribution": "분포 분석",
        "outliers": "이상치 분석",
        "group_comparison": "그룹 비교",
        "relationship": "관계 분석",
        "time_series": "시계열 탐색",
    }
    label = operation_labels[result.plan.operation]
    insight = _advanced_result_insight(result)
    answer = (
        f"{insight} {label}에는 필터 후 {result.denominator_row_count}행 중 "
        f"계산 가능한 {result.valid_row_count}행을 사용했으며, 통계량과 차트 데이터를 "
        "동일한 결과 payload에서 반환했습니다. [1]"
    )
    risk = (
        "통계적 유의성은 실무적 중요성이나 인과관계를 뜻하지 않습니다. "
        + (" ".join(result.warnings) if result.warnings else "가정과 분모를 함께 확인하세요.")
    )
    return {
        "question": question,
        "status": "ANSWER",
        "mode": "deterministic-advanced-analysis",
        "answer": answer,
        "risk": risk,
        "next_action": "차트와 가정·검정법을 확인한 뒤 구간 수, window, 신뢰수준을 후속 질문으로 수정하세요.",
        "claims": [{"text": answer, "citation_ids": [citation["source_id"]]}],
        "citations": [citation],
        "retrieval": {
            "strategy": "typed-advanced-plan+duckdb+scipy+pandas",
            "vector_store": "not_used_for_numeric_analysis",
            "returned_evidence": 1,
        },
        "dataset_profile": profile,
        "advanced_analysis": result.model_dump(mode="json"),
        "planning": outcome.model_dump(mode="json"),
        "conversation": {
            "context_used": bool(history_turns),
            "history_turns_received": history_turns,
            "scope": "current_advanced_analysis_plan",
        },
        "safety": {
            "read_only": True,
            "unsafe_request_detected": False,
            "unsafe_context_detected": False,
            "deterministic_gate_is_source_of_truth": True,
        },
        "llm": {"provider": "deterministic-data-science-planner", "status": "not_called"},
    }


def _prediction_chat_payload(
    question: str,
    profile: dict[str, Any],
    outcome: DataSciencePlanningOutcome,
    result: PredictionResult,
    history_turns: int,
) -> dict[str, Any]:
    citation = _dataset_citation(profile, section="validated prediction result")
    primary_metric = result.model_card.primary_metric
    if result.status == "MODEL_READY":
        test_value = (result.test_metrics or {}).get(primary_metric)
        baseline_test = result.baseline.get("test_metrics", {}).get(primary_metric)
        answer = (
            f"선택 모델은 ‘{result.selected_model}’이며 held-out test {primary_metric}는 "
            f"{_display_analysis_value(test_value)}, baseline은 {_display_analysis_value(baseline_test)}입니다. "
            f"validation에서 baseline 개선을 확인한 뒤 test를 1회 평가했으며, "
            f"분할 근거·오차·불확실성·설명·model card를 함께 반환했습니다. [1]"
        )
        next_action = "test metric과 error analysis를 확인하고, 실제 사용 전 별도 외부 데이터로 재검증하세요."
    else:
        baseline_validation = result.baseline.get("validation_metrics", {}).get(primary_metric)
        candidate_values = [
            item.get("validation_metrics", {}).get(primary_metric)
            for item in result.candidates
            if isinstance(item, dict)
        ]
        candidate_values = [value for value in candidate_values if isinstance(value, (int, float))]
        best_candidate = min(candidate_values) if primary_metric in {"mae", "rmse", "log_loss"} and candidate_values else max(candidate_values) if candidate_values else None
        answer = (
            f"validation {primary_metric}: 가장 좋은 후보 {_display_analysis_value(best_candidate)}, "
            f"baseline {_display_analysis_value(baseline_validation)}. "
            f"{result.plan.task} 후보가 baseline을 충분히 개선하지 못했습니다. "
            "과장된 모델 승격을 막기 위해 NO_MODEL_GAIN으로 종료했습니다. [1]"
        )
        next_action = "target 정의, 누수 없는 feature, 표본 기간을 재검토한 뒤 다시 검증하세요."
    return {
        "question": question,
        "status": "ANSWER",
        "mode": "deterministic-prediction",
        "answer": answer,
        "risk": "이 결과는 업로드 데이터 내부의 제한된 offline 검증이며 미래 성능이나 인과효과를 보장하지 않습니다.",
        "next_action": next_action,
        "claims": [{"text": answer, "citation_ids": [citation["source_id"]]}],
        "citations": [citation],
        "retrieval": {
            "strategy": "typed-prediction-plan+baseline+held-out-test",
            "vector_store": "not_used_for_predictive_analysis",
            "returned_evidence": 1,
        },
        "dataset_profile": profile,
        "prediction": result.model_dump(mode="json"),
        "planning": outcome.model_dump(mode="json"),
        "conversation": {
            "context_used": bool(history_turns),
            "history_turns_received": history_turns,
            "scope": "current_prediction_plan",
        },
        "safety": {
            "read_only": True,
            "unsafe_request_detected": False,
            "unsafe_context_detected": False,
            "deterministic_gate_is_source_of_truth": True,
        },
        "llm": {"provider": "deterministic-data-science-planner", "status": "not_called"},
    }


def _data_science_clarification_payload(
    question: str,
    profile: dict[str, Any],
    outcome: DataSciencePlanningOutcome,
    history_turns: int,
) -> dict[str, Any]:
    return {
        "question": question,
        "status": "NEEDS_MORE_EVIDENCE",
        "mode": "data-science-clarification",
        "answer": outcome.message,
        "risk": "target·feature·시간·그룹 컬럼을 추측하면 서로 다른 통계나 모델이 생성될 수 있습니다.",
        "next_action": "실제 컬럼명과 원하는 분석·예측 대상을 질문에 포함해 주세요.",
        "claims": [],
        "citations": [],
        "retrieval": {"strategy": "typed-plan-clarification", "returned_evidence": 0},
        "dataset_profile": profile,
        "planning": outcome.model_dump(mode="json"),
        "conversation": {"context_used": False, "history_turns_received": history_turns},
        "safety": {"read_only": True, "deterministic_gate_is_source_of_truth": True},
        "llm": {"provider": "deterministic-data-science-planner", "status": "not_called"},
    }


def _friendly_data_science_guardrail(error: AnalysisContractError) -> str:
    message = str(error)
    supervised = re.search(
        r"(regression|classification) requires at least (\d+) rows with a target; found (\d+)",
        message,
    )
    if supervised:
        task = "회귀" if supervised.group(1) == "regression" else "분류"
        return (
            f"현재 target 유효값은 {int(supervised.group(3))}행이라 {task} 예측에 필요한 "
            f"최소 {int(supervised.group(2))}행을 충족하지 못했습니다."
        )
    forecast = re.search(
        r"forecasting requires at least (\d+) complete time points; found (\d+)",
        message,
    )
    if forecast:
        return (
            f"현재 완전한 시점은 {int(forecast.group(2))}개라 forecast에 필요한 "
            f"최소 {int(forecast.group(1))}개 시점을 충족하지 못했습니다."
        )
    minimum_rows = re.search(
        r"(distribution|outlier analysis|relationship analysis|time-series analysis) "
        r"requires at least (\d+) (?:valid numeric rows|complete pairs|complete time/value rows)",
        message,
    )
    if minimum_rows:
        labels = {
            "distribution": "분포 분석",
            "outlier analysis": "이상치 분석",
            "relationship analysis": "관계 분석",
            "time-series analysis": "시계열 분석",
        }
        return f"{labels[minimum_rows.group(1)]}에는 유효한 관측값이 최소 {minimum_rows.group(2)}개 필요합니다."
    if "target is constant" in message:
        return "target 값이 모두 같아 학습하고 평가할 변화가 없습니다. 값이 두 종류 이상인 target이 필요합니다."
    if "target leakage detected" in message:
        return "target과 동일한 feature가 감지되어 누수 방지를 위해 예측을 중단했습니다. 해당 feature를 제외해 주세요."
    if "rows per class" in message:
        return "가장 작은 class의 표본이 부족합니다. 분류는 class별 최소 20행이 필요합니다."
    if "no usable features remain" in message:
        return "누수·식별자·상수 feature를 제외한 뒤 사용할 feature가 남지 않았습니다."
    if "non-constant columns" in message:
        return "관계 분석에는 값이 변하는 수치 컬럼 두 개가 필요합니다."
    if "2..50 non-empty groups" in message:
        return "그룹 비교에는 값이 있는 그룹이 2개 이상 50개 이하여야 합니다."
    return "현재 데이터가 요청한 분석의 최소 표본·타입·누수 안전 조건을 충족하지 못했습니다."


def _data_science_guardrail_payload(
    question: str,
    profile: dict[str, Any],
    outcome: DataSciencePlanningOutcome,
    error: AnalysisContractError,
    history_turns: int,
) -> dict[str, Any]:
    citation = _dataset_citation(profile, section="data science safety gate")
    answer = _friendly_data_science_guardrail(error)
    return {
        "question": question,
        "status": "NEEDS_MORE_EVIDENCE",
        "mode": "data-science-guardrail",
        "answer": answer + " [1]",
        "risk": "조건을 낮춰 억지로 모델이나 통계를 실행하지 않고 안전 gate에서 중단했습니다.",
        "next_action": "표본 수, target 분포, 시간 컬럼과 누수 없는 feature를 보완한 뒤 다시 요청하세요.",
        "claims": [{"text": answer, "citation_ids": [citation["source_id"]]}],
        "citations": [citation],
        "retrieval": {"strategy": "data-science-safety-gate", "returned_evidence": 1},
        "dataset_profile": profile,
        "planning": outcome.model_dump(mode="json"),
        "conversation": {
            "context_used": bool(history_turns),
            "history_turns_received": history_turns,
            "scope": "current_dataset_safety_gate",
        },
        "safety": {
            "read_only": True,
            "deterministic_gate_is_source_of_truth": True,
            "execution_blocked": True,
        },
        "llm": {"provider": "deterministic-data-science-planner", "status": "not_called"},
    }


def _analysis_clarification_payload(
    question: str,
    profile: dict[str, Any],
    outcome: PlanningOutcome,
    history_turns: int,
) -> dict[str, Any]:
    citation = _dataset_citation(profile, section="dataset manifest")
    return {
        "question": question,
        "status": "NEEDS_MORE_EVIDENCE",
        "mode": "analysis-clarification",
        "answer": outcome.message,
        "risk": "분석 대상 컬럼이 모호하면 서로 다른 수치를 계산할 수 있습니다.",
        "next_action": "컬럼명, 집계 방법, 필요한 조건을 질문에 포함해 주세요.",
        "claims": [],
        "citations": [citation],
        "retrieval": {
            "strategy": "dataset-analysis-clarification",
            "vector_store": "not_used_for_analysis_clarification",
            "returned_evidence": 1,
        },
        "dataset_profile": profile,
        "planning": outcome.model_dump(mode="json"),
        "conversation": {
            "context_used": False,
            "history_turns_received": history_turns,
            "user_turns_used": 0,
            "scope": "current_question_only",
        },
        "safety": {
            "read_only": True,
            "unsafe_request_detected": False,
            "unsafe_context_detected": False,
            "deterministic_gate_is_source_of_truth": True,
        },
        "llm": {"provider": "deterministic-planner", "status": "clarification_required"},
    }


def _analysis_reset_payload(
    question: str,
    profile: dict[str, Any],
    outcome: PlanningOutcome,
    history_turns: int,
) -> dict[str, Any]:
    citation = _dataset_citation(profile, section="dataset manifest")
    answer = (
        f"분석 조건을 초기화했습니다. 업로드한 {profile['filename']}은 이 대화에 "
        "그대로 연결되어 있고 원본 데이터는 변경되지 않았습니다. [1]"
    )
    return {
        "question": question,
        "status": "ANSWER",
        "mode": "analysis-session-reset",
        "answer": answer,
        "risk": "집계·필터·정렬 상태만 지웠으며 업로드 원본은 덮어쓰거나 삭제하지 않았습니다.",
        "next_action": "원본 기준으로 새 분석을 질문하거나 추천 분석을 선택하세요.",
        "claims": [{"text": answer, "citation_ids": [citation["source_id"]]}],
        "citations": [citation],
        "retrieval": {
            "strategy": "dataset-analysis-session-reset",
            "vector_store": "not_used_for_analysis_session_reset",
            "returned_evidence": 1,
        },
        "dataset_profile": profile,
        "planning": outcome.model_dump(mode="json"),
        "conversation": {
            "context_used": True,
            "history_turns_received": history_turns,
            "user_turns_used": 1,
            "scope": "current_dataset_original",
        },
        "safety": {
            "read_only": True,
            "unsafe_request_detected": False,
            "unsafe_context_detected": False,
            "deterministic_gate_is_source_of_truth": True,
        },
        "llm": {"provider": "deterministic-planner", "status": "not_called"},
    }


LOGGER = logging.getLogger("decisionops_control_tower")
VALID_ROLES = {"viewer", "reviewer", "admin"}
WRITE_ROLES = {"reviewer", "admin"}
VALID_DEPLOYMENT_MODES = {"local", "hosted"}
MIN_HOSTED_CREDENTIAL_LENGTH = 24


def _configure_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")
    LOGGER.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser()


def _env_token() -> str:
    return os.environ.get("CONTROL_TOWER_API_TOKEN", "").strip()


def _parse_role_tokens(raw: str) -> dict[str, str]:
    """Parse role credentials as role:credential or role=credential chunks."""

    roles: dict[str, str] = {}
    if not raw.strip():
        return roles
    for chunk in raw.split(","):
        item = chunk.strip()
        if not item:
            continue
        separator = ":" if ":" in item else "=" if "=" in item else ""
        if not separator:
            raise ValueError("CONTROL_TOWER_ROLE_TOKENS must use role:credential chunks")
        role, credential = [part.strip() for part in item.split(separator, 1)]
        role = role.lower()
        if role not in VALID_ROLES:
            raise ValueError(f"unsupported control tower role: {role}")
        if not credential:
            raise ValueError("empty control tower credential is not allowed")
        if credential in roles:
            raise ValueError("duplicate control tower credential is not allowed")
        roles[credential] = role
    return roles


def _credential_digest(credential: str) -> str:
    return hashlib.sha256(credential.encode("utf-8")).hexdigest()


def _deployment_mode(value: str | None) -> str:
    mode = (value or os.environ.get("CONTROL_TOWER_DEPLOYMENT_MODE", "local")).strip().lower()
    if mode not in VALID_DEPLOYMENT_MODES:
        raise ValueError(
            "CONTROL_TOWER_DEPLOYMENT_MODE must be one of: "
            + ", ".join(sorted(VALID_DEPLOYMENT_MODES))
        )
    return mode


def _configured_auth_roles(
    auth_token: str | None,
    auth_roles: dict[str, str] | None,
    deployment_mode: str,
) -> dict[str, str]:
    if auth_roles is not None:
        raw_roles: dict[str, str] = {}
        for credential, role in auth_roles.items():
            credential = credential.strip()
            role = role.strip().lower()
            if not credential:
                raise ValueError("empty control tower credential is not allowed")
            if role not in VALID_ROLES:
                raise ValueError(f"unsupported control tower role: {role}")
            raw_roles[credential] = role
    else:
        raw_roles = _parse_role_tokens(os.environ.get("CONTROL_TOWER_ROLE_TOKENS", ""))
        legacy_token = _env_token() if auth_token is None else auth_token.strip()
        if legacy_token:
            if legacy_token in raw_roles:
                raise ValueError("duplicate control tower credential is not allowed")
            raw_roles[legacy_token] = "reviewer"

    if deployment_mode == "hosted":
        if not raw_roles:
            raise ValueError("hosted deployment requires write authentication credentials")
        if not set(raw_roles.values()).intersection(WRITE_ROLES):
            raise ValueError("hosted deployment requires a reviewer or admin credential")
        if any(len(credential) < MIN_HOSTED_CREDENTIAL_LENGTH for credential in raw_roles):
            raise ValueError(
                f"hosted credentials must be at least {MIN_HOSTED_CREDENTIAL_LENGTH} characters"
            )

    return {_credential_digest(credential): role for credential, role in raw_roles.items()}


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _needs_pipeline_refresh(output_root: Path) -> bool:
    required = [
        output_root / "reports" / "control_state.json",
        output_root / "reports" / "control_review_queue.csv",
        output_root / "reports" / "impact_cards.json",
        output_root / "reports" / "impact_policy_audit.json",
        output_root / "reports" / "reviewer_policy_robustness.json",
        output_root / "reports" / "reviewer_action_plan.json",
        output_root / "reports" / "reviewer_evidence_bundles.json",
        output_root / "reports" / "agent_reviewer_brief.json",
        output_root / "reports" / "approval_audit_integrity.json",
        output_root / "reports" / "api_contract.json",
        output_root / "dashboard" / "index.html",
    ]
    return not all(path.is_file() for path in required)


def _artifact_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "size_bytes": 0, "mtime_utc": None}
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime)),
    }


def create_app(
    output_root: Path | str | None = None,
    bike_root: Path | str | None = None,
    workbench_root: Path | str | None = None,
    refresh_artifacts: bool = True,
    auth_token: str | None = None,
    auth_roles: dict[str, str] | None = None,
    deployment_mode: str | None = None,
    rag_service: RagService | None = None,
) -> FastAPI:
    _configure_logging()
    root = Path(output_root) if output_root is not None else _env_path("OUTPUT_ROOT", DEFAULT_OUTPUT_ROOT)
    bike = Path(bike_root) if bike_root is not None else _env_path("BIKE_ROOT", DEFAULT_BIKE_ROOT)
    workbench = (
        Path(workbench_root)
        if workbench_root is not None
        else _env_path("WORKBENCH_ROOT", DEFAULT_WORKBENCH_ROOT)
    )
    runtime_mode = _deployment_mode(deployment_mode)
    app = FastAPI(
        title="Decision Intelligence Copilot",
        version="0.3.0",
        description=(
            "Validated natural-language tabular analysis with DuckDB execution, reproducible "
            "provenance, evidence RAG, and deterministic safety gates."
        ),
    )
    app.state.output_root = root
    app.state.bike_root = bike
    app.state.workbench_root = workbench
    app.state.refresh_artifacts = refresh_artifacts
    app.state.deployment_mode = runtime_mode
    app.state.auth_roles = _configured_auth_roles(auth_token, auth_roles, runtime_mode)
    app.state.rag_service = rag_service or RagService()
    app.state.project_root = Path(__file__).resolve().parents[2]
    app.state.started_at = time.time()
    app.state.ready = False

    @app.middleware("http")
    async def structured_request_log(request: Request, call_next):
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            LOGGER.exception(
                json.dumps(
                    {
                        "event": "request_error",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": duration_ms,
                    },
                    ensure_ascii=False,
                )
            )
            raise
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        LOGGER.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
                ensure_ascii=False,
            )
        )
        return response

    def ensure_ready() -> None:
        if app.state.ready:
            return
        if app.state.refresh_artifacts or _needs_pipeline_refresh(app.state.output_root):
            run(app.state.output_root, app.state.bike_root, app.state.workbench_root)
        initialize_store(app.state.output_root)
        app.state.ready = True

    def resolve_role(
        x_control_tower_token: str | None = Header(default=None, alias="X-Control-Tower-Token"),
    ) -> str:
        roles = app.state.auth_roles
        if not roles:
            return "demo"
        candidate_digest = _credential_digest((x_control_tower_token or "").strip())
        for configured_digest, role in roles.items():
            if hmac.compare_digest(candidate_digest, configured_digest):
                return role
        raise HTTPException(status_code=401, detail="invalid or missing control tower credential")

    def require_write_role(role: str = Depends(resolve_role)) -> str:
        if role == "demo":
            return role
        if role not in WRITE_ROLES:
            raise HTTPException(status_code=403, detail="reviewer or admin role required")
        return role

    def ops_metrics() -> dict[str, Any]:
        state = _read_json(app.state.output_root / "reports" / "control_state.json", {})
        artifacts = {
            "control_state": _artifact_status(app.state.output_root / "reports" / "control_state.json"),
            "review_queue": _artifact_status(
                app.state.output_root / "reports" / "control_review_queue.csv"
            ),
            "api_contract": _artifact_status(app.state.output_root / "reports" / "api_contract.json"),
            "impact_cards": _artifact_status(app.state.output_root / "reports" / "impact_cards.json"),
            "impact_policy_audit": _artifact_status(
                app.state.output_root / "reports" / "impact_policy_audit.json"
            ),
            "reviewer_policy_robustness": _artifact_status(
                app.state.output_root / "reports" / "reviewer_policy_robustness.json"
            ),
            "reviewer_action_plan": _artifact_status(
                app.state.output_root / "reports" / "reviewer_action_plan.json"
            ),
            "reviewer_evidence_bundles": _artifact_status(
                app.state.output_root / "reports" / "reviewer_evidence_bundles.json"
            ),
            "agent_reviewer_brief": _artifact_status(
                app.state.output_root / "reports" / "agent_reviewer_brief.json"
            ),
            "agent_candidate_review_notes": _artifact_status(
                app.state.output_root / "reports" / "agent_candidate_review_notes.json"
            ),
            "dashboard": _artifact_status(app.state.output_root / "dashboard" / "index.html"),
            "sqlite_database": _artifact_status(database_path(app.state.output_root)),
            "approval_audit_integrity": _artifact_status(
                app.state.output_root / "reports" / "approval_audit_integrity.json"
            ),
        }
        audit_integrity = verify_audit_integrity(app.state.output_root)
        return {
            "status": "ok",
            "uptime_seconds": round(time.time() - app.state.started_at, 3),
            "auth_required": bool(app.state.auth_roles),
            "configured_roles": sorted(set(app.state.auth_roles.values())),
            "deployment_mode": app.state.deployment_mode,
            "refresh_artifacts": bool(app.state.refresh_artifacts),
            "public_deploy_decision": state.get("public_deploy_decision", "UNKNOWN"),
            "demo_mode_ready": bool(state.get("demo_mode_ready")),
            "queue": queue_summary(app.state.output_root),
            "approval_audit_integrity": audit_integrity,
            "rag": app.state.rag_service.status(),
            "artifacts": artifacts,
        }

    def runtime_sources() -> dict[str, Any]:
        state = _read_json(app.state.output_root / "reports" / "control_state.json", {})
        queue = list_queue(app.state.output_root)
        cards = _read_json(app.state.output_root / "reports" / "impact_cards.json", [])
        if not isinstance(cards, list):
            cards = []
        policy_audit = _read_json(app.state.output_root / "reports" / "impact_policy_audit.json", [])
        if not isinstance(policy_audit, list):
            policy_audit = []
        policy_robustness = _read_json(
            app.state.output_root / "reports" / "reviewer_policy_robustness.json", {}
        )
        if not isinstance(policy_robustness, dict):
            policy_robustness = {}
        action_plan = _read_json(app.state.output_root / "reports" / "reviewer_action_plan.json", [])
        if not isinstance(action_plan, list):
            action_plan = []
        evidence_bundles = _read_json(
            app.state.output_root / "reports" / "reviewer_evidence_bundles.json", []
        )
        if not isinstance(evidence_bundles, list):
            evidence_bundles = []
        return {
            "state": state,
            "queue": queue,
            "impact_cards": cards,
            "impact_policy_audit": policy_audit,
            "reviewer_policy_robustness": policy_robustness,
            "reviewer_action_plan": action_plan,
            "reviewer_evidence_bundles": evidence_bundles,
        }

    @app.get("/")
    def read_root() -> dict[str, str]:
        ensure_ready()
        return {
            "service": "decisionops-control-tower",
            "health": "/health",
            "dashboard": "/dashboard",
            "impact_cards": "/api/impact-cards",
            "impact_policy_audit": "/api/impact-policy-audit",
            "reviewer_policy_robustness": "/api/reviewer-policy-robustness",
            "reviewer_action_plan": "/api/reviewer-action-plan",
            "reviewer_evidence_bundles": "/api/reviewer-evidence-bundles",
            "agent_reviewer_brief": "/api/agent/reviewer-brief",
            "chat": "/api/chat",
            "analyze_dataset": "/api/data/analyze",
            "query_dataset": "/api/data/query",
            "migration_case": "/api/migration/case-study",
            "ops": "/api/ops-metrics",
            "approval_audit_integrity": "/api/approval-audit-integrity",
            "openapi": "/docs",
        }

    @app.get("/health")
    def health() -> dict[str, Any]:
        ensure_ready()
        state = _read_json(app.state.output_root / "reports" / "control_state.json", {})
        return {
            "status": "ok",
            "project": "decisionops-control-tower",
            "demo_mode_ready": bool(state.get("demo_mode_ready")),
            "public_deploy_decision": state.get("public_deploy_decision", "UNKNOWN"),
            "impact_card_rows": state.get("metrics", {}).get("impact_card_rows", 0),
            "impact_policy_audit_rows": state.get("metrics", {}).get("impact_policy_audit_rows", 0),
            "impact_model_validated_estimate_units": state.get("metrics", {}).get(
                "impact_model_validated_estimate_units", 0
            ),
            "impact_realized_units": state.get("metrics", {}).get("impact_realized_units", 0),
            "impact_realized_claim_blocked_units": state.get("metrics", {}).get(
                "impact_realized_claim_blocked_units", 0
            ),
            "reviewer_policy_robustness_rows": state.get("metrics", {}).get(
                "reviewer_policy_robustness_rows", 0
            ),
            "reviewer_action_plan_rows": state.get("metrics", {}).get("reviewer_action_plan_rows", 0),
            "reviewer_evidence_bundle_rows": state.get("metrics", {}).get(
                "reviewer_evidence_bundle_rows", 0
            ),
            "reviewer_evidence_fresh_rows": state.get("metrics", {}).get(
                "reviewer_evidence_fresh_rows", 0
            ),
            "queue": queue_summary(app.state.output_root),
            "approval_audit_integrity": verify_audit_integrity(app.state.output_root),
            "auth_required": bool(app.state.auth_roles),
            "configured_roles": sorted(set(app.state.auth_roles.values())),
            "deployment_mode": app.state.deployment_mode,
            "rag": app.state.rag_service.status(),
            "database": str(database_path(app.state.output_root)),
            "output_root": str(app.state.output_root),
        }

    @app.get("/api/control-state")
    def control_state() -> dict[str, Any]:
        ensure_ready()
        state = _read_json(app.state.output_root / "reports" / "control_state.json", {})
        state["queue_summary"] = queue_summary(app.state.output_root)
        return state

    @app.get("/api/review-queue")
    def review_queue(approval_state: str | None = None) -> dict[str, Any]:
        ensure_ready()
        items = list_queue(app.state.output_root, approval_state=approval_state)
        return {"count": len(items), "items": items}

    @app.get("/api/impact-cards")
    def impact_cards(guardrail_state: str | None = None) -> dict[str, Any]:
        ensure_ready()
        items = _read_json(app.state.output_root / "reports" / "impact_cards.json", [])
        if not isinstance(items, list):
            items = []
        if guardrail_state:
            items = [item for item in items if item.get("guardrail_state") == guardrail_state]
        return {"count": len(items), "items": items}

    @app.get("/api/impact-policy-audit")
    def impact_policy_audit(policy: str | None = None) -> dict[str, Any]:
        ensure_ready()
        items = _read_json(app.state.output_root / "reports" / "impact_policy_audit.json", [])
        if not isinstance(items, list):
            items = []
        if policy:
            items = [item for item in items if item.get("policy") == policy]
        return {"count": len(items), "items": items}

    @app.get("/api/reviewer-action-plan")
    def reviewer_action_plan(decision: str | None = None) -> dict[str, Any]:
        ensure_ready()
        items = _read_json(app.state.output_root / "reports" / "reviewer_action_plan.json", [])
        if not isinstance(items, list):
            items = []
        if decision:
            items = [item for item in items if item.get("reviewer_decision") == decision]
        return {"count": len(items), "items": items}

    @app.get("/api/reviewer-policy-robustness")
    def reviewer_policy_robustness(
        scenario: str | None = None,
        policy: str | None = None,
    ) -> dict[str, Any]:
        ensure_ready()
        payload = _read_json(
            app.state.output_root / "reports" / "reviewer_policy_robustness.json", {}
        )
        if not isinstance(payload, dict):
            payload = {}
        items = payload.get("rows", [])
        if not isinstance(items, list):
            items = []
        if scenario:
            items = [item for item in items if item.get("scenario") == scenario]
        if policy:
            items = [item for item in items if item.get("policy") == policy]
        return {
            "count": len(items),
            "method": payload.get("method", {}),
            "summary": payload.get("summary", {}),
            "items": items,
        }

    @app.get("/api/reviewer-evidence-bundles")
    def reviewer_evidence_bundles(
        freshness_status: str | None = None,
        evidence_lock_status: str | None = None,
    ) -> dict[str, Any]:
        ensure_ready()
        items = _read_json(
            app.state.output_root / "reports" / "reviewer_evidence_bundles.json", []
        )
        if not isinstance(items, list):
            items = []
        if freshness_status:
            items = [
                item for item in items if item.get("freshness_status") == freshness_status
            ]
        if evidence_lock_status:
            items = [
                item
                for item in items
                if item.get("evidence_lock_status") == evidence_lock_status
            ]
        return {"count": len(items), "items": items}

    @app.post("/api/review-queue/{control_id}/decision")
    def review_decision(
        control_id: str,
        payload: DecisionRequest,
        role: str = Depends(require_write_role),
    ) -> dict[str, Any]:
        ensure_ready()
        try:
            item = record_decision(
                app.state.output_root,
                control_id,
                payload.decision,
                reviewer=payload.reviewer,
                note=payload.note,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="control_id not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "recorded", "role": role, "item": item}

    @app.get("/api/review-history")
    def review_history(limit: int = 100) -> dict[str, Any]:
        ensure_ready()
        safe_limit = max(1, min(limit, 500))
        items = list_history(app.state.output_root, limit=safe_limit)
        return {"count": len(items), "items": items}

    @app.get("/api/approval-audit-integrity")
    def approval_audit_integrity() -> dict[str, Any]:
        ensure_ready()
        return verify_audit_integrity(app.state.output_root)

    @app.get("/api/ops-metrics")
    def read_ops_metrics() -> dict[str, Any]:
        ensure_ready()
        return ops_metrics()

    @app.get("/api/agent/reviewer-brief")
    def agent_reviewer_brief() -> dict[str, Any]:
        ensure_ready()
        sources = runtime_sources()
        return build_reviewer_brief(
            state=sources["state"],
            queue=sources["queue"],
            impact_cards=sources["impact_cards"],
            policy_audit=sources["impact_policy_audit"],
            action_plan=sources["reviewer_action_plan"],
            ops=ops_metrics(),
        )

    @app.post("/api/chat")
    def chat(
        payload: ChatRequest,
        x_control_tower_token: str | None = Header(
            default=None,
            alias="X-Control-Tower-Token",
        ),
    ) -> dict[str, Any]:
        ensure_ready()
        if (
            app.state.deployment_mode == "hosted"
            and os.environ.get("CONTROL_TOWER_LLM_PROVIDER", "").strip().lower() == "openai"
        ):
            resolve_role(x_control_tower_token)
        try:
            dataset_profile = None
            if payload.dataset is not None:
                loaded_dataset = load_dataset(
                    filename=payload.dataset.filename,
                    data_format=payload.dataset.format,
                    content=payload.dataset.content,
                    content_encoding=payload.dataset.content_encoding,
                )
                dataset_profile = profile_dataset(loaded_dataset)
                history = [turn.model_dump() for turn in payload.history]
                if not requires_guarded_chat(payload.question.strip(), history):
                    manifest = DatasetManifest.from_profile(dataset_profile)
                    data_science_outcome = plan_data_science(
                        payload.question.strip(),
                        manifest,
                        loaded_dataset.frame,
                        payload.previous_advanced_plan,
                        payload.previous_prediction_plan,
                        payload.previous_analysis_plan,
                    )
                    if (
                        data_science_outcome.status == "planned"
                        and data_science_outcome.advanced_plan is not None
                    ):
                        try:
                            advanced_result = execute_advanced_plan(
                                loaded_dataset,
                                manifest,
                                data_science_outcome.advanced_plan,
                            )
                        except AnalysisContractError as exc:
                            return _data_science_guardrail_payload(
                                payload.question.strip(),
                                dataset_profile,
                                data_science_outcome,
                                exc,
                                len(payload.history),
                            )
                        return _advanced_chat_payload(
                            payload.question.strip(),
                            dataset_profile,
                            data_science_outcome,
                            advanced_result,
                            len(payload.history),
                        )
                    if (
                        data_science_outcome.status == "planned"
                        and data_science_outcome.prediction_plan is not None
                    ):
                        try:
                            prediction_result = execute_prediction_plan(
                                loaded_dataset,
                                manifest,
                                data_science_outcome.prediction_plan,
                            )
                        except AnalysisContractError as exc:
                            return _data_science_guardrail_payload(
                                payload.question.strip(),
                                dataset_profile,
                                data_science_outcome,
                                exc,
                                len(payload.history),
                            )
                        return _prediction_chat_payload(
                            payload.question.strip(),
                            dataset_profile,
                            data_science_outcome,
                            prediction_result,
                            len(payload.history),
                        )
                    if data_science_outcome.status == "clarification":
                        return _data_science_clarification_payload(
                            payload.question.strip(),
                            dataset_profile,
                            data_science_outcome,
                            len(payload.history),
                        )
                    outcome = plan_analysis(
                        payload.question.strip(),
                        manifest,
                        loaded_dataset.frame,
                        payload.previous_analysis_plan,
                    )
                    if outcome.status == "planned" and outcome.plan is not None:
                        result = execute_plan(loaded_dataset, manifest, outcome.plan)
                        return _analysis_chat_payload(
                            question=payload.question.strip(),
                            profile=dataset_profile,
                            outcome=outcome,
                            result=result,
                            history_turns=len(payload.history),
                            context_used=payload.previous_analysis_plan is not None,
                        )
                    if outcome.status == "clarification":
                        return _analysis_clarification_payload(
                            question=payload.question.strip(),
                            profile=dataset_profile,
                            outcome=outcome,
                            history_turns=len(payload.history),
                        )
                    if (
                        outcome.status == "not_applicable"
                        and outcome.message == ANALYSIS_RESET_REQUEST_MESSAGE
                    ):
                        return _analysis_reset_payload(
                            question=payload.question.strip(),
                            profile=dataset_profile,
                            outcome=outcome,
                            history_turns=len(payload.history),
                        )
                    if (
                        outcome.status == "not_applicable"
                        and outcome.message == CONVERSATION_REQUEST_MESSAGE
                    ):
                        return _dataset_conversation_chat_payload(
                            question=payload.question.strip(),
                            profile=dataset_profile,
                            outcome=outcome,
                            frame=loaded_dataset.frame,
                            history_turns=len(payload.history),
                        )
                    if (
                        outcome.status == "not_applicable"
                        and outcome.message == OVERVIEW_REQUEST_MESSAGE
                    ):
                        return _dataset_overview_chat_payload(
                            question=payload.question.strip(),
                            profile=dataset_profile,
                            outcome=outcome,
                            frame=loaded_dataset.frame,
                            history_turns=len(payload.history),
                        )
                    if (
                        outcome.status == "not_applicable"
                        and outcome.message == PROFILE_REQUEST_MESSAGE
                    ):
                        return _dataset_profile_chat_payload(
                            question=payload.question.strip(),
                            profile=dataset_profile,
                            outcome=outcome,
                            history_turns=len(payload.history),
                        )
                    if (
                        outcome.status == "not_applicable"
                        and outcome.message == CAPABILITY_REQUEST_MESSAGE
                    ):
                        return _dataset_capability_chat_payload(
                            question=payload.question.strip(),
                            profile=dataset_profile,
                            outcome=outcome,
                            frame=loaded_dataset.frame,
                            history=history,
                        )
            return app.state.rag_service.answer(
                question=payload.question.strip(),
                sources=runtime_sources(),
                project_root=app.state.project_root,
                top_k=payload.top_k,
                dataset_profile=dataset_profile,
                history=[turn.model_dump() for turn in payload.history],
            )
        except RagUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except (AnalysisContractError, DatasetAnalysisError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/data/analyze")
    def analyze_uploaded_dataset(
        payload: DatasetInput,
        response_envelope: bool = False,
    ) -> dict[str, Any]:
        ensure_ready()
        try:
            profile = analyze_dataset(
                filename=payload.filename,
                data_format=payload.format,
                content=payload.content,
                content_encoding=payload.content_encoding,
            )
        except DatasetAnalysisError as exc:
            if response_envelope:
                return {
                    "status": "rejected",
                    "error": {
                        "code": "dataset_validation_failed",
                        "message": str(exc),
                    },
                }
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if response_envelope:
            return {"status": "accepted", "profile": profile}
        return profile

    @app.post("/api/data/query")
    def query_uploaded_dataset(payload: DatasetQueryRequest) -> dict[str, Any]:
        ensure_ready()
        try:
            dataset = load_dataset(
                filename=payload.dataset.filename,
                data_format=payload.dataset.format,
                content=payload.dataset.content,
                content_encoding=payload.dataset.content_encoding,
            )
            manifest = DatasetManifest.from_profile(profile_dataset(dataset))
            return execute_plan(dataset, manifest, payload.plan).model_dump(mode="json")
        except (AnalysisContractError, DatasetAnalysisError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/data/advanced")
    def analyze_uploaded_dataset_advanced(payload: AdvancedAnalysisRequest) -> dict[str, Any]:
        ensure_ready()
        try:
            dataset = load_dataset(
                filename=payload.dataset.filename,
                data_format=payload.dataset.format,
                content=payload.dataset.content,
                content_encoding=payload.dataset.content_encoding,
            )
            manifest = DatasetManifest.from_profile(profile_dataset(dataset))
            return execute_advanced_plan(dataset, manifest, payload.plan).model_dump(mode="json")
        except (AnalysisContractError, DatasetAnalysisError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/data/predict")
    def predict_uploaded_dataset(payload: PredictionRequest) -> dict[str, Any]:
        ensure_ready()
        try:
            dataset = load_dataset(
                filename=payload.dataset.filename,
                data_format=payload.dataset.format,
                content=payload.dataset.content,
                content_encoding=payload.dataset.content_encoding,
            )
            manifest = DatasetManifest.from_profile(profile_dataset(dataset))
            return execute_prediction_plan(dataset, manifest, payload.plan).model_dump(mode="json")
        except (AnalysisContractError, DatasetAnalysisError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/migration/case-study")
    def read_migration_case_study() -> dict[str, Any]:
        ensure_ready()
        return run_migration_case().model_dump(mode="json")

    @app.get("/api/agent/candidate/{candidate_id}/review-notes")
    def agent_candidate_review_notes(candidate_id: str) -> dict[str, Any]:
        ensure_ready()
        sources = runtime_sources()
        notes = build_candidate_review_notes(
            candidate_id=candidate_id,
            state=sources["state"],
            impact_cards=sources["impact_cards"],
            action_plan=sources["reviewer_action_plan"],
        )
        if notes is None:
            raise HTTPException(status_code=404, detail="candidate_id not found")
        return notes

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        ensure_ready()
        sources = runtime_sources()
        recorded_chat = build_recorded_chat(sources, app.state.project_root)
        rag_status = app.state.rag_service.status()
        return HTMLResponse(
            render_copilot_dashboard(
                recorded_chat=recorded_chat,
                migration_case=run_migration_case().model_dump(mode="json"),
                evidence=load_product_evidence(app.state.output_root),
                live_chat=True,
                vector_store=str(rag_status.get("vector_store", "memory")),
            )
        )

    return app


app = create_app()
