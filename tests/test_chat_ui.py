from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.chat_ui import render_chat_surface


def test_recorded_chat_escapes_script_payload_and_rejects_unsafe_url():
    malicious = "</script><script>alert('xss')</script>"
    rendered = render_chat_surface(
        {
            "테스트 질문": {
                "status": "ANSWER",
                "answer": malicious,
                "citations": [
                    {
                        "source_id": "malicious",
                        "title": malicious,
                        "url": "javascript:alert('xss')",
                    }
                ],
            }
        },
        live_chat=False,
        vector_store="memory",
    )

    assert malicious not in rendered
    assert "javascript:" not in rendered
    assert "\\u003c/script\\u003e" in rendered
    assert 'aria-disabled="true"' in rendered
    assert "data-chat-reset" in rendered
    assert "conversationHistory.slice(-12)" in rendered
    assert "recorded_previous_answer" in rendered
    assert "앞선 질문을 이어서 이해합니다" in rendered
    assert "previous_analysis_plan: previousAnalysisPlan" in rendered
    assert "previous_advanced_plan: previousAdvancedPlan" in rendered
    assert "previous_prediction_plan: previousPredictionPlan" in rendered
    assert "addAnalysisResult(message, payload.analysis)" in rendered
    assert "addAdvancedResult(message, payload.advanced_analysis)" in rendered
    assert "addPredictionResult(message, payload.prediction)" in rendered
    assert "검증된 AdvancedAnalysisPlan 보기" in rendered
    assert "검증된 PredictionPlan 보기" in rendered
    assert "buildSeriesChart" in rendered
    assert 'buildAnalysisChart(["bin", "count"], rows, true)' in rendered
    assert "Permutation importance · validation 기준" in rendered
    assert "검증된 분석 결과" in rendered
    assert "analysis.numeric_source_of_truth" in rendered
    assert 'format === "xlsx" || format === "parquet"' in rendered
    assert "arrayBufferToBase64" in rendered
    assert "buildAnalysisChart(columns, rows)" in rendered
    assert "analysis-chart__bar" in rendered
    assert "analysis-chart__bar--negative" in rendered
    assert "Math.abs(row[numericColumn])" in rendered
    assert "new Set(numericRows.map((row) => row[numericColumn])).size <= 1" in rendered
    assert "검증된 AnalysisPlan 보기" in rendered
    assert "friendlyDatasetError" in rendered
    assert "columnNameNormalizationLabel" in rendered
    assert "tableStructureNormalizationLabel" in rendered
    assert "컬럼명 자동 정리" in rendered
    assert "Analysis Copilot · profile" in rendered
    assert "Analysis Copilot · guide" in rendered
    assert "Analysis Copilot · 조건 확인" in rendered
    assert "Analysis Copilot · 원본 복원" in rendered
    assert "Analysis Copilot · overview" in rendered
    assert "runAutomaticOverview(true)" in rendered
    assert "let requestInFlight = false" in rendered
    assert "if (!trimmed || requestInFlight) return" in rendered
    assert 'setRequestState(true, "파일 확인 중")' in rendered
    assert "data-analysis-session" in rendered
    assert "data-analysis-reset" in rendered
    assert "data-chat-context-title" in rendered
    assert "data-upload-trigger" in rendered
    assert "data-evidence-toggle" in rendered
    assert "data-drop-target" in rendered
    assert "showPendingMessage" in rendered
    assert "CSV 저장" in rendered
    assert "SQL 복사" in rendered
    assert "SQL · 실행 계획 보기" in rendered
    assert "downloadRows" in rendered
    assert '/^[=+\\-@\\t\\r]/.test(text)' in rendered
    assert "chat-root--evidence-open" in rendered
    assert "Enter 전송" in rendered
    assert "새 대화" in rendered
    assert "파일은 업로드 해제 전까지 유지" in rendered
    assert "이 대화에 계속 연결" in rendered
    assert "const candidateDataset" in rendered
    assert "overviewMessage.offsetTop" in rendered
    assert "업로드 데이터 자동 분석 시작" in rendered
    assert "addDatasetOverview(message, payload.overview)" in rendered
    assert "addSuggestedQuestions(message, payload.suggested_questions)" in rendered
    assert "자동 데이터 점검 · 품질과 기초 통계" in rendered
    assert "기초통계 분모" in rendered
    assert "chat-suggestion" in rendered
    assert "dataset-summary--error" in rendered
    assert 'role="status" aria-live="polite"' in rendered

    live_rendered = render_chat_surface(
        {},
        live_chat=True,
        vector_store="memory",
    )
    assert "제목/빈 행 뒤 실제 header와 빈·중복 컬럼명 자동 정리" in live_rendered
