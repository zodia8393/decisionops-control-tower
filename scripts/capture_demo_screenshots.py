#!/usr/bin/env python3
"""Capture portfolio demo screenshots with Playwright.

This script is intentionally optional: CI does not need a browser, but a local
portfolio package should contain real product screenshots.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any
from urllib.request import urlopen


DEFAULT_URL = "http://127.0.0.1:8093"
DEFAULT_OUTPUT_DIR = Path("docs/assets/demo")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--timeout-ms", type=int, default=15000)
    return parser.parse_args()


def _find_browser() -> str | None:
    for name in ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable"]:
        path = shutil.which(name)
        if path:
            return path
    return None


def _require_healthy(base_url: str) -> dict[str, Any]:
    with urlopen(base_url.rstrip("/") + "/health", timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "ok":
        raise AssertionError(f"health endpoint is not ok: {payload}")
    return payload


def _shot_path(output_dir: Path, name: str) -> Path:
    return output_dir / f"{name}.png"


def capture_screenshots(base_url: str, output_dir: Path, timeout_ms: int = 15000) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Playwright is required for screenshot capture. Install it locally or run this on the workstation with Playwright."
        ) from exc

    health = _require_healthy(base_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    browser_path = _find_browser()
    captures: list[dict[str, Any]] = []

    with sync_playwright() as p:
        launch_args = {"headless": True, "args": ["--no-sandbox"]}
        if browser_path:
            launch_args["executable_path"] = browser_path
        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1100},
            device_scale_factor=1,
            locale="ko-KR",
        )
        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        def capture(name: str, path: str, selector: str | None = None, *, full_page: bool = False) -> None:
            page.goto(base_url.rstrip("/") + path, wait_until="networkidle")
            if selector:
                locator = page.locator(selector).first
                locator.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
            page.screenshot(path=_shot_path(output_dir, name), full_page=full_page)
            if selector:
                locator.screenshot(path=_shot_path(output_dir, f"{name}_section"))
                captures.append(
                    {
                        "name": f"{name}_section",
                        "path": str(_shot_path(output_dir, f"{name}_section")),
                        "url": base_url.rstrip("/") + path,
                        "selector": selector,
                    }
                )
            captures.append(
                {
                    "name": name,
                    "path": str(_shot_path(output_dir, name)),
                    "url": base_url.rstrip("/") + path,
                    "selector": selector,
                    "full_page": full_page,
                }
            )

        capture("dashboard_overview", "/dashboard", full_page=False)
        capture("dashboard_full_page", "/dashboard", full_page=True)
        capture("impact_map", "/dashboard#impact-map", "#impact-map")
        capture("policy_audit", "/dashboard#policy-audit", "#policy-audit")
        capture(
            "reviewer_policy_robustness",
            "/dashboard#policy-robustness",
            "#policy-robustness",
        )
        capture("reviewer_action_plan", "/dashboard#action-plan", "#action-plan")
        capture(
            "reviewer_evidence_bundles",
            "/dashboard#evidence-bundles",
            "#evidence-bundles",
        )
        capture("reviewer_queue", "/dashboard#reviewer-queue", "#reviewer-queue")
        capture("openapi_docs", "/docs", full_page=False)
        context.close()
        browser.close()

    manifest = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_url": base_url,
        "health": {
            "status": health.get("status"),
            "demo_mode_ready": health.get("demo_mode_ready"),
            "public_deploy_decision": health.get("public_deploy_decision"),
            "impact_card_rows": health.get("impact_card_rows"),
            "queue": health.get("queue"),
            "auth_required": health.get("auth_required"),
        },
        "captures": [
            {
                **item,
                "size_bytes": Path(item["path"]).stat().st_size,
            }
            for item in captures
        ],
    }
    manifest_path = output_dir / "demo_screenshot_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def main() -> None:
    args = parse_args()
    manifest = capture_screenshots(args.url, Path(args.output_dir), timeout_ms=args.timeout_ms)
    total_bytes = sum(item["size_bytes"] for item in manifest["captures"])
    print(
        "demo screenshots captured: "
        f"count={len(manifest['captures'])}, "
        f"total_bytes={total_bytes}, "
        f"manifest={manifest['manifest_path']}"
    )


if __name__ == "__main__":
    main()
