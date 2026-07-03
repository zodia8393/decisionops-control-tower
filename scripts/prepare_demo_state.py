#!/usr/bin/env python3
"""Prepare a reproducible local demo state for the Control Tower."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from decisionops_control_tower.pipeline import (
    DEFAULT_BIKE_ROOT,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_WORKBENCH_ROOT,
    run,
)
from decisionops_control_tower.store import database_path, initialize_store, queue_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--bike-root", default=str(DEFAULT_BIKE_ROOT))
    parser.add_argument("--workbench-root", default=str(DEFAULT_WORKBENCH_ROOT))
    parser.add_argument(
        "--reset-approval-store",
        action="store_true",
        help="Archive the existing SQLite approval DB before reseeding pending demo state.",
    )
    return parser.parse_args()


def archive_database(output_root: Path) -> str | None:
    db_path = database_path(output_root)
    if not db_path.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = output_root / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"control_tower.sqlite.{stamp}.bak"
    db_path.replace(backup_path)
    return str(backup_path)


def prepare_demo_state(
    output_root: Path,
    bike_root: Path,
    workbench_root: Path,
    *,
    reset_approval_store: bool = False,
) -> dict[str, object]:
    archived = archive_database(output_root) if reset_approval_store else None
    summary = run(output_root, bike_root, workbench_root)
    store = initialize_store(output_root)
    return {
        "demo_mode_ready": summary["demo_mode_ready"],
        "public_deploy_decision": summary["public_deploy_decision"],
        "queue": queue_summary(output_root),
        "database": store["database"],
        "archived_database": archived,
        "dashboard": summary["reports"]["dashboard"],
    }


def main() -> None:
    args = parse_args()
    payload = prepare_demo_state(
        Path(args.output_root),
        Path(args.bike_root),
        Path(args.workbench_root),
        reset_approval_store=args.reset_approval_store,
    )
    print(
        "demo state ready: "
        f"demo_mode_ready={payload['demo_mode_ready']}, "
        f"public_deploy_decision={payload['public_deploy_decision']}, "
        f"queue_total={payload['queue']['total']}, "
        f"database={payload['database']}, "
        f"archived_database={payload['archived_database']}, "
        f"dashboard={payload['dashboard']}"
    )


if __name__ == "__main__":
    main()
