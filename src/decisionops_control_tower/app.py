"""FastAPI product surface for DecisionOps Control Tower."""

from __future__ import annotations

import html
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Literal
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from decisionops_control_tower.pipeline import (
    DEFAULT_BIKE_ROOT,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_WORKBENCH_ROOT,
    run,
)
from decisionops_control_tower.store import (
    database_path,
    initialize_store,
    list_history,
    list_queue,
    queue_summary,
    record_decision,
)


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject", "needs_more_evidence"]
    reviewer: str = Field(default="ops_reviewer", min_length=1, max_length=80)
    note: str = Field(default="", max_length=1000)


LOGGER = logging.getLogger("decisionops_control_tower")
VALID_ROLES = {"viewer", "reviewer", "admin"}
WRITE_ROLES = {"reviewer", "admin"}


def _configure_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")
    LOGGER.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser()


def _env_token() -> str:
    return os.environ.get("CONTROL_TOWER_API_TOKEN", "").strip()


def _parse_role_tokens(raw: str) -> dict[str, str]:
    """Parse role credentials as role:credential or role=credential chunks."""

    roles: dict[str, str] = {}
    if not raw.strip():
        return roles
    for chunk in raw.split(","):
        item = chunk.strip()
        if not item:
            continue
        separator = ":" if ":" in item else "=" if "=" in item else ""
        if not separator:
            raise ValueError("CONTROL_TOWER_ROLE_TOKENS must use role:credential chunks")
        role, credential = [part.strip() for part in item.split(separator, 1)]
        role = role.lower()
        if role not in VALID_ROLES:
            raise ValueError(f"unsupported control tower role: {role}")
        if not credential:
            raise ValueError("empty control tower credential is not allowed")
        roles[credential] = role
    return roles


def _configured_auth_roles(
    auth_token: str | None,
    auth_roles: dict[str, str] | None,
) -> dict[str, str]:
    if auth_roles is not None:
        roles: dict[str, str] = {}
        for credential, role in auth_roles.items():
            credential = credential.strip()
            role = role.strip().lower()
            if not credential:
                raise ValueError("empty control tower credential is not allowed")
            if role not in VALID_ROLES:
                raise ValueError(f"unsupported control tower role: {role}")
            roles[credential] = role
        return roles
    roles = _parse_role_tokens(os.environ.get("CONTROL_TOWER_ROLE_TOKENS", ""))
    legacy_token = _env_token() if auth_token is None else auth_token.strip()
    if legacy_token:
        roles[legacy_token] = "reviewer"
    return roles


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _needs_pipeline_refresh(output_root: Path) -> bool:
    required = [
        output_root / "reports" / "control_state.json",
        output_root / "reports" / "control_review_queue.csv",
        output_root / "reports" / "impact_cards.json",
        output_root / "reports" / "api_contract.json",
        output_root / "dashboard" / "index.html",
    ]
    return not all(path.is_file() for path in required)


def _artifact_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "size_bytes": 0, "mtime_utc": None}
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime)),
    }


def _render_dashboard(
    state: dict[str, Any],
    queue: list[dict[str, Any]],
    history: list[dict[str, Any]],
    summary: dict[str, Any],
    ops: dict[str, Any],
    impact_cards: list[dict[str, Any]],
) -> str:
    status = "DEMO READY" if state.get("demo_mode_ready") else "BLOCKED"
    blockers = "".join(
        f"<li>{html.escape(str(blocker))}</li>" for blocker in state.get("blockers", [])
    )
    if not blockers:
        blockers = "<li>none</li>"
    rows = []
    for item in queue[:50]:
        control_id = html.escape(str(item["control_id"]))
        approval_state = html.escape(str(item["approval_state"]))
        actions = ""
        if item["approval_state"] == "pending_reviewer":
            actions = (
                f'<button type="button" data-control-id="{control_id}" data-decision="approve">'
                "Approve</button>"
                f'<button type="button" data-control-id="{control_id}" data-decision="reject">'
                "Reject</button>"
                f'<button type="button" data-control-id="{control_id}" '
                'data-decision="needs_more_evidence">Need Evidence</button>'
            )
        rows.append(
            "<tr>"
            f"<td>{control_id}</td>"
            f"<td>{html.escape(str(item['priority']))}</td>"
            f"<td>{html.escape(str(item['task_id']))}</td>"
            f"<td>{approval_state}</td>"
            f"<td>{html.escape(str(item['guardrail_hits']))}</td>"
            f"<td>{actions}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan=\"6\">no review items</td></tr>")
    history_rows = []
    for item in history[:12]:
        history_rows.append(
            "<tr>"
            f"<td>{html.escape(str(item['created_at_utc']))}</td>"
            f"<td>{html.escape(str(item['control_id']))}</td>"
            f"<td>{html.escape(str(item['decision']))}</td>"
            f"<td>{html.escape(str(item['reviewer']))}</td>"
            "</tr>"
        )
    if not history_rows:
        history_rows.append("<tr><td colspan=\"4\">no approval history</td></tr>")
    metrics = state.get("metrics", {})
    by_state = summary.get("by_state", {})
    auth_label = "ON" if ops.get("auth_required") else "OFF"
    roles_label = ", ".join(ops.get("configured_roles", [])) or "demo"
    artifact_rows = []
    for name, item in ops.get("artifacts", {}).items():
        artifact_rows.append(
            "<tr>"
            f"<td>{html.escape(str(name))}</td>"
            f"<td>{html.escape(str(item.get('exists')))}</td>"
            f"<td>{html.escape(str(item.get('mtime_utc')))}</td>"
            "</tr>"
        )
    if not artifact_rows:
        artifact_rows.append("<tr><td colspan=\"3\">no artifact status</td></tr>")
    impact_rows = []
    for item in impact_cards[:20]:
        impact_rows.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('impact_card_id', '')))}</td>"
            f"<td>{html.escape(str(item.get('priority', '')))}</td>"
            f"<td>{html.escape(str(item.get('station_name', '')))}</td>"
            f"<td>{html.escape(str(item.get('recommended_action', '')))}</td>"
            f"<td>{html.escape(str(item.get('candidate_units_addressed', '')))}</td>"
            f"<td>{html.escape(str(item.get('guardrail_state', '')))}</td>"
            "</tr>"
        )
    if not impact_rows:
        impact_rows.append("<tr><td colspan=\"6\">no impact cards</td></tr>")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DecisionOps Control Tower</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #14213d;
      --muted: #5f6c7b;
      --line: #d9dee7;
      --paper: #ffffff;
      --surface: #f7f9fc;
      --ok: #0b6e4f;
      --warn: #9a3412;
      --accent: #1f6feb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--surface);
    }}
    header {{
      background: var(--paper);
      border-bottom: 1px solid var(--line);
      padding: 24px 32px;
    }}
    main {{ padding: 24px 32px 40px; }}
    h1, h2 {{ margin: 0; letter-spacing: 0; }}
    h1 {{ font-size: 28px; }}
    h2 {{ font-size: 18px; margin-top: 28px; }}
    .status {{ margin-top: 8px; color: var(--muted); }}
    .status strong {{ color: {"var(--ok)" if status == "DEMO READY" else "var(--warn)"}; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 20px;
    }}
    .metric {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 86px;
    }}
    .metric span {{ color: var(--muted); font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 24px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      background: var(--paper);
      border: 1px solid var(--line);
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{ background: #eef3f9; }}
    button {{
      border: 1px solid var(--accent);
      background: #ffffff;
      color: var(--accent);
      border-radius: 6px;
      padding: 6px 8px;
      margin: 0 4px 4px 0;
      cursor: pointer;
    }}
    ul {{ background: var(--paper); border: 1px solid var(--line); border-radius: 8px; padding: 14px 28px; }}
    @media (max-width: 760px) {{
      header, main {{ padding-left: 16px; padding-right: 16px; }}
      table {{ display: block; overflow-x: auto; white-space: nowrap; }}
    }}
  </style>
</head>
<body data-auth-required="{str(bool(ops.get("auth_required"))).lower()}">
  <header>
    <h1>DecisionOps Control Tower</h1>
    <div class="status"><strong>{status}</strong> · public deploy: {html.escape(str(state.get("public_deploy_decision", "UNKNOWN")))}</div>
  </header>
  <main>
    <section class="metrics">
      <div class="metric"><span>Total queue</span><strong>{summary.get("total", 0)}</strong></div>
      <div class="metric"><span>Pending</span><strong>{by_state.get("pending_reviewer", 0)}</strong></div>
      <div class="metric"><span>Impact cards</span><strong>{metrics.get("impact_card_rows", 0)}</strong></div>
      <div class="metric"><span>Candidate units</span><strong>{metrics.get("impact_candidate_units_addressed", 0)}</strong></div>
      <div class="metric"><span>Guarded success</span><strong>{float(metrics.get("guarded_success_rate", 0.0)):.3f}</strong></div>
      <div class="metric"><span>Holdout success</span><strong>{float(metrics.get("holdout_success_rate", 0.0)):.3f}</strong></div>
      <div class="metric"><span>Incident rows</span><strong>{metrics.get("incident_rows", 0)}</strong></div>
      <div class="metric"><span>Write auth</span><strong>{auth_label}</strong></div>
      <div class="metric"><span>Roles</span><strong>{html.escape(roles_label)}</strong></div>
    </section>
    <h2>Blockers</h2>
    <ul>{blockers}</ul>
    <h2>Operations</h2>
    <table>
      <thead><tr><th>Artifact</th><th>Exists</th><th>Updated UTC</th></tr></thead>
      <tbody>{''.join(artifact_rows)}</tbody>
    </table>
    <h2>Impact Cards</h2>
    <table>
      <thead><tr><th>Card</th><th>Priority</th><th>Station</th><th>Action</th><th>Units</th><th>Guardrail</th></tr></thead>
      <tbody>{''.join(impact_rows)}</tbody>
    </table>
    <h2>Reviewer Queue</h2>
    <table>
      <thead><tr><th>Control ID</th><th>Priority</th><th>Task</th><th>State</th><th>Guardrails</th><th>Decision</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <h2>Approval History</h2>
    <table>
      <thead><tr><th>Time</th><th>Control ID</th><th>Decision</th><th>Reviewer</th></tr></thead>
      <tbody>{''.join(history_rows)}</tbody>
    </table>
  </main>
  <script>
    document.addEventListener("click", async (event) => {{
      const button = event.target.closest("button[data-decision]");
      if (!button) return;
      button.disabled = true;
      const controlId = button.dataset.controlId;
      const decision = button.dataset.decision;
      const headers = {{"Content-Type": "application/json"}};
      if (document.body.dataset.authRequired === "true") {{
        let approvalCredential = sessionStorage.getItem("controlTowerCredential");
        if (!approvalCredential) {{
          approvalCredential = window.prompt("Control Tower approval credential");
          if (!approvalCredential) {{
            button.disabled = false;
            return;
          }}
          sessionStorage.setItem("controlTowerCredential", approvalCredential);
        }}
        headers["X-Control-Tower-Token"] = approvalCredential;
      }}
      const response = await fetch(`/api/review-queue/${{controlId}}/decision`, {{
        method: "POST",
        headers,
        body: JSON.stringify({{decision, reviewer: "dashboard_reviewer"}})
      }});
      if (!response.ok) {{
        button.disabled = false;
        if (response.status === 401) {{
          sessionStorage.removeItem("controlTowerCredential");
        }}
        alert("Decision failed");
        return;
      }}
      window.location.reload();
    }});
  </script>
</body>
</html>
"""


def create_app(
    output_root: Path | str | None = None,
    bike_root: Path | str | None = None,
    workbench_root: Path | str | None = None,
    refresh_artifacts: bool = True,
    auth_token: str | None = None,
    auth_roles: dict[str, str] | None = None,
) -> FastAPI:
    _configure_logging()
    root = Path(output_root) if output_root is not None else _env_path("OUTPUT_ROOT", DEFAULT_OUTPUT_ROOT)
    bike = Path(bike_root) if bike_root is not None else _env_path("BIKE_ROOT", DEFAULT_BIKE_ROOT)
    workbench = (
        Path(workbench_root)
        if workbench_root is not None
        else _env_path("WORKBENCH_ROOT", DEFAULT_WORKBENCH_ROOT)
    )
    app = FastAPI(
        title="DecisionOps Control Tower",
        version="0.1.0",
        description="FastAPI/SQLite reviewer workflow for the DecisionOps AI suite.",
    )
    app.state.output_root = root
    app.state.bike_root = bike
    app.state.workbench_root = workbench
    app.state.refresh_artifacts = refresh_artifacts
    app.state.auth_roles = _configured_auth_roles(auth_token, auth_roles)
    app.state.started_at = time.time()
    app.state.ready = False

    @app.middleware("http")
    async def structured_request_log(request: Request, call_next):
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            LOGGER.exception(
                json.dumps(
                    {
                        "event": "request_error",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": duration_ms,
                    },
                    ensure_ascii=False,
                )
            )
            raise
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        LOGGER.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
                ensure_ascii=False,
            )
        )
        return response

    def ensure_ready() -> None:
        if app.state.ready:
            return
        if app.state.refresh_artifacts or _needs_pipeline_refresh(app.state.output_root):
            run(app.state.output_root, app.state.bike_root, app.state.workbench_root)
        initialize_store(app.state.output_root)
        app.state.ready = True

    def resolve_role(
        x_control_tower_token: str | None = Header(default=None, alias="X-Control-Tower-Token"),
    ) -> str:
        roles = app.state.auth_roles
        if not roles:
            return "demo"
        role = roles.get(x_control_tower_token or "")
        if role is None:
            raise HTTPException(status_code=401, detail="invalid or missing control tower credential")
        return role

    def require_write_role(role: str = Depends(resolve_role)) -> str:
        if role == "demo":
            return role
        if role not in WRITE_ROLES:
            raise HTTPException(status_code=403, detail="reviewer or admin role required")
        return role

    def ops_metrics() -> dict[str, Any]:
        state = _read_json(app.state.output_root / "reports" / "control_state.json", {})
        artifacts = {
            "control_state": _artifact_status(app.state.output_root / "reports" / "control_state.json"),
            "review_queue": _artifact_status(
                app.state.output_root / "reports" / "control_review_queue.csv"
            ),
            "api_contract": _artifact_status(app.state.output_root / "reports" / "api_contract.json"),
            "impact_cards": _artifact_status(app.state.output_root / "reports" / "impact_cards.json"),
            "dashboard": _artifact_status(app.state.output_root / "dashboard" / "index.html"),
            "sqlite_database": _artifact_status(database_path(app.state.output_root)),
        }
        return {
            "status": "ok",
            "uptime_seconds": round(time.time() - app.state.started_at, 3),
            "auth_required": bool(app.state.auth_roles),
            "configured_roles": sorted(set(app.state.auth_roles.values())),
            "refresh_artifacts": bool(app.state.refresh_artifacts),
            "public_deploy_decision": state.get("public_deploy_decision", "UNKNOWN"),
            "demo_mode_ready": bool(state.get("demo_mode_ready")),
            "queue": queue_summary(app.state.output_root),
            "artifacts": artifacts,
        }

    @app.get("/")
    def read_root() -> dict[str, str]:
        ensure_ready()
        return {
            "service": "decisionops-control-tower",
            "health": "/health",
            "dashboard": "/dashboard",
            "impact_cards": "/api/impact-cards",
            "ops": "/api/ops-metrics",
            "openapi": "/docs",
        }

    @app.get("/health")
    def health() -> dict[str, Any]:
        ensure_ready()
        state = _read_json(app.state.output_root / "reports" / "control_state.json", {})
        return {
            "status": "ok",
            "project": "decisionops-control-tower",
            "demo_mode_ready": bool(state.get("demo_mode_ready")),
            "public_deploy_decision": state.get("public_deploy_decision", "UNKNOWN"),
            "impact_card_rows": state.get("metrics", {}).get("impact_card_rows", 0),
            "queue": queue_summary(app.state.output_root),
            "auth_required": bool(app.state.auth_roles),
            "configured_roles": sorted(set(app.state.auth_roles.values())),
            "database": str(database_path(app.state.output_root)),
            "output_root": str(app.state.output_root),
        }

    @app.get("/api/control-state")
    def control_state() -> dict[str, Any]:
        ensure_ready()
        state = _read_json(app.state.output_root / "reports" / "control_state.json", {})
        state["queue_summary"] = queue_summary(app.state.output_root)
        return state

    @app.get("/api/review-queue")
    def review_queue(approval_state: str | None = None) -> dict[str, Any]:
        ensure_ready()
        items = list_queue(app.state.output_root, approval_state=approval_state)
        return {"count": len(items), "items": items}

    @app.get("/api/impact-cards")
    def impact_cards(guardrail_state: str | None = None) -> dict[str, Any]:
        ensure_ready()
        items = _read_json(app.state.output_root / "reports" / "impact_cards.json", [])
        if not isinstance(items, list):
            items = []
        if guardrail_state:
            items = [item for item in items if item.get("guardrail_state") == guardrail_state]
        return {"count": len(items), "items": items}

    @app.post("/api/review-queue/{control_id}/decision")
    def review_decision(
        control_id: str,
        payload: DecisionRequest,
        role: str = Depends(require_write_role),
    ) -> dict[str, Any]:
        ensure_ready()
        try:
            item = record_decision(
                app.state.output_root,
                control_id,
                payload.decision,
                reviewer=payload.reviewer,
                note=payload.note,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="control_id not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "recorded", "role": role, "item": item}

    @app.get("/api/review-history")
    def review_history(limit: int = 100) -> dict[str, Any]:
        ensure_ready()
        safe_limit = max(1, min(limit, 500))
        items = list_history(app.state.output_root, limit=safe_limit)
        return {"count": len(items), "items": items}

    @app.get("/api/ops-metrics")
    def read_ops_metrics() -> dict[str, Any]:
        ensure_ready()
        return ops_metrics()

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        ensure_ready()
        state = _read_json(app.state.output_root / "reports" / "control_state.json", {})
        queue = list_queue(app.state.output_root)
        history = list_history(app.state.output_root, limit=25)
        summary = queue_summary(app.state.output_root)
        cards = _read_json(app.state.output_root / "reports" / "impact_cards.json", [])
        if not isinstance(cards, list):
            cards = []
        return HTMLResponse(_render_dashboard(state, queue, history, summary, ops_metrics(), cards))

    return app


app = create_app()
