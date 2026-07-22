#!/usr/bin/env python3
"""Evaluate advanced analysis and prediction against versioned golden cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.data_science_evaluation import (
    data_science_set_identity,
    evaluate_data_science_cases,
    load_data_science_cases,
    render_data_science_report,
)


DEFAULT_GOLDEN_SET = PROJECT_ROOT / "tests" / "fixtures" / "data_science_golden_tasks.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-set", type=Path, default=DEFAULT_GOLDEN_SET)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    parser.add_argument("--minimum-pass-rate", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    datasets, cases = load_data_science_cases(args.golden_set)
    report = evaluate_data_science_cases(datasets, cases)
    report["configuration"] = data_science_set_identity(args.golden_set)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.report_md:
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(render_data_science_report(report), encoding="utf-8")
    metrics = report["metrics"]
    print(
        "data-science evaluation complete: "
        f"datasets={metrics['dataset_count']}, cases={metrics['case_count']}, "
        f"e2e={metrics['end_to_end_pass_rate']:.3f}, "
        f"plan_schema={metrics['plan_schema_validity']:.3f}, "
        f"oracle={metrics['independent_oracle_match_rate']:.3f}, "
        f"gates={metrics['safety_gate_pass_rate']:.3f}"
    )
    if metrics["end_to_end_pass_rate"] < args.minimum_pass_rate:
        raise SystemExit(
            f"data-science pass rate {metrics['end_to_end_pass_rate']:.3f} "
            f"is below {args.minimum_pass_rate:.3f}"
        )


if __name__ == "__main__":
    main()
