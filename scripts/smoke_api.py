#!/usr/bin/env python3
"""Smoke-test the FastAPI surface without mutating reviewer decisions."""

from __future__ import annotations

import argparse
import secrets
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
    parser.add_argument(
        "--auth-smoke",
        action="store_true",
        help="Also verify write-auth behavior with an in-process reviewer token without mutating data.",
    )
    return parser.parse_args()


def _smoke_basic(args: argparse.Namespace) -> None:
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
    policy = client.get("/api/impact-policy-audit")
    policy.raise_for_status()
    robustness = client.get("/api/reviewer-policy-robustness")
    robustness.raise_for_status()
    action_plan = client.get("/api/reviewer-action-plan")
    action_plan.raise_for_status()
    evidence_bundles = client.get("/api/reviewer-evidence-bundles")
    evidence_bundles.raise_for_status()
    audit_integrity = client.get("/api/approval-audit-integrity")
    audit_integrity.raise_for_status()
    if audit_integrity.json()["status"] != "pass":
        raise AssertionError("approval audit integrity smoke failed")
    agent = client.get("/api/agent/reviewer-brief")
    agent.raise_for_status()
    first_impact = impact.json()["items"][0]
    candidate = client.get(f"/api/agent/candidate/{first_impact['impact_card_id']}/review-notes")
    candidate.raise_for_status()
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
        f"policy_rows={policy.json()['count']}, "
        f"robustness_rows={robustness.json()['count']}, "
        f"action_plan_rows={action_plan.json()['count']}, "
        f"evidence_bundles={evidence_bundles.json()['count']}, "
        f"audit_integrity={audit_integrity.json()['status']}, "
        f"agent_mode={agent.json()['mode']}, "
        f"auth_required={payload['auth_required']}, "
        f"public_deploy_decision={payload['public_deploy_decision']}"
    )


def _smoke_auth(args: argparse.Namespace) -> None:
    token = secrets.token_urlsafe(32)
    client = TestClient(
        create_app(
            output_root=Path(args.output_root),
            bike_root=Path(args.bike_root),
            workbench_root=Path(args.workbench_root),
            refresh_artifacts=False,
            auth_token=token,
        )
    )
    health = client.get("/health")
    health.raise_for_status()
    payload = health.json()
    if not payload["auth_required"] or payload["configured_roles"] != ["reviewer"]:
        raise AssertionError("auth smoke expected reviewer auth to be enabled")
    missing = client.post(
        "/api/review-queue/CTRL-NOT-A-REAL-ID/decision",
        json={"decision": "approve", "reviewer": "smoke"},
    )
    if missing.status_code != 401:
        raise AssertionError(f"missing credential returned {missing.status_code}, expected 401")
    authorized = client.post(
        "/api/review-queue/CTRL-NOT-A-REAL-ID/decision",
        headers={"X-Control-Tower-Token": token},
        json={"decision": "approve", "reviewer": "smoke"},
    )
    if authorized.status_code != 404:
        raise AssertionError(f"authorized missing item returned {authorized.status_code}, expected 404")
    print("auth smoke complete: reviewer token accepted, missing token rejected, no queue row mutated")


def main() -> None:
    args = parse_args()
    _smoke_basic(args)
    if args.auth_smoke:
        _smoke_auth(args)


if __name__ == "__main__":
    main()
