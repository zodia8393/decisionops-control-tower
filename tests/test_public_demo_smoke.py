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

from decisionops_control_tower.dashboard import render_dashboard
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
    return render_dashboard(
        state={"demo_mode_ready": True, "public_deploy_decision": "NO_GO", "metrics": {}},
        queue=[],
        impact_cards=[],
        include_actions=False,
        include_script=False,
    )


def test_static_dashboard_satisfies_public_read_only_contract():
    result = validate_demo_html(static_dashboard())

    assert result == {"required_marker_count": 3, "forbidden_marker_count": 3}


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
