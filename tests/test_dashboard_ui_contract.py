from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in [SRC, SCRIPTS]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from decisionops_control_tower.app import create_app
from fastapi.testclient import TestClient
from prepare_demo_state import prepare_demo_state
from decisionops_control_tower.pipeline import DEFAULT_BIKE_ROOT, DEFAULT_WORKBENCH_ROOT, run
from verify_dashboard_ui import verify_dashboard_html


def test_dashboard_ui_contract_matches_live_testclient_dashboard(tmp_path):
    client = TestClient(create_app(output_root=tmp_path))
    dashboard = client.get("/dashboard")

    result = verify_dashboard_html(dashboard.text)

    assert dashboard.status_code == 200
    assert result["required_checks"] > 20
    assert result["forbidden_checks"] > 0


def test_prepare_demo_state_can_archive_existing_store(tmp_path):
    run(tmp_path)
    existing_db = tmp_path / "control_tower.sqlite"
    existing_db.write_text("placeholder", encoding="utf-8")

    payload = prepare_demo_state(
        tmp_path,
        DEFAULT_BIKE_ROOT,
        DEFAULT_WORKBENCH_ROOT,
        reset_approval_store=True,
    )

    assert payload["demo_mode_ready"] is True
    assert payload["queue"]["total"] > 0
    assert payload["archived_database"]
    assert Path(payload["archived_database"]).exists()
    assert existing_db.exists()
