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
    console_errors: list[str] = []
    qa: dict[str, Any] = {}

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
        page.on(
            "console",
            lambda message: console_errors.append(message.text) if message.type == "error" else None,
        )
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
        desktop_targets = [
            "summary",
            "candidates",
            "policy",
            "evidence",
            "review",
            "system",
            "chat",
        ]
        for target in desktop_targets:
            page.locator(f'[data-panel-target="{target}"]').click()
            visible_panels = page.locator("[data-workspace-panel]:visible")
            if visible_panels.count() != 1:
                raise AssertionError(f"desktop sidebar exposed multiple panels after selecting {target}")
            if visible_panels.get_attribute("data-workspace-panel") != target:
                raise AssertionError(f"desktop sidebar did not activate {target}")
        qa["desktop_sidebar_navigation"] = "7/7"
        qa["desktop_default_panel"] = "chat"

        page.goto(base_url.rstrip("/") + "/dashboard", wait_until="networkidle")
        page.locator("[data-chat-question]").first.click()
        page.locator(".chat-response-meta").wait_for(state="visible")
        page.wait_for_timeout(300)
        page.locator("#decision-chat").screenshot(
            path=_shot_path(output_dir, "chat_grounded_response")
        )
        captures.append(
            {
                "name": "chat_grounded_response",
                "path": str(_shot_path(output_dir, "chat_grounded_response")),
                "url": base_url.rstrip("/") + "/dashboard#decision-chat",
                "selector": "#decision-chat",
                "full_page": False,
            }
        )
        qa["desktop_horizontal_overflow"] = page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
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
        capture(
            "approval_audit_integrity",
            "/dashboard#approval-audit-integrity",
            "#approval-audit-integrity",
        )
        capture("reviewer_queue", "/dashboard#reviewer-queue", "#reviewer-queue")
        capture("openapi_docs", "/docs", full_page=False)
        context.close()

        mobile_context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=1,
            locale="ko-KR",
        )
        mobile = mobile_context.new_page()
        mobile.on(
            "console",
            lambda message: console_errors.append(message.text) if message.type == "error" else None,
        )
        mobile.set_default_timeout(timeout_ms)
        mobile.goto(base_url.rstrip("/") + "/dashboard", wait_until="networkidle")
        mobile.screenshot(path=_shot_path(output_dir, "mobile_overview"), full_page=False)
        captures.append(
            {
                "name": "mobile_overview",
                "path": str(_shot_path(output_dir, "mobile_overview")),
                "url": base_url.rstrip("/") + "/dashboard",
                "selector": None,
                "full_page": False,
            }
        )
        mobile.locator("[data-sidebar-toggle]").click()
        mobile.wait_for_timeout(250)
        drawer_box = mobile.locator("#app-sidebar").bounding_box()
        if (
            not mobile.locator("body").evaluate("node => node.classList.contains('sidebar-open')")
            or drawer_box is None
            or drawer_box["x"] < -1
        ):
            raise AssertionError("mobile sidebar drawer did not open")
        mobile.locator('[data-panel-target="summary"]').click()
        if not mobile.locator("#workspace-summary").is_visible():
            raise AssertionError("mobile sidebar did not activate the summary panel")
        if mobile.locator("#workspace-chat").is_visible():
            raise AssertionError("mobile sidebar left the chat panel visible with the summary panel")
        if mobile.locator("body").evaluate("node => node.classList.contains('sidebar-open')"):
            raise AssertionError("mobile sidebar drawer did not close after navigation")
        mobile.locator("[data-sidebar-toggle]").click()
        mobile.wait_for_timeout(250)
        mobile.locator('[data-panel-target="chat"]').click()
        if not mobile.locator("#workspace-chat").is_visible():
            raise AssertionError("mobile sidebar did not return to the chat panel")
        qa["mobile_sidebar_drawer"] = "PASS"
        qa["mobile_sidebar_navigation"] = "summary → chat"

        mobile.locator("[data-chat-question]").first.click()
        mobile.locator(".chat-response-meta").wait_for(state="visible")
        mobile.wait_for_timeout(300)
        mobile.locator("#decision-chat").screenshot(
            path=_shot_path(output_dir, "mobile_chat_grounded_response")
        )
        captures.append(
            {
                "name": "mobile_chat_grounded_response",
                "path": str(_shot_path(output_dir, "mobile_chat_grounded_response")),
                "url": base_url.rstrip("/") + "/dashboard#decision-chat",
                "selector": "#decision-chat",
                "full_page": False,
            }
        )
        qa["mobile_horizontal_overflow"] = mobile.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        mobile_context.close()
        browser.close()

    if qa.get("desktop_horizontal_overflow") or qa.get("mobile_horizontal_overflow"):
        raise AssertionError("dashboard has horizontal overflow")
    if console_errors:
        raise AssertionError(f"dashboard emitted browser console errors: {console_errors}")

    health = _require_healthy(base_url)
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
            "rag": health.get("rag"),
        },
        "captures": [
            {
                **item,
                "size_bytes": Path(item["path"]).stat().st_size,
            }
            for item in captures
        ],
        "qa": {
            **qa,
            "console_errors": console_errors,
        },
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
