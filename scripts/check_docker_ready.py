#!/usr/bin/env python3
"""Report Docker CLI, daemon, and compose readiness for local deployment."""

from __future__ import annotations

import json
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
        version = _run(["docker", "--version"])
        info = _run(["docker", "info", "--format", "{{json .ServerVersion}}"])
        compose = _run(["docker", "compose", "version"])
        payload["docker_version"] = version["stdout"] if version["ok"] else None
        payload["daemon_ready"] = info["ok"]
        payload["compose_ready"] = compose["ok"]
        payload["details"] = {"version": version, "info": info, "compose": compose}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
