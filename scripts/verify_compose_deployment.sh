#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-decisionops-control-tower-compose-smoke}"
export PORT="${PORT:-8094}"
COMPOSE_CLEANUP="${COMPOSE_CLEANUP:-0}"

cd "$PROJECT_ROOT"

docker_cmd() {
  local err="/tmp/decisionops-docker-direct-$$.err"
  local out="/tmp/decisionops-docker-direct-$$.out"
  if docker "$@" >"$out" 2>"$err"; then
    cat "$out"
    return 0
  fi
  local direct_status=$?
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

echo "[1/5] Docker readiness"
scripts/check_docker_ready.py
docker_cmd info --format 'server={{.ServerVersion}} storage={{.Driver}} cgroup={{.CgroupDriver}}'

echo "[2/5] Compose config"
compose_cmd config --quiet

echo "[3/5] Compose up"
compose_cmd up --build -d

echo "[4/5] HTTP smoke"
health_ok=false
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/tmp/decisionops-compose-health.json 2>/dev/null; then
    health_ok=true
    break
  fi
  sleep 1
done
if [[ "$health_ok" != "true" ]]; then
  echo "Compose service did not answer /health within 60 seconds." >&2
  compose_cmd logs --tail 120 >&2 || true
  exit 1
fi

python3 -m json.tool /tmp/decisionops-compose-health.json
curl -fsS "http://127.0.0.1:${PORT}/api/ops-metrics" >/tmp/decisionops-compose-ops.json
python3 -m json.tool /tmp/decisionops-compose-ops.json | sed -n '1,80p'
curl -fsS -o /tmp/decisionops-compose-dashboard.html -w 'dashboard_http=%{http_code} bytes=%{size_download}\n' "http://127.0.0.1:${PORT}/dashboard"
curl -fsS -o /tmp/decisionops-compose-openapi.json -w 'openapi_http=%{http_code} bytes=%{size_download}\n' "http://127.0.0.1:${PORT}/openapi.json"

echo "[5/5] Compose status"
container_id="$(compose_cmd ps -q control-tower)"
container_healthy=false
for _ in $(seq 1 90); do
  health_status="$(docker_cmd inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")"
  if [[ "$health_status" == "healthy" || "$health_status" == "none" ]]; then
    container_healthy=true
    break
  fi
  sleep 1
done
compose_cmd ps
if [[ "$container_healthy" != "true" ]]; then
  health_status="$(docker_cmd inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id" || true)"
  if [[ "$health_status" == "healthy" || "$health_status" == "none" ]]; then
    container_healthy=true
  fi
fi
if [[ "$container_healthy" != "true" ]]; then
  echo "Compose service healthcheck did not become healthy within 90 seconds." >&2
  docker_cmd inspect --format '{{json .State.Health}}' "$container_id" >&2 || true
  compose_cmd logs --tail 120 >&2 || true
  exit 1
fi

echo
echo "OK: Compose deployment smoke passed."
echo "Dashboard: http://127.0.0.1:${PORT}/dashboard"
if [[ "$COMPOSE_CLEANUP" == "1" ]]; then
  compose_cmd down
  echo "Compose stack removed."
else
  echo "Cleanup: COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME} PORT=${PORT} docker compose down"
fi
