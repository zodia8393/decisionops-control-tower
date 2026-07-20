from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.chat_ui import render_chat_surface


def test_recorded_chat_escapes_script_payload_and_rejects_unsafe_url():
    malicious = "</script><script>alert('xss')</script>"
    rendered = render_chat_surface(
        {
            "테스트 질문": {
                "status": "ANSWER",
                "answer": malicious,
                "citations": [
                    {
                        "source_id": "malicious",
                        "title": malicious,
                        "url": "javascript:alert('xss')",
                    }
                ],
            }
        },
        live_chat=False,
        vector_store="memory",
    )

    assert malicious not in rendered
    assert "javascript:" not in rendered
    assert "\\u003c/script\\u003e" in rendered
    assert 'aria-disabled="true"' in rendered
