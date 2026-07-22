import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pytest

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
    _load_public_inputs,
    run,
)


PUBLIC_FIXTURE = ROOT / "tests" / "fixtures" / "public_demo_inputs.json"


def test_public_fixture_preserves_latest_aggregate_contract(tmp_path):
    fixture = json.loads(PUBLIC_FIXTURE.read_text(encoding="utf-8"))
    summary = run(
        tmp_path,
        bike_root=tmp_path / "missing-bike-root",
        workbench_root=tmp_path / "missing-workbench-root",
        public_inputs_path=PUBLIC_FIXTURE,
    )

    assert summary["source_status"]["public_snapshot_fixture"] is True
    assert summary["source_status"]["bike_demo_fallback"] is False
    assert summary["source_status"]["workbench_demo_fallback"] is False
    observed_at = fixture["_snapshot"]["source_observed_at"]
    assert summary["source_status"]["data_observed_at"] == observed_at
    assert summary["source_status"]["bike_public_deploy_decision"] == "GO"
    assert summary["source_status"]["seoul_validation_status"] == "READY"
    assert summary["metrics"]["seoul_snapshot_count"] == int(
        fixture["bike"]["seoul_validation_summary"]["snapshot_count"]
    )
    assert summary["metrics"]["seoul_priority_rows"] == len(
        fixture["bike"]["seoul_priority"]
    )
    assert summary["metrics"]["review_queue_items"] == len(
        fixture["workbench"]["review_queue"]
    )
    assert summary["metrics"]["incident_rows"] == len(
        fixture["workbench"]["incident_surface"]["incidents"]
    )
    assert summary["metrics"]["impact_verified_units"] > 0
    assert summary["metrics"]["impact_model_validated_estimate_units"] > 0
    assert summary["metrics"]["impact_realized_units"] == 0
    assert summary["metrics"]["impact_realized_claim_blocked_units"] == summary["metrics"][
        "impact_candidate_units_addressed"
    ]
    dashboard = Path(summary["reports"]["dashboard"]).read_text(encoding="utf-8")
    assert "Decision Intelligence Copilot" in dashboard
    assert 'id="workspace-summary"' not in dashboard


def test_public_fixture_rejects_missing_required_section(tmp_path):
    fixture = tmp_path / "missing-workbench.json"
    fixture.write_text(json.dumps({"bike": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing object section: workbench"):
        _load_public_inputs(fixture)


def test_public_fixture_rejects_local_path_leak(tmp_path):
    fixture = tmp_path / "local-path.json"
    fixture.write_text(
        json.dumps(
            {
                "bike": {"report_path": "/DATA/private/report.json"},
                "workbench": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exposes a local path"):
        _load_public_inputs(fixture)


def test_public_fixture_rejects_missing_snapshot_metadata(tmp_path):
    fixture = tmp_path / "missing-snapshot.json"
    fixture.write_text(json.dumps({"bike": {}, "workbench": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing object section: _snapshot"):
        _load_public_inputs(fixture)


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
    assert "Decision Intelligence Copilot" in dashboard_html
    assert "One Copilot · Verified execution" in dashboard_html
    assert "분석 Copilot" in dashboard_html
    assert "무엇을 분석해 볼까요?" in dashboard_html
    assert 'class="chat-attach"' in dashboard_html
    assert 'class="chat-evidence-backdrop"' in dashboard_html
    assert "데이터와 근거" in dashboard_html
    assert 'data-product-target="analysis"' in dashboard_html
    assert 'data-product-target="migration"' in dashboard_html
    assert 'data-product-target="validation"' in dashboard_html
    assert 'data-product-target="technical"' in dashboard_html
    assert 'id="workspace-analysis"' in dashboard_html
    assert 'id="workspace-migration"' in dashboard_html
    assert 'id="workspace-validation"' in dashboard_html
    assert 'id="workspace-technical"' in dashboard_html
    assert 'id="workspace-summary"' not in dashboard_html
    assert 'data-live-chat="false"' in dashboard_html
    assert "Recorded demo" in dashboard_html
    assert "Migration Lab" in dashboard_html
    assert "Correctness fixture" in dashboard_html
    assert "Scale & recovery rehearsal" in dashboard_html
    assert "Evaluation evidence" in dashboard_html
    assert "사용자 평가" in dashboard_html
    assert "현재 범위에서 생략" in dashboard_html
    assert "Claim boundary" in dashboard_html
    assert "Execution flow" in dashboard_html
    assert "Safety & privacy contract" in dashboard_html
    assert "Control ID" not in dashboard_html
    assert "SEOUL-IMPACT" not in dashboard_html
    assert "task_" not in dashboard_html
    assert "table-wrap" in dashboard_html
    assert "data-decision" not in dashboard_html

    api_contract = json.loads(Path(summary["reports"]["api_contract"]).read_text(encoding="utf-8"))
    paths = {item["path"] for item in api_contract["endpoints"]}
    assert "/api/agent/reviewer-brief" in paths
    assert "/api/chat" in paths
    assert "/api/data/analyze" in paths
    assert "/api/data/query" in paths
    assert "/api/migration/case-study" in paths
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


def test_quality_floor_requires_fresh_passing_junit(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    (reports / "pytest.xml").write_text(
        '<testsuite tests="32" failures="0" errors="0" />\n',
        encoding="utf-8",
    )
    bike_root = tmp_path / "bike-root"
    station_reports = bike_root / "station_level" / "reports"
    seoul_reports = bike_root / "seoul_ddareungi" / "reports"
    station_reports.mkdir(parents=True)
    seoul_reports.mkdir(parents=True)
    (station_reports / "station_snapshot_readiness.json").write_text(
        json.dumps({"ready_for_prospective_validation": True}), encoding="utf-8"
    )
    (station_reports / "station_public_deploy_readiness.json").write_text(
        json.dumps({"decision": "GO"}), encoding="utf-8"
    )
    (seoul_reports / "validation_summary.json").write_text(
        json.dumps({"validation_status": "READY", "snapshot_count": 30}), encoding="utf-8"
    )
    (seoul_reports / "model_metrics.json").write_text(
        json.dumps({"model_status": "READY"}), encoding="utf-8"
    )
    with (seoul_reports / "rebalancing_priority.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "station_id",
                "station_name",
                "station_lat",
                "station_lon",
                "recommended_action",
                "recommended_bikes_delta",
                "severity_score",
                "capacity",
                "bikes_available",
                "docks_available",
                "captured_at_kst",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "station_id": "fresh-1",
                "station_name": "최신 대여소",
                "station_lat": "37.55",
                "station_lon": "126.98",
                "recommended_action": "remove_bikes",
                "recommended_bikes_delta": "-10",
                "severity_score": "2.0",
                "capacity": "20",
                "bikes_available": "19",
                "docks_available": "1",
                "captured_at_kst": datetime.now(timezone.utc).isoformat(),
            }
        )

    run(
        tmp_path,
        bike_root=bike_root,
        workbench_root=tmp_path / "missing-workbench-root",
    )
    with (reports / "quality_gate_scores.csv").open(newline="", encoding="utf-8") as handle:
        verified = list(csv.DictReader(handle))
    evidence = json.loads((reports / "quality_evidence.json").read_text(encoding="utf-8"))

    assert min(float(row["score"]) for row in verified) == 96.1
    assert evidence["all_required_evidence"] is True

    (reports / "pytest.xml").write_text(
        '<testsuite tests="32" failures="1" errors="0" />\n',
        encoding="utf-8",
    )
    run(
        tmp_path,
        bike_root=bike_root,
        workbench_root=tmp_path / "missing-workbench-root",
    )
    with (reports / "quality_gate_scores.csv").open(newline="", encoding="utf-8") as handle:
        unverified = list(csv.DictReader(handle))

    assert min(float(row["score"]) for row in unverified) == 95.9


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


def test_public_go_allows_model_estimate_but_blocks_realized_impact_claim():
    inputs = {
        "bike": {
            "public_deploy": {"decision": "GO"},
            "seoul_priority": [
                {
                    "station_id": "s1",
                    "station_name": "검증된 추정 후보",
                    "station_lat": "37.55",
                    "station_lon": "126.98",
                    "recommended_bikes_delta": "10",
                    "severity_score": "2.0",
                    "recommended_action": "send_bikes",
                    "capacity": "20",
                    "bikes_available": "0",
                    "docks_available": "20",
                }
            ],
            "seoul_validation_summary": {
                "validation_status": "READY",
                "snapshot_count": 340,
                "min_snapshots_for_validation": 24,
                "precision_at_50": 0.9,
            },
        }
    }

    cards = _build_impact_cards(inputs, limit=1)
    audit = _build_impact_policy_audit(cards)
    estimate = next(
        row for row in audit if row["policy"] == "model_validated_estimate_claim"
    )
    unsafe_realized = next(
        row for row in audit if row["policy"] == "unsafe_realized_impact_claim"
    )
    guarded_realized = next(
        row for row in audit if row["policy"] == "guarded_realized_impact_claim"
    )

    assert cards[0]["public_claim_state"] == "allowed"
    assert cards[0]["public_claim_scope"] == "validated_model_estimate_only"
    assert cards[0]["impact_evidence_tier"] == "model_validated_estimate"
    assert cards[0]["model_validated_estimate_units"] == 10
    assert cards[0]["realized_delta_vs_no_action_units"] is None
    assert cards[0]["realized_impact_status"] == "not_observed"
    assert estimate["audit_result"] == "pass"
    assert unsafe_realized["audit_result"] == "fail"
    assert unsafe_realized["unsupported_claim_units"] == 10
    assert guarded_realized["audit_result"] == "pass"
    assert guarded_realized["blocked_public_claim_units"] == 10
    assert guarded_realized["unsupported_claim_units"] == 0


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
