#!/usr/bin/env python3
"""Capture portfolio demo screenshots with Playwright.

This script is intentionally optional: CI does not need a browser, but a local
portfolio package should contain real product screenshots.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any
from urllib.request import urlopen


DEFAULT_URL = "http://127.0.0.1:8093"
DEFAULT_OUTPUT_DIR = Path("docs/assets/demo")
DEFAULT_ANALYSIS_FIXTURE = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "browser_sales.csv"
)
RECOVERABLE_HEADER_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "browser_invalid_duplicate.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--timeout-ms", type=int, default=15000)
    parser.add_argument("--analysis-fixture", type=Path, default=DEFAULT_ANALYSIS_FIXTURE)
    return parser.parse_args()


def _find_browser() -> str | None:
    for name in ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable"]:
        path = shutil.which(name)
        if path and not path.startswith("/snap/"):
            return path
    return None


def _require_healthy(base_url: str) -> dict[str, Any]:
    with urlopen(base_url.rstrip("/") + "/health", timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "ok":
        raise AssertionError(f"health endpoint is not ok: {payload}")
    return payload


def _shot_path(output_dir: Path, name: str) -> Path:
    return output_dir / f"{name}.png"


def _data_science_fixture() -> bytes:
    rows = ["date,row_id,group,x,y,label"]
    for index in range(160):
        x = index / 10
        y = 3 * x + ((index % 7) - 3) * 0.03
        label = "high" if x >= 8 else "low"
        rows.append(f"2025-01-{(index % 28) + 1:02d},{index},{'A' if index % 2 else 'B'},{x:.1f},{y:.3f},{label}")
    return ("\n".join(rows) + "\n").encode("utf-8")


def capture_screenshots(
    base_url: str,
    output_dir: Path,
    timeout_ms: int = 15000,
    analysis_fixture: Path = DEFAULT_ANALYSIS_FIXTURE,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Playwright is required for screenshot capture. Install it locally or run this on the workstation with Playwright."
        ) from exc

    health = _require_healthy(base_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    browser_path = _find_browser()
    captures: list[dict[str, Any]] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    qa: dict[str, Any] = {}

    with sync_playwright() as p:
        launch_args = {"headless": True, "args": ["--no-sandbox"]}
        if browser_path:
            launch_args["executable_path"] = browser_path
        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1100},
            device_scale_factor=1,
            locale="ko-KR",
        )
        page = context.new_page()
        page.on(
            "console",
            lambda message: console_errors.append(message.text) if message.type == "error" else None,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.set_default_timeout(timeout_ms)

        def capture(name: str, path: str, selector: str | None = None, *, full_page: bool = False) -> None:
            page.goto(base_url.rstrip("/") + path, wait_until="networkidle")
            if selector:
                locator = page.locator(selector).first
                locator.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
            page.screenshot(path=_shot_path(output_dir, name), full_page=full_page)
            if selector:
                locator.screenshot(path=_shot_path(output_dir, f"{name}_section"))
                captures.append(
                    {
                        "name": f"{name}_section",
                        "path": str(_shot_path(output_dir, f"{name}_section")),
                        "url": base_url.rstrip("/") + path,
                        "selector": selector,
                    }
                )
            captures.append(
                {
                    "name": name,
                    "path": str(_shot_path(output_dir, name)),
                    "url": base_url.rstrip("/") + path,
                    "selector": selector,
                    "full_page": full_page,
                }
            )

        capture("dashboard_overview", "/dashboard", full_page=False)
        capture("dashboard_full_page", "/dashboard", full_page=True)
        desktop_targets = ["analysis", "migration", "validation", "technical"]
        for target in desktop_targets:
            page.locator(f'[data-product-target="{target}"]').click()
            visible_panels = page.locator("[data-product-panel]:visible")
            if visible_panels.count() != 1:
                raise AssertionError(f"desktop sidebar exposed multiple panels after selecting {target}")
            if visible_panels.get_attribute("data-product-panel") != target:
                raise AssertionError(f"desktop sidebar did not activate {target}")
        qa["desktop_sidebar_navigation"] = "4/4"
        qa["desktop_default_panel"] = "analysis"

        page.locator('[data-product-target="migration"]').click()
        rdb_migration = page.locator("#migration-rdb")
        if not rdb_migration.is_visible():
            raise AssertionError("Firebird to PostgreSQL integration is not visible")
        rdb_text = rdb_migration.inner_text().lower().replace(",", "")
        if not all(
            value in rdb_text
            for value in [
                "firebird → postgresql integration",
                "120000",
                "119988 accepted + 12 rejected",
                "rollback",
                "pass",
                "replay processed",
                "fk violations",
                "schema drift",
                "blocked",
            ]
        ):
            raise AssertionError(f"RDB migration evidence is incomplete: {rdb_text}")
        migration = page.locator("#migration-correctness")
        if not migration.is_visible():
            raise AssertionError("migration correctness case is not visible in Migration Lab")
        migration_text = migration.inner_text()
        migration_text_normalized = migration_text.lower()
        if not all(
            value in migration_text_normalized
            for value in ["source rows", "20", "accepted", "11", "rejected", "9"]
        ):
            raise AssertionError(f"migration reconciliation summary is incomplete: {migration_text}")
        migration.locator("details summary").click()
        if migration.locator("details[open]").count() != 1:
            raise AssertionError("migration reject lineage did not expand")
        page.locator(".product-topbar").evaluate("node => node.style.visibility = 'hidden'")
        page.locator("#workspace-migration").screenshot(path=_shot_path(output_dir, "migration_lab"))
        captures.append(
            {
                "name": "migration_lab",
                "path": str(_shot_path(output_dir, "migration_lab")),
                "url": base_url.rstrip("/") + "/dashboard#workspace-migration",
                "selector": "#workspace-migration",
                "full_page": False,
            }
        )
        qa["desktop_rdb_migration"] = (
            "Firebird → PostgreSQL · 120,000 = 119,988 + 12 · rollback/resume/replay PASS"
        )
        qa["desktop_migration_case"] = "20 = 11 accepted + 9 rejected"
        page.locator('[data-product-target="analysis"]').click()

        page.goto(base_url.rstrip("/") + "/dashboard", wait_until="networkidle")
        if not page.locator(".chat-onboarding").is_visible():
            raise AssertionError("dataset onboarding is not visible in the chat flow")
        if "분석 데이터가 아직 없습니다" not in page.locator(".chat-contextbar").inner_text():
            raise AssertionError("empty dataset state is not visible above the conversation")
        page.locator("[data-chat-question]").first.click()
        if "먼저 분석할 파일" not in page.locator("[data-dataset-summary]").inner_text():
            raise AssertionError("analysis preset did not require a dataset")
        if page.locator(".chat-message:not([data-chat-welcome])").count() != 0:
            raise AssertionError("analysis preset executed before a dataset was uploaded")
        qa["desktop_dataset_required"] = "PASS"

        with page.expect_file_chooser() as chooser_info:
            page.locator(".chat-upload-trigger").click()
        chooser_info.value.set_files(analysis_fixture)
        page.wait_for_function(
            "() => document.querySelector('[data-dataset-summary]').textContent.includes('5행 × 4열')"
        )
        if "이 대화에 계속 연결" not in page.locator("[data-dataset-summary]").inner_text():
            raise AssertionError("uploaded dataset is not presented as sticky chat context")
        if page.locator(".chat-onboarding").is_visible():
            raise AssertionError("dataset onboarding remained visible after upload")
        if "browser_sales.csv · 5행 × 4열" not in page.locator(".chat-contextbar").inner_text():
            raise AssertionError("connected dataset is not summarized above the conversation")
        if page.locator("[data-chat-evidence]").is_visible():
            raise AssertionError("desktop evidence drawer should be collapsed by default")
        page.locator(".chat-contextbar .chat-evidence-toggle").click()
        session_state = page.locator("[data-analysis-session]")
        if not session_state.is_visible() or "누적 조건 없음" not in session_state.inner_text():
            raise AssertionError("dataset session state is not visible after upload")
        page.locator(".chat-evidence__close").click()
        if page.locator("[data-chat-evidence]").is_visible():
            raise AssertionError("desktop evidence drawer did not close")
        qa["desktop_evidence_disclosure"] = "collapsed → open → collapsed"
        page.locator(".dataset-overview").last.wait_for(state="visible")
        automatic_overview = page.locator(".chat-message--assistant").last
        automatic_overview_text = automatic_overview.inner_text().lower()
        if not all(
            value in automatic_overview_text
            for value in [
                "analysis copilot · overview",
                "자동 데이터 점검 · 품질과 기초 통계",
                "revenue",
                "orders",
            ]
        ):
            raise AssertionError(
                f"automatic dataset overview is incomplete: {automatic_overview_text}"
            )
        if automatic_overview.locator(".chat-suggestion").count() < 3:
            raise AssertionError("automatic overview did not expose executable recommendations")
        page.locator("#decision-chat").screenshot(
            path=_shot_path(output_dir, "chat_dataset_overview")
        )
        captures.append(
            {
                "name": "chat_dataset_overview",
                "path": str(_shot_path(output_dir, "chat_dataset_overview")),
                "url": base_url.rstrip("/") + "/dashboard#decision-chat",
                "selector": "#decision-chat",
                "full_page": False,
            }
        )
        automatic_overview.locator(".chat-suggestion").first.dblclick()
        page.locator(".analysis-result").last.wait_for(state="visible")
        recommended_result = page.locator(".analysis-result").last
        if page.locator(".analysis-result").count() != 1:
            raise AssertionError("double-clicking a recommendation started duplicate analyses")
        if "duckdb" not in recommended_result.inner_text().lower():
            raise AssertionError("recommended analysis bypassed the verified DuckDB executor")
        if recommended_result.locator(".analysis-chart").count() != 1:
            raise AssertionError("recommended analysis did not render a visualization")
        page.locator(
            ".chat-message--assistant:has(.dataset-overview) .chat-suggestion"
        ).nth(1).click()
        page.wait_for_function(
            "() => document.querySelectorAll('.analysis-result').length === 2"
        )
        fresh_grouped = page.locator(".analysis-result").last
        fresh_plan = fresh_grouped.locator(".analysis-plan code").text_content() or ""
        if not all(
            value in fresh_plan
            for value in ['"operation": "aggregate"', '"group_by": [', '"region"', '"operation": "mean"']
        ):
            raise AssertionError("complete grouped question was treated as an incompatible select follow-up")
        if "조건 통과 5행" not in fresh_grouped.inner_text():
            raise AssertionError("fresh grouped analysis did not use the full fixture denominator")
        qa["desktop_automatic_dataset_overview"] = (
            "upload → description/quality/basic statistics/recommendations"
        )
        qa["desktop_recommendation_execution"] = "recommendation → DuckDB result/chart"
        qa["desktop_duplicate_request_guard"] = "recommendation double-click → 1 result"
        qa["desktop_new_analysis_transition"] = "rank select → fresh grouped mean"
        page.locator("[data-chat-input]").fill("다른 분석 더 할수있는거는?")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('추가 분석')"
        )
        additional_guide = page.locator(".chat-message--assistant").last
        if "analysis copilot · guide" not in additional_guide.inner_text().lower():
            raise AssertionError("natural additional-analysis question missed the capability guide")
        if additional_guide.locator(".chat-suggestion").count() < 4:
            raise AssertionError("additional capability guide did not expose fresh executable options")
        additional_guide.locator(".chat-suggestion").first.click()
        page.wait_for_function(
            "() => document.querySelectorAll('.analysis-result').length === 3"
        )
        if "duckdb" not in page.locator(".analysis-result").last.inner_text().lower():
            raise AssertionError("additional recommendation bypassed the verified DuckDB executor")
        qa["desktop_additional_capability_guide"] = (
            "natural 'other analysis' → fresh recommendations → DuckDB execution"
        )
        page.locator("[data-chat-reset]").click()
        if page.locator("[data-analysis-session]").get_attribute("hidden") is not None:
            raise AssertionError("conversation reset disconnected the uploaded dataset")
        if "누적 조건 없음" not in page.locator("[data-analysis-session-state]").inner_text():
            raise AssertionError("conversation reset did not return analysis to the original dataset")
        page.locator("[data-chat-input]").fill("channel별 비율 보여줘")
        page.locator("[data-chat-submit]").click()
        page.locator(".analysis-result").last.wait_for(state="visible")
        share_result = page.locator(".analysis-result").last
        if not all(value in share_result.inner_text() for value in ["web", "60", "store", "40"]):
            raise AssertionError("categorical share analysis returned unexpected values")
        if share_result.locator(".analysis-chart__bar").count() != 2:
            raise AssertionError("categorical share analysis did not render two bars")
        qa["desktop_categorical_share"] = "channel share = web 60% + store 40%"
        qa["desktop_sticky_dataset"] = "conversation reset → same uploaded dataset retained"
        page.locator("[data-chat-reset]").click()
        page.locator("[data-chat-input]").fill("지역별 매출 합계 상위 2개")
        page.locator("[data-chat-submit]").click()
        page.locator(".analysis-result").last.wait_for(state="visible")
        result = page.locator(".analysis-result").last
        result_text = result.inner_text()
        if not all(value in result_text for value in ["Seoul", "180", "Jeju", "120", "duckdb"]):
            raise AssertionError(f"analysis result did not contain expected values: {result_text}")
        if result.locator(".analysis-chart__bar").count() != 2:
            raise AssertionError("analysis result did not render the expected two chart bars")
        if result.locator("[data-export-csv]").count() != 1:
            raise AssertionError("analysis result did not expose CSV export")
        if result.locator("[data-copy-sql]").count() != 1:
            raise AssertionError("analysis result did not expose SQL copy")
        if result.locator(".analysis-provenance[open]").count() != 0:
            raise AssertionError("SQL provenance should use progressive disclosure by default")
        with page.expect_download() as download_info:
            result.locator("[data-export-csv]").click()
        if download_info.value.suggested_filename != "analysis-result.csv":
            raise AssertionError("analysis CSV export used an unexpected filename")
        result.locator("[data-copy-sql]").click()
        page.wait_for_function(
            "() => document.querySelector('[data-chat-toast]')?.textContent.includes('SQL')"
        )
        if "SELECT" not in (result.locator(".analysis-query").text_content() or ""):
            raise AssertionError("analysis result did not expose SQL provenance")
        if result.locator(".analysis-plan").count() != 1:
            raise AssertionError("analysis result did not expose the validated AnalysisPlan")
        page.locator("[data-chat-input]").fill("그중 상위 1개만")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelectorAll('.analysis-result').length === 2"
        )
        follow_up_result = page.locator(".analysis-result").last
        if "1행" not in follow_up_result.locator("summary").first.inner_text():
            raise AssertionError("analysis follow-up did not reuse the prior plan with limit 1")
        qa["desktop_dataset_analysis"] = "upload → plan → table/chart/SQL"
        qa["desktop_result_actions"] = "CSV download + SQL copy"
        qa["desktop_analysis_follow_up"] = "top 2 → top 1"

        page.locator("[data-chat-input]").fill("평균으로 바꿔줘")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelectorAll('.analysis-result').length === 3"
        )
        metric_result = page.locator(".analysis-result").last
        metric_plan = metric_result.locator(".analysis-plan code").text_content() or ""
        if not all(value in metric_plan for value in ['"operation": "mean"', '"column": "revenue"']):
            raise AssertionError(f"analysis follow-up did not revise sum to mean: {metric_plan}")
        if not all(value in metric_result.inner_text() for value in ["Jeju", "120"]):
            raise AssertionError("mean follow-up returned unexpected rows")
        qa["desktop_analysis_metric_revision"] = "sum → mean"

        page.locator("[data-chat-input]").fill("web만 보고 1개만 보여줘")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelectorAll('.analysis-result').length === 4"
        )
        filter_result = page.locator(".analysis-result").last
        filter_plan = filter_result.locator(".analysis-plan code").text_content() or ""
        if not all(value in filter_plan for value in ['"column": "channel"', '"value": "web"']):
            raise AssertionError("analysis follow-up did not add the categorical filter")
        if "조건 통과 3행" not in filter_result.inner_text():
            raise AssertionError("analysis follow-up did not expose the filtered denominator")
        qa["desktop_analysis_filter_revision"] = "channel = web"
        page.locator("[data-chat-input]").fill("orders 평균으로 바꿔줘")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelectorAll('.analysis-result').length === 5"
        )
        target_result = page.locator(".analysis-result").last
        target_plan = target_result.locator(".analysis-plan code").text_content() or ""
        if not all(value in target_plan for value in ['"operation": "mean"', '"column": "orders"']):
            raise AssertionError("follow-up metric target remained on the previous column")
        if "orders 평균" not in page.locator("[data-analysis-session-state]").inner_text():
            raise AssertionError("active analysis state did not expose the revised target")
        page.locator(".chat-contextbar .chat-evidence-toggle").click()
        page.locator("[data-analysis-reset]").click()
        page.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('원본 복원')",
        )
        page.locator(".chat-evidence__close").click()
        if "원본 복원" not in page.locator(".chat-message--assistant").last.inner_text():
            raise AssertionError("analysis reset did not return a visible session-reset response")
        if "누적 조건 없음" not in page.locator("[data-analysis-session-state]").inner_text():
            raise AssertionError("analysis-only reset did not preserve the dataset at original state")
        qa["desktop_analysis_target_revision"] = "revenue → orders while preserving filter/group"
        qa["desktop_analysis_state_reset"] = "conditions reset → dataset retained"
        page.locator("#decision-chat").screenshot(
            path=_shot_path(output_dir, "chat_dataset_analysis")
        )
        captures.append(
            {
                "name": "chat_dataset_analysis",
                "path": str(_shot_path(output_dir, "chat_dataset_analysis")),
                "url": base_url.rstrip("/") + "/dashboard#decision-chat",
                "selector": "#decision-chat",
                "full_page": False,
            }
        )
        page.locator("[data-chat-reset]").click()
        if page.locator(".analysis-result").count() != 0:
            raise AssertionError("new conversation did not clear analysis results")
        qa["desktop_analysis_reset"] = "PASS"
        page.locator("[data-chat-input]").fill("안녕")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('파일이 연결')"
        )
        page.locator("[data-chat-input]").fill("이거 뭐야?")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('Analysis Copilot · profile')"
        )
        page.locator("[data-chat-input]").fill("뭘 할 수 있어?")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('Analysis Copilot · guide')"
        )
        qa["desktop_natural_conversation"] = "greeting → profile → capability guide"
        page.locator("[data-chat-input]").fill("Seoul과 Busan만 보여줘")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelectorAll('.analysis-result').length === 1"
        )
        multi_value_plan = (
            page.locator(".analysis-result").last.locator(".analysis-plan code").text_content()
            or ""
        )
        if not all(
            value in multi_value_plan
            for value in ['"operator": "in"', '"Seoul"', '"Busan"']
        ):
            raise AssertionError("multiple categorical values were not compiled to an IN filter")
        page.locator("[data-chat-input]").fill("매출 60에서 100 사이만 보여줘")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelectorAll('.analysis-result').length === 2"
        )
        range_result = page.locator(".analysis-result").last
        range_plan = range_result.locator(".analysis-plan code").text_content() or ""
        if not all(value in range_plan for value in ['"operator": "gte"', '"operator": "lte"']):
            raise AssertionError("numeric range was not compiled to two bounded filters")
        if "조건 통과 3행" not in range_result.inner_text():
            raise AssertionError("numeric range returned an unexpected denominator")
        page.locator("[data-chat-input]").fill("매출 대비 주문수 비율 보여줘")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('파생 비율')"
        )
        if page.locator(".analysis-result").count() != 2:
            raise AssertionError("unsupported row-level ratio executed a misleading analysis")
        qa["desktop_composite_filters"] = "multi-value IN + numeric range"
        qa["desktop_derived_ratio_guard"] = "unsupported formula → explicit clarification"
        page.locator("[data-chat-reset]").click()
        if page.locator(".analysis-result").count() != 0:
            raise AssertionError("natural conversation QA did not reset cleanly")
        page.locator("[data-dataset-file]").set_input_files(
            {
                "name": "data-science-browser.csv",
                "mimeType": "text/csv",
                "buffer": _data_science_fixture(),
            }
        )
        page.wait_for_function(
            "() => document.querySelector('[data-dataset-summary]').textContent.includes('160행 × 6열')"
        )
        page.locator(".dataset-overview").last.wait_for(state="visible")
        page.locator("[data-chat-input]").fill("x 히스토그램으로 분포 분석")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('Analysis Copilot · Advanced')"
        )
        advanced_result = page.locator(".analysis-result").last
        if advanced_result.locator(".analysis-chart__bar").count() < 5:
            raise AssertionError("advanced distribution did not render histogram bars")
        if "AdvancedAnalysisPlan" not in (advanced_result.locator(".analysis-plan").text_content() or ""):
            raise AssertionError("advanced result did not expose its typed plan")
        advanced_count = page.locator(".analysis-result").count()
        page.locator("[data-chat-input]").fill("구간을 20으로 바꿔줘")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "count => document.querySelectorAll('.analysis-result').length > count",
            arg=advanced_count,
        )
        advanced_plan = page.locator(".analysis-result").last.locator(".analysis-plan code").text_content() or ""
        if '"bins": 20' not in advanced_plan:
            raise AssertionError("advanced follow-up did not revise histogram bins")
        qa["desktop_advanced_analysis"] = "distribution → chart/plan/provenance → bins 20"
        page.locator("[data-chat-reset]").click()
        page.locator("[data-chat-input]").fill("y 회귀 모델로 예측")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('Analysis Copilot · Prediction')"
        )
        prediction_result = page.locator(".analysis-result").last
        prediction_text = prediction_result.inner_text()
        if not all(
            value in prediction_text
            for value in ["검증된 예측 결과", "Baseline validation", "Held-out test", "bounded_permutation_shapley"]
        ):
            raise AssertionError(f"prediction result evidence is incomplete: {prediction_text}")
        if "PredictionPlan" not in (prediction_result.locator(".analysis-plan").text_content() or ""):
            raise AssertionError("prediction result did not retain its typed plan")
        if prediction_result.locator(".analysis-query").count() != 1:
            raise AssertionError("prediction result did not expose source-row SQL provenance")
        if prediction_result.locator(".analysis-details[open]").count() != 0:
            raise AssertionError("prediction technical details should be collapsed by default")
        if prediction_result.locator("[data-export-csv]").count() != 1:
            raise AssertionError("prediction result did not expose CSV export")
        if "현재 예측" not in page.locator("[data-analysis-session-state]").inner_text():
            raise AssertionError("prediction plan is not retained as current chat state")
        page.locator("#decision-chat").screenshot(
            path=_shot_path(output_dir, "chat_data_science_prediction")
        )
        captures.append(
            {
                "name": "chat_data_science_prediction",
                "path": str(_shot_path(output_dir, "chat_data_science_prediction")),
                "url": base_url.rstrip("/") + "/dashboard#decision-chat",
                "selector": "#decision-chat",
                "full_page": False,
            }
        )
        qa["desktop_prediction"] = "baseline → held-out test → interval/error/SHAP/model card"
        page.locator("[data-chat-reset]").click()
        page.locator("[data-dataset-file]").set_input_files(
            {
                "name": "profit.csv",
                "mimeType": "text/csv",
                "buffer": "region,profit\nSeoul,100\nBusan,-50\nDaejeon,20\n".encode("utf-8"),
            }
        )
        page.locator(".dataset-overview").last.wait_for(state="visible")
        page.locator("[data-chat-input]").fill("region별 profit 합계")
        page.locator("[data-chat-submit]").click()
        page.locator(".analysis-result").last.wait_for(state="visible")
        signed_result = page.locator(".analysis-result").last
        if signed_result.locator(".analysis-chart__bar").count() != 3:
            raise AssertionError("signed chart omitted a positive or negative result row")
        if signed_result.locator(".analysis-chart__bar--negative").count() != 1:
            raise AssertionError("signed chart did not distinguish the negative value")
        page.locator("[data-chat-input]").fill("가장 성과 좋은 지역은?")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('조건 확인')",
        )
        clarification = page.locator(".chat-message--assistant").last
        clarification.wait_for(state="visible")
        clarification_text = clarification.inner_text().lower()
        if not all(
            value in clarification_text
            for value in ["analysis copilot · 조건 확인", "실행 가능한 분석으로 해석하지 못했습니다"]
        ):
            raise AssertionError("unsupported dataset question escaped to an unrelated answer")
        qa["desktop_signed_chart"] = "3 rows including 1 negative bar"
        qa["desktop_dataset_scope_guard"] = "unsupported question → dataset clarification"
        page.locator("[data-chat-reset]").click()
        page.locator("[data-dataset-file]").set_input_files(
            {
                "name": "daily-report.csv",
                "mimeType": "text/csv",
                "buffer": (
                    "2024년 01월 일별 종합배출내역\n"
                    "\n"
                    "배출일,요일,배출량(g),배출량비율(%),배출횟수,배출횟수비율(%)\n"
                    "01,월,13219184975,52.1,7520254,52.1\n"
                    "02,화,12165433235,47.9,6915125,47.9\n"
                    "합계,,25384618210,100,14435379,100\n"
                ).encode("utf-8"),
            }
        )
        page.wait_for_function(
            "() => document.querySelector('[data-dataset-summary]').textContent.includes('3행을 header로 사용')"
        )
        page.locator(".dataset-overview").last.wait_for(state="visible")
        report_overview = page.locator(".chat-message--assistant").last.inner_text().lower()
        if not all(
            value in report_overview
            for value in [
                "analysis copilot · overview",
                "합계·총계 성격의 행 1개",
                "기초통계 분모 2/3행",
                "합계 행을 제외하고 배출량(g) 기준 상위 5개 보여줘",
            ]
        ):
            raise AssertionError(
                f"report overview did not account for the summary row: {report_overview}"
            )
        page.locator("[data-chat-input]").fill("이 데이터는 어떤 데이터지?")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('Analysis Copilot · profile')"
        )
        profile_answer = page.locator(".chat-message--assistant").last
        profile_answer_text = profile_answer.inner_text()
        if not all(
            value in profile_answer_text.lower()
            for value in ["analysis copilot · profile", "2024년 01월 일별 종합배출내역", "3행 × 6열"]
        ):
            raise AssertionError(
                f"report-style dataset profile answer is incomplete: {profile_answer_text}"
            )
        if profile_answer.locator(".analysis-result").count() != 0:
            raise AssertionError("dataset description incorrectly executed a SELECT plan")
        qa["desktop_report_header_detection"] = "row 3 promoted → 3 data rows"
        qa["desktop_dataset_profile_answer"] = "description without SELECT"
        page.locator("[data-chat-input]").fill("할수있는 분석은?")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('Analysis Copilot · guide')"
        )
        capability_answer = page.locator(".chat-message--assistant").last
        capability_answer_text = capability_answer.inner_text().lower()
        if not all(
            value in capability_answer_text
            for value in [
                "analysis copilot · guide",
                "합계 행을 제외하고 배출량(g) 기준 상위 5개 보여줘",
                "요일별 배출량(g) 평균",
                "상관계수",
                "합계·총계 성격의 행 1개",
            ]
        ):
            raise AssertionError(
                f"dataset capability guide is incomplete: {capability_answer_text}"
            )
        if capability_answer.locator(".analysis-result").count() != 0:
            raise AssertionError("dataset capability guide incorrectly executed an analysis plan")
        qa["desktop_dataset_capability_guide"] = (
            "schema-aware examples without RAG abstention"
        )
        page.locator("[data-chat-input]").fill("배출일별 건수")
        page.locator("[data-chat-submit]").click()
        page.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('Analysis Copilot · DuckDB')"
        )
        daily_count = page.locator(".chat-message--assistant").last
        daily_count_text = daily_count.inner_text().lower()
        if not all(
            value in daily_count_text
            for value in [
                "analysis copilot · duckdb",
                "전체 3행 중 2행을 계산에 사용",
                "배출일별 2개 그룹은 모두 1건",
                "원본 3행은 유지",
            ]
        ):
            raise AssertionError(
                f"summary-row default exclusion is incomplete: {daily_count_text}"
            )
        if any(
            row.strip().startswith("합계")
            for row in daily_count.locator(".analysis-table tbody tr").all_inner_texts()
        ):
            raise AssertionError("summary row remained in grouped count output")
        if daily_count.locator(".analysis-chart").count() != 0:
            raise AssertionError("uniform grouped counts rendered a low-information chart")
        daily_plan = daily_count.locator(".analysis-plan code").text_content() or ""
        if not all(value in daily_plan for value in ['"operator": "ne"', '"value": "합계"']):
            raise AssertionError("summary-row exclusion is missing from AnalysisPlan")
        qa["desktop_summary_row_default"] = "3 input → 2 denominator; uniform chart omitted"
        page.locator("[data-chat-reset]").click()
        page.locator("[data-dataset-file]").set_input_files(RECOVERABLE_HEADER_FIXTURE)
        page.wait_for_function(
            "() => document.querySelector('[data-dataset-summary]').textContent.includes('컬럼명 자동 정리')"
        )
        dataset_repair = page.locator("[data-dataset-summary]")
        if "dataset-summary--success" not in (dataset_repair.get_attribute("class") or ""):
            raise AssertionError("recoverable dataset header was not accepted")
        if "revenue → revenue_2" not in dataset_repair.inner_text():
            raise AssertionError("dataset header repair mapping is not visible")
        qa["desktop_dataset_header_normalization"] = "duplicate → revenue_2"

        page.locator("[data-dataset-file]").set_input_files(
            {
                "name": "unsafe.csv",
                "mimeType": "text/csv",
                "buffer": b"region,api_key\nSeoul,do-not-store\n",
            }
        )
        page.wait_for_function(
            "() => document.querySelector('[data-dataset-summary]').textContent.includes('민감 컬럼')"
        )
        dataset_error = page.locator("[data-dataset-summary]")
        if "dataset-summary--error" not in (dataset_error.get_attribute("class") or ""):
            raise AssertionError("dataset validation error is not exposed as an error state")
        if page.locator("[data-dataset-file]").evaluate("node => node.files.length") != 0:
            raise AssertionError("rejected dataset remained selected")
        retained_state = page.locator("[data-analysis-session]").inner_text()
        if not all(value in retained_state for value in ["browser_invalid_duplicate.csv", "계속 연결"]):
            raise AssertionError("rejected replacement disconnected the previous valid dataset")
        if "기존 browser_invalid_duplicate.csv" not in dataset_error.inner_text():
            raise AssertionError("replacement failure did not tell the user that prior data was retained")
        qa["desktop_dataset_validation_error"] = "sensitive header rejected → readable inline error"
        qa["desktop_failed_replacement_guard"] = "invalid replacement → prior dataset retained"
        qa["desktop_horizontal_overflow"] = page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        capture("validation_results", "/dashboard#workspace-validation", "#workspace-validation")
        capture("technical_details", "/dashboard#workspace-technical", "#workspace-technical")
        capture("openapi_docs", "/docs", full_page=False)
        context.close()

        mobile_context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=1,
            locale="ko-KR",
        )
        mobile = mobile_context.new_page()
        mobile.on(
            "console",
            lambda message: console_errors.append(message.text) if message.type == "error" else None,
        )
        mobile.on("pageerror", lambda error: page_errors.append(str(error)))
        mobile.set_default_timeout(timeout_ms)
        mobile.goto(base_url.rstrip("/") + "/dashboard", wait_until="networkidle")
        mobile.screenshot(path=_shot_path(output_dir, "mobile_overview"), full_page=False)
        captures.append(
            {
                "name": "mobile_overview",
                "path": str(_shot_path(output_dir, "mobile_overview")),
                "url": base_url.rstrip("/") + "/dashboard",
                "selector": None,
                "full_page": False,
            }
        )
        mobile.locator("[data-sidebar-toggle]").click()
        mobile.wait_for_timeout(250)
        drawer_box = mobile.locator("#copilot-sidebar").bounding_box()
        if (
            not mobile.locator("body").evaluate("node => node.classList.contains('sidebar-open')")
            or drawer_box is None
            or drawer_box["x"] < -1
        ):
            raise AssertionError("mobile sidebar drawer did not open")
        mobile.locator('[data-product-target="validation"]').click()
        if not mobile.locator("#workspace-validation").is_visible():
            raise AssertionError("mobile sidebar did not activate the validation panel")
        if mobile.locator("#workspace-analysis").is_visible():
            raise AssertionError("mobile sidebar left analysis visible with validation")
        if mobile.locator("body").evaluate("node => node.classList.contains('sidebar-open')"):
            raise AssertionError("mobile sidebar drawer did not close after navigation")
        mobile.locator("[data-sidebar-toggle]").click()
        mobile.wait_for_timeout(250)
        mobile.locator('[data-product-target="analysis"]').click()
        if not mobile.locator("#workspace-analysis").is_visible():
            raise AssertionError("mobile sidebar did not return to analysis")
        if mobile.locator("[data-chat-evidence]").is_visible():
            raise AssertionError("mobile evidence panel should be collapsed by default")
        evidence_toggle = mobile.locator(".chat-contextbar .chat-evidence-toggle")
        evidence_toggle.click()
        if not mobile.locator("[data-chat-evidence]").is_visible():
            raise AssertionError("mobile data and evidence panel did not open")
        mobile.locator(".chat-evidence__close").click()
        if mobile.locator("[data-chat-evidence]").is_visible():
            raise AssertionError("mobile data and evidence panel did not close")
        qa["mobile_sidebar_drawer"] = "PASS"
        qa["mobile_sidebar_navigation"] = "validation → analysis"
        qa["mobile_evidence_disclosure"] = "collapsed → open → collapsed"

        with mobile.expect_file_chooser() as chooser_info:
            mobile.locator("[data-upload-trigger]").first.click()
        chooser_info.value.set_files(analysis_fixture)
        mobile.wait_for_function(
            "() => document.querySelector('[data-dataset-summary]').textContent.includes('5행 × 4열')"
        )
        mobile.locator(".dataset-overview").last.wait_for(state="visible")
        if "browser_sales.csv · 5행 × 4열" not in mobile.locator(".chat-contextbar").inner_text():
            raise AssertionError("mobile dataset context bar did not update after upload")
        if mobile.locator(".chat-suggestion").count() < 3:
            raise AssertionError("mobile automatic overview recommendations are missing")
        mobile.locator("[data-chat-input]").fill("region별 revenue 합계 상위 2개")
        mobile.locator("[data-chat-submit]").click()
        mobile_result = mobile.locator(".analysis-result")
        mobile_result.wait_for(state="visible")
        mobile_result.scroll_into_view_if_needed()
        mobile.wait_for_timeout(250)
        mobile.screenshot(path=_shot_path(output_dir, "mobile_dataset_analysis"), full_page=False)
        captures.append(
            {
                "name": "mobile_dataset_analysis",
                "path": str(_shot_path(output_dir, "mobile_dataset_analysis")),
                "url": base_url.rstrip("/") + "/dashboard#decision-chat",
                "selector": "#decision-chat",
                "full_page": False,
            }
        )
        qa["mobile_dataset_analysis"] = "PASS"
        qa["mobile_automatic_dataset_overview"] = "PASS"
        mobile.locator("[data-chat-reset]").click()
        mobile.locator("[data-dataset-file]").set_input_files(
            {
                "name": "data-science-mobile.csv",
                "mimeType": "text/csv",
                "buffer": _data_science_fixture(),
            }
        )
        mobile.wait_for_function(
            "() => document.querySelector('[data-dataset-summary]').textContent.includes('160행 × 6열')"
        )
        mobile.locator(".dataset-overview").last.wait_for(state="visible")
        mobile.locator("[data-chat-input]").fill("y 회귀 모델로 예측")
        mobile.locator("[data-chat-submit]").click()
        mobile.wait_for_function(
            "() => document.querySelector('.chat-message--assistant:last-child')?.textContent.includes('Analysis Copilot · Prediction')"
        )
        mobile_prediction = mobile.locator(".analysis-result").last
        if "Held-out test" not in mobile_prediction.inner_text():
            raise AssertionError("mobile prediction result did not render model evidence")
        mobile_prediction.scroll_into_view_if_needed()
        mobile.screenshot(path=_shot_path(output_dir, "mobile_data_science_prediction"), full_page=False)
        captures.append(
            {
                "name": "mobile_data_science_prediction",
                "path": str(_shot_path(output_dir, "mobile_data_science_prediction")),
                "url": base_url.rstrip("/") + "/dashboard#decision-chat",
                "selector": ".analysis-result",
                "full_page": False,
            }
        )
        qa["mobile_prediction"] = "PASS"
        qa["mobile_horizontal_overflow"] = mobile.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        mobile_context.close()
        browser.close()

    if qa.get("desktop_horizontal_overflow") or qa.get("mobile_horizontal_overflow"):
        raise AssertionError("dashboard has horizontal overflow")
    if console_errors:
        raise AssertionError(f"dashboard emitted browser console errors: {console_errors}")
    if page_errors:
        raise AssertionError(f"dashboard emitted browser page errors: {page_errors}")

    health = _require_healthy(base_url)
    manifest = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_url": base_url,
        "health": {
            "status": health.get("status"),
            "demo_mode_ready": health.get("demo_mode_ready"),
            "public_deploy_decision": health.get("public_deploy_decision"),
            "impact_card_rows": health.get("impact_card_rows"),
            "queue": health.get("queue"),
            "auth_required": health.get("auth_required"),
            "rag": health.get("rag"),
        },
        "captures": [
            {
                **item,
                "size_bytes": Path(item["path"]).stat().st_size,
            }
            for item in captures
        ],
        "qa": {
            **qa,
            "console_errors": console_errors,
            "page_errors": page_errors,
        },
    }
    manifest_path = output_dir / "demo_screenshot_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def main() -> None:
    args = parse_args()
    manifest = capture_screenshots(
        args.url,
        Path(args.output_dir),
        timeout_ms=args.timeout_ms,
        analysis_fixture=args.analysis_fixture,
    )
    total_bytes = sum(item["size_bytes"] for item in manifest["captures"])
    print(
        "demo screenshots captured: "
        f"count={len(manifest['captures'])}, "
        f"total_bytes={total_bytes}, "
        f"manifest={manifest['manifest_path']}"
    )


if __name__ == "__main__":
    main()
