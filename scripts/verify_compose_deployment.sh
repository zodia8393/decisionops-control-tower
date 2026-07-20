#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-decisionops-control-tower-compose-smoke-$$}"
DEFAULT_IMAGE_NAME="decisionops-control-tower:compose-smoke-$$"
export IMAGE_NAME="${IMAGE_NAME:-$DEFAULT_IMAGE_NAME}"
export PORT="${PORT:-}"
export QDRANT_PORT="${QDRANT_PORT:-}"
COMPOSE_CLEANUP="${COMPOSE_CLEANUP:-1}"
TMP_ROOT="$(mktemp -d /tmp/decisionops-compose-smoke.XXXXXX)"
COMPOSE_STARTED=0
IMAGE_BUILT=0
IMAGE_IS_EPHEMERAL=0

if [[ "$IMAGE_NAME" == "$DEFAULT_IMAGE_NAME" ]]; then
  IMAGE_IS_EPHEMERAL=1
fi

if [[ -z "$PORT" || -z "$QDRANT_PORT" ]]; then
  read -r discovered_port discovered_qdrant_port < <(python3 - <<'PY'
import socket
with socket.socket() as app_sock, socket.socket() as qdrant_sock:
    app_sock.bind(("127.0.0.1", 0))
    qdrant_sock.bind(("127.0.0.1", 0))
    print(app_sock.getsockname()[1], qdrant_sock.getsockname()[1])
PY
)
  PORT="${PORT:-$discovered_port}"
  QDRANT_PORT="${QDRANT_PORT:-$discovered_qdrant_port}"
  export PORT
  export QDRANT_PORT
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
  if [[ "$COMPOSE_STARTED" -eq 1 && "$COMPOSE_CLEANUP" == "1" ]]; then
    compose_cmd down --volumes >/dev/null 2>&1 || true
  fi
  if [[ "$IMAGE_BUILT" -eq 1 && "$IMAGE_IS_EPHEMERAL" -eq 1 && "$COMPOSE_CLEANUP" == "1" ]]; then
    docker_cmd image rm "$IMAGE_NAME" >/dev/null 2>&1 || true
  fi
  if [[ "$TMP_ROOT" == /tmp/decisionops-compose-smoke.* && -d "$TMP_ROOT" ]]; then
    rm -rf -- "$TMP_ROOT"
  fi
}
trap cleanup EXIT

echo "[1/5] Docker readiness"
scripts/check_docker_ready.py
docker_cmd info --format 'server={{.ServerVersion}} storage={{.Driver}} cgroup={{.CgroupDriver}}'

echo "[2/5] Compose config"
compose_cmd config --quiet

echo "[3/5] Compose up"
compose_cmd up --build -d
COMPOSE_STARTED=1
IMAGE_BUILT=1

echo "[4/5] HTTP smoke"
health_ok=false
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >"$TMP_ROOT/health.json" 2>/dev/null; then
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

python3 -m json.tool "$TMP_ROOT/health.json"
curl -fsS "http://127.0.0.1:${PORT}/api/ops-metrics" >"$TMP_ROOT/ops.json"
python3 -m json.tool "$TMP_ROOT/ops.json" | sed -n '1,80p'
curl -fsS -o "$TMP_ROOT/dashboard.html" -w 'dashboard_http=%{http_code} bytes=%{size_download}\n' "http://127.0.0.1:${PORT}/dashboard"
curl -fsS -o "$TMP_ROOT/openapi.json" -w 'openapi_http=%{http_code} bytes=%{size_download}\n' "http://127.0.0.1:${PORT}/openapi.json"
chat_ok=false
for _ in $(seq 1 30); do
  if curl -fsS \
    -H 'Content-Type: application/json' \
    -d '{"question":"현재 public deployment 상태와 그 이유를 알려줘."}' \
    "http://127.0.0.1:${PORT}/api/chat" >"$TMP_ROOT/chat.json" 2>/dev/null; then
    chat_ok=true
    break
  fi
  sleep 1
done
if [[ "$chat_ok" != "true" ]]; then
  echo "Compose RAG chat did not answer within 30 seconds." >&2
  compose_cmd logs --tail 120 >&2 || true
  exit 1
fi
python3 - "$TMP_ROOT/chat.json" <<'PY'
import json
from pathlib import Path
import sys

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["retrieval"]["vector_store"] == "qdrant", payload["retrieval"]
assert payload["citations"], "RAG response did not include citations"
assert payload["status"] in {"ANSWER", "REVIEW_REQUIRED"}, payload["status"]
print(
    "chat_http=200 "
    f"status={payload['status']} vector_store={payload['retrieval']['vector_store']} "
    f"citations={len(payload['citations'])}"
)
PY

echo "[5/5] Compose status"
container_id="$(compose_cmd ps -q control-tower)"
qdrant_container_id="$(compose_cmd ps -q qdrant)"
[[ -n "$container_id" ]] || {
  echo "Compose service container id is empty." >&2
  exit 1
}
[[ -n "$qdrant_container_id" ]] || {
  echo "Qdrant service container id is empty." >&2
  exit 1
}
published="$(docker_cmd port "$container_id" 8093/tcp)"
[[ "$published" == "127.0.0.1:${PORT}" ]] || {
  echo "Unexpected published address: $published" >&2
  exit 1
}
qdrant_published="$(docker_cmd port "$qdrant_container_id" 6333/tcp)"
[[ "$qdrant_published" == "127.0.0.1:${QDRANT_PORT}" ]] || {
  echo "Unexpected Qdrant published address: $qdrant_published" >&2
  exit 1
}
container_healthy=false
for _ in $(seq 1 90); do
  health_status="$(docker_cmd inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")"
  if [[ "$health_status" == "healthy" ]]; then
    container_healthy=true
    break
  fi
  sleep 1
done
compose_cmd ps
if [[ "$container_healthy" != "true" ]]; then
  health_status="$(docker_cmd inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id" || true)"
  if [[ "$health_status" == "healthy" ]]; then
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
  echo "Compose stack, volume, and default ephemeral smoke image will be removed automatically."
else
  echo "Cleanup: COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME} PORT=${PORT} docker compose down"
  if [[ "$IMAGE_IS_EPHEMERAL" -eq 1 ]]; then
    echo "Cleanup: docker image rm ${IMAGE_NAME}"
  fi
fi
