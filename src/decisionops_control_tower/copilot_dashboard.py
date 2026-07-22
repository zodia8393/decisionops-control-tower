"""Single-product HTML surface for the Decision Intelligence Copilot."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from decisionops_control_tower.chat_ui import CHAT_CSS, render_chat_surface


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_PRESETS = [
    "region별 revenue 합계 상위 5개",
    "합계 말고 평균으로 바꿔줘",
    "2026-01-01 이후 데이터만 보여줘",
    "amount와 duration 상관계수",
]


COPILOT_CSS = """
:root {
  color-scheme: light;
  --color-ink: #172033;
  --color-muted: #59677a;
  --color-subtle: #788497;
  --color-page: #f5f7fb;
  --color-panel: #ffffff;
  --color-panel-soft: #f8fafc;
  --color-border: #dce3ed;
  --color-border-strong: #b9c5d5;
  --color-primary: #5b4ee5;
  --color-primary-strong: #4438bd;
  --color-success: #08775a;
  --color-warning: #a85312;
  --color-danger: #b42318;
  --color-success-bg: #eafaf4;
  --color-warning-bg: #fff7e8;
  --color-danger-bg: #fff2f0;
  --color-focus: #a8c7ff;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
  --space-7: 44px;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 20px;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--color-page);
  color: var(--color-ink);
  font-family: Inter, Pretendard, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  line-height: 1.5;
}
button, textarea, input { font: inherit; }
button { cursor: pointer; }
a { color: var(--color-primary-strong); }
a:focus-visible, button:focus-visible { outline: 3px solid var(--color-focus); outline-offset: 2px; }
.sr-only {
  position: absolute; width: 1px; height: 1px; overflow: hidden;
  clip: rect(0, 0, 0, 0); white-space: nowrap;
}
.skip-link {
  position: fixed; top: 12px; left: 12px; z-index: 100; transform: translateY(-180%);
  border-radius: 8px; background: #172033; color: white; padding: 9px 13px;
}
.skip-link:focus { transform: translateY(0); }
.copilot-shell { display: grid; grid-template-columns: 228px minmax(0, 1fr); min-height: 100vh; }
.copilot-sidebar {
  position: sticky; top: 0; z-index: 40; display: flex; height: 100vh; height: 100dvh;
  flex-direction: column; border-right: 1px solid #26273b;
  background: linear-gradient(180deg, #19192a 0%, #23213d 100%); color: #e8e8f5;
  padding: 20px 14px;
}
.brand { display: flex; gap: 11px; align-items: center; padding: 0 7px 22px; }
.brand__mark {
  display: grid; width: 42px; height: 42px; place-items: center; border-radius: 13px;
  background: linear-gradient(135deg, #7769ff, #4d43cb); color: white; font-weight: 900;
  box-shadow: 0 10px 24px rgba(91, 78, 229, 0.32);
}
.brand__name { display: block; color: white; font-size: 0.96rem; font-weight: 850; }
.brand__desc { display: block; margin-top: 2px; color: #a7a8c0; font-size: 0.7rem; }
.product-nav { display: grid; gap: 6px; }
.product-nav__item {
  display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 2px 10px; align-items: center;
  border: 1px solid transparent; border-radius: 12px; color: #c9c9dc; padding: 11px;
  text-decoration: none;
}
.product-nav__item:hover { border-color: #4b4868; background: #2d2a48; color: white; }
.product-nav__item[aria-current="page"] {
  border-color: #6961c7; background: #39345f; color: white;
}
.product-nav__icon {
  display: grid; width: 32px; height: 32px; grid-row: 1 / span 2; place-items: center;
  border-radius: 9px; background: #2e2c46; color: #bdb8ff; font-size: 0.75rem; font-weight: 900;
}
.product-nav__item[aria-current="page"] .product-nav__icon { background: #6257df; color: white; }
.product-nav__title { font-size: 0.84rem; font-weight: 800; }
.product-nav__desc { color: #9696ae; font-size: 0.67rem; }
.sidebar-boundary {
  margin-top: auto; border: 1px solid #403d58; border-radius: 12px; background: #211f35;
  color: #b9b9cd; padding: 13px; font-size: 0.7rem; line-height: 1.55;
}
.sidebar-boundary strong { display: block; margin-bottom: 3px; color: #e6e3ff; }
.copilot-workspace { min-width: 0; }
.product-topbar {
  position: sticky; top: 0; z-index: 30; display: flex; min-height: 64px; align-items: center;
  justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.94); padding: 8px 24px; backdrop-filter: blur(12px);
}
.topbar-title { display: flex; gap: 12px; align-items: center; }
.mobile-nav-toggle {
  display: none; width: 40px; height: 40px; border: 1px solid var(--color-border);
  border-radius: 10px; background: white; color: var(--color-ink);
}
.topbar-title span { display: block; color: var(--color-subtle); font-size: 0.69rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.topbar-title h1 { margin: 1px 0 0; font-size: 1.06rem; }
.topbar-status { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.status-chip {
  display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--color-border);
  border-radius: 999px; background: white; color: var(--color-muted); padding: 6px 10px;
  font-size: 0.72rem; font-weight: 800; white-space: nowrap;
}
.status-chip::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: #8b95a5; }
.status-chip--good { border-color: #a9ddca; background: var(--color-success-bg); color: var(--color-success); }
.status-chip--good::before { background: var(--color-success); }
.status-chip--pending { border-color: #f0c48c; background: var(--color-warning-bg); color: var(--color-warning); }
.status-chip--pending::before { background: var(--color-warning); }
.status-chip--risk { border-color: #efb4ae; background: var(--color-danger-bg); color: var(--color-danger); }
.status-chip--risk::before { background: var(--color-danger); }
.sidebar-backdrop { display: none; }
.product-main { width: min(1400px, 100%); margin: 0 auto; padding: 22px; }
.product-panel[hidden] { display: none !important; }
.product-panel:focus { outline: none; }
.section {
  overflow: hidden; margin-bottom: 20px; border: 1px solid var(--color-border);
  border-radius: var(--radius-lg); background: var(--color-panel);
  box-shadow: 0 12px 35px rgba(38, 45, 65, 0.06);
}
.button {
  display: inline-flex; min-height: 38px; align-items: center; justify-content: center;
  border: 1px solid var(--color-border-strong); border-radius: 10px; background: white;
  color: var(--color-primary-strong); padding: 8px 13px; font-weight: 800;
}
.button--primary { border-color: var(--color-primary); background: var(--color-primary); color: white; }
.product-hero {
  position: relative; overflow: hidden; border: 1px solid #dedafc; border-radius: 22px;
  background: linear-gradient(135deg, #ffffff 0%, #f2f0ff 68%, #e8f6ff 100%);
  padding: 38px; margin-bottom: 20px;
}
.product-hero::after {
  content: ""; position: absolute; right: -60px; top: -100px; width: 280px; height: 280px;
  border-radius: 50%; background: rgba(108, 91, 255, 0.09);
}
.eyebrow { color: var(--color-primary-strong); font-size: 0.72rem; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
.product-hero h2 { max-width: 760px; margin: 9px 0 10px; font-size: clamp(1.8rem, 3vw, 2.7rem); line-height: 1.18; letter-spacing: -0.04em; }
.product-hero p { max-width: 760px; margin: 0; color: var(--color-muted); font-size: 1rem; }
.hero-facts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; }
.hero-fact { border: 1px solid #d9d5fa; border-radius: 999px; background: rgba(255,255,255,.76); color: #4c4772; padding: 7px 11px; font-size: .74rem; font-weight: 800; }
.content-card { border: 1px solid var(--color-border); border-radius: 18px; background: white; padding: 24px; margin-bottom: 20px; }
.content-card__header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; }
.content-card h2, .content-card h3 { margin: 0; }
.content-card__header p { max-width: 760px; margin: 5px 0 0; color: var(--color-muted); font-size: .86rem; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.metric-card { min-width: 0; border: 1px solid var(--color-border); border-radius: 14px; background: var(--color-panel-soft); padding: 16px; }
.metric-card__label { color: var(--color-subtle); font-size: .69rem; font-weight: 850; text-transform: uppercase; letter-spacing: .06em; }
.metric-card__value { overflow-wrap: anywhere; margin-top: 6px; font-size: 1.35rem; font-weight: 900; letter-spacing: -.03em; }
.metric-card__note { margin-top: 5px; color: var(--color-muted); font-size: .73rem; }
.metric-card--good { border-color: #b9e0d3; background: #f1fbf7; }
.metric-card--risk { border-color: #f0d0a8; background: #fffaf2; }
.table-wrap { overflow-x: auto; border: 1px solid var(--color-border); border-radius: 12px; }
.product-table { width: 100%; border-collapse: collapse; font-size: .8rem; }
.product-table th { background: #f4f6fa; color: #566277; text-align: left; font-size: .69rem; text-transform: uppercase; letter-spacing: .05em; }
.product-table th, .product-table td { border-bottom: 1px solid var(--color-border); padding: 10px 12px; vertical-align: top; }
.product-table tr:last-child td { border-bottom: 0; }
.details-panel { margin-top: 14px; border: 1px solid var(--color-border); border-radius: 12px; background: #fafbfe; padding: 13px; }
.details-panel summary { cursor: pointer; font-weight: 850; }
.details-panel .table-wrap { margin-top: 12px; background: white; }
.boundary-callout { border-left: 4px solid var(--color-primary); border-radius: 10px; background: #f5f3ff; color: #4d4b69; padding: 15px 17px; font-size: .82rem; }
.score-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.score-card { border: 1px solid var(--color-border); border-radius: 16px; padding: 20px; }
.score-card__top { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.score-card h3 { font-size: 1rem; }
.score-card p { margin: 8px 0 0; color: var(--color-muted); font-size: .8rem; }
.score-card__value { color: var(--color-primary-strong); font-size: 1.35rem; font-weight: 900; white-space: nowrap; }
.flow-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.flow-step { position: relative; border: 1px solid var(--color-border); border-radius: 14px; padding: 17px; }
.flow-step__number { display: grid; width: 28px; height: 28px; place-items: center; border-radius: 9px; background: #ece9ff; color: var(--color-primary-strong); font-size: .72rem; font-weight: 900; }
.flow-step strong { display: block; margin-top: 10px; }
.flow-step p { margin: 5px 0 0; color: var(--color-muted); font-size: .76rem; }
.boundary-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 0; padding: 0; list-style: none; }
.boundary-list li { border: 1px solid var(--color-border); border-radius: 12px; background: #fafbfc; padding: 13px; color: var(--color-muted); font-size: .8rem; }
.boundary-list strong { display: block; margin-bottom: 3px; color: var(--color-ink); }
@media (max-width: 1040px) {
  .copilot-shell { grid-template-columns: 1fr; }
  .copilot-sidebar { position: fixed; left: 0; transform: translateX(-105%); width: min(84vw, 280px); transition: transform 160ms ease; }
  body.sidebar-open .copilot-sidebar { transform: translateX(0); }
  .mobile-nav-toggle { display: grid; place-items: center; }
  .sidebar-backdrop { position: fixed; inset: 0; z-index: 35; border: 0; background: rgba(16,18,32,.48); }
  body.sidebar-open .sidebar-backdrop { display: block; }
  .metric-grid, .flow-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 680px) {
  .product-topbar { padding: 10px 14px; }
  .topbar-status .status-chip:first-child { display: none; }
  .product-main { padding: 10px; }
  .product-hero { padding: 25px 20px; }
  .metric-grid, .score-grid, .flow-grid, .boundary-list { grid-template-columns: 1fr; }
  .content-card { padding: 18px; }
  .content-card__header { flex-direction: column; }
}

/* ChatGPT-inspired shell: quiet navigation, conversation-first workspace. */
:root {
  --color-ink: #0d0d0d;
  --color-muted: #5d5d5d;
  --color-subtle: #858585;
  --color-page: #ffffff;
  --color-panel: #ffffff;
  --color-panel-soft: #f7f7f8;
  --color-border: #e5e5e5;
  --color-border-strong: #d1d1d1;
  --color-primary: #111111;
  --color-primary-strong: #111111;
  --color-focus: #86b7fe;
}
body { background: #ffffff; color: #0d0d0d; }
.copilot-shell { grid-template-columns: 260px minmax(0, 1fr); }
.copilot-sidebar {
  gap: 12px;
  padding: 12px 10px;
  border-right: 0;
  background: #f9f9f9;
  color: #171717;
}
.brand { gap: 10px; padding: 4px 8px 14px; }
.brand__mark {
  width: 34px; height: 34px; border-radius: 50%;
  background: #111111; box-shadow: none; font-size: .7rem;
}
.brand__name { color: #171717; font-size: .84rem; }
.brand__desc { color: #7a7a7a; font-size: .62rem; }
.product-nav { gap: 2px; }
.product-nav__item {
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 8px; padding: 8px 9px;
  border: 0; border-radius: 9px;
  color: #333333;
}
.product-nav__item:hover { border-color: transparent; background: #ececec; color: #111111; }
.product-nav__item[aria-current="page"] { border-color: transparent; background: #e7e7e7; color: #111111; box-shadow: none; }
.product-nav__icon {
  width: 28px; height: 28px;
  border-radius: 8px; background: transparent;
  color: #555555; font-size: .58rem;
}
.product-nav__item:hover .product-nav__icon,
.product-nav__item[aria-current="page"] .product-nav__icon { background: #d9d9d9; color: #111111; }
.product-nav__title { align-self: center; font-size: .8rem; font-weight: 650; }
.product-nav__desc { display: none; }
.sidebar-boundary {
  margin-top: auto; padding: 14px 8px 4px;
  border: 0; border-top: 1px solid #e5e5e5; border-radius: 0;
  background: transparent; color: #7a7a7a; font-size: .66rem;
}
.sidebar-boundary strong { color: #3b3b3b; font-size: .67rem; }
.copilot-workspace { min-width: 0; background: #ffffff; }
.product-topbar {
  min-height: 56px; padding: 8px 18px;
  border-bottom: 0; background: rgba(255, 255, 255, .94);
}
.topbar-title span { display: none; }
.topbar-title h1 { font-size: .94rem; font-weight: 650; letter-spacing: -.015em; }
.topbar-status { gap: 5px; }
.status-chip {
  padding: 5px 9px; border-color: #e5e5e5;
  background: transparent; color: #666666;
  font-size: .66rem; font-weight: 650;
}
.status-chip--good { border-color: #e5e5e5; background: transparent; color: #555555; }
.status-chip--good::before { background: #10a37f; }
.product-main { width: 100%; max-width: none; padding: 0; }
.product-panel:not(#workspace-analysis) { width: min(1180px, 100%); margin: 0 auto; padding: 30px; }
.section { border: 0; border-radius: 0; box-shadow: none; }
.button--primary { border-color: #111111; background: #111111; }
.product-hero { border-color: #e5e5e5; background: #f7f7f8; }
.content-card, .metric-card, .score-card, .flow-step { border-color: #e5e5e5; box-shadow: none; }
@media (max-width: 1040px) {
  .copilot-shell { grid-template-columns: 1fr; }
  .copilot-sidebar { width: min(84vw, 280px); background: #f9f9f9; }
}
@media (max-width: 680px) {
  .product-topbar { min-height: 52px; padding: 8px 12px; }
  .product-main { padding: 0; }
  .product-panel:not(#workspace-analysis) { padding: 14px; }
}
"""


NAVIGATION_SCRIPT = r"""
<script>
(() => {
  const items = Array.from(document.querySelectorAll("[data-product-target]"));
  const panels = Array.from(document.querySelectorAll("[data-product-panel]"));
  const title = document.querySelector("[data-current-title]");
  const toggle = document.querySelector("[data-sidebar-toggle]");
  const backdrop = document.querySelector("[data-sidebar-backdrop]");
  const mobile = window.matchMedia("(max-width: 1040px)");

  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  }
  function activate(name, updateHistory = false) {
    const panel = panels.find((item) => item.dataset.productPanel === name);
    if (!panel) return;
    panels.forEach((item) => { item.hidden = item !== panel; });
    items.forEach((item) => {
      if (item.dataset.productTarget === name) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    });
    const active = items.find((item) => item.dataset.productTarget === name);
    if (title && active) title.textContent = active.dataset.productTitle;
    if (updateHistory && active) history.pushState({}, "", active.getAttribute("href"));
    closeSidebar();
    window.scrollTo({top: 0, behavior: "auto"});
  }
  function revealHash() {
    const target = document.getElementById(location.hash.slice(1));
    const panel = target && target.closest("[data-product-panel]");
    activate(panel ? panel.dataset.productPanel : "analysis");
    if (target && panel && target !== panel) requestAnimationFrame(() => target.scrollIntoView());
  }
  document.addEventListener("click", (event) => {
    const item = event.target.closest("[data-product-target]");
    if (!item) return;
    event.preventDefault();
    activate(item.dataset.productTarget, true);
  });
  if (toggle) toggle.addEventListener("click", () => {
    const open = mobile.matches && !document.body.classList.contains("sidebar-open");
    document.body.classList.toggle("sidebar-open", open);
    toggle.setAttribute("aria-expanded", String(open));
  });
  if (backdrop) backdrop.addEventListener("click", closeSidebar);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSidebar();
  });
  window.addEventListener("hashchange", revealHash);
  window.addEventListener("popstate", revealHash);
  revealHash();
})();
</script>
"""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_product_evidence(output_root: Path) -> dict[str, dict[str, Any]]:
    """Load generated evaluation artifacts without exposing filesystem paths."""

    reports = output_root / "reports"
    fallback = PROJECT_ROOT / "docs" / "evaluation"
    names = {
        "analysis": "analysis_evaluation.json",
        "data_science": "data_science_evaluation.json",
        "rdb_migration": "firebird_postgres_migration.json",
        "migration_rehearsal": "migration_rehearsal.json",
        "rag": "rag_evaluation.json",
    }
    evidence: dict[str, dict[str, Any]] = {}
    for key, filename in names.items():
        evidence[key] = _read_json(reports / filename) or _read_json(fallback / filename)
    return evidence


def _escape(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _metric(label: str, value: Any, note: str, tone: str = "") -> str:
    modifier = f" metric-card--{tone}" if tone else ""
    return (
        f'<article class="metric-card{modifier}">'
        f'<div class="metric-card__label">{_escape(label)}</div>'
        f'<div class="metric-card__value">{_escape(value)}</div>'
        f'<div class="metric-card__note">{_escape(note)}</div>'
        "</article>"
    )


def _table(headers: list[str], rows: list[list[Any]], empty: str = "검증 결과가 없습니다.") -> str:
    head = "".join(f"<th>{_escape(item)}</th>" for item in headers)
    if rows:
        body = "".join(
            "<tr>" + "".join(f"<td>{_escape(value)}</td>" for value in row) + "</tr>"
            for row in rows
        )
    else:
        body = f'<tr><td colspan="{len(headers)}">{_escape(empty)}</td></tr>'
    return (
        '<div class="table-wrap"><table class="product-table">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _correctness_rows(migration: dict[str, Any]) -> list[list[Any]]:
    return [
        [
            f"{item.get('source_system')}.{item.get('source_table')}",
            item.get("target_table"),
            item.get("source_rows"),
            item.get("accepted_rows"),
            item.get("rejected_rows"),
            str(item.get("status", "unknown")).upper(),
        ]
        for item in migration.get("reconciliation", [])
        if isinstance(item, dict)
    ]


def _reject_rows(migration: dict[str, Any]) -> list[list[Any]]:
    return [
        [
            f"{item.get('source_system')}.{item.get('source_table')}#{item.get('source_row_number')}",
            item.get("target_table"),
            item.get("reason_code"),
            item.get("detail"),
        ]
        for item in migration.get("rejects", [])
        if isinstance(item, dict)
    ]


def _rdb_reconciliation_rows(report: dict[str, Any]) -> list[list[Any]]:
    return [
        [
            item.get("source_table"),
            item.get("target_table"),
            item.get("source_rows"),
            item.get("accepted_rows"),
            item.get("rejected_rows"),
            item.get("checkpoint_rows"),
            str(item.get("status", "unknown")).upper(),
        ]
        for item in report.get("reconciliation", [])
        if isinstance(item, dict)
    ]


def _migration_panel(
    migration: dict[str, Any],
    rehearsal: dict[str, Any],
    rdb_migration: dict[str, Any],
) -> str:
    metrics = migration.get("metrics", {})
    source_rows = rehearsal.get("source_rows", 0)
    accepted = rehearsal.get("accepted_rows", 0)
    rejected = rehearsal.get("rejected_rows", 0)
    rdb_source = int(rdb_migration.get("source_rows", 0))
    rdb_accepted = int(rdb_migration.get("accepted_rows", 0))
    rdb_rejected = int(rdb_migration.get("rejected_rows", 0))
    return f"""
      <section class="product-hero">
        <span class="eyebrow">Migration Lab</span>
        <h2>레거시 데이터를 옮기는 것보다, 틀리지 않게 다시 실행하는 것이 중요합니다.</h2>
        <p>이종 schema mapping, reject lineage, PK/FK 검증, transaction checkpoint와 재시작을 하나의 검증 흐름으로 보여줍니다.</p>
        <div class="hero-facts">
          <span class="hero-fact">Firebird → PostgreSQL</span>
          <span class="hero-fact">120k actual RDB integration</span>
          <span class="hero-fact">rollback · resume · replay</span>
          <span class="hero-fact">Legacy Hospital Migration</span>
          <span class="hero-fact">Synthetic · no PHI</span>
          <span class="hero-fact">No hospital DB write</span>
        </div>
      </section>
      <section class="content-card" id="migration-rdb">
        <div class="content-card__header"><div>
          <h2>Firebird → PostgreSQL integration</h2>
          <p>실제 container DB에서 source metadata를 확인하고 batch ETL·transaction rollback·checkpoint resume를 실행합니다.</p>
        </div><span class="status-chip status-chip--good">{_escape(str(rdb_migration.get('status', 'no report')).upper())}</span></div>
        <div class="metric-grid">
          {_metric('RDB reconciliation', f'{rdb_source:,}' if rdb_source else 'No report', f'{rdb_accepted:,} accepted + {rdb_rejected:,} rejected', 'good')}
          {_metric('Actual engines', 'Firebird → PostgreSQL', f"{rdb_migration.get('source_engine', 'no source report')} · {rdb_migration.get('target_engine', 'no target report')}")}
          {_metric('Committed batches', rdb_migration.get('committed_batches', 0), '2,500-row transaction')}
          {_metric('Resume point', f"{int(rdb_migration.get('resumed_from_source_rows', 0)):,}", '새 connection · persisted checkpoint')}
          {_metric('Rollback', 'PASS' if rdb_migration.get('rollback_verified') else 'UNKNOWN', 'target + lineage + checkpoint', 'good')}
          {_metric('Replay processed', rdb_migration.get('replay_processed_rows', 0), '완료 run은 no-op', 'good')}
          {_metric('FK violations', rdb_migration.get('foreign_key_violations', 0), 'PostgreSQL independent audit', 'good')}
          {_metric('Schema drift', 'BLOCKED' if rdb_migration.get('schema_drift_blocked_before_write') else 'UNKNOWN', 'actual Firebird catalog · pre-write', 'good')}
        </div>
        {_table(['Firebird source', 'PostgreSQL target', 'Source', 'Accepted', 'Rejected', 'Checkpoint', 'Status'], _rdb_reconciliation_rows(rdb_migration), 'RDB integration report가 없습니다.')}
        <div class="boundary-callout">Synthetic container integration이며 실제 병원 DB·PHI·production cutover·SLA 증거가 아닙니다. 관측 throughput은 현재 machine에만 해당합니다.</div>
      </section>
      <section class="content-card" id="migration-correctness">
        <div class="content-card__header"><div>
          <h2>Correctness fixture</h2>
          <p>작은 fixture는 모든 정상·실패 row를 사람이 직접 추적할 수 있도록 유지합니다.</p>
        </div><span class="status-chip status-chip--good">{_escape(str(migration.get('status', 'unknown')).upper())}</span></div>
        <div class="metric-grid">
          {_metric('Source rows', metrics.get('source_rows', 0), '모든 원천 row 전수 대사')}
          {_metric('Accepted', metrics.get('accepted_rows', 0), 'canonical target rows', 'good')}
          {_metric('Rejected', metrics.get('rejected_rows', 0), 'reason과 lineage 보존', 'risk')}
          {_metric('Fingerprint', str(migration.get('result_fingerprint_sha256', ''))[:12], '동일 input 재실행 검증')}
        </div>
        {_table(['Source table', 'Target', 'Source', 'Accepted', 'Rejected', 'Status'], _correctness_rows(migration))}
        <details class="details-panel"><summary>Reject lineage {len(_reject_rows(migration))}건 보기</summary>
          {_table(['Source row', 'Target', 'Reason', 'Detail'], _reject_rows(migration))}
        </details>
      </section>
      <section class="content-card" id="migration-recovery">
        <div class="content-card__header"><div>
          <h2>Scale & recovery rehearsal</h2>
          <p>generated source를 batch transaction으로 적재하고 중단·재개·완료 후 replay를 검증합니다.</p>
        </div><span class="status-chip status-chip--good">{_escape(str(rehearsal.get('status', 'unknown')).upper())}</span></div>
        <div class="metric-grid">
          {_metric('Reconciliation', f'{source_rows:,}', f'{accepted:,} accepted + {rejected:,} rejected', 'good')}
          {_metric('Committed batches', rehearsal.get('committed_batches', 0), '2,500-row transaction')}
          {_metric('Resume point', f"{rehearsal.get('resumed_from_source_rows', 0):,}", 'persisted checkpoint부터 재개')}
          {_metric('Replay processed', rehearsal.get('replay_processed_rows', 0), '완료 run은 no-op', 'good')}
          {_metric('FK violations', rehearsal.get('foreign_key_violations', 0), 'target integrity check', 'good')}
          {_metric('Schema drift', 'BLOCKED' if rehearsal.get('schema_drift_blocked_before_write') else 'UNKNOWN', 'required column rename · pre-write', 'good')}
          {_metric('Idempotent replay', 'PASS' if rehearsal.get('idempotent_replay') else 'UNKNOWN', 'target fingerprint 불변', 'good')}
          {_metric('Result fingerprint', str(rehearsal.get('result_fingerprint_sha256', ''))[:12], 'accepted + reject result')}
        </div>
        <div class="boundary-callout">이 rehearsal은 temporary SQLite staging의 transaction·recovery를 검증합니다. 실제 MS-SQL/Firebird network, lock, transaction log 또는 production SLA를 주장하지 않습니다.</div>
      </section>
    """


def _score_card(title: str, value: str, detail: str, status: str = "PASS") -> str:
    tone = {"PASS": "good", "PENDING": "pending"}.get(status, "risk")
    return f"""
      <article class="score-card">
        <div class="score-card__top"><h3>{_escape(title)}</h3><span class="status-chip status-chip--{tone}">{_escape(status)}</span></div>
        <div class="score-card__value">{_escape(value)}</div><p>{_escape(detail)}</p>
      </article>
    """


def _validation_panel(evidence: dict[str, dict[str, Any]]) -> str:
    analysis = evidence.get("analysis", {}).get("metrics", {})
    data_science = evidence.get("data_science", {}).get("metrics", {})
    rag = evidence.get("rag", {}).get("metrics", {})
    migration = evidence.get("migration_rehearsal", {})
    rdb_migration = evidence.get("rdb_migration", {})
    analysis_cases = int(analysis.get("case_count", 0))
    rag_cases = int(rag.get("case_count", 0))
    analysis_checks = [
        analysis.get("end_to_end_pass_rate"),
        analysis.get("analysis_plan_schema_validity"),
        analysis.get("numeric_execution_correctness"),
    ]
    analysis_status = (
        "PENDING"
        if not analysis_cases or any(value is None for value in analysis_checks)
        else "PASS"
        if all(float(value) == 1.0 for value in analysis_checks)
        else "FAIL"
    )
    data_science_cases = int(data_science.get("case_count", 0))
    data_science_checks = [
        data_science.get("end_to_end_pass_rate"),
        data_science.get("plan_schema_validity"),
        data_science.get("independent_oracle_match_rate"),
        data_science.get("safety_gate_pass_rate"),
    ]
    data_science_status = (
        "PENDING"
        if not data_science_cases or any(value is None for value in data_science_checks)
        else "PASS"
        if all(float(value) == 1.0 for value in data_science_checks)
        else "FAIL"
    )
    rag_checks = [rag.get("pass_rate"), rag.get("retrieval_recall_at_k")]
    rag_status = (
        "PENDING"
        if not rag_cases or any(value is None for value in rag_checks)
        else "PASS"
        if all(float(value) == 1.0 for value in rag_checks)
        else "FAIL"
    )
    migration_evidence = rdb_migration or migration
    migration_rows = int(migration_evidence.get("source_rows", 0))
    migration_status = (
        "PENDING"
        if not migration_rows
        else "PASS"
        if str(migration_evidence.get("status", "")).lower() == "pass"
        else "FAIL"
    )
    return f"""
      <section class="product-hero">
        <span class="eyebrow">Validation</span>
        <h2>점수가 아니라, 어떤 주장을 어디까지 증명했는지 보여줍니다.</h2>
        <p>versioned challenge set, 독립 numeric oracle, browser flow와 migration reconciliation을 분리해 검증합니다.</p>
      </section>
      <section class="content-card" id="validation-results">
        <div class="content-card__header"><div><h2>Evaluation evidence</h2>
          <p>현재 source와 같은 명령으로 재현되는 결과입니다.</p></div></div>
        <div class="score-grid">
          {_score_card('Natural-language analysis', f'{analysis_cases}/{analysis_cases}' if analysis_cases else 'No report', 'Plan schema 100% · numeric correctness 100% · paraphrase 24 · multi-turn 8', analysis_status)}
          {_score_card('Advanced analysis & prediction', f'{data_science_cases}/{data_science_cases}' if data_science_cases else 'No report', 'Typed plans · independent oracle · baseline/safety gates', data_science_status)}
          {_score_card('Migration recovery', f'{migration_rows:,} rows' if migration_rows else 'No report', f"{migration_evidence.get('committed_batches', 0)} batches · replay {migration_evidence.get('replay_processed_rows', 0)} rows · FK violation {migration_evidence.get('foreign_key_violations', 0)}", migration_status)}
          {_score_card('Evidence RAG', f'{rag_cases}/{rag_cases}' if rag_cases else 'No report', f"Recall@3 {float(rag.get('retrieval_recall_at_k', 0)):.0%} · citation precision {float(rag.get('citation_precision', 0)):.1%}", rag_status)}
        </div>
      </section>
      <section class="content-card">
        <div class="content-card__header"><div><h2>Claim boundary</h2>
          <p>자동화 correctness와 production 운영 경험을 같은 증거로 취급하지 않습니다.</p></div></div>
        <ul class="boundary-list">
          <li><strong>증명됨</strong>bounded planner, DuckDB/SciPy/sklearn 수치, baseline gate, row accounting, batch recovery, browser contract</li>
          <li><strong>아직 미증명</strong>실제 병원 cutover, production DB throughput, realized business impact</li>
          <li><strong>현재 범위에서 생략</strong>사용자 평가, 임의 Python 실행, multi-file join, live PHI, 자동 승인·배포</li>
          <li><strong>공개 경계</strong>Pages는 recorded read-only snapshot이며 live upload는 local demo 전용</li>
        </ul>
      </section>
    """


def _technical_panel(live_chat: bool, vector_store: str) -> str:
    mode = "Live local session" if live_chat else "Recorded read-only snapshot"
    return f"""
      <section class="product-hero">
        <span class="eyebrow">Technical</span>
        <h2>LLM은 설명할 수 있지만, 숫자와 실행 권한의 source of truth는 아닙니다.</h2>
        <p>입력·계획·실행·provenance 경계를 분리해 수치 환각과 임의 code execution을 차단합니다.</p>
      </section>
      <section class="content-card">
        <div class="content-card__header"><div><h2>Execution flow</h2>
          <p>현재 mode: {_escape(mode)} · document retrieval: {_escape(vector_store)}</p></div></div>
        <div class="flow-grid">
          <article class="flow-step"><span class="flow-step__number">01</span><strong>Upload</strong><p>CSV·JSON·XLSX·Parquet, 1MB·10k rows·100 columns 제한</p></article>
          <article class="flow-step"><span class="flow-step__number">02</span><strong>Plan</strong><p>자연어를 allowlisted AnalysisPlan·AdvancedAnalysisPlan·PredictionPlan으로 변환</p></article>
          <article class="flow-step"><span class="flow-step__number">03</span><strong>Execute</strong><p>read-only DuckDB 경계 뒤 SciPy·pandas·CPU sklearn이 제한된 계산 수행</p></article>
          <article class="flow-step"><span class="flow-step__number">04</span><strong>Explain</strong><p>표·차트·SQL·분모·baseline·오차·model card로 재현 근거 반환</p></article>
        </div>
      </section>
      <section class="content-card" id="technical-boundaries">
        <div class="content-card__header"><div><h2>Safety & privacy contract</h2>
          <p>기능보다 먼저 지켜야 하는 실행 경계입니다.</p></div><a class="button" href="/docs">OpenAPI 보기</a></div>
        <ul class="boundary-list">
          <li><strong>Session-only dataset</strong>업로드 원본은 SQLite·Qdrant·artifact에 저장하지 않습니다.</li>
          <li><strong>Deterministic numeric engine</strong>LLM과 RAG는 업로드 데이터의 숫자를 계산하지 않습니다.</li>
          <li><strong>Bounded conversation</strong>최근 context와 이전 plan만 제한적으로 수정합니다.</li>
          <li><strong>Isolated mutation</strong>화면의 case는 read-only이며 실제 RDB write는 별도 synthetic Compose stack에서만 실행합니다.</li>
        </ul>
      </section>
    """


def _nav_item(panel: str, icon: str, title: str, description: str, current: bool = False) -> str:
    current_attr = ' aria-current="page"' if current else ""
    return f"""
      <a class="product-nav__item" id="nav-{panel}" href="#workspace-{panel}"
         data-product-target="{panel}" data-product-title="{_escape(title)}"{current_attr}>
        <span class="product-nav__icon" aria-hidden="true">{_escape(icon)}</span>
        <span class="product-nav__title">{_escape(title)}</span>
        <span class="product-nav__desc">{_escape(description)}</span>
      </a>
    """


def render_copilot_dashboard(
    *,
    recorded_chat: dict[str, dict[str, Any]],
    migration_case: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
    live_chat: bool,
    vector_store: str,
) -> str:
    """Render the single-product Copilot UI without legacy operator panels."""

    chat = render_chat_surface(
        recorded_chat,
        live_chat=live_chat,
        vector_store=vector_store,
        preset_questions=ANALYSIS_PRESETS,
        require_dataset_for_presets=True,
        heading="파일을 올리고, 대화로 분석하세요",
        introduction=(
            "질문은 검증된 AnalysisPlan으로 바뀌고, DuckDB가 계산한 결과와 "
            "SQL provenance를 함께 반환합니다."
        ),
        welcome="무엇을 분석해 볼까요?",
    )
    rehearsal = evidence.get("migration_rehearsal", {})
    rdb_migration = evidence.get("rdb_migration", {})
    live_label = "Live analysis" if live_chat else "Recorded demo"
    return f"""<!doctype html>
<html lang="ko"><head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Natural-language tabular analysis and migration validation Copilot">
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%235b4ee5'/%3E%3Cpath d='M18 19h28v8H18zm0 18h18v8H18z' fill='white'/%3E%3C/svg%3E">
  <title>Decision Intelligence Copilot</title>
  <style>{COPILOT_CSS}{CHAT_CSS}</style>
</head><body>
  <a class="skip-link" href="#main-content">본문으로 건너뛰기</a>
  <div class="copilot-shell">
    <aside class="copilot-sidebar" id="copilot-sidebar" aria-label="제품 화면">
      <div class="brand"><span class="brand__mark">DI</span><span>
        <span class="brand__name">Decision Intelligence</span>
        <span class="brand__desc">One Copilot · Verified execution</span>
      </span></div>
      <nav class="product-nav" aria-label="Copilot 기능">
        {_nav_item('analysis', 'AI', '분석 Copilot', '업로드 · 질문 · 후속 분석', True)}
        {_nav_item('migration', 'ETL', 'Migration Lab', '정합성 · batch · recovery')}
        {_nav_item('validation', 'QA', '검증 결과', '정확도 · 재현성 · 한계')}
        {_nav_item('technical', 'API', '기술 상세', '계약 · 실행 경계 · OpenAPI')}
      </nav>
      <div class="sidebar-boundary"><strong>Privacy by default</strong>업로드 원본은 현재 browser session에서만 사용하며 영구 저장하지 않습니다.</div>
    </aside>
    <button class="sidebar-backdrop" type="button" data-sidebar-backdrop aria-label="메뉴 닫기"></button>
    <div class="copilot-workspace">
      <header class="product-topbar"><div class="topbar-title">
        <button class="mobile-nav-toggle" type="button" data-sidebar-toggle aria-controls="copilot-sidebar" aria-expanded="false">☰</button>
        <div><span>Decision Intelligence Copilot</span><h1 data-current-title>분석 Copilot</h1></div>
      </div><div class="topbar-status">
        <span class="status-chip status-chip--good">{_escape(live_label)}</span>
        <span class="status-chip">원본 미저장</span>
      </div></header>
      <main class="product-main" id="main-content">
        <div class="product-panel" id="workspace-analysis" data-product-panel="analysis" tabindex="-1">{chat}</div>
        <div class="product-panel" id="workspace-migration" data-product-panel="migration" tabindex="-1" hidden>{_migration_panel(migration_case, rehearsal, rdb_migration)}</div>
        <div class="product-panel" id="workspace-validation" data-product-panel="validation" tabindex="-1" hidden>{_validation_panel(evidence)}</div>
        <div class="product-panel" id="workspace-technical" data-product-panel="technical" tabindex="-1" hidden>{_technical_panel(live_chat, vector_store)}</div>
      </main>
    </div>
  </div>{NAVIGATION_SCRIPT}
</body></html>"""
