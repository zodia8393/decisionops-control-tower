#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_ROOT="${OUTPUT_ROOT:-/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower}"

cd "$PROJECT_ROOT"
PYTHONPATH=src python3 -m decisionops_control_tower.pipeline --output-root "$OUTPUT_ROOT"
PYTHONPATH=src python3 scripts/smoke_api.py --output-root "$OUTPUT_ROOT"
PYTHONPATH=src python3 scripts/write_monitoring_snapshot.py --output-root "$OUTPUT_ROOT"
PYTHONPATH=src python3 scripts/write_deployment_readiness.py --output-root "$OUTPUT_ROOT"
PYTHONPATH=src python3 -m pytest tests -q
