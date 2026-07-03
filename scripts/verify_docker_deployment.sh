#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-decisionops-control-tower:local}"
PORT="${PORT:-8093}"
CONTAINER_NAME="${CONTAINER_NAME:-decisionops-control-tower-smoke}"
DOCKER_CLEANUP="${DOCKER_CLEANUP:-0}"

cd "$PROJECT_ROOT"

echo "[1/6] Docker readiness"
scripts/check_docker_ready.py
docker info --format 'server={{.ServerVersion}} storage={{.Driver}} cgroup={{.CgroupDriver}}'
docker compose version

echo "[2/6] Compose config"
docker compose config --quiet

echo "[3/6] Build image"
docker build -t "$IMAGE_NAME" .

echo "[4/6] Run container"
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "${PORT}:8093" \
  -v /DATA/HJ/prj/data-scientist-career/projects:/DATA/HJ/prj/data-scientist-career/projects \
  -e OUTPUT_ROOT=/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower \
  -e BIKE_ROOT=/DATA/HJ/prj/data-scientist-career/projects/bike-share-demand-resilience \
  -e WORKBENCH_ROOT=/DATA/HJ/prj/data-scientist-career/projects/agentic-decisionops-workbench \
  -e LOG_LEVEL=INFO \
  "$IMAGE_NAME" >/dev/null

echo "[5/6] HTTP smoke"
health_ok=false
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/tmp/decisionops-docker-health.json 2>/dev/null; then
    health_ok=true
    break
  fi
  sleep 1
done
if [[ "$health_ok" != "true" ]]; then
  echo "Container did not answer /health within 30 seconds." >&2
  docker logs "$CONTAINER_NAME" --tail 80 >&2 || true
  exit 1
fi

python3 -m json.tool /tmp/decisionops-docker-health.json
curl -fsS "http://127.0.0.1:${PORT}/api/ops-metrics" >/tmp/decisionops-docker-ops.json
python3 -m json.tool /tmp/decisionops-docker-ops.json | sed -n '1,80p'
curl -fsS -o /tmp/decisionops-docker-dashboard.html -w 'dashboard_http=%{http_code} bytes=%{size_download}\n' "http://127.0.0.1:${PORT}/dashboard"
curl -fsS -o /tmp/decisionops-docker-openapi.json -w 'openapi_http=%{http_code} bytes=%{size_download}\n' "http://127.0.0.1:${PORT}/openapi.json"

echo "[6/6] Container health"
container_healthy=false
for _ in $(seq 1 30); do
  health_status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CONTAINER_NAME")"
  if [[ "$health_status" == "healthy" || "$health_status" == "none" ]]; then
    container_healthy=true
    break
  fi
  sleep 1
done
docker ps --filter "name=${CONTAINER_NAME}" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
if [[ "$container_healthy" != "true" ]]; then
  echo "Container healthcheck did not become healthy within 30 seconds." >&2
  docker inspect --format '{{json .State.Health}}' "$CONTAINER_NAME" >&2 || true
  docker logs "$CONTAINER_NAME" --tail 80 >&2 || true
  exit 1
fi

echo
echo "OK: Docker deployment smoke passed."
echo "Dashboard: http://127.0.0.1:${PORT}/dashboard"
if [[ "$DOCKER_CLEANUP" == "1" ]]; then
  docker rm -f "$CONTAINER_NAME" >/dev/null
  echo "Container removed."
else
  echo "Cleanup: docker rm -f ${CONTAINER_NAME}"
fi
