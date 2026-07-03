#!/usr/bin/env python3
"""Verify the dashboard UI contract without adding a browser dependency."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlopen

from fastapi.testclient import TestClient

from decisionops_control_tower.app import create_app
from decisionops_control_tower.pipeline import (
    DEFAULT_BIKE_ROOT,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_WORKBENCH_ROOT,
)


REQUIRED_SNIPPETS = [
    'lang="ko"',
    '<meta name="viewport"',
    ':focus-visible',
    '@media (max-width: 640px)',
    'class="button button--primary" href="#reviewer-queue"',
    "검토 대기열 보기",
    "지도에서 보기",
    "서울 따릉이 후보 조치 위치 지도",
    "서울 따릉이 후보 조치 실제 지도 타일",
    "openstreetmap.org/export/embed.html",
    'referrerpolicy="no-referrer"',
    "후보 번호 지도",
    "외부 지도 타일이 차단되면",
    "지도 표시 가능 후보",
    'href="#ddareungi-action-1"',
    'id="ddareungi-action-1"',
    "판단 근거 보기",
    "좌표 상태",
    "검토 기준 보기",
    "원천 근거 요약",
    'data-decision="approve"',
    "운영 판단 상태 JSON",
]

FORBIDDEN_VISIBLE_SNIPPETS = [
    ">Control ID<",
    ">SEOUL-IMPACT",
    ">task_",
    "<th>Control ID</th>",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--bike-root", default=str(DEFAULT_BIKE_ROOT))
    parser.add_argument("--workbench-root", default=str(DEFAULT_WORKBENCH_ROOT))
    parser.add_argument("--url", help="Optional live dashboard URL to verify instead of TestClient.")
    return parser.parse_args()


def _html_from_test_client(args: argparse.Namespace) -> str:
    client = TestClient(
        create_app(
            output_root=Path(args.output_root),
            bike_root=Path(args.bike_root),
            workbench_root=Path(args.workbench_root),
            refresh_artifacts=False,
        )
    )
    response = client.get("/dashboard")
    response.raise_for_status()
    return response.text


def _html_from_url(url: str) -> str:
    with urlopen(url, timeout=8) as response:
        return response.read().decode("utf-8")


def verify_dashboard_html(html: str) -> dict[str, int]:
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in html]
    forbidden = [snippet for snippet in FORBIDDEN_VISIBLE_SNIPPETS if snippet in html]
    if missing:
        raise AssertionError(f"dashboard is missing required UI snippets: {missing}")
    if forbidden:
        raise AssertionError(f"dashboard still exposes raw internal labels: {forbidden}")
    return {
        "bytes": len(html.encode("utf-8")),
        "required_checks": len(REQUIRED_SNIPPETS),
        "forbidden_checks": len(FORBIDDEN_VISIBLE_SNIPPETS),
    }


def main() -> None:
    args = parse_args()
    html = _html_from_url(args.url) if args.url else _html_from_test_client(args)
    result = verify_dashboard_html(html)
    print(
        "dashboard ui verification complete: "
        f"bytes={result['bytes']}, "
        f"required_checks={result['required_checks']}, "
        f"forbidden_checks={result['forbidden_checks']}"
    )


if __name__ == "__main__":
    main()
