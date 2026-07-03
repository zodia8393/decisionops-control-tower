from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.app import create_app


def test_fastapi_review_workflow_persists_approval(tmp_path):
    client = TestClient(create_app(output_root=tmp_path))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["demo_mode_ready"] is True
    assert health.json()["auth_required"] is False

    queue = client.get("/api/review-queue").json()
    assert queue["count"] > 0
    control_id = queue["items"][0]["control_id"]

    decision = client.post(
        f"/api/review-queue/{control_id}/decision",
        json={"decision": "approve", "reviewer": "pytest_reviewer", "note": "smoke"},
    )
    assert decision.status_code == 200
    assert decision.json()["item"]["approval_state"] == "approved"

    history = client.get("/api/review-history").json()
    assert history["count"] == 1
    assert history["items"][0]["control_id"] == control_id
    assert history["items"][0]["decision"] == "approve"

    reopened = TestClient(create_app(output_root=tmp_path))
    approved = reopened.get("/api/review-queue", params={"approval_state": "approved"}).json()
    assert any(item["control_id"] == control_id for item in approved["items"])


def test_fastapi_validation_and_dashboard(tmp_path):
    client = TestClient(create_app(output_root=tmp_path))

    queue = client.get("/api/review-queue").json()
    control_id = queue["items"][0]["control_id"]

    invalid = client.post(
        f"/api/review-queue/{control_id}/decision",
        json={"decision": "ship_it", "reviewer": "pytest_reviewer"},
    )
    assert invalid.status_code == 422

    missing = client.post(
        "/api/review-queue/CTRL-9999/decision",
        json={"decision": "reject", "reviewer": "pytest_reviewer"},
    )
    assert missing.status_code == 404

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "DecisionOps Control Tower" in dashboard.text
    assert "Reviewer Queue" in dashboard.text
    assert "Impact Cards" in dashboard.text

    impact = client.get("/api/impact-cards")
    assert impact.status_code == 200
    assert impact.json()["count"] > 0
    assert impact.json()["items"][0]["guardrail_state"] in {"ready_for_review", "validation_not_ready"}

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/api/review-queue/{control_id}/decision" in openapi.json()["paths"]
    assert "/api/ops-metrics" in openapi.json()["paths"]
    assert "/api/impact-cards" in openapi.json()["paths"]


def test_fastapi_write_auth_when_token_configured(tmp_path):
    client = TestClient(create_app(output_root=tmp_path, auth_token="legacy-pass"))

    health = client.get("/health", headers={"X-Request-ID": "pytest-request"})
    assert health.status_code == 200
    assert health.headers["x-request-id"] == "pytest-request"
    assert health.json()["auth_required"] is True
    assert health.json()["configured_roles"] == ["reviewer"]

    queue = client.get("/api/review-queue").json()
    control_id = queue["items"][0]["control_id"]

    missing_token = client.post(
        f"/api/review-queue/{control_id}/decision",
        json={"decision": "reject", "reviewer": "pytest_reviewer"},
    )
    assert missing_token.status_code == 401

    wrong_token = client.post(
        f"/api/review-queue/{control_id}/decision",
        headers={"X-Control-Tower-Token": "wrong"},
        json={"decision": "reject", "reviewer": "pytest_reviewer"},
    )
    assert wrong_token.status_code == 401

    accepted = client.post(
        f"/api/review-queue/{control_id}/decision",
        headers={"X-Control-Tower-Token": "legacy-pass"},
        json={"decision": "reject", "reviewer": "pytest_reviewer"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["role"] == "reviewer"
    assert accepted.json()["item"]["approval_state"] == "rejected"


def test_role_tokens_allow_reviewer_or_admin_only_for_writes(tmp_path):
    client = TestClient(
        create_app(
            output_root=tmp_path,
            auth_roles={
                "view-pass": "viewer",
                "review-pass": "reviewer",
                "admin-pass": "admin",
            },
        )
    )

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["configured_roles"] == ["admin", "reviewer", "viewer"]

    queue = client.get("/api/review-queue").json()
    control_id = queue["items"][0]["control_id"]

    viewer = client.post(
        f"/api/review-queue/{control_id}/decision",
        headers={"X-Control-Tower-Token": "view-pass"},
        json={"decision": "approve", "reviewer": "pytest_viewer"},
    )
    assert viewer.status_code == 403

    reviewer = client.post(
        f"/api/review-queue/{control_id}/decision",
        headers={"X-Control-Tower-Token": "review-pass"},
        json={"decision": "approve", "reviewer": "pytest_reviewer"},
    )
    assert reviewer.status_code == 200
    assert reviewer.json()["role"] == "reviewer"

    queue = client.get("/api/review-queue", params={"approval_state": "pending_reviewer"}).json()
    next_control_id = queue["items"][0]["control_id"]
    admin = client.post(
        f"/api/review-queue/{next_control_id}/decision",
        headers={"X-Control-Tower-Token": "admin-pass"},
        json={"decision": "needs_more_evidence", "reviewer": "pytest_admin"},
    )
    assert admin.status_code == 200
    assert admin.json()["role"] == "admin"


def test_role_config_rejects_invalid_roles(tmp_path):
    with pytest.raises(ValueError, match="unsupported control tower role"):
        create_app(output_root=tmp_path, auth_roles={"bad-pass": "operator"})

    with pytest.raises(ValueError, match="empty control tower credential"):
        create_app(output_root=tmp_path, auth_roles={"": "viewer"})


def test_ops_metrics_report_artifact_health(tmp_path):
    client = TestClient(create_app(output_root=tmp_path))

    ops = client.get("/api/ops-metrics")
    assert ops.status_code == 200
    payload = ops.json()
    assert payload["status"] == "ok"
    assert payload["queue"]["total"] > 0
    assert payload["artifacts"]["control_state"]["exists"] is True
    assert payload["artifacts"]["impact_cards"]["exists"] is True
    assert payload["artifacts"]["sqlite_database"]["exists"] is True
