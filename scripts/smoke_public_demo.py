#!/usr/bin/env python3
"""Verify the public Copilot snapshot without exercising live or write APIs."""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable
from urllib.request import Request, urlopen


DEFAULT_URL = "https://zodia8393.github.io/decisionops-control-tower/"
REQUIRED_MARKERS = (
    "Decision Intelligence Copilot",
    "One Copilot · Verified execution",
    "분석 Copilot",
    "Migration Lab",
    "Legacy Hospital Migration",
    "검증 결과",
    "기술 상세",
    "CSV · JSON · XLSX · Parquet 선택",
    "무엇을 분석해 볼까요?",
    'data-live-chat="false"',
    "Recorded demo",
    "Recorded read-only snapshot",
    "Session-only dataset",
)
FORBIDDEN_MARKERS = (
    'data-decision="',
    'fetch(`/api/review-queue/',
    "X-Control-Tower-Token",
    'data-live-chat="true"',
    'id="workspace-summary"',
    'id="workspace-candidates"',
    'id="workspace-review"',
)


class PublicDemoSmokeError(RuntimeError):
    """Raised when the public dashboard violates its read-only contract."""


def validate_demo_html(html: str) -> dict[str, Any]:
    missing = [marker for marker in REQUIRED_MARKERS if marker not in html]
    exposed = [marker for marker in FORBIDDEN_MARKERS if marker in html]
    if missing:
        raise PublicDemoSmokeError(f"public demo markers are missing: {missing}")
    if exposed:
        raise PublicDemoSmokeError(f"public demo exposes write markers: {exposed}")
    return {
        "required_marker_count": len(REQUIRED_MARKERS),
        "forbidden_marker_count": len(FORBIDDEN_MARKERS),
        "mode": "Recorded read-only snapshot",
    }


def fetch_public_demo(
    url: str,
    *,
    timeout: float = 10.0,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "control-tower-pages-smoke/1.0"})
    with opener(request, timeout=timeout) as response:
        status = int(getattr(response, "status", None) or 200)
        content_type = response.headers.get_content_type()
        final_url = response.geturl()
        html = response.read().decode("utf-8")

    if status != 200:
        raise PublicDemoSmokeError(f"public demo returned HTTP {status}")
    if content_type != "text/html":
        raise PublicDemoSmokeError(f"public demo returned unexpected content type: {content_type}")
    contract = validate_demo_html(html)
    return {
        "status": "ok",
        "http_status": status,
        "content_type": content_type,
        "final_url": final_url,
        **contract,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(fetch_public_demo(args.url, timeout=args.timeout), ensure_ascii=False))


if __name__ == "__main__":
    main()
