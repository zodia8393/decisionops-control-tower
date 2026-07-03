#!/usr/bin/env python3
"""Smoke-test the FastAPI surface without mutating reviewer decisions."""

from __future__ import annotations

import argparse
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


def main() -> None:
    args = parse_args()
    client = TestClient(
        create_app(
            output_root=Path(args.output_root),
            bike_root=Path(args.bike_root),
            workbench_root=Path(args.workbench_root),
            refresh_artifacts=False,
        )
    )
    health = client.get("/health")
    health.raise_for_status()
    queue = client.get("/api/review-queue")
    queue.raise_for_status()
    impact = client.get("/api/impact-cards")
    impact.raise_for_status()
    ops = client.get("/api/ops-metrics")
    ops.raise_for_status()
    dashboard = client.get("/dashboard")
    dashboard.raise_for_status()
    openapi = client.get("/openapi.json")
    openapi.raise_for_status()
    payload = health.json()
    print(
        "api smoke complete: "
        f"status={payload['status']}, "
        f"queue_total={payload['queue']['total']}, "
        f"impact_cards={impact.json()['count']}, "
        f"auth_required={payload['auth_required']}, "
        f"public_deploy_decision={payload['public_deploy_decision']}"
    )


if __name__ == "__main__":
    main()
