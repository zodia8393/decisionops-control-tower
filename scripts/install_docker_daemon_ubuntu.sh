#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Run as the normal user with sudo privileges, not as root." >&2
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required." >&2
  exit 1
fi

echo "[1/5] OS"
. /etc/os-release
echo "Detected: ${PRETTY_NAME:-unknown}"

echo "[2/5] Install Docker daemon from Ubuntu repository"
sudo apt-get update
sudo apt-get install -y docker.io

echo "[3/5] Enable and start docker.service"
sudo systemctl enable --now docker
sudo systemctl --no-pager --full status docker | sed -n '1,12p'

echo "[4/5] Add current user to docker group if needed"
if ! id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
  sudo usermod -aG docker "$USER"
  echo "Added $USER to docker group. Open a new terminal or run: newgrp docker"
else
  echo "$USER is already in docker group."
fi

echo "[5/5] Verify"
docker --version
docker compose version || true
sudo docker info --format 'server={{.ServerVersion}} storage={{.Driver}} cgroup={{.CgroupDriver}}'

echo
echo "If 'docker info' works only with sudo, open a new terminal or run: newgrp docker"
