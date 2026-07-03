import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.pipeline import _build_impact_cards, _build_review_queue, run


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
    assert summary["source_status"]["seoul_validation_status"] in {"READY", "NOT_READY"}
    assert summary["metrics"]["guarded_success_rate"] == 1.0
    assert summary["metrics"]["holdout_success_rate"] == 1.0
    assert Path(summary["reports"]["control_state"]).exists()
    assert Path(summary["reports"]["api_contract"]).exists()
    assert Path(summary["reports"]["review_queue"]).exists()
    assert Path(summary["reports"]["impact_cards"]).exists()
    assert Path(summary["reports"]["impact_cards_json"]).exists()
    assert Path(summary["reports"]["dashboard"]).exists()
    dashboard_html = Path(summary["reports"]["dashboard"]).read_text(encoding="utf-8")
    assert "오늘의 결론" in dashboard_html
    assert "검토 대기열 보기" in dashboard_html
    assert "지도에서 보기" in dashboard_html
    assert "지도에서 위치 확인" in dashboard_html
    assert "서울 따릉이 후보 조치 위치 지도" in dashboard_html
    assert "서울 따릉이 후보 조치 실제 지도 타일" in dashboard_html
    assert "openstreetmap.org/export/embed.html" in dashboard_html
    assert 'referrerpolicy="no-referrer"' in dashboard_html
    assert "후보 번호 지도" in dashboard_html
    assert "외부 지도 타일이 차단되면" in dashboard_html
    assert "점이 클수록 예상 완화량이 큽니다." in dashboard_html
    assert 'href="#ddareungi-action-1"' in dashboard_html
    assert 'id="ddareungi-action-1"' in dashboard_html
    assert "표에서 세부 보기" in dashboard_html
    assert "판단 근거 보기" in dashboard_html
    assert "권고 이유" in dashboard_html
    assert "좌표 상태" in dashboard_html
    assert "서울 따릉이 대여소 현황과 재배치 우선순위 산출물" in dashboard_html
    assert "검토 기준 보기" in dashboard_html
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

    impact_cards = json.loads(Path(summary["reports"]["impact_cards_json"]).read_text(encoding="utf-8"))
    assert impact_cards[0]["station_lat"]
    assert impact_cards[0]["station_lon"]
    assert impact_cards[0]["coordinate_status"] == "valid"


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
