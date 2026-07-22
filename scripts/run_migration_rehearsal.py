#!/usr/bin/env python3
"""Run the synthetic legacy-hospital scale and recovery rehearsal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.migration_rehearsal import (
    MigrationRehearsalConfig,
    render_migration_rehearsal_report,
    run_migration_rehearsal,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--entities-per-source", type=int, default=20_000)
    parser.add_argument("--chunk-size", type=int, default=2_500)
    parser.add_argument("--interrupt-after-batches", type=int, default=3)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = MigrationRehearsalConfig(
        entities_per_source=args.entities_per_source,
        chunk_size=args.chunk_size,
        interrupt_after_batches=args.interrupt_after_batches,
    )
    report = run_migration_rehearsal(args.database, config)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.report_md:
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(
            render_migration_rehearsal_report(report), encoding="utf-8"
        )
    print(
        "migration rehearsal complete: "
        f"status={report.status}, source_rows={report.source_rows}, "
        f"accepted={report.accepted_rows}, rejected={report.rejected_rows}, "
        f"resumed_from={report.resumed_from_source_rows}, "
        f"replay_processed={report.replay_processed_rows}, "
        f"rows_per_second={report.observed_rows_per_second:.0f}"
    )
    if report.status != "pass":
        raise SystemExit("migration scale and recovery rehearsal failed")


if __name__ == "__main__":
    main()
