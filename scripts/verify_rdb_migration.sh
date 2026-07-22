#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-decisionops-migration-rdb}"
REPORT_DIR="${MIGRATION_REPORT_DIR:-$PROJECT_ROOT/build/migration-rdb}"

cd "$PROJECT_ROOT"
mkdir -p "$REPORT_DIR"
export COMPOSE_PROJECT_NAME MIGRATION_REPORT_DIR="$REPORT_DIR"

cleanup() {
  docker compose -f compose.migration.yaml down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose -f compose.migration.yaml up \
  --build \
  --abort-on-container-exit \
  --exit-code-from migration-runner

python3 - "$REPORT_DIR/firebird_postgres_migration.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert report["status"] == "pass", report
assert report["source_rows"] == 120_000, report["source_rows"]
assert report["source_rows"] == report["accepted_rows"] + report["rejected_rows"]
assert report["rollback_verified"] is True
assert report["checkpoint_resume_verified"] is True
assert report["idempotent_replay"] is True
assert report["replay_processed_rows"] == 0
assert report["schema_drift_blocked_before_write"] is True
assert report["foreign_key_violations"] == 0
assert all(item["status"] == "pass" for item in report["reconciliation"])
print(
    "RDB migration PASS: "
    f"{report['source_rows']:,} = {report['accepted_rows']:,} accepted + "
    f"{report['rejected_rows']:,} rejected"
)
PY
