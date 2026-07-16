#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_IMAGE_NAME="decisionops-control-tower:docker-smoke-$$"
IMAGE_NAME="${IMAGE_NAME:-$DEFAULT_IMAGE_NAME}"
PORT="${PORT:-}"
CONTAINER_NAME="${CONTAINER_NAME:-decisionops-control-tower-smoke-$$}"
DOCKER_CLEANUP="${DOCKER_CLEANUP:-1}"
TMP_ROOT="$(mktemp -d /tmp/decisionops-docker-smoke.XXXXXX)"
CONTAINER_STARTED=0
IMAGE_BUILT=0
IMAGE_IS_EPHEMERAL=0

if [[ "$IMAGE_NAME" == "$DEFAULT_IMAGE_NAME" ]]; then
  IMAGE_IS_EPHEMERAL=1
fi

if [[ -z "$PORT" ]]; then
  PORT="$(python3 - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
fi

cd "$PROJECT_ROOT"

docker_cmd() {
  local err="$TMP_ROOT/docker-direct.err"
  local out="$TMP_ROOT/docker-direct.out"
  local direct_status
  if docker "$@" >"$out" 2>"$err"; then
    cat "$out"
    return 0
  else
    direct_status=$?
  fi
  if command -v sg >/dev/null 2>&1; then
    local quoted
    printf -v quoted "%q " docker "$@"
    if sg docker -c "$quoted"; then
      return 0
    fi
  fi
  cat "$out" >&2 || true
  cat "$err" >&2 || true
  return "$direct_status"
}

compose_cmd() {
  docker_cmd compose "$@"
}

cleanup() {
  if [[ "$CONTAINER_STARTED" -eq 1 && "$DOCKER_CLEANUP" == "1" ]]; then
    docker_cmd rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fi
  if [[ "$IMAGE_BUILT" -eq 1 && "$IMAGE_IS_EPHEMERAL" -eq 1 && "$DOCKER_CLEANUP" == "1" ]]; then
    docker_cmd image rm "$IMAGE_NAME" >/dev/null 2>&1 || true
  fi
  if [[ "$TMP_ROOT" == /tmp/decisionops-docker-smoke.* && -d "$TMP_ROOT" ]]; then
    rm -rf -- "$TMP_ROOT"
  fi
}
trap cleanup EXIT

echo "[1/6] Docker readiness"
scripts/check_docker_ready.py
docker_cmd info --format 'server={{.ServerVersion}} storage={{.Driver}} cgroup={{.CgroupDriver}}'
compose_cmd version

echo "[2/6] Compose config"
compose_cmd config --quiet

echo "[3/6] Build image"
docker_cmd build -t "$IMAGE_NAME" .
IMAGE_BUILT=1

echo "[4/6] Run container"
docker_cmd rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker_cmd run -d \
  --name "$CONTAINER_NAME" \
  -p "127.0.0.1:${PORT}:8093" \
  -v /DATA/HJ/prj/data-scientist-career/projects:/DATA/HJ/prj/data-scientist-career/projects \
  -e OUTPUT_ROOT=/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower \
  -e BIKE_ROOT=/DATA/HJ/prj/data-scientist-career/projects/bike-share-demand-resilience \
  -e WORKBENCH_ROOT=/DATA/HJ/prj/data-scientist-career/projects/agentic-decisionops-workbench \
  -e LOG_LEVEL=INFO \
  "$IMAGE_NAME" >/dev/null
CONTAINER_STARTED=1
published="$(docker_cmd port "$CONTAINER_NAME" 8093/tcp)"
[[ "$published" == "127.0.0.1:${PORT}" ]] || {
  echo "Unexpected published address: $published" >&2
  exit 1
}

echo "[5/6] HTTP smoke"
health_ok=false
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >"$TMP_ROOT/health.json" 2>/dev/null; then
    health_ok=true
    break
  fi
  sleep 1
done
if [[ "$health_ok" != "true" ]]; then
  echo "Container did not answer /health within 30 seconds." >&2
  docker_cmd logs "$CONTAINER_NAME" --tail 80 >&2 || true
  exit 1
fi

python3 -m json.tool "$TMP_ROOT/health.json"
curl -fsS "http://127.0.0.1:${PORT}/api/ops-metrics" >"$TMP_ROOT/ops.json"
python3 -m json.tool "$TMP_ROOT/ops.json" | sed -n '1,80p'
curl -fsS -o "$TMP_ROOT/dashboard.html" -w 'dashboard_http=%{http_code} bytes=%{size_download}\n' "http://127.0.0.1:${PORT}/dashboard"
curl -fsS -o "$TMP_ROOT/openapi.json" -w 'openapi_http=%{http_code} bytes=%{size_download}\n' "http://127.0.0.1:${PORT}/openapi.json"

echo "[6/6] Container health"
container_healthy=false
for _ in $(seq 1 90); do
  health_status="$(docker_cmd inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CONTAINER_NAME")"
  if [[ "$health_status" == "healthy" ]]; then
    container_healthy=true
    break
  fi
  sleep 1
done
docker_cmd ps --filter "name=${CONTAINER_NAME}" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
if [[ "$container_healthy" != "true" ]]; then
  health_status="$(docker_cmd inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CONTAINER_NAME" || true)"
  if [[ "$health_status" == "healthy" ]]; then
    container_healthy=true
  fi
fi
if [[ "$container_healthy" != "true" ]]; then
  echo "Container healthcheck did not become healthy within 90 seconds." >&2
  docker_cmd inspect --format '{{json .State.Health}}' "$CONTAINER_NAME" >&2 || true
  docker_cmd logs "$CONTAINER_NAME" --tail 80 >&2 || true
  exit 1
fi

echo
echo "OK: Docker deployment smoke passed."
echo "Dashboard: http://127.0.0.1:${PORT}/dashboard"
if [[ "$DOCKER_CLEANUP" == "1" ]]; then
  echo "Container and default ephemeral smoke image will be removed automatically."
else
  echo "Cleanup: docker rm -f ${CONTAINER_NAME}"
  if [[ "$IMAGE_IS_EPHEMERAL" -eq 1 ]]; then
    echo "Cleanup: docker image rm ${IMAGE_NAME}"
  fi
fi
