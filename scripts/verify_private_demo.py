#!/usr/bin/env python3
"""Verify the private-demo auth boundary without printing credentials."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fastapi.testclient import TestClient

from decisionops_control_tower.app import create_app
from decisionops_control_tower.pipeline import (
    DEFAULT_BIKE_ROOT,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_WORKBENCH_ROOT,
)


VALID_ROLES = {"viewer", "reviewer", "admin"}
WRITE_ROLES = {"reviewer", "admin"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--bike-root", default=str(DEFAULT_BIKE_ROOT))
    parser.add_argument("--workbench-root", default=str(DEFAULT_WORKBENCH_ROOT))
    parser.add_argument(
        "--url",
        help="Optional live server base URL, for example http://127.0.0.1:8093.",
    )
    return parser.parse_args()


def _configured_credentials() -> dict[str, str]:
    credentials: dict[str, str] = {}
    raw_roles = os.environ.get("CONTROL_TOWER_ROLE_TOKENS", "").strip()
    for chunk in raw_roles.split(","):
        item = chunk.strip()
        if not item:
            continue
        separator = ":" if ":" in item else "=" if "=" in item else ""
        if not separator:
            raise AssertionError("CONTROL_TOWER_ROLE_TOKENS must use role:credential chunks")
        role, credential = [part.strip() for part in item.split(separator, 1)]
        role = role.lower()
        if role not in VALID_ROLES:
            raise AssertionError(f"unsupported private demo role: {role}")
        if not credential:
            raise AssertionError("empty private demo credential is not allowed")
        credentials[credential] = role

    legacy = os.environ.get("CONTROL_TOWER_API_TOKEN", "").strip()
    if legacy:
        credentials[legacy] = "reviewer"
    return credentials


def _credential_for(credentials: dict[str, str], roles: set[str]) -> str | None:
    for credential, role in credentials.items():
        if role in roles:
            return credential
    return None


def _request_json(
    base_url: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["X-Control-Tower-Token"] = token
    request = Request(
        base_url.rstrip("/") + path,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=8) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        text = exc.read().decode("utf-8")
        return exc.code, json.loads(text) if text else {}


def _verify_with_testclient(
    output_root: Path,
    bike_root: Path,
    workbench_root: Path,
    credentials: dict[str, str],
) -> dict[str, Any]:
    client = TestClient(
        create_app(
            output_root=output_root,
            bike_root=bike_root,
            workbench_root=workbench_root,
        )
    )
    health = client.get("/health")
    health.raise_for_status()
    queue = client.get("/api/review-queue")
    queue.raise_for_status()
    impact = client.get("/api/impact-cards")
    impact.raise_for_status()

    missing = client.post(
        "/api/review-queue/CTRL-NOT-A-REAL-ID/decision",
        json={"decision": "approve", "reviewer": "private_demo_smoke"},
    )

    viewer_token = _credential_for(credentials, {"viewer"})
    viewer_status = None
    if viewer_token:
        viewer = client.post(
            "/api/review-queue/CTRL-NOT-A-REAL-ID/decision",
            headers={"X-Control-Tower-Token": viewer_token},
            json={"decision": "approve", "reviewer": "private_demo_smoke"},
        )
        viewer_status = viewer.status_code

    write_token = _credential_for(credentials, WRITE_ROLES)
    accepted = client.post(
        "/api/review-queue/CTRL-NOT-A-REAL-ID/decision",
        headers={"X-Control-Tower-Token": write_token or ""},
        json={"decision": "approve", "reviewer": "private_demo_smoke"},
    )

    return _assert_private_demo_result(
        health.json(),
        queue.json(),
        impact.json(),
        missing.status_code,
        accepted.status_code,
        viewer_status,
    )


def _verify_with_url(base_url: str, credentials: dict[str, str]) -> dict[str, Any]:
    health_status, health = _request_json(base_url, "GET", "/health")
    queue_status, queue = _request_json(base_url, "GET", "/api/review-queue")
    impact_status, impact = _request_json(base_url, "GET", "/api/impact-cards")
    if health_status != 200 or queue_status != 200 or impact_status != 200:
        raise AssertionError(
            "private demo endpoints must return HTTP 200 before auth checks"
        )

    missing_status, _ = _request_json(
        base_url,
        "POST",
        "/api/review-queue/CTRL-NOT-A-REAL-ID/decision",
        payload={"decision": "approve", "reviewer": "private_demo_smoke"},
    )
    viewer_token = _credential_for(credentials, {"viewer"})
    viewer_status = None
    if viewer_token:
        viewer_status, _ = _request_json(
            base_url,
            "POST",
            "/api/review-queue/CTRL-NOT-A-REAL-ID/decision",
            token=viewer_token,
            payload={"decision": "approve", "reviewer": "private_demo_smoke"},
        )
    write_token = _credential_for(credentials, WRITE_ROLES)
    accepted_status, _ = _request_json(
        base_url,
        "POST",
        "/api/review-queue/CTRL-NOT-A-REAL-ID/decision",
        token=write_token,
        payload={"decision": "approve", "reviewer": "private_demo_smoke"},
    )

    return _assert_private_demo_result(
        health,
        queue,
        impact,
        missing_status,
        accepted_status,
        viewer_status,
    )


def _assert_private_demo_result(
    health: dict[str, Any],
    queue: dict[str, Any],
    impact: dict[str, Any],
    missing_status: int,
    accepted_status: int,
    viewer_status: int | None,
) -> dict[str, Any]:
    if not health.get("auth_required"):
        raise AssertionError("private demo requires CONTROL_TOWER_ROLE_TOKENS or CONTROL_TOWER_API_TOKEN")
    if queue.get("count", 0) <= 0:
        raise AssertionError("private demo review queue is empty")
    if impact.get("count", 0) <= 0:
        raise AssertionError("private demo impact cards are empty")
    if missing_status != 401:
        raise AssertionError(f"missing credential returned {missing_status}, expected 401")
    if viewer_status is not None and viewer_status != 403:
        raise AssertionError(f"viewer write returned {viewer_status}, expected 403")
    if accepted_status != 404:
        raise AssertionError(
            f"reviewer/admin credential returned {accepted_status}, expected 404 for fake control_id"
        )
    return {
        "status": "ok",
        "auth_required": True,
        "configured_roles": health.get("configured_roles", []),
        "queue_total": queue.get("count"),
        "impact_cards": impact.get("count"),
        "missing_credential_status": missing_status,
        "viewer_write_status": viewer_status,
        "write_credential_status": accepted_status,
        "public_deploy_decision": health.get("public_deploy_decision"),
    }


def verify_private_demo(
    output_root: Path,
    bike_root: Path,
    workbench_root: Path,
    *,
    url: str | None = None,
) -> dict[str, Any]:
    credentials = _configured_credentials()
    if not credentials:
        raise AssertionError("no private demo credential is configured")
    if not _credential_for(credentials, WRITE_ROLES):
        raise AssertionError("private demo needs at least one reviewer or admin credential")
    if url:
        return _verify_with_url(url, credentials)
    return _verify_with_testclient(output_root, bike_root, workbench_root, credentials)


def format_summary(payload: dict[str, Any]) -> str:
    return (
        "private demo verification complete: "
        f"status={payload['status']}, "
        f"roles={','.join(payload['configured_roles'])}, "
        f"queue_total={payload['queue_total']}, "
        f"impact_cards={payload['impact_cards']}, "
        f"missing_credential_status={payload['missing_credential_status']}, "
        f"viewer_write_status={payload['viewer_write_status']}, "
        f"write_credential_status={payload['write_credential_status']}, "
        f"public_deploy_decision={payload['public_deploy_decision']}"
    )


def main() -> None:
    args = parse_args()
    payload = verify_private_demo(
        Path(args.output_root),
        Path(args.bike_root),
        Path(args.workbench_root),
        url=args.url,
    )
    print(format_summary(payload))


if __name__ == "__main__":
    main()
