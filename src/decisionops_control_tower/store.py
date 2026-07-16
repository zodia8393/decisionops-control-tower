"""SQLite store for the Control Tower approval workflow."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


QUEUE_COLUMNS = [
    "control_id",
    "queue_id",
    "priority",
    "task_id",
    "action",
    "guardrail_hits",
    "approval_state",
    "owner",
    "review_context",
]

DECISION_TO_STATE = {
    "approve": "approved",
    "reject": "rejected",
    "needs_more_evidence": "needs_more_evidence",
}

AUDIT_CHAIN_VERSION = "approval-history-sha256-v1"
GENESIS_HASH = "0" * 64


def database_path(output_root: Path) -> Path:
    return output_root / "control_tower.sqlite"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(output_root: Path) -> sqlite3.Connection:
    output_root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path(output_root))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if table not in {"control_queue", "approval_history"}:
        raise ValueError(f"unsupported table for schema inspection: {table}")
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _audit_event_hash(
    *,
    control_id: str,
    decision: str,
    reviewer: str,
    note: str,
    created_at_utc: str,
    previous_event_hash: str,
    payload_version: str = AUDIT_CHAIN_VERSION,
) -> str:
    payload = {
        "control_id": control_id,
        "created_at_utc": created_at_utc,
        "decision": decision,
        "note": note,
        "payload_version": payload_version,
        "previous_event_hash": previous_event_hash,
        "reviewer": reviewer,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _ensure_history_chain_schema(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, "approval_history")
    migrations = {
        "payload_version": "TEXT NOT NULL DEFAULT ''",
        "previous_event_hash": "TEXT NOT NULL DEFAULT ''",
        "event_hash": "TEXT NOT NULL DEFAULT ''",
    }
    for column, definition in migrations.items():
        if column in columns:
            continue
        try:
            conn.execute(f"ALTER TABLE approval_history ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise


def _backfill_legacy_history_chain(conn: sqlite3.Connection) -> None:
    """Chain legacy rows once without silently repairing later tampering."""

    previous_hash = GENESIS_HASH
    rows = conn.execute("SELECT * FROM approval_history ORDER BY id").fetchall()
    for row in rows:
        payload_version = row["payload_version"] or AUDIT_CHAIN_VERSION
        expected = _audit_event_hash(
            control_id=row["control_id"],
            decision=row["decision"],
            reviewer=row["reviewer"],
            note=row["note"],
            created_at_utc=row["created_at_utc"],
            previous_event_hash=previous_hash,
            payload_version=payload_version,
        )
        if not row["event_hash"] and not row["previous_event_hash"]:
            conn.execute(
                """
                UPDATE approval_history
                SET payload_version = ?, previous_event_hash = ?, event_hash = ?
                WHERE id = ?
                """,
                (payload_version, previous_hash, expected, row["id"]),
            )
            previous_hash = expected
            continue
        # Keep the first mismatch intact so verification can expose it.
        previous_hash = row["event_hash"]


def _read_queue_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def initialize_store(output_root: Path) -> dict[str, Any]:
    """Create tables and upsert queue rows from the latest pipeline artifact."""

    queue_path = output_root / "reports" / "control_review_queue.csv"
    source_rows = _read_queue_csv(queue_path)
    now = _now_utc()
    with _connect(output_root) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS control_queue (
                control_id TEXT PRIMARY KEY,
                queue_id TEXT NOT NULL,
                priority TEXT NOT NULL,
                task_id TEXT,
                action TEXT,
                guardrail_hits TEXT,
                approval_state TEXT NOT NULL,
                owner TEXT NOT NULL,
                review_context TEXT NOT NULL DEFAULT '',
                source_updated_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            )
            """
        )
        if "review_context" not in _table_columns(conn, "control_queue"):
            try:
                conn.execute("ALTER TABLE control_queue ADD COLUMN review_context TEXT NOT NULL DEFAULT ''")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                control_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                note TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                payload_version TEXT NOT NULL DEFAULT '',
                previous_event_hash TEXT NOT NULL DEFAULT '',
                event_hash TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (control_id) REFERENCES control_queue(control_id)
            )
            """
        )
        _ensure_history_chain_schema(conn)
        _backfill_legacy_history_chain(conn)
        for row in source_rows:
            values = {
                "control_id": row.get("control_id", ""),
                "queue_id": row.get("queue_id", ""),
                "priority": row.get("priority", "P2"),
                "task_id": row.get("task_id", ""),
                "action": row.get("action", ""),
                "guardrail_hits": row.get("guardrail_hits", ""),
                "approval_state": row.get("approval_state", "pending_reviewer"),
                "owner": row.get("owner", "ops_reviewer"),
                "review_context": row.get("review_context", ""),
                "source_updated_at_utc": now,
                "updated_at_utc": now,
            }
            if not values["control_id"]:
                continue
            conn.execute(
                """
                INSERT INTO control_queue (
                    control_id, queue_id, priority, task_id, action, guardrail_hits,
                    approval_state, owner, review_context, source_updated_at_utc, updated_at_utc
                )
                VALUES (
                    :control_id, :queue_id, :priority, :task_id, :action, :guardrail_hits,
                    :approval_state, :owner, :review_context, :source_updated_at_utc, :updated_at_utc
                )
                ON CONFLICT(control_id) DO UPDATE SET
                    queue_id = excluded.queue_id,
                    priority = excluded.priority,
                    task_id = excluded.task_id,
                    action = excluded.action,
                    guardrail_hits = excluded.guardrail_hits,
                    review_context = excluded.review_context,
                    owner = CASE
                        WHEN control_queue.approval_state = 'pending_reviewer'
                        THEN excluded.owner
                        ELSE control_queue.owner
                    END,
                    source_updated_at_utc = excluded.source_updated_at_utc
                """,
                values,
            )
        queue_count = conn.execute("SELECT COUNT(*) FROM control_queue").fetchone()[0]
        history_count = conn.execute("SELECT COUNT(*) FROM approval_history").fetchone()[0]
        chained_history_count = conn.execute(
            "SELECT COUNT(*) FROM approval_history WHERE event_hash != ''"
        ).fetchone()[0]
    return {
        "database": str(database_path(output_root)),
        "source_rows": len(source_rows),
        "queue_rows": queue_count,
        "history_rows": history_count,
        "chained_history_rows": chained_history_count,
    }


def list_queue(output_root: Path, approval_state: str | None = None) -> list[dict[str, Any]]:
    initialize_store(output_root)
    sql = """
        SELECT *
        FROM control_queue
    """
    params: tuple[Any, ...] = ()
    if approval_state:
        sql += " WHERE approval_state = ?"
        params = (approval_state,)
    sql += """
        ORDER BY
            CASE priority
                WHEN 'P0' THEN 0
                WHEN 'P1' THEN 1
                WHEN 'P2' THEN 2
                ELSE 9
            END,
            control_id
    """
    with _connect(output_root) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def queue_summary(output_root: Path) -> dict[str, Any]:
    initialize_store(output_root)
    with _connect(output_root) as conn:
        total = conn.execute("SELECT COUNT(*) FROM control_queue").fetchone()[0]
        by_state = {
            row["approval_state"]: row["count"]
            for row in conn.execute(
                """
                SELECT approval_state, COUNT(*) AS count
                FROM control_queue
                GROUP BY approval_state
                ORDER BY approval_state
                """
            ).fetchall()
        }
    return {"total": total, "by_state": by_state}


def record_decision(
    output_root: Path,
    control_id: str,
    decision: str,
    reviewer: str = "ops_reviewer",
    note: str = "",
) -> dict[str, Any]:
    if decision not in DECISION_TO_STATE:
        raise ValueError(f"unsupported decision: {decision}")
    reviewer = reviewer.strip() or "ops_reviewer"
    note = note.strip()
    now = _now_utc()
    next_state = DECISION_TO_STATE[decision]
    initialize_store(output_root)
    with _connect(output_root) as conn:
        existing = conn.execute(
            "SELECT control_id FROM control_queue WHERE control_id = ?", (control_id,)
        ).fetchone()
        if existing is None:
            raise KeyError(control_id)
        conn.execute(
            """
            UPDATE control_queue
            SET approval_state = ?, owner = ?, updated_at_utc = ?
            WHERE control_id = ?
            """,
            (next_state, reviewer, now, control_id),
        )
        previous = conn.execute(
            "SELECT event_hash FROM approval_history ORDER BY id DESC LIMIT 1"
        ).fetchone()
        previous_event_hash = previous["event_hash"] if previous else GENESIS_HASH
        event_hash = _audit_event_hash(
            control_id=control_id,
            decision=decision,
            reviewer=reviewer,
            note=note,
            created_at_utc=now,
            previous_event_hash=previous_event_hash,
        )
        conn.execute(
            """
            INSERT INTO approval_history (
                control_id, decision, reviewer, note, created_at_utc,
                payload_version, previous_event_hash, event_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                control_id,
                decision,
                reviewer,
                note,
                now,
                AUDIT_CHAIN_VERSION,
                previous_event_hash,
                event_hash,
            ),
        )
        row = conn.execute(
            "SELECT * FROM control_queue WHERE control_id = ?", (control_id,)
        ).fetchone()
    return _row_to_dict(row)


def list_history(output_root: Path, limit: int = 100) -> list[dict[str, Any]]:
    initialize_store(output_root)
    with _connect(output_root) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM approval_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def verify_audit_integrity(output_root: Path) -> dict[str, Any]:
    """Verify the approval hash chain and replay it against current queue state."""

    initialize_store(output_root)
    with _connect(output_root) as conn:
        history = conn.execute("SELECT * FROM approval_history ORDER BY id").fetchall()
        queue_rows = {
            row["control_id"]: row
            for row in conn.execute(
                "SELECT control_id, approval_state, owner FROM control_queue"
            ).fetchall()
        }

    previous_hash = GENESIS_HASH
    first_invalid_event_id: int | None = None
    replay_state: dict[str, tuple[str, str]] = {}
    for row in history:
        expected_hash = _audit_event_hash(
            control_id=row["control_id"],
            decision=row["decision"],
            reviewer=row["reviewer"],
            note=row["note"],
            created_at_utc=row["created_at_utc"],
            previous_event_hash=previous_hash,
            payload_version=row["payload_version"],
        )
        if (
            row["payload_version"] != AUDIT_CHAIN_VERSION
            or row["previous_event_hash"] != previous_hash
            or row["event_hash"] != expected_hash
        ) and first_invalid_event_id is None:
            first_invalid_event_id = int(row["id"])
        previous_hash = row["event_hash"]
        expected_state = DECISION_TO_STATE.get(row["decision"])
        if expected_state is not None:
            replay_state[row["control_id"]] = (expected_state, row["reviewer"])

    replay_mismatches = []
    for control_id, (expected_state, expected_owner) in replay_state.items():
        actual = queue_rows.get(control_id)
        if actual is None:
            replay_mismatches.append(
                {"control_id": control_id, "reason": "queue_row_missing"}
            )
            continue
        if actual["approval_state"] != expected_state or actual["owner"] != expected_owner:
            replay_mismatches.append(
                {
                    "control_id": control_id,
                    "reason": "queue_state_mismatch",
                    "expected_state": expected_state,
                    "actual_state": actual["approval_state"],
                }
            )

    chain_valid = first_invalid_event_id is None
    replay_valid = not replay_mismatches
    return {
        "status": "pass" if chain_valid and replay_valid else "fail",
        "contract_version": AUDIT_CHAIN_VERSION,
        "event_count": len(history),
        "chain_valid": chain_valid,
        "replay_valid": replay_valid,
        "first_invalid_event_id": first_invalid_event_id,
        "replay_mismatch_count": len(replay_mismatches),
        "replay_mismatches": replay_mismatches[:20],
        "head_event_hash": previous_hash if history else GENESIS_HASH,
        "scope": "local SQLite tamper evidence; not a signed external attestation",
    }
