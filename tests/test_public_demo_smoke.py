from email.message import Message
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
for path in [SCRIPTS, SRC]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from decisionops_control_tower.copilot_dashboard import render_copilot_dashboard
from decisionops_control_tower.migration_case import run_migration_case
from smoke_public_demo import PublicDemoSmokeError, fetch_public_demo, validate_demo_html


class FakeResponse:
    status = 200

    def __init__(self, html: str, content_type: str = "text/html"):
        self._html = html.encode("utf-8")
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self) -> str:
        return "https://example.test/control-tower/"

    def read(self) -> bytes:
        return self._html


def static_dashboard() -> str:
    return render_copilot_dashboard(
        recorded_chat={},
        migration_case=run_migration_case().model_dump(mode="json"),
        evidence={
            "analysis": {
                "metrics": {
                    "case_count": 72,
                    "end_to_end_pass_rate": 1.0,
                    "analysis_plan_schema_validity": 1.0,
                    "numeric_execution_correctness": 1.0,
                }
            },
            "migration_rehearsal": {
                "status": "pass",
                "source_rows": 120000,
                "accepted_rows": 119962,
                "rejected_rows": 38,
                "committed_batches": 48,
                "resumed_from_source_rows": 7500,
                "replay_processed_rows": 0,
                "foreign_key_violations": 0,
                "schema_drift_blocked_before_write": True,
                "idempotent_replay": True,
            },
            "rag": {
                "metrics": {
                    "case_count": 36,
                    "pass_rate": 1.0,
                    "retrieval_recall_at_k": 1.0,
                }
            },
            "usability": {"participant_count": 0, "portfolio_ready": False},
        },
        live_chat=False,
        vector_store="recorded",
    )


def test_static_dashboard_satisfies_public_read_only_contract():
    html = static_dashboard()
    result = validate_demo_html(html)

    assert result == {
        "required_marker_count": 13,
        "forbidden_marker_count": 7,
        "mode": "Recorded read-only snapshot",
    }
    assert "function activate(name" in html
    assert 'data-product-panel="analysis"' in html
    assert 'id="workspace-review"' not in html


def test_static_dashboard_explains_unproven_claim_boundaries():
    html = static_dashboard()

    assert "사용자 평가" in html
    assert "현재 범위에서 생략" in html
    assert "아직 미증명" in html
    assert validate_demo_html(html)["mode"] == "Recorded read-only snapshot"


def test_public_demo_smoke_requires_an_explicit_recorded_mode():
    html = static_dashboard().replace("Recorded read-only snapshot", "상태 미표시")

    with pytest.raises(PublicDemoSmokeError, match="markers are missing"):
        validate_demo_html(html)


def test_public_demo_smoke_rejects_write_controls():
    with pytest.raises(PublicDemoSmokeError, match="exposes write markers"):
        validate_demo_html(static_dashboard() + '<button data-decision="approve">approve</button>')


def test_public_demo_smoke_rejects_non_html_response():
    with pytest.raises(PublicDemoSmokeError, match="unexpected content type"):
        fetch_public_demo(
            "https://example.test/control-tower/",
            opener=lambda *_args, **_kwargs: FakeResponse(
                static_dashboard(),
                "application/octet-stream",
            ),
        )
