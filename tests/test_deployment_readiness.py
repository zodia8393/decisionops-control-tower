import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in [SRC, SCRIPTS]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from decisionops_control_tower.pipeline import DEFAULT_BIKE_ROOT, DEFAULT_WORKBENCH_ROOT, run
from decisionops_control_tower.store import database_path, list_queue, record_decision
from write_deployment_readiness import collect_readiness, write_readiness, _run_docker


READY_DOCKER = {
    "docker_cli_found": True,
    "docker_path": "/usr/bin/docker",
    "docker_version": "Docker version test",
    "daemon_ready": True,
    "compose_ready": True,
    "buildx_ready": False,
    "details": {},
}


def test_deployment_readiness_writes_private_demo_gate(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTROL_TOWER_ROLE_TOKENS", raising=False)
    monkeypatch.delenv("CONTROL_TOWER_API_TOKEN", raising=False)
    run(tmp_path)

    payload = collect_readiness(
        tmp_path,
        DEFAULT_BIKE_ROOT,
        DEFAULT_WORKBENCH_ROOT,
        require_docker=True,
        docker_status=READY_DOCKER,
    )
    paths = write_readiness(tmp_path, payload)

    assert payload["decisions"]["local_private_demo"] == "GO"
    assert payload["decisions"]["container_demo"] == "GO"
    assert payload["decisions"]["hosted_write_api"] == "NO_GO"
    assert payload["decisions"]["public_deploy"] == (
        "GO" if payload["control_state"]["public_deploy_ready"] else "NO_GO"
    )
    assert payload["artifacts"]["reviewer_evidence_bundles"]["exists"] is True
    assert payload["artifacts"]["approval_audit_integrity"]["exists"] is True
    assert payload["approval_audit_integrity"]["status"] == "pass"
    assert payload["auth"]["scheme"] == "demo"
    assert any("buildx" in warning for warning in payload["warnings"])
    assert Path(paths["json"]).exists()
    assert Path(paths["markdown"]).exists()


def test_deployment_readiness_can_require_auth_for_hosted_demo(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTROL_TOWER_ROLE_TOKENS", raising=False)
    monkeypatch.delenv("CONTROL_TOWER_API_TOKEN", raising=False)
    run(tmp_path)

    payload = collect_readiness(
        tmp_path,
        DEFAULT_BIKE_ROOT,
        DEFAULT_WORKBENCH_ROOT,
        require_auth=True,
        require_docker=True,
        docker_status={**READY_DOCKER, "buildx_ready": True},
    )

    assert payload["decisions"]["hosted_private_demo"] == "NO_GO"
    assert "write auth credentials are not configured" in payload["blockers"]["hosted_private_demo"]


def test_deployment_readiness_rejects_weak_hosted_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROL_TOWER_ROLE_TOKENS", "reviewer:short-token")
    monkeypatch.delenv("CONTROL_TOWER_API_TOKEN", raising=False)
    run(tmp_path)

    payload = collect_readiness(
        tmp_path,
        DEFAULT_BIKE_ROOT,
        DEFAULT_WORKBENCH_ROOT,
        require_auth=True,
        docker_status={**READY_DOCKER, "buildx_ready": True},
    )

    assert payload["decisions"]["hosted_private_demo"] == "NO_GO"
    assert payload["auth"]["hosted_auth_ready"] is False
    assert any("at least 24" in item for item in payload["blockers"]["hosted_private_demo"])


def test_deployment_readiness_accepts_strong_reviewer_auth(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "CONTROL_TOWER_ROLE_TOKENS",
        "reviewer:reviewer-credential-with-32-characters",
    )
    monkeypatch.delenv("CONTROL_TOWER_API_TOKEN", raising=False)
    run(tmp_path)

    payload = collect_readiness(
        tmp_path,
        DEFAULT_BIKE_ROOT,
        DEFAULT_WORKBENCH_ROOT,
        require_auth=True,
        docker_status={**READY_DOCKER, "buildx_ready": True},
    )

    assert payload["decisions"]["hosted_private_demo"] == "GO"
    assert payload["auth"]["hosted_auth_ready"] is True
    assert payload["auth"]["configured_roles"] == ["reviewer"]


def test_public_read_only_gate_does_not_require_hosted_write_auth(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTROL_TOWER_ROLE_TOKENS", raising=False)
    monkeypatch.delenv("CONTROL_TOWER_API_TOKEN", raising=False)
    run(tmp_path)
    state_path = tmp_path / "reports" / "control_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(
        {
            "public_deploy_ready": True,
            "public_deploy_decision": "GO",
            "blockers": [],
        }
    )
    state_path.write_text(json.dumps(state), encoding="utf-8")

    payload = collect_readiness(
        tmp_path,
        tmp_path / "missing-bike-root",
        tmp_path / "missing-workbench-root",
        docker_status={**READY_DOCKER, "buildx_ready": True},
    )

    assert payload["decisions"]["public_read_only_snapshot"] == "GO"
    assert payload["decisions"]["public_deploy"] == "GO"
    assert payload["decisions"]["hosted_write_api"] == "NO_GO"
    assert payload["blockers"]["public_deploy"] == []


def test_docker_probe_falls_back_to_sg_group(monkeypatch):
    calls = []

    def fake_run(command, timeout=15):
        calls.append(command)
        if command[:2] == ["docker", "info"]:
            return {"ok": False, "returncode": 1, "stdout": "", "stderr": "permission denied"}
        if command[:3] == ["sg", "docker", "-c"]:
            return {"ok": True, "returncode": 0, "stdout": '"29.1.3"', "stderr": ""}
        return {"ok": True, "returncode": 0, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr("write_deployment_readiness.shutil.which", lambda name: "/usr/bin/sg" if name == "sg" else "/usr/bin/docker")
    monkeypatch.setattr("write_deployment_readiness._run", fake_run)

    result = _run_docker(["docker", "info", "--format", "{{json .ServerVersion}}"])

    assert result["ok"] is True
    assert result["via_group"] == "docker"
    assert calls[1][:3] == ["sg", "docker", "-c"]


def test_deployment_readiness_blocks_tampered_approval_history(tmp_path):
    run(tmp_path)
    control_id = list_queue(tmp_path)[0]["control_id"]
    record_decision(tmp_path, control_id, "approve", "reviewer_a", "원본")
    with sqlite3.connect(database_path(tmp_path)) as conn:
        conn.execute("UPDATE approval_history SET note = '변조' WHERE id = 1")

    payload = collect_readiness(
        tmp_path,
        DEFAULT_BIKE_ROOT,
        DEFAULT_WORKBENCH_ROOT,
        docker_status=READY_DOCKER,
    )

    assert payload["decisions"]["local_private_demo"] == "NO_GO"
    assert payload["approval_audit_integrity"]["status"] == "fail"
    assert any("approval audit" in item for item in payload["blockers"]["local_private_demo"])
