#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_ROOT="${OUTPUT_ROOT:-/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8093}"

cd "$PROJECT_ROOT"
export PYTHONPATH=src
export OUTPUT_ROOT
uvicorn decisionops_control_tower.app:app --host "$HOST" --port "$PORT" --no-access-log
