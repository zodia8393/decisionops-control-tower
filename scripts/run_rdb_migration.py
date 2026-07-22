#!/usr/bin/env python3
"""Run the containerized Firebird to PostgreSQL migration evidence case."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from decisionops_control_tower.rdb_migration import (
    RdbMigrationConfig,
    render_rdb_migration_report,
    run_rdb_migration,
    write_rdb_migration_reports,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entities-per-table", type=int, default=40_000)
    parser.add_argument("--batch-size", type=int, default=2_500)
    parser.add_argument("--interrupt-after-batches", type=int, default=1)
    parser.add_argument("--report-json", type=Path, default=Path("/reports/report.json"))
    parser.add_argument("--report-md", type=Path, default=Path("/reports/report.md"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = RdbMigrationConfig(
        entities_per_table=args.entities_per_table,
        batch_size=args.batch_size,
        interrupt_after_batches=args.interrupt_after_batches,
        firebird_host=os.getenv("MIGRATION_FIREBIRD_HOST", "migration-firebird"),
        firebird_port=int(os.getenv("MIGRATION_FIREBIRD_PORT", "3050")),
        firebird_database=os.getenv(
            "MIGRATION_FIREBIRD_DATABASE",
            "/var/lib/firebird/data/legacy_hospital.fdb",
        ),
        firebird_user=os.getenv("MIGRATION_FIREBIRD_USER", "SYSDBA"),
        firebird_password=os.environ["MIGRATION_FIREBIRD_PASSWORD"],
        postgres_host=os.getenv("MIGRATION_POSTGRES_HOST", "migration-postgres"),
        postgres_port=int(os.getenv("MIGRATION_POSTGRES_PORT", "5432")),
        postgres_database=os.getenv("MIGRATION_POSTGRES_DATABASE", "migration"),
        postgres_user=os.getenv("MIGRATION_POSTGRES_USER", "migration"),
        postgres_password=os.environ["MIGRATION_POSTGRES_PASSWORD"],
    )
    report = run_rdb_migration(config)
    write_rdb_migration_reports(report, args.report_json, args.report_md)
    print(render_rdb_migration_report(report))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
