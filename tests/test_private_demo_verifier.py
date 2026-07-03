from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in [SRC, SCRIPTS]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from verify_private_demo import format_summary, verify_private_demo


def test_private_demo_verifier_checks_auth_boundary_without_printing_tokens(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "CONTROL_TOWER_ROLE_TOKENS",
        "viewer:viewer-secret,reviewer:reviewer-secret,admin:admin-secret",
    )
    monkeypatch.delenv("CONTROL_TOWER_API_TOKEN", raising=False)

    payload = verify_private_demo(
        tmp_path,
        tmp_path / "missing-bike-root",
        tmp_path / "missing-workbench-root",
    )
    summary = format_summary(payload)

    assert payload["status"] == "ok"
    assert payload["configured_roles"] == ["admin", "reviewer", "viewer"]
    assert payload["queue_total"] > 0
    assert payload["impact_cards"] > 0
    assert payload["missing_credential_status"] == 401
    assert payload["viewer_write_status"] == 403
    assert payload["write_credential_status"] == 404
    assert "viewer-secret" not in summary
    assert "reviewer-secret" not in summary
    assert "admin-secret" not in summary


def test_private_demo_verifier_requires_write_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROL_TOWER_ROLE_TOKENS", "viewer:viewer-secret")
    monkeypatch.delenv("CONTROL_TOWER_API_TOKEN", raising=False)

    with pytest.raises(AssertionError, match="reviewer or admin"):
        verify_private_demo(
            tmp_path,
            tmp_path / "missing-bike-root",
            tmp_path / "missing-workbench-root",
        )
