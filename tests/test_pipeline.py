import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.pipeline import (
    _build_impact_cards,
    _build_impact_policy_audit,
    _build_review_queue,
    _build_reviewer_action_plan,
    _build_reviewer_evidence_bundles,
    _build_reviewer_policy_robustness,
    run,
)


def test_control_tower_seed_writes_product_surface(tmp_path):
    summary = run(
        tmp_path,
        bike_root=tmp_path / "missing-bike-root",
        workbench_root=tmp_path / "missing-workbench-root",
    )

    assert summary["status"] == "seed_ready"
    assert summary["demo_mode_ready"] is True
    assert summary["public_deploy_decision"] in {"GO", "NO_GO"}
    assert summary["source_status"]["bike_demo_fallback"] is True
    assert summary["source_status"]["workbench_demo_fallback"] is True
    assert summary["metrics"]["review_queue_items"] > 0
    assert summary["metrics"]["impact_card_rows"] > 0
    assert summary["metrics"]["impact_candidate_units_addressed"] > 0
    assert summary["metrics"]["impact_policy_audit_rows"] >= 8
    assert summary["metrics"]["impact_unsupported_claim_units_avoided"] > 0
    assert summary["metrics"]["reviewer_policy_robustness_rows"] == 36
    assert summary["metrics"]["reviewer_policy_guarded_dominance_rate"] >= 0.99
    assert summary["metrics"]["reviewer_action_plan_rows"] > 0
    assert summary["metrics"]["reviewer_evidence_bundle_rows"] > 0
    assert summary["source_status"]["seoul_validation_status"] in {"READY", "NOT_READY"}
    assert summary["metrics"]["guarded_success_rate"] == 1.0
    assert summary["metrics"]["holdout_success_rate"] == 1.0
    assert Path(summary["reports"]["control_state"]).exists()
    assert Path(summary["reports"]["api_contract"]).exists()
    assert Path(summary["reports"]["review_queue"]).exists()
    assert Path(summary["reports"]["impact_cards"]).exists()
    assert Path(summary["reports"]["impact_cards_json"]).exists()
    assert Path(summary["reports"]["impact_policy_audit"]).exists()
    assert Path(summary["reports"]["impact_policy_audit_json"]).exists()
    assert Path(summary["reports"]["reviewer_policy_robustness"]).exists()
    assert Path(summary["reports"]["reviewer_policy_robustness_json"]).exists()
    assert Path(summary["reports"]["reviewer_action_plan"]).exists()
    assert Path(summary["reports"]["reviewer_action_plan_json"]).exists()
    assert Path(summary["reports"]["reviewer_evidence_bundles"]).exists()
    assert Path(summary["reports"]["reviewer_evidence_bundles_json"]).exists()
    assert Path(summary["reports"]["agent_reviewer_brief"]).exists()
    assert Path(summary["reports"]["agent_candidate_review_notes"]).exists()
    assert Path(summary["reports"]["dashboard"]).exists()
    dashboard_html = Path(summary["reports"]["dashboard"]).read_text(encoding="utf-8")
    assert "오늘의 결론" in dashboard_html
    assert "검토 대기열 보기" in dashboard_html
    assert "지도에서 보기" in dashboard_html
    assert "정책 비교 보기" in dashboard_html
    assert "Stress test 보기" in dashboard_html
    assert "검토 계획 보기" in dashboard_html
    assert "근거 패킷 보기" in dashboard_html
    assert "AI Reviewer Brief" in dashboard_html
    assert "agent mode:" in dashboard_html
    assert "deterministic gate:" in dashboard_html
    assert "Evidence lock" in dashboard_html
    assert "read-only reviewer assistant" in dashboard_html
    assert "지도에서 위치 확인" in dashboard_html
    assert "서울 따릉이 후보 조치 위치 지도" in dashboard_html
    assert "tile.openstreetmap.org" in dashboard_html
    assert "지도 타일 © OpenStreetMap contributors" in dashboard_html
    assert "후보 번호 오버레이 지도" in dashboard_html
    assert "후보 번호는 실제 지도 타일 위에 표시됩니다" in dashboard_html
    assert "점이 클수록 예상 완화량이 큽니다." in dashboard_html
    assert 'href="#ddareungi-action-1"' in dashboard_html
    assert 'id="ddareungi-action-1"' in dashboard_html
    assert "표에서 세부 보기" in dashboard_html
    assert "판단 근거 보기" in dashboard_html
    assert "권고 이유" in dashboard_html
    assert "좌표 상태" in dashboard_html
    assert "서울 따릉이 대여소 현황과 재배치 우선순위 산출물" in dashboard_html
    assert "검토 기준 보기" in dashboard_html
    assert "영향 정책 비교" in dashboard_html
    assert "Reviewer policy robustness" in dashboard_html
    assert "Oracle regret" in dashboard_html
    assert "검토 실행 계획" in dashboard_html
    assert "심의 근거 패킷" in dashboard_html
    assert "SHA-256" in dashboard_html
    assert "미검증 claim 단위" in dashboard_html
    assert "권장 결정" in dashboard_html
    assert "원천 근거 요약" in dashboard_html
    assert "다음 결정 기준" in dashboard_html
    assert "로컬 감사 기록" in dashboard_html
    assert "회수 여부 검토" in dashboard_html
    assert "무엇을 판단하나" in dashboard_html
    assert "무엇을 검토하나" in dashboard_html
    assert "Control ID" not in dashboard_html
    assert "SEOUL-IMPACT" not in dashboard_html
    assert "task_" not in dashboard_html
    assert "table-wrap" in dashboard_html
    assert "data-decision" not in dashboard_html

    api_contract = json.loads(Path(summary["reports"]["api_contract"]).read_text(encoding="utf-8"))
    paths = {item["path"] for item in api_contract["endpoints"]}
    assert "/api/agent/reviewer-brief" in paths
    assert "/api/agent/candidate/{candidate_id}/review-notes" in paths
    assert "/api/reviewer-evidence-bundles" in paths
    assert "/api/reviewer-policy-robustness" in paths

    agent_brief = json.loads(Path(summary["reports"]["agent_reviewer_brief"]).read_text(encoding="utf-8"))
    assert agent_brief["mode"] == "fallback"
    assert agent_brief["claim_safety"]["rule"]
    candidate_notes = json.loads(
        Path(summary["reports"]["agent_candidate_review_notes"]).read_text(encoding="utf-8")
    )
    assert candidate_notes
    assert candidate_notes[0]["mode"] == "fallback"
    assert candidate_notes[0]["claim_safety"]["public_deploy_decision"] == summary["public_deploy_decision"]

    impact_cards = json.loads(Path(summary["reports"]["impact_cards_json"]).read_text(encoding="utf-8"))
    assert impact_cards[0]["station_lat"]
    assert impact_cards[0]["station_lon"]
    assert impact_cards[0]["coordinate_status"] == "valid"
    assert impact_cards[0]["public_claim_state"] == "blocked_until_public_deploy_ready"

    evidence_bundles = json.loads(
        Path(summary["reports"]["reviewer_evidence_bundles_json"]).read_text(
            encoding="utf-8"
        )
    )
    assert evidence_bundles
    assert len(evidence_bundles[0]["evidence_fingerprint_sha256"]) == 64
    assert evidence_bundles[0]["freshness_status"] in {
        "fresh",
        "stale",
        "missing_timestamp",
        "future_timestamp",
    }
    with Path(summary["reports"]["reviewer_evidence_bundles"]).open(
        newline="", encoding="utf-8"
    ) as handle:
        csv_header = next(csv.reader(handle))
    assert csv_header[-2:] == ["evidence_lock_status", "evidence_contract_json"]


def test_policy_audit_and_action_plan_block_public_overclaim():
    inputs = {
        "bike": {
            "public_deploy": {"decision": "NO_GO"},
            "seoul_priority": [
                {
                    "station_id": "s1",
                    "station_name": "검증된 대여소",
                    "station_lat": "37.55",
                    "station_lon": "126.98",
                    "recommended_bikes_delta": "-10",
                    "severity_score": "2.0",
                    "recommended_action": "remove_bikes",
                    "capacity": "20",
                    "bikes_available": "19",
                    "docks_available": "1",
                }
            ],
            "seoul_validation_summary": {
                "validation_status": "READY",
                "snapshot_count": 30,
                "min_snapshots_for_validation": 24,
                "precision_at_50": 0.9,
            },
        }
    }

    cards = _build_impact_cards(inputs, limit=1)
    audit = _build_impact_policy_audit(cards)
    plan = _build_reviewer_action_plan(cards)
    unsafe = next(row for row in audit if row["policy"] == "unsafe_auto_publish")
    guarded = next(row for row in audit if row["policy"] == "guarded_all_review")

    assert cards[0]["guardrail_state"] == "ready_for_review"
    assert cards[0]["public_claim_state"] == "blocked_until_public_deploy_ready"
    assert unsafe["audit_result"] == "fail"
    assert unsafe["unsupported_claim_units"] == 10
    assert guarded["audit_result"] == "pass"
    assert guarded["blocked_public_claim_units"] == 10
    assert guarded["unsupported_claim_units"] == 0
    assert plan[0]["reviewer_decision"] == "approve_local_review_only"


def test_reviewer_policy_robustness_is_deterministic_and_guarded():
    cards = [
        {
            "impact_card_id": f"SEOUL-IMPACT-{index:04d}",
            "priority": "P0" if index <= 4 else "P1",
            "candidate_units_addressed": units,
            "confidence_score": confidence,
            "coordinate_status": "valid",
            "guardrail_state": "ready_for_review",
        }
        for index, (units, confidence) in enumerate(
            [(9, 0.95), (20, 0.7), (13, 0.9), (16, 0.8), (8, 0.85), (7, 0.75)],
            start=1,
        )
    ]

    first = _build_reviewer_policy_robustness(cards)
    second = _build_reviewer_policy_robustness(cards)

    assert first == second
    assert first["summary"]["scenario_count"] == 4
    assert first["summary"]["comparison_rows"] == 36
    assert first["summary"]["guarded_dominance_rate"] >= 0.99
    assert first["summary"]["guarded_worst_case_regret_units"] == 0.0
    assert first["summary"]["guarded_public_claim_violations"] == 0
    assert {row["scenario"] for row in first["rows"]} == {
        "baseline",
        "unit_estimate_jitter",
        "confidence_stress",
        "top_candidate_dropout",
    }


def test_reviewer_policy_robustness_flags_invalid_evidence():
    cards = [
        {
            "impact_card_id": "SEOUL-IMPACT-0001",
            "priority": "P0",
            "candidate_units_addressed": 10,
            "confidence_score": 0.5,
            "coordinate_status": "missing",
            "guardrail_state": "validation_not_ready",
        }
    ]

    result = _build_reviewer_policy_robustness(cards)

    guarded = [
        row
        for row in result["rows"]
        if row["policy"] == "confidence_weighted_guarded_capacity"
    ]
    assert guarded
    baseline = [row for row in guarded if row["scenario"] == "baseline"]
    assert all(row["invalid_evidence_rows"] == 1 for row in baseline)
    assert all(row["public_claim_violation_count"] == 0 for row in guarded)


def test_evidence_bundles_gate_stale_and_missing_sources_and_hash_content():
    cards = [
        {
            "impact_card_id": "SEOUL-IMPACT-0001",
            "station_name": "최신 대여소",
            "recommended_action": "send_bikes",
            "candidate_units_addressed": 7,
            "confidence_score": 0.9,
            "coordinate_status": "valid",
            "guardrail_state": "ready_for_review",
            "public_claim_state": "blocked_until_public_deploy_ready",
            "captured_at_kst": "2026-07-10T18:30:00+09:00",
        },
        {
            "impact_card_id": "SEOUL-IMPACT-0002",
            "station_name": "오래된 대여소",
            "recommended_action": "remove_bikes",
            "candidate_units_addressed": 5,
            "confidence_score": 0.8,
            "coordinate_status": "valid",
            "guardrail_state": "ready_for_review",
            "public_claim_state": "blocked_until_public_deploy_ready",
            "captured_at_kst": "2026-07-10T10:00:00+09:00",
        },
        {
            "impact_card_id": "SEOUL-IMPACT-0003",
            "station_name": "시각 누락 대여소",
            "recommended_action": "monitor",
            "candidate_units_addressed": 1,
            "confidence_score": 0.7,
            "coordinate_status": "valid",
            "guardrail_state": "ready_for_review",
            "public_claim_state": "blocked_until_public_deploy_ready",
            "captured_at_kst": "",
        },
    ]
    action_plan = _build_reviewer_action_plan(cards, limit=3)

    bundles = _build_reviewer_evidence_bundles(
        cards,
        action_plan,
        generated_at_utc="2026-07-10T10:00:00+00:00",
        freshness_sla_hours=3.0,
    )

    assert bundles[0]["freshness_status"] == "fresh"
    assert bundles[0]["evidence_lock_status"] == "locked_fresh"
    assert bundles[0]["reviewer_decision"] == "approve_local_review_only"
    assert bundles[1]["freshness_status"] == "stale"
    assert bundles[1]["reviewer_decision"] == "needs_more_evidence"
    assert bundles[2]["freshness_status"] == "missing_timestamp"
    assert bundles[2]["reviewer_decision"] == "needs_more_evidence"

    changed_cards = [{**card} for card in cards]
    changed_cards[0]["candidate_units_addressed"] = 8
    changed = _build_reviewer_evidence_bundles(
        changed_cards,
        action_plan,
        generated_at_utc="2026-07-10T10:00:00+00:00",
    )
    assert (
        changed[0]["evidence_fingerprint_sha256"]
        != bundles[0]["evidence_fingerprint_sha256"]
    )


def test_public_deploy_stays_blocked_until_bike_readiness(tmp_path):
    summary = run(
        tmp_path,
        bike_root=tmp_path / "missing-bike-root",
        workbench_root=tmp_path / "missing-workbench-root",
    )

    if summary["source_status"]["bike_public_deploy_decision"] != "GO":
        assert summary["public_deploy_decision"] == "NO_GO"
        assert any("bike-share public deploy decision" in item for item in summary["blockers"])


def test_impact_cards_do_not_hide_missing_or_invalid_coordinates_as_zero():
    inputs = {
        "bike": {
            "public_deploy": {"decision": "NO_GO"},
            "seoul_priority": [
                {
                    "station_id": "bad-1",
                    "station_name": "좌표 누락 대여소",
                    "station_lat": "",
                    "station_lon": "127.0",
                    "recommended_bikes_delta": "-3",
                    "severity_score": "1.0",
                    "recommended_action": "remove_bikes",
                    "capacity": "10",
                    "bikes_available": "10",
                    "docks_available": "0",
                },
                {
                    "station_id": "bad-2",
                    "station_name": "범위 오류 대여소",
                    "station_lat": "0",
                    "station_lon": "0",
                    "recommended_bikes_delta": "5",
                    "severity_score": "2.0",
                    "recommended_action": "send_bikes",
                    "capacity": "12",
                    "bikes_available": "0",
                    "docks_available": "12",
                },
            ],
            "seoul_validation_summary": {
                "validation_status": "NOT_READY",
                "snapshot_count": 1,
                "min_snapshots_for_validation": 12,
                "precision_at_50": 0.8,
            },
        }
    }

    cards = _build_impact_cards(inputs, limit=2)

    assert cards[0]["station_lat"] is None
    assert cards[0]["station_lon"] is None
    assert cards[0]["coordinate_status"] == "missing"
    assert cards[1]["station_lat"] is None
    assert cards[1]["station_lon"] is None
    assert cards[1]["coordinate_status"] == "out_of_range"


def test_review_queue_uses_requested_action_and_human_context():
    queue = _build_review_queue(
        [
            {
                "queue_id": "HRQ-0007",
                "task_id": "task_007",
                "priority": "P0",
                "requested_action": "refuse",
                "guardrail_hits": "deployment_no_go",
                "review_question": (
                    "자동 실행 또는 배포를 거부합니다. guardrail=['deployment_no_go']. "
                    "근거: station=n/a, risk=n/a, incident=n/a, severity=n/a, "
                    "snapshot=74/336, deploy=NO_GO."
                ),
            }
        ]
    )

    assert queue[0]["action"] == "refuse"
    assert "자동 실행/공개 배포 거부 유지" in queue[0]["review_context"]
    assert "스냅샷: 74/336" in queue[0]["review_context"]
    assert "배포 판단: NO_GO" in queue[0]["review_context"]
