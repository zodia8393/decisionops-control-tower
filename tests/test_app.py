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
    assert health.json()["impact_policy_audit_rows"] > 0
    assert health.json()["reviewer_action_plan_rows"] > 0

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
    assert "검토 대기열" in dashboard.text
    assert "따릉이 후보 조치" in dashboard.text
    assert "영향 정책 비교" in dashboard.text
    assert "검토 실행 계획" in dashboard.text
    assert "오늘의 결론" in dashboard.text
    assert "지금 해야 할 일" in dashboard.text
    assert "검토 대기열 보기" in dashboard.text
    assert "지도에서 보기" in dashboard.text
    assert "정책 비교 보기" in dashboard.text
    assert "검토 계획 보기" in dashboard.text
    assert "지도에서 위치 확인" in dashboard.text
    assert "서울 따릉이 후보 조치 위치 지도" in dashboard.text
    assert "서울 따릉이 후보 조치 실제 지도 타일" in dashboard.text
    assert "openstreetmap.org/export/embed.html" in dashboard.text
    assert 'referrerpolicy="no-referrer"' in dashboard.text
    assert "후보 번호 지도" in dashboard.text
    assert "외부 지도 타일이 차단되면" in dashboard.text
    assert "지도 표시 가능 후보" in dashboard.text
    assert 'class="map-point' in dashboard.text
    assert 'href="#ddareungi-action-1"' in dashboard.text
    assert 'id="ddareungi-action-1"' in dashboard.text
    assert "표에서 세부 보기" in dashboard.text
    assert "판단 근거 보기" in dashboard.text
    assert "권고 이유" in dashboard.text
    assert "좌표 상태" in dashboard.text
    assert "서울 따릉이 대여소 현황과 재배치 우선순위 산출물" in dashboard.text
    assert "검토 기준 보기" in dashboard.text
    assert "미검증 claim 단위" in dashboard.text
    assert "권장 결정" in dashboard.text
    assert "원천 근거 요약" in dashboard.text
    assert "bike-share benchmark 대여소" in dashboard.text
    assert "다음 결정 기준" in dashboard.text
    assert "로컬 감사 기록" in dashboard.text
    assert "운영 판단 상태 JSON" in dashboard.text
    assert "회수 여부 검토" in dashboard.text
    assert "무엇을 판단하나" in dashboard.text
    assert "무엇을 검토하나" in dashboard.text
    assert "Control ID" not in dashboard.text
    assert "SEOUL-IMPACT" not in dashboard.text
    assert "task_" not in dashboard.text
    assert ":focus-visible" in dashboard.text

    impact = client.get("/api/impact-cards")
    assert impact.status_code == 200
    assert impact.json()["count"] > 0
    first_impact_item = impact.json()["items"][0]
    assert first_impact_item["guardrail_state"] in {"ready_for_review", "validation_not_ready"}
    assert first_impact_item["station_lat"]
    assert first_impact_item["station_lon"]
    assert first_impact_item["coordinate_status"] == "valid"

    policy = client.get("/api/impact-policy-audit")
    assert policy.status_code == 200
    assert policy.json()["count"] >= 8
    unsafe = [item for item in policy.json()["items"] if item["policy"] == "unsafe_auto_publish"]
    assert unsafe and unsafe[0]["audit_result"] == "fail"

    action_plan = client.get("/api/reviewer-action-plan")
    assert action_plan.status_code == 200
    assert action_plan.json()["count"] > 0
    assert action_plan.json()["items"][0]["reviewer_decision"] in {
        "approve_local_review_only",
        "approve_for_private_demo",
        "needs_more_evidence",
    }

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/api/review-queue/{control_id}/decision" in openapi.json()["paths"]
    assert "/api/ops-metrics" in openapi.json()["paths"]
    assert "/api/impact-cards" in openapi.json()["paths"]
    assert "/api/impact-policy-audit" in openapi.json()["paths"]
    assert "/api/reviewer-action-plan" in openapi.json()["paths"]


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
    assert payload["artifacts"]["impact_policy_audit"]["exists"] is True
    assert payload["artifacts"]["reviewer_action_plan"]["exists"] is True
    assert payload["artifacts"]["sqlite_database"]["exists"] is True
