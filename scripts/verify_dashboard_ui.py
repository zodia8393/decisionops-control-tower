#!/usr/bin/env python3
"""Verify the dashboard UI contract without adding a browser dependency."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlopen

from fastapi.testclient import TestClient

from decisionops_control_tower.app import create_app
from decisionops_control_tower.pipeline import (
    DEFAULT_BIKE_ROOT,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_WORKBENCH_ROOT,
)


REQUIRED_SNIPPETS = [
    'lang="ko"',
    '<meta name="viewport"',
    'rel="icon"',
    ':focus-visible',
    '@media (max-width: 1040px)',
    'id="decision-chat"',
    'data-live-chat="true"',
    "Decision Intelligence Copilot",
    "One Copilot · Verified execution",
    'data-product-target="analysis"',
    'data-product-target="migration"',
    'data-product-target="validation"',
    'data-product-target="technical"',
    'id="workspace-analysis"',
    'id="workspace-migration"',
    'id="workspace-validation"',
    'id="workspace-technical"',
    "product-panel[hidden]",
    "data-sidebar-toggle",
    "function activate(name",
    "분석 Copilot",
    "무엇을 분석해 볼까요?",
    "검증된 분석 결과",
    "previous_analysis_plan",
    "previous_advanced_plan",
    "previous_prediction_plan",
    "numeric_source_of_truth",
    "buildAnalysisChart",
    "analysis-chart__bar",
    "new Set(numericRows.map",
    "검증된 AnalysisPlan 보기",
    "검증된 AdvancedAnalysisPlan 보기",
    "검증된 PredictionPlan 보기",
    "Analysis Copilot · Advanced",
    "Analysis Copilot · Prediction",
    "Permutation importance · validation 기준",
    "데이터와 근거",
    "data-upload-trigger",
    "data-evidence-toggle",
    'class="chat-attach"',
    'class="chat-evidence-backdrop"',
    "ChatGPT-inspired conversation surface",
    "data-drop-target",
    "showPendingMessage",
    "CSV 저장",
    "SQL 복사",
    "SQL · 실행 계획 보기",
    "Enter 전송",
    "새 대화",
    "앞선 질문을 이어서 이해합니다",
    "CSV · JSON · XLSX · Parquet 선택",
    "제목/빈 행 뒤 실제 header와 빈·중복 컬럼명 자동 정리",
    "컬럼명 자동 정리",
    "표 구조 자동 정리",
    "Analysis Copilot · profile",
    "Analysis Copilot · guide",
    "Analysis Copilot · overview",
    "dataset-conversation",
    "data-science-guardrail",
    "실행 조건",
    "자동 데이터 점검 · 품질과 기초 통계",
    "runAutomaticOverview",
    "chat-suggestion",
    "파일을 선택하지 않았습니다",
    "Migration Lab",
    "Legacy Hospital Migration",
    "Correctness fixture",
    "Reject lineage",
    "Scale & recovery rehearsal",
    "120,000",
    "Evaluation evidence",
    "72/72",
    "22/22",
    "36/36",
    "사용자 평가",
    "현재 범위에서 생략",
    "Claim boundary",
    "Execution flow",
    "Safety & privacy contract",
    "Session-only dataset",
    "Isolated mutation",
    "OpenAPI 보기",
]

FORBIDDEN_VISIBLE_SNIPPETS = [
    ">Control ID<",
    ">SEOUL-IMPACT",
    ">task_",
    "<th>Control ID</th>",
    'class="app-sidebar"',
    'data-panel-target="summary"',
    'data-workspace-panel="chat"',
    'id="workspace-summary"',
    'id="workspace-candidates"',
    'id="workspace-review"',
    'id="reviewer-queue"',
    "DecisionOps Control Tower",
    '<span class="sidebar-nav__title">운영 현황</span>',
    '<span class="sidebar-nav__title">검토·승인</span>',
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--bike-root", default=str(DEFAULT_BIKE_ROOT))
    parser.add_argument("--workbench-root", default=str(DEFAULT_WORKBENCH_ROOT))
    parser.add_argument("--url", help="Optional live dashboard URL to verify instead of TestClient.")
    return parser.parse_args()


def _html_from_test_client(args: argparse.Namespace) -> str:
    client = TestClient(
        create_app(
            output_root=Path(args.output_root),
            bike_root=Path(args.bike_root),
            workbench_root=Path(args.workbench_root),
            refresh_artifacts=False,
        )
    )
    response = client.get("/dashboard")
    response.raise_for_status()
    return response.text


def _html_from_url(url: str) -> str:
    with urlopen(url, timeout=8) as response:
        return response.read().decode("utf-8")


def verify_dashboard_html(html: str) -> dict[str, int]:
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in html]
    forbidden = [snippet for snippet in FORBIDDEN_VISIBLE_SNIPPETS if snippet in html]
    if missing:
        raise AssertionError(f"dashboard is missing required UI snippets: {missing}")
    if forbidden:
        raise AssertionError(f"dashboard still exposes raw internal labels: {forbidden}")
    return {
        "bytes": len(html.encode("utf-8")),
        "required_checks": len(REQUIRED_SNIPPETS),
        "forbidden_checks": len(FORBIDDEN_VISIBLE_SNIPPETS),
    }


def main() -> None:
    args = parse_args()
    html = _html_from_url(args.url) if args.url else _html_from_test_client(args)
    result = verify_dashboard_html(html)
    print(
        "dashboard ui verification complete: "
        f"bytes={result['bytes']}, "
        f"required_checks={result['required_checks']}, "
        f"forbidden_checks={result['forbidden_checks']}"
    )


if __name__ == "__main__":
    main()
