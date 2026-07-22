from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.data_science_evaluation import (
    evaluate_data_science_cases,
    load_data_science_cases,
)


GOLDEN = ROOT / "tests" / "fixtures" / "data_science_golden_tasks.json"


def test_data_science_golden_set_passes_typed_plan_oracle_and_safety_gates():
    datasets, cases = load_data_science_cases(GOLDEN)
    report = evaluate_data_science_cases(datasets, cases)

    assert report["metrics"]["case_count"] >= 20
    assert report["metrics"]["end_to_end_pass_rate"] == 1.0, report["failures"]
    assert report["metrics"]["plan_schema_validity"] == 1.0
    assert report["metrics"]["independent_oracle_match_rate"] == 1.0
    assert report["metrics"]["safety_gate_pass_rate"] == 1.0
