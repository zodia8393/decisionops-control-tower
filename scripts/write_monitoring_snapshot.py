#!/usr/bin/env python3
"""Write a reproducible ops-metrics snapshot artifact."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from fastapi.testclient import TestClient

from decisionops_control_tower.app import create_app
from decisionops_control_tower.pipeline import (
    DEFAULT_BIKE_ROOT,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_WORKBENCH_ROOT,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--bike-root", default=str(DEFAULT_BIKE_ROOT))
    parser.add_argument("--workbench-root", default=str(DEFAULT_WORKBENCH_ROOT))
    return parser.parse_args()


def collect_snapshot(output_root: Path, bike_root: Path, workbench_root: Path) -> dict:
    client = TestClient(
        create_app(
            output_root=output_root,
            bike_root=bike_root,
            workbench_root=workbench_root,
            refresh_artifacts=False,
        )
    )
    response = client.get("/api/ops-metrics")
    response.raise_for_status()
    payload = response.json()
    payload["captured_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return payload


def write_snapshot(output_root: Path, payload: dict) -> dict[str, str]:
    reports = output_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    snapshot_path = reports / "ops_metrics_snapshot.json"
    history_path = reports / "ops_metrics_history.jsonl"
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return {"snapshot": str(snapshot_path), "history": str(history_path)}


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    payload = collect_snapshot(output_root, Path(args.bike_root), Path(args.workbench_root))
    paths = write_snapshot(output_root, payload)
    queue = payload.get("queue", {})
    print(
        "monitoring snapshot complete: "
        f"status={payload.get('status')}, "
        f"queue_total={queue.get('total')}, "
        f"public_deploy_decision={payload.get('public_deploy_decision')}, "
        f"snapshot={paths['snapshot']}"
    )


if __name__ == "__main__":
    main()
