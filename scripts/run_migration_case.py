#!/usr/bin/env python3
"""Run the synthetic legacy-hospital migration validation case."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.migration_case import (
    DEFAULT_MIGRATION_CASE_PATH,
    load_migration_case,
    render_migration_report,
    run_migration_case,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, default=DEFAULT_MIGRATION_CASE_PATH)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_migration_case(load_migration_case(args.case))
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.report_md:
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(render_migration_report(report), encoding="utf-8")
    print(
        "migration case complete: "
        f"status={report.status}, source_rows={report.metrics['source_rows']}, "
        f"accepted={report.metrics['accepted_rows']}, "
        f"rejected={report.metrics['rejected_rows']}, "
        f"fingerprint={report.result_fingerprint_sha256[:12]}"
    )
    if report.status != "pass":
        raise SystemExit("migration reconciliation failed")


if __name__ == "__main__":
    main()
