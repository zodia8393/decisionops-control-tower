from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in [SRC, SCRIPTS]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from decisionops_control_tower.pipeline import DEFAULT_BIKE_ROOT, DEFAULT_WORKBENCH_ROOT
from write_monitoring_snapshot import collect_snapshot, write_snapshot


def test_monitoring_snapshot_writes_current_and_history(tmp_path):
    payload = collect_snapshot(tmp_path, DEFAULT_BIKE_ROOT, DEFAULT_WORKBENCH_ROOT)
    paths = write_snapshot(tmp_path, payload)

    snapshot = Path(paths["snapshot"])
    history = Path(paths["history"])
    assert snapshot.exists()
    assert history.exists()
    assert "captured_at_utc" in snapshot.read_text(encoding="utf-8")
    assert len(history.read_text(encoding="utf-8").splitlines()) == 1
