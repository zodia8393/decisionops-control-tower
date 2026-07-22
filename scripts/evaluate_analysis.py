#!/usr/bin/env python3
"""Evaluate the analysis copilot against versioned schema and conversation challenges."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.analysis_evaluation import (
    analysis_set_identity,
    evaluate_analysis_cases,
    load_analysis_cases,
    render_analysis_report,
)


DEFAULT_GOLDEN_SET = PROJECT_ROOT / "tests" / "fixtures" / "analysis_golden_tasks.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-set", type=Path, default=DEFAULT_GOLDEN_SET)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    parser.add_argument("--minimum-pass-rate", type=float, default=0.9)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0.0 <= args.minimum_pass_rate <= 1.0:
        raise SystemExit("--minimum-pass-rate must be between 0 and 1")
    datasets, cases = load_analysis_cases(args.golden_set)
    report = evaluate_analysis_cases(datasets, cases)
    report["configuration"] = analysis_set_identity(args.golden_set)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.report_md:
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(render_analysis_report(report), encoding="utf-8")
    metrics = report["metrics"]
    print(
        "analysis evaluation complete: "
        f"datasets={metrics['dataset_count']}, cases={metrics['case_count']}, "
        f"e2e={metrics['end_to_end_pass_rate']:.3f}, "
        f"plan_schema={metrics['analysis_plan_schema_validity']:.3f}, "
        f"numeric={metrics['numeric_execution_correctness']:.3f}"
    )
    if metrics["end_to_end_pass_rate"] < args.minimum_pass_rate:
        raise SystemExit(
            "analysis pass rate "
            f"{metrics['end_to_end_pass_rate']:.3f} is below {args.minimum_pass_rate:.3f}"
        )


if __name__ == "__main__":
    main()
