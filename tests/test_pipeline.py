from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.pipeline import run


def test_control_tower_seed_writes_product_surface(tmp_path):
    summary = run(tmp_path)

    assert summary["status"] == "seed_ready"
    assert summary["demo_mode_ready"] is True
    assert summary["public_deploy_decision"] in {"GO", "NO_GO"}
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


def test_public_deploy_stays_blocked_until_bike_readiness(tmp_path):
    summary = run(tmp_path)

    if summary["source_status"]["bike_public_deploy_decision"] != "GO":
        assert summary["public_deploy_decision"] == "NO_GO"
        assert any("bike-share public deploy decision" in item for item in summary["blockers"])
