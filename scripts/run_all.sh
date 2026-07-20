#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_ROOT="${OUTPUT_ROOT:-/DATA/HJ/prj/data-scientist-career/projects/decisionops-control-tower}"
BIKE_ROOT="${BIKE_ROOT:-/DATA/HJ/prj/data-scientist-career/projects/bike-share-demand-resilience}"
WORKBENCH_ROOT="${WORKBENCH_ROOT:-/DATA/HJ/prj/data-scientist-career/projects/agentic-decisionops-workbench}"
PUBLIC_INPUTS_JSON="${PUBLIC_INPUTS_JSON:-}"

cd "$PROJECT_ROOT"
mkdir -p "$OUTPUT_ROOT/reports"
PYTHONPATH=src python3 -m pytest tests -q --junitxml="$OUTPUT_ROOT/reports/pytest.xml"
PIPELINE_ARGS=(
  --output-root "$OUTPUT_ROOT"
  --bike-root "$BIKE_ROOT"
  --workbench-root "$WORKBENCH_ROOT"
)
if [[ -n "$PUBLIC_INPUTS_JSON" ]]; then
  PIPELINE_ARGS+=(--public-inputs-json "$PUBLIC_INPUTS_JSON")
fi
PYTHONPATH=src python3 -m decisionops_control_tower.pipeline "${PIPELINE_ARGS[@]}"
PYTHONPATH=src python3 scripts/evaluate_rag.py \
  --output-root "$OUTPUT_ROOT" \
  --report-json "$OUTPUT_ROOT/reports/rag_evaluation.json" \
  --report-md "$OUTPUT_ROOT/reports/rag_evaluation.md" \
  --minimum-pass-rate 1.0
PYTHONPATH=src python3 scripts/smoke_api.py --output-root "$OUTPUT_ROOT" --bike-root "$BIKE_ROOT" --workbench-root "$WORKBENCH_ROOT" --auth-smoke
PYTHONPATH=src python3 scripts/verify_dashboard_ui.py --output-root "$OUTPUT_ROOT" --bike-root "$BIKE_ROOT" --workbench-root "$WORKBENCH_ROOT"
PYTHONPATH=src python3 scripts/write_monitoring_snapshot.py --output-root "$OUTPUT_ROOT" --bike-root "$BIKE_ROOT" --workbench-root "$WORKBENCH_ROOT"
PYTHONPATH=src python3 scripts/write_deployment_readiness.py --output-root "$OUTPUT_ROOT" --bike-root "$BIKE_ROOT" --workbench-root "$WORKBENCH_ROOT"
