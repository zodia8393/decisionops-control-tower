#!/usr/bin/env python3
"""Report Docker CLI, daemon, and compose readiness for local deployment."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from typing import Any


def _run(command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _run_docker(command: list[str]) -> dict[str, Any]:
    direct = _run(command)
    if direct["ok"] or command[:1] != ["docker"] or shutil.which("sg") is None:
        return direct

    quoted = " ".join(shlex.quote(part) for part in command)
    via_group = _run(["sg", "docker", "-c", quoted])
    if via_group["ok"]:
        via_group["via_group"] = "docker"
        via_group["direct_stderr"] = direct["stderr"]
        return via_group
    direct["sg_docker_attempt"] = via_group
    return direct


def main() -> None:
    docker_path = shutil.which("docker")
    payload: dict[str, Any] = {
        "docker_cli_found": docker_path is not None,
        "docker_path": docker_path,
        "docker_version": None,
        "daemon_ready": False,
        "compose_ready": False,
        "details": {},
    }
    if docker_path:
        version = _run_docker(["docker", "--version"])
        info = _run_docker(["docker", "info", "--format", "{{json .ServerVersion}}"])
        compose = _run_docker(["docker", "compose", "version"])
        payload["docker_version"] = version["stdout"] if version["ok"] else None
        payload["daemon_ready"] = info["ok"]
        payload["compose_ready"] = compose["ok"]
        payload["details"] = {"version": version, "info": info, "compose": compose}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
