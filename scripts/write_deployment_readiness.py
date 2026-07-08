#!/usr/bin/env python3
"""Write a deployment readiness gate artifact without exposing credentials."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
from typing import Any

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
        "--require-auth",
        action="store_true",
        help="Mark hosted/private deployment NO_GO unless write credentials are configured.",
    )
    parser.add_argument(
        "--require-docker",
        action="store_true",
        help="Mark container deployment NO_GO unless Docker daemon and compose are reachable.",
    )
    return parser.parse_args()


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "size_bytes": 0, "mtime_utc": None}
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(
            timespec="seconds"
        ),
    }


def _run(command: list[str], timeout: int = 15) -> dict[str, Any]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _run_docker(command: list[str], timeout: int = 15) -> dict[str, Any]:
    direct = _run(command, timeout=timeout)
    if direct["ok"] or command[:1] != ["docker"] or shutil.which("sg") is None:
        return direct

    quoted = " ".join(shlex.quote(part) for part in command)
    via_group = _run(["sg", "docker", "-c", quoted], timeout=timeout)
    if via_group["ok"]:
        via_group["via_group"] = "docker"
        via_group["direct_stderr"] = direct["stderr"]
        return via_group
    direct["sg_docker_attempt"] = via_group
    return direct


def inspect_docker() -> dict[str, Any]:
    docker_path = shutil.which("docker")
    payload: dict[str, Any] = {
        "docker_cli_found": docker_path is not None,
        "docker_path": docker_path,
        "docker_version": None,
        "daemon_ready": False,
        "compose_ready": False,
        "buildx_ready": False,
        "details": {},
    }
    if docker_path is None:
        return payload

    version = _run_docker(["docker", "--version"])
    info = _run_docker(["docker", "info", "--format", "{{json .ServerVersion}}"])
    compose = _run_docker(["docker", "compose", "version"])
    buildx = _run_docker(["docker", "buildx", "version"])
    payload.update(
        {
            "docker_version": version["stdout"] if version["ok"] else None,
            "daemon_ready": info["ok"],
            "compose_ready": compose["ok"],
            "buildx_ready": buildx["ok"],
            "details": {
                "version": version,
                "info": info,
                "compose": compose,
                "buildx": buildx,
            },
        }
    )
    return payload


def _auth_status() -> dict[str, Any]:
    role_tokens = os.environ.get("CONTROL_TOWER_ROLE_TOKENS", "").strip()
    legacy_token = os.environ.get("CONTROL_TOWER_API_TOKEN", "").strip()
    if role_tokens:
        scheme = "role_tokens"
    elif legacy_token:
        scheme = "legacy_reviewer_token"
    else:
        scheme = "demo"
    return {
        "auth_configured": bool(role_tokens or legacy_token),
        "scheme": scheme,
        "role_tokens_configured": bool(role_tokens),
        "legacy_token_configured": bool(legacy_token),
    }


def _decision(go: bool) -> str:
    return "GO" if go else "NO_GO"


def collect_readiness(
    output_root: Path,
    bike_root: Path,
    workbench_root: Path,
    *,
    require_auth: bool = False,
    require_docker: bool = False,
    docker_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    client = TestClient(
        create_app(
            output_root=output_root,
            bike_root=bike_root,
            workbench_root=workbench_root,
            refresh_artifacts=False,
        )
    )
    ops_response = client.get("/api/ops-metrics")
    ops_ok = ops_response.status_code == 200
    ops_payload = ops_response.json() if ops_ok else {}

    reports = output_root / "reports"
    state = _read_json(reports / "control_state.json", {})
    auth = _auth_status()
    docker = docker_status if docker_status is not None else inspect_docker()
    docker_ready = bool(docker.get("daemon_ready") and docker.get("compose_ready"))

    artifacts = {
        "control_state": _artifact(reports / "control_state.json"),
        "review_queue": _artifact(reports / "control_review_queue.csv"),
        "api_contract": _artifact(reports / "api_contract.json"),
        "impact_policy_audit": _artifact(reports / "impact_policy_audit.json"),
        "reviewer_action_plan": _artifact(reports / "reviewer_action_plan.json"),
        "agent_reviewer_brief": _artifact(reports / "agent_reviewer_brief.json"),
        "agent_candidate_review_notes": _artifact(reports / "agent_candidate_review_notes.json"),
        "dashboard": _artifact(output_root / "dashboard" / "index.html"),
        "sqlite_database": _artifact(output_root / "control_tower.sqlite"),
        "ops_metrics_snapshot": _artifact(reports / "ops_metrics_snapshot.json"),
        "ops_metrics_history": _artifact(reports / "ops_metrics_history.jsonl"),
    }
    required_artifact_names = [
        "control_state",
        "review_queue",
        "api_contract",
        "impact_policy_audit",
        "reviewer_action_plan",
        "agent_reviewer_brief",
        "agent_candidate_review_notes",
        "dashboard",
    ]
    artifact_blockers = [
        f"{name} artifact is missing"
        for name in required_artifact_names
        if not artifacts[name]["exists"]
    ]
    demo_blockers = list(artifact_blockers)
    if not state.get("demo_mode_ready"):
        demo_blockers.append("control state is not demo-ready")
    if not ops_ok:
        demo_blockers.append("ops metrics endpoint is not healthy")

    container_blockers = list(demo_blockers)
    if not docker_ready:
        container_blockers.append("Docker daemon or compose is not ready")

    hosted_private_blockers = list(container_blockers)
    if not auth["auth_configured"]:
        hosted_private_blockers.append("write auth credentials are not configured")

    public_blockers = list(hosted_private_blockers)
    public_blockers.extend(state.get("blockers", []))
    if not state.get("public_deploy_ready"):
        public_blockers.append("control state public_deploy_ready is false")

    warnings: list[str] = []
    if not docker_ready:
        warnings.append("Docker daemon/compose is not currently ready in this shell")
    if docker.get("docker_cli_found") and not docker.get("buildx_ready"):
        warnings.append("Docker buildx plugin is not ready; compose can fall back to classic builder")
    if not auth["auth_configured"]:
        warnings.append("No write auth credential is configured; local demo mode remains writable")
    if not artifacts["ops_metrics_snapshot"]["exists"]:
        warnings.append("ops metrics snapshot has not been written yet")

    local_demo_go = not demo_blockers
    container_demo_go = local_demo_go and docker_ready
    hosted_private_go = container_demo_go and auth["auth_configured"]
    public_go = hosted_private_go and bool(state.get("public_deploy_ready"))
    overall_blockers = list(demo_blockers)
    if require_docker and not container_demo_go:
        overall_blockers.append("container_demo is NO_GO")
    if require_auth and not hosted_private_go:
        overall_blockers.append("hosted_private_demo is NO_GO")

    return {
        "status": "ok" if not overall_blockers else "blocked",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decisions": {
            "local_private_demo": _decision(local_demo_go),
            "container_demo": _decision(container_demo_go),
            "hosted_private_demo": _decision(hosted_private_go),
            "public_deploy": _decision(public_go),
        },
        "overall_blockers": overall_blockers,
        "blockers": {
            "local_private_demo": demo_blockers,
            "container_demo": container_blockers,
            "hosted_private_demo": hosted_private_blockers,
            "public_deploy": public_blockers,
        },
        "warnings": warnings,
        "auth": {
            **auth,
            "configured_roles": ops_payload.get("configured_roles", []),
        },
        "docker": docker,
        "control_state": {
            "demo_mode_ready": bool(state.get("demo_mode_ready")),
            "public_deploy_ready": bool(state.get("public_deploy_ready")),
            "public_deploy_decision": state.get("public_deploy_decision", "UNKNOWN"),
            "source_status": state.get("source_status", {}),
        },
        "ops_metrics": {
            "endpoint_ok": ops_ok,
            "status": ops_payload.get("status"),
            "queue": ops_payload.get("queue", {}),
            "artifacts": ops_payload.get("artifacts", {}),
        },
        "artifacts": artifacts,
    }


def _markdown(payload: dict[str, Any]) -> str:
    decisions = payload["decisions"]
    warnings = payload["warnings"] or ["none"]
    public_blockers = payload["blockers"]["public_deploy"] or ["none"]
    return "\n".join(
        [
            "# Deployment Readiness Gate",
            "",
            f"- Captured UTC: `{payload['captured_at_utc']}`",
            f"- Status: `{payload['status']}`",
            "",
            "| Target | Decision |",
            "|---|---|",
            f"| Local private demo | {decisions['local_private_demo']} |",
            f"| Container demo | {decisions['container_demo']} |",
            f"| Hosted private demo | {decisions['hosted_private_demo']} |",
            f"| Public deploy | {decisions['public_deploy']} |",
            "",
            "## Public Deploy Blockers",
            "",
            *[f"- {item}" for item in public_blockers],
            "",
            "## Warnings",
            "",
            *[f"- {item}" for item in warnings],
            "",
        ]
    )


def write_readiness(output_root: Path, payload: dict[str, Any]) -> dict[str, str]:
    reports = output_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    json_path = reports / "deployment_readiness.json"
    md_path = reports / "deployment_readiness.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def main() -> None:
    args = parse_args()
    payload = collect_readiness(
        Path(args.output_root),
        Path(args.bike_root),
        Path(args.workbench_root),
        require_auth=args.require_auth,
        require_docker=args.require_docker,
    )
    paths = write_readiness(Path(args.output_root), payload)
    print(
        "deployment readiness complete: "
        f"local_private_demo={payload['decisions']['local_private_demo']}, "
        f"container_demo={payload['decisions']['container_demo']}, "
        f"hosted_private_demo={payload['decisions']['hosted_private_demo']}, "
        f"public_deploy={payload['decisions']['public_deploy']}, "
        f"report={paths['json']}"
    )


if __name__ == "__main__":
    main()
