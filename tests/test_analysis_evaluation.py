from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.analysis_evaluation import (
    MIN_ANALYSIS_CASES,
    analysis_set_identity,
    evaluate_analysis_cases,
    load_analysis_cases,
    render_analysis_report,
)


GOLDEN_SET = ROOT / "tests" / "fixtures" / "analysis_golden_tasks.json"


def test_analysis_golden_set_is_versioned_unique_and_cross_domain():
    datasets, cases = load_analysis_cases(GOLDEN_SET)
    identity = analysis_set_identity(GOLDEN_SET)

    assert len(cases) >= MIN_ANALYSIS_CASES
    assert len({case["id"] for case in cases}) == len(cases)
    assert len(datasets) >= 4
    assert {case["expected_status"] for case in cases} == {"planned", "clarification"}
    assert identity["golden_set_version"] == "1.1"
    assert len(identity["golden_set_sha256"]) == 64


def test_holdout_schema_evaluation_meets_goal_thresholds():
    datasets, cases = load_analysis_cases(GOLDEN_SET)

    report = evaluate_analysis_cases(datasets, cases)
    report["configuration"] = analysis_set_identity(GOLDEN_SET)

    assert report["metrics"]["end_to_end_pass_rate"] >= 0.9, report["failures"]
    assert report["metrics"]["analysis_plan_schema_validity"] == 1.0
    assert report["metrics"]["numeric_execution_correctness"] == 1.0
    assert report["metrics"]["paraphrase_case_count"] >= 20
    assert report["metrics"]["paraphrase_pass_rate"] >= 0.9
    assert report["metrics"]["multiturn_case_count"] >= 8
    assert report["metrics"]["multiturn_pass_rate"] >= 0.9
    assert "holdout-schema" in render_analysis_report(report)
