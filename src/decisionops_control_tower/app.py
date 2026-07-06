"""FastAPI product surface for DecisionOps Control Tower."""

from __future__ import annotations

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

from decisionops_control_tower.dashboard import render_dashboard
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
        output_root / "reports" / "impact_policy_audit.json",
        output_root / "reports" / "reviewer_action_plan.json",
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
            "impact_policy_audit": _artifact_status(
                app.state.output_root / "reports" / "impact_policy_audit.json"
            ),
            "reviewer_action_plan": _artifact_status(
                app.state.output_root / "reports" / "reviewer_action_plan.json"
            ),
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
            "impact_policy_audit": "/api/impact-policy-audit",
            "reviewer_action_plan": "/api/reviewer-action-plan",
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
            "impact_policy_audit_rows": state.get("metrics", {}).get("impact_policy_audit_rows", 0),
            "reviewer_action_plan_rows": state.get("metrics", {}).get("reviewer_action_plan_rows", 0),
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

    @app.get("/api/impact-policy-audit")
    def impact_policy_audit(policy: str | None = None) -> dict[str, Any]:
        ensure_ready()
        items = _read_json(app.state.output_root / "reports" / "impact_policy_audit.json", [])
        if not isinstance(items, list):
            items = []
        if policy:
            items = [item for item in items if item.get("policy") == policy]
        return {"count": len(items), "items": items}

    @app.get("/api/reviewer-action-plan")
    def reviewer_action_plan(decision: str | None = None) -> dict[str, Any]:
        ensure_ready()
        items = _read_json(app.state.output_root / "reports" / "reviewer_action_plan.json", [])
        if not isinstance(items, list):
            items = []
        if decision:
            items = [item for item in items if item.get("reviewer_decision") == decision]
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
        policy_audit = _read_json(app.state.output_root / "reports" / "impact_policy_audit.json", [])
        if not isinstance(policy_audit, list):
            policy_audit = []
        action_plan = _read_json(app.state.output_root / "reports" / "reviewer_action_plan.json", [])
        if not isinstance(action_plan, list):
            action_plan = []
        return HTMLResponse(
            render_dashboard(
                state=state,
                queue=queue,
                history=history,
                summary=summary,
                ops=ops_metrics(),
                impact_cards=cards,
                impact_policy_audit=policy_audit,
                reviewer_action_plan=action_plan,
            )
        )

    return app


app = create_app()
