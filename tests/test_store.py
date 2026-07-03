import csv
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower import store


def _write_queue_csv(output_root: Path) -> None:
    reports = output_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    with (reports / "control_review_queue.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "control_id",
                "queue_id",
                "priority",
                "task_id",
                "action",
                "guardrail_hits",
                "approval_state",
                "owner",
                "review_context",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "control_id": "CTRL-0001",
                "queue_id": "HRQ-0001",
                "priority": "P1",
                "task_id": "task_001",
                "action": "escalate",
                "guardrail_hits": "high_uncertainty_review",
                "approval_state": "pending_reviewer",
                "owner": "ops_reviewer",
                "review_context": "요청: 사람 검토",
            }
        )


def test_initialize_store_tolerates_duplicate_review_context_migration(tmp_path, monkeypatch):
    _write_queue_csv(tmp_path)
    with sqlite3.connect(store.database_path(tmp_path)) as conn:
        conn.execute(
            """
            CREATE TABLE control_queue (
                control_id TEXT PRIMARY KEY,
                queue_id TEXT NOT NULL,
                priority TEXT NOT NULL,
                task_id TEXT,
                action TEXT,
                guardrail_hits TEXT,
                approval_state TEXT NOT NULL,
                owner TEXT NOT NULL,
                source_updated_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            )
            """
        )

    store.initialize_store(tmp_path)
    monkeypatch.setattr(store, "_table_columns", lambda conn, table: set())

    result = store.initialize_store(tmp_path)

    assert result["queue_rows"] == 1
    assert store.list_queue(tmp_path)[0]["review_context"] == "요청: 사람 검토"
