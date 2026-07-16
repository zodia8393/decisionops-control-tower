from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.app import create_app


def create_test_app(tmp_path: Path, **kwargs):
    """Build deterministic demo inputs instead of reading live /DATA artifacts."""
    return create_app(
        output_root=tmp_path,
        bike_root=tmp_path / "missing-bike",
        workbench_root=tmp_path / "missing-workbench",
        **kwargs,
    )


def test_fastapi_review_workflow_persists_approval(tmp_path):
    client = TestClient(create_test_app(tmp_path))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["demo_mode_ready"] is True
    assert health.json()["auth_required"] is False
    assert health.json()["impact_policy_audit_rows"] > 0
    assert health.json()["reviewer_policy_robustness_rows"] == 36
    assert health.json()["reviewer_action_plan_rows"] > 0
    assert health.json()["reviewer_evidence_bundle_rows"] > 0

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

    integrity = client.get("/api/approval-audit-integrity")
    assert integrity.status_code == 200
    assert integrity.json()["status"] == "pass"
    assert integrity.json()["event_count"] == 1

    reopened = TestClient(create_test_app(tmp_path))
    approved = reopened.get("/api/review-queue", params={"approval_state": "approved"}).json()
    assert any(item["control_id"] == control_id for item in approved["items"])


def test_fastapi_validation_and_dashboard(tmp_path):
    client = TestClient(create_test_app(tmp_path))

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
    assert 'rel="icon"' in dashboard.text
    assert "검토 대기열" in dashboard.text
    assert "따릉이 후보 조치" in dashboard.text
    assert "영향 정책 비교" in dashboard.text
    assert "Reviewer policy robustness" in dashboard.text
    assert "검토 실행 계획" in dashboard.text
    assert "심의 근거 패킷" in dashboard.text
    assert "근거 패킷 보기" in dashboard.text
    assert "SHA-256" in dashboard.text
    assert "승인 감사 무결성" in dashboard.text
    assert "State replay" in dashboard.text
    assert "오늘의 결론" in dashboard.text
    assert "지금 해야 할 일" in dashboard.text
    assert "검토 대기열 보기" in dashboard.text
    assert "지도에서 보기" in dashboard.text
    assert "정책 비교 보기" in dashboard.text
    assert "검토 계획 보기" in dashboard.text
    assert "AI Reviewer Brief" in dashboard.text
    assert "agent mode:" in dashboard.text
    assert "deterministic gate:" in dashboard.text
    assert "Evidence lock" in dashboard.text
    assert "read-only reviewer assistant" in dashboard.text
    assert "지도에서 위치 확인" in dashboard.text
    assert "서울 따릉이 후보 조치 위치 지도" in dashboard.text
    assert "tile.openstreetmap.org" in dashboard.text
    assert "지도 타일 © OpenStreetMap contributors" in dashboard.text
    assert "후보 번호 오버레이 지도" in dashboard.text
    assert "후보 번호는 실제 지도 타일 위에 표시됩니다" in dashboard.text
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

    evidence = client.get("/api/reviewer-evidence-bundles")
    assert evidence.status_code == 200
    assert evidence.json()["count"] > 0
    first_bundle = evidence.json()["items"][0]
    assert len(first_bundle["evidence_fingerprint_sha256"]) == 64
    assert first_bundle["freshness_status"] in {
        "fresh",
        "stale",
        "missing_timestamp",
        "future_timestamp",
    }
    filtered = client.get(
        "/api/reviewer-evidence-bundles",
        params={"freshness_status": first_bundle["freshness_status"]},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] > 0

    robustness = client.get(
        "/api/reviewer-policy-robustness",
        params={
            "scenario": "confidence_stress",
            "policy": "confidence_weighted_guarded_capacity",
        },
    )
    assert robustness.status_code == 200
    assert robustness.json()["count"] == 3
    assert robustness.json()["summary"]["guarded_public_claim_violations"] == 0

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/api/review-queue/{control_id}/decision" in openapi.json()["paths"]
    assert "/api/ops-metrics" in openapi.json()["paths"]
    assert "/api/impact-cards" in openapi.json()["paths"]
    assert "/api/impact-policy-audit" in openapi.json()["paths"]
    assert "/api/approval-audit-integrity" in openapi.json()["paths"]
    assert "/api/reviewer-action-plan" in openapi.json()["paths"]
    assert "/api/reviewer-policy-robustness" in openapi.json()["paths"]
    assert "/api/reviewer-evidence-bundles" in openapi.json()["paths"]
    assert "/api/agent/reviewer-brief" in openapi.json()["paths"]
    assert "/api/agent/candidate/{candidate_id}/review-notes" in openapi.json()["paths"]


def test_agent_reviewer_brief_is_fallback_and_evidence_locked(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTROL_TOWER_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(create_test_app(tmp_path))

    health = client.get("/health")
    assert health.status_code == 200
    health_payload = health.json()

    brief = client.get("/api/agent/reviewer-brief")
    assert brief.status_code == 200
    payload = brief.json()
    assert payload["mode"] == "fallback"
    assert payload["llm"]["status"] == "not_configured"
    assert payload["source_status"]["public_deploy_decision"] == health_payload["public_deploy_decision"]
    assert payload["source_status"]["impact_card_rows"] == health_payload["impact_card_rows"]
    assert payload["source_status"]["queue_total"] == health_payload["queue"]["total"]
    assert payload["claim_safety"]["public_deploy_decision"] == health_payload["public_deploy_decision"]
    assert payload["claim_safety"]["allowed_public_claim"] is False
    assert "source of truth" in payload["claim_safety"]["rule"]
    assert payload["evidence_refs"]

    impact = client.get("/api/impact-cards").json()
    first = impact["items"][0]
    notes = client.get(f"/api/agent/candidate/{first['impact_card_id']}/review-notes")
    assert notes.status_code == 200
    note_payload = notes.json()
    assert note_payload["mode"] == "fallback"
    assert note_payload["matched_aliases"]["impact_card_id"] == first["impact_card_id"]
    assert note_payload["claim_safety"]["public_deploy_decision"] == health_payload["public_deploy_decision"]

    missing = client.get("/api/agent/candidate/NOT-A-CANDIDATE/review-notes")
    assert missing.status_code == 404


def test_fastapi_write_auth_when_token_configured(tmp_path):
    client = TestClient(create_test_app(tmp_path, auth_token="test-token"))

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
        headers={"X-Control-Tower-Token": "test-password"},
        json={"decision": "reject", "reviewer": "pytest_reviewer"},
    )
    assert wrong_token.status_code == 401

    accepted = client.post(
        f"/api/review-queue/{control_id}/decision",
        headers={"X-Control-Tower-Token": "test-token"},
        json={"decision": "reject", "reviewer": "pytest_reviewer"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["role"] == "reviewer"
    assert accepted.json()["item"]["approval_state"] == "rejected"


def test_role_tokens_allow_reviewer_or_admin_only_for_writes(tmp_path):
    client = TestClient(
        create_test_app(
            tmp_path,
            auth_roles={
                "test-token": "viewer",
                "test-access-token": "reviewer",
                "test-api-key": "admin",
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
        headers={"X-Control-Tower-Token": "test-token"},
        json={"decision": "approve", "reviewer": "pytest_viewer"},
    )
    assert viewer.status_code == 403

    reviewer = client.post(
        f"/api/review-queue/{control_id}/decision",
        headers={"X-Control-Tower-Token": "test-access-token"},
        json={"decision": "approve", "reviewer": "pytest_reviewer"},
    )
    assert reviewer.status_code == 200
    assert reviewer.json()["role"] == "reviewer"

    queue = client.get("/api/review-queue", params={"approval_state": "pending_reviewer"}).json()
    next_control_id = queue["items"][0]["control_id"]
    admin = client.post(
        f"/api/review-queue/{next_control_id}/decision",
        headers={"X-Control-Tower-Token": "test-api-key"},
        json={"decision": "needs_more_evidence", "reviewer": "pytest_admin"},
    )
    assert admin.status_code == 200
    assert admin.json()["role"] == "admin"


def test_role_config_rejects_invalid_roles(tmp_path):
    with pytest.raises(ValueError, match="unsupported control tower role"):
        create_test_app(tmp_path, auth_roles={"test-password": "operator"})

    with pytest.raises(ValueError, match="empty control tower credential"):
        create_test_app(tmp_path, auth_roles={"": "viewer"})


def test_ops_metrics_report_artifact_health(tmp_path):
    client = TestClient(create_test_app(tmp_path))

    ops = client.get("/api/ops-metrics")
    assert ops.status_code == 200
    payload = ops.json()
    assert payload["status"] == "ok"
    assert payload["queue"]["total"] > 0
    assert payload["artifacts"]["control_state"]["exists"] is True
    assert payload["artifacts"]["impact_cards"]["exists"] is True
    assert payload["artifacts"]["impact_policy_audit"]["exists"] is True
    assert payload["artifacts"]["reviewer_policy_robustness"]["exists"] is True
    assert payload["artifacts"]["reviewer_action_plan"]["exists"] is True
    assert payload["artifacts"]["reviewer_evidence_bundles"]["exists"] is True
    assert payload["artifacts"]["agent_reviewer_brief"]["exists"] is True
    assert payload["artifacts"]["agent_candidate_review_notes"]["exists"] is True
    assert payload["artifacts"]["sqlite_database"]["exists"] is True
