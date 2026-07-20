"""Shared HTML renderer for the DecisionOps reviewer dashboard."""

from __future__ import annotations

import html
import math
from typing import Any

from decisionops_control_tower.chat_ui import CHAT_CSS, render_chat_surface


DASHBOARD_CSS = """
:root {
  color-scheme: light;
  --color-ink: #132033;
  --color-muted: #526174;
  --color-subtle: #6b7788;
  --color-page: #f4f6f9;
  --color-panel: #ffffff;
  --color-panel-soft: #f8fafc;
  --color-border: #d8e0ea;
  --color-border-strong: #b7c3d2;
  --color-primary: #0f5f8c;
  --color-primary-strong: #0a4668;
  --color-success: #0f6b4e;
  --color-warning: #a24b12;
  --color-danger: #b42318;
  --color-danger-bg: #fff4f2;
  --color-warning-bg: #fff7ed;
  --color-success-bg: #ecfdf3;
  --color-focus: #8ec5ff;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
  --space-7: 44px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --content-max: 1180px;
}
* {
  box-sizing: border-box;
}
html {
  scroll-behavior: smooth;
}
body {
  margin: 0;
  background: var(--color-page);
  color: var(--color-ink);
  font-family:
    ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 16px;
  line-height: 1.5;
}
a {
  color: var(--color-primary);
}
a:focus-visible,
button:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}
.app-shell {
  min-height: 100vh;
}
.hero {
  background: var(--color-panel);
  border-bottom: 1px solid var(--color-border);
}
.hero__inner,
.main {
  width: min(100%, var(--content-max));
  margin: 0 auto;
  padding-left: var(--space-5);
  padding-right: var(--space-5);
}
.hero__inner {
  padding-top: var(--space-6);
  padding-bottom: var(--space-5);
}
.main {
  padding-top: var(--space-6);
  padding-bottom: var(--space-7);
}
.topline,
.section__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.eyebrow {
  color: var(--color-muted);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}
.hero__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 360px);
  gap: var(--space-6);
  align-items: end;
  margin-top: var(--space-4);
}
h1,
h2,
h3,
p {
  margin: 0;
  letter-spacing: 0;
}
h1 {
  max-width: 760px;
  font-size: 2.5rem;
  line-height: 1.08;
}
h2 {
  font-size: 1.32rem;
  line-height: 1.22;
}
h3 {
  font-size: 1rem;
}
.hero__copy {
  max-width: 760px;
  margin-top: var(--space-4);
  color: var(--color-muted);
  font-size: 1.03rem;
}
.hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-top: var(--space-5);
}
.button,
button {
  appearance: none;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-panel);
  color: var(--color-primary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 9px 13px;
  font: inherit;
  font-size: 0.93rem;
  font-weight: 700;
  line-height: 1.2;
  text-decoration: none;
}
.button:hover,
button:hover {
  border-color: var(--color-primary);
  color: var(--color-primary-strong);
}
.button--primary {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #ffffff;
}
.button--primary:hover {
  border-color: var(--color-primary-strong);
  background: var(--color-primary-strong);
  color: #ffffff;
}
.button--small,
td button {
  min-height: 32px;
  padding: 6px 9px;
  font-size: 0.84rem;
}
button:disabled {
  cursor: wait;
  opacity: 0.62;
}
.readiness-panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-panel-soft);
  padding: var(--space-4);
}
.readiness-panel__title {
  color: var(--color-muted);
  font-size: 0.86rem;
  font-weight: 700;
}
.readiness-list {
  display: grid;
  gap: var(--space-3);
  margin: var(--space-4) 0 0;
  padding: 0;
  list-style: none;
}
.todo-list {
  display: grid;
  gap: var(--space-3);
  margin: var(--space-4) 0 0;
  padding: 0;
  list-style: none;
}
.readiness-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.todo-list li {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: var(--space-3);
  align-items: start;
}
.todo-list strong {
  display: block;
  font-size: 0.94rem;
}
.todo-detail {
  display: block;
  margin-top: 2px;
  color: var(--color-muted);
  font-size: 0.84rem;
}
.todo-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: var(--color-primary);
  color: #ffffff;
  font-size: 0.78rem;
  font-weight: 800;
}
.readiness-list span:first-child {
  color: var(--color-muted);
  font-size: 0.9rem;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-panel);
  color: var(--color-muted);
  padding: 3px 9px;
  font-size: 0.78rem;
  font-weight: 800;
  line-height: 1.1;
  white-space: nowrap;
}
.status-pill--good {
  border-color: #a9d8bf;
  background: var(--color-success-bg);
  color: var(--color-success);
}
.status-pill--warn {
  border-color: #fed7aa;
  background: var(--color-warning-bg);
  color: var(--color-warning);
}
.status-pill--danger {
  border-color: #fecdca;
  background: var(--color-danger-bg);
  color: var(--color-danger);
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}
.metric-card {
  min-height: 112px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-panel);
  padding: var(--space-4);
}
.metric-card__label {
  color: var(--color-muted);
  font-size: 0.82rem;
  font-weight: 700;
}
.metric-card__value {
  display: block;
  margin-top: var(--space-2);
  color: var(--color-ink);
  font-size: 1.75rem;
  font-weight: 800;
  line-height: 1.1;
  word-break: keep-all;
}
.metric-card__detail {
  margin-top: var(--space-2);
  color: var(--color-subtle);
  font-size: 0.82rem;
}
.metric-card--risk {
  border-color: #fecdca;
  background: var(--color-danger-bg);
}
.metric-card--good {
  border-color: #a9d8bf;
  background: var(--color-success-bg);
}
.section {
  margin-top: var(--space-6);
}
.section:first-child {
  margin-top: 0;
}
.section__header {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: var(--space-4);
  margin-bottom: var(--space-3);
}
.section__intro {
  max-width: 760px;
  margin-top: var(--space-2);
  color: var(--color-muted);
  font-size: 0.95rem;
}
.callout {
  border: 1px solid #fed7aa;
  border-left: 4px solid var(--color-warning);
  border-radius: var(--radius-md);
  background: #fffaf3;
  padding: var(--space-4);
}
.callout--good {
  border-color: #a9d8bf;
  border-left-color: var(--color-success);
  background: #f3fbf6;
}
.callout ul {
  margin: var(--space-2) 0 0;
  padding-left: var(--space-5);
}
.agent-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(260px, 0.75fr);
  gap: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-panel);
  padding: var(--space-4);
}
.agent-summary {
  display: grid;
  gap: var(--space-3);
}
.agent-summary__text {
  color: var(--color-ink);
  font-size: 1rem;
  font-weight: 650;
}
.agent-lists {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}
.agent-list {
  margin: 0;
  padding-left: var(--space-5);
  color: var(--color-muted);
  font-size: 0.9rem;
}
.agent-list li + li {
  margin-top: var(--space-2);
}
.agent-evidence {
  border-left: 1px solid var(--color-border);
  padding-left: var(--space-4);
}
.agent-evidence dl {
  display: grid;
  grid-template-columns: minmax(90px, 0.8fr) minmax(0, 1fr);
  gap: var(--space-2) var(--space-3);
  margin: var(--space-3) 0 0;
}
.agent-evidence dt {
  color: var(--color-muted);
  font-size: 0.8rem;
  font-weight: 800;
}
.agent-evidence dd {
  margin: 0;
  color: var(--color-ink);
  font-size: 0.86rem;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.agent-note {
  margin-top: var(--space-3);
  color: var(--color-subtle);
  font-size: 0.82rem;
}
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-panel);
}
.map-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 340px);
  gap: var(--space-4);
  align-items: start;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-panel);
  padding: var(--space-4);
}
.map-figure {
  margin: 0;
  min-height: 340px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: #f7fafc;
  overflow: hidden;
}
.map-canvas {
  position: relative;
  width: 100%;
  height: 380px;
  border: 0;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-panel-soft);
}
.map-overlay {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.map-source-note {
  padding: var(--space-3);
  color: var(--color-subtle);
  font-size: 0.8rem;
}
.map-panel > div {
  min-width: 0;
}
.location-map {
  display: block;
  width: 100%;
  height: 100%;
}
.map-tile-bg {
  fill: #eef3f8;
}
.map-tile {
  pointer-events: none;
}
.map-frame {
  fill: transparent;
  stroke: rgba(15, 95, 140, 0.26);
  stroke-width: 2;
}
.map-marker-link {
  pointer-events: auto;
}
.map-point {
  fill: var(--color-danger);
  fill-opacity: 0.9;
  stroke: #ffffff;
  stroke-width: 3;
}
.map-point--p1 {
  fill: var(--color-warning);
}
.map-point--p2 {
  fill: var(--color-primary);
}
.map-marker-label {
  fill: #ffffff;
  font-size: 13px;
  font-weight: 800;
  pointer-events: none;
}
.map-marker-link:hover .map-point,
.map-marker-link:focus-visible .map-point {
  stroke: var(--color-focus);
  stroke-width: 5;
}
.map-axis-label,
.map-caption {
  fill: var(--color-muted);
  font-size: 14px;
  font-weight: 700;
}
.map-list {
  display: grid;
  align-content: start;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}
.map-list li {
  border-bottom: 1px solid var(--color-border);
  padding-bottom: var(--space-3);
}
.map-list li:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}
.map-list strong {
  display: block;
  color: var(--color-ink);
  font-size: 0.94rem;
}
.map-list span {
  display: block;
  margin-top: 3px;
  color: var(--color-muted);
  font-size: 0.84rem;
}
.map-link {
  display: inline-flex;
  align-items: center;
  margin-top: var(--space-2);
  margin-right: var(--space-3);
  font-size: 0.84rem;
  font-weight: 800;
}
.data-table {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
}
.data-table th,
.data-table td {
  border-bottom: 1px solid var(--color-border);
  padding: 11px 12px;
  text-align: left;
  vertical-align: top;
  font-size: 0.9rem;
}
.data-table th {
  background: #f2f5f8;
  color: #344256;
  font-size: 0.76rem;
  font-weight: 800;
  text-transform: uppercase;
}
.data-table tr:last-child td {
  border-bottom: 0;
}
.data-table tr {
  scroll-margin-top: var(--space-5);
}
.data-table tr:target td {
  background: #fff7ed;
  box-shadow: inset 4px 0 0 var(--color-warning);
}
.detail-row td {
  background: #fbfdff;
  padding-top: 0;
}
.queue-detail-row td {
  background: #f8fafc;
}
.evidence-drawer {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-panel-soft);
  padding: var(--space-3);
}
.evidence-drawer summary {
  cursor: pointer;
  color: var(--color-primary);
  font-weight: 800;
}
.evidence-drawer summary:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 3px;
  border-radius: var(--radius-sm);
}
.evidence-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-3);
}
.evidence-item {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-panel);
  padding: var(--space-3);
}
.evidence-item strong {
  display: block;
  color: var(--color-muted);
  font-size: 0.78rem;
}
.evidence-item span {
  display: block;
  margin-top: 3px;
  color: var(--color-ink);
  font-size: 0.88rem;
  font-weight: 700;
}
.evidence-note {
  margin-top: var(--space-3);
  color: var(--color-muted);
  font-size: 0.86rem;
}
.cell-title {
  display: block;
  color: var(--color-ink);
  font-weight: 800;
}
.cell-note {
  display: block;
  margin-top: 3px;
  color: var(--color-subtle);
  font-size: 0.78rem;
  line-height: 1.35;
}
.mono {
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 0.85rem;
}
.action-group {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.soft-tag {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-panel-soft);
  color: var(--color-muted);
  padding: 3px 8px;
  font-size: 0.78rem;
  font-weight: 700;
}
.empty-row {
  color: var(--color-muted);
}
@media (max-width: 960px) {
  .hero__grid {
    grid-template-columns: 1fr;
    align-items: start;
  }
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .map-panel {
    grid-template-columns: 1fr;
  }
  .agent-panel,
  .agent-lists {
    grid-template-columns: 1fr;
  }
  .agent-evidence {
    border-left: 0;
    border-top: 1px solid var(--color-border);
    padding-left: 0;
    padding-top: var(--space-4);
  }
  .evidence-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .hero__inner,
  .main {
    padding-left: var(--space-4);
    padding-right: var(--space-4);
  }
  .hero__inner {
    padding-top: var(--space-5);
  }
  h1 {
    font-size: 2rem;
  }
  .hero__actions,
  .section__header {
    align-items: stretch;
    flex-direction: column;
  }
  .button {
    width: 100%;
  }
  .metric-grid {
    grid-template-columns: 1fr;
  }
  .metric-card {
    min-height: 96px;
  }
  .map-canvas {
    height: 320px;
  }
  .agent-evidence dl {
    grid-template-columns: 1fr;
  }
  .evidence-grid {
    grid-template-columns: 1fr;
  }
}
"""


DISPLAY_LABELS = {
    "DEMO READY": "데모 준비 완료",
    "BLOCKED": "차단됨",
    "GO": "GO",
    "NO_GO": "NO_GO",
    "ON": "사용",
    "OFF": "미사용",
    "P0": "긴급(P0)",
    "P1": "중요(P1)",
    "P2": "관찰(P2)",
    "True": "있음",
    "False": "없음",
    "None": "없음",
    "ready_for_review": "검토 가능",
    "validation_not_ready": "검증 전",
    "pending_reviewer": "검토 대기",
    "approved": "승인됨",
    "rejected": "반려됨",
    "needs_more_evidence": "근거 요청",
    "approve": "승인",
    "reject": "반려",
    "send_bikes": "자전거 보충",
    "remove_bikes": "자전거 회수",
    "monitor": "모니터링",
    "unsafe_auto_publish": "무검토 공개 기준선",
    "guarded_all_review": "전량 검토 후 로컬 근거",
    "source_order_capacity": "원천 순서 검토",
    "impact_guarded_capacity": "영향 우선 검토",
    "confidence_weighted_guarded_capacity": "Confidence 조정 안전 검토",
    "baseline": "기준 입력",
    "unit_estimate_jitter": "후보 효과 변동",
    "confidence_stress": "Confidence 하락",
    "top_candidate_dropout": "상위 source 누락",
    "approve_local_review_only": "로컬 검토 승인",
    "approve_for_private_demo": "비공개 시연 승인",
    "fresh": "최신",
    "stale": "기한 초과",
    "missing_timestamp": "시각 없음",
    "future_timestamp": "미래 시각 오류",
    "locked_fresh": "최신 근거 잠금",
    "blocked_stale": "오래된 근거 차단",
    "blocked_missing_timestamp": "시각 없는 근거 차단",
    "blocked_future_timestamp": "미래 시각 근거 차단",
    "deployment_no_go": "배포 보류",
    "high_uncertainty_review": "불확실성 높음",
    "unsafe_write_action": "쓰기 위험",
    "missing_evidence_request": "근거 부족",
    "cross_source_conflict_review": "자료 충돌",
    "publication_restricted": "공개 제한",
    "valid": "좌표 확인됨",
    "missing": "좌표 없음",
    "out_of_range": "좌표 범위 오류",
    "fallback": "fallback",
    "llm": "LLM",
}


BLOCKER_LABELS = {
    "review queue has no actionable items": "검토자가 처리할 수 있는 queue 항목이 없습니다.",
    "bike-share public deploy decision is not GO": "bike-share 공개 배포 결정이 GO가 아닙니다.",
    "Seoul Ddareungi impact cards are local-review only until validation is READY": (
        "서울 따릉이 impact card는 검증 상태가 READY가 될 때까지 로컬 검토 전용입니다."
    ),
    "Seoul Ddareungi impact cards are local-review only until validation and deploy readiness are READY": (
        "서울 따릉이 impact card는 검증과 배포 readiness가 모두 READY가 될 때까지 로컬 검토 전용입니다."
    ),
}


ARTIFACT_LABELS = {
    "control_state": "운영 판단 상태 JSON",
    "review_queue": "검토 대기열 CSV",
    "api_contract": "API 계약 JSON",
    "impact_cards": "따릉이 후보 조치 JSON",
    "impact_policy_audit": "영향 정책 비교 JSON",
    "reviewer_action_plan": "검토 실행 계획 JSON",
    "reviewer_evidence_bundles": "심의 근거 패킷 JSON",
    "dashboard": "대시보드 HTML",
    "sqlite_database": "승인 이력 SQLite",
    "approval_audit_integrity": "승인 감사 무결성 JSON",
    "ops_metrics_snapshot": "운영 상태 스냅샷",
    "ops_metrics_history": "운영 상태 이력",
}


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _display(value: Any) -> str:
    return DISPLAY_LABELS.get(str(value), str(value))


def _trailing_number(value: Any) -> int | None:
    digits = ""
    for char in reversed(str(value or "")):
        if char.isdigit():
            digits = char + digits
            continue
        if digits:
            break
    return int(digits) if digits else None


def _id_cell(title: str, note: str = "") -> str:
    note_html = f'<span class="cell-note">{_escape(note)}</span>' if note else ""
    return f'<span class="cell-title">{_escape(title)}</span>{note_html}'


def _impact_decision_title(item: dict[str, Any]) -> str:
    station = str(item.get("station_name") or "대상 대여소").strip()
    units = _trailing_number(item.get("candidate_units_addressed")) or item.get(
        "candidate_units_addressed", ""
    )
    action = str(item.get("recommended_action", "monitor"))
    if action == "remove_bikes":
        return f"{station}: 자전거 {units}대 회수 여부 검토"
    if action == "send_bikes":
        return f"{station}: 자전거 {units}대 보충 여부 검토"
    return f"{station}: 모니터링 유지 여부 검토"


def _impact_anchor_id(index: int) -> str:
    return f"ddareungi-action-{index}"


def _friendly_record_label(item: dict[str, Any]) -> str:
    number = _trailing_number(item.get("control_id"))
    return f"검토 기록 {number}" if number is not None else "검토 기록"


def _impact_current_state(item: dict[str, Any]) -> str:
    capacity = item.get("capacity", "")
    bikes = item.get("bikes_available", "")
    docks = item.get("docks_available", "")
    return f"자전거 {bikes}대 / 빈 거치대 {docks}칸 / 총 거치대 {capacity}칸"


def _impact_expected_effect(item: dict[str, Any]) -> str:
    units = item.get("candidate_units_addressed", "")
    metric = str(item.get("impact_metric", ""))
    if metric == "return_overflow_pressure_units":
        return f"반납 포화 압력 {units}단위 완화 예상"
    if metric == "rental_shortage_pressure_units":
        return f"대여 불가 압력 {units}단위 완화 예상"
    return f"운영 위험 {units}단위 모니터링"


def _impact_reason(item: dict[str, Any]) -> str:
    action = str(item.get("recommended_action", "monitor"))
    issue = str(item.get("issue_type", ""))
    if action == "remove_bikes" or issue == "dock_shortage":
        return "빈 거치대가 부족해 반납 포화가 날 수 있어 자전거 회수 여부를 검토합니다."
    if action == "send_bikes" or issue == "bike_shortage":
        return "대여 가능한 자전거가 부족해 대여 불가가 날 수 있어 자전거 보충 여부를 검토합니다."
    return "현재 상태가 임계 구간에 가까워 추가 관찰이 필요한 후보입니다."


def _validation_note(item: dict[str, Any]) -> str:
    if str(item.get("guardrail_state")) == "validation_not_ready":
        return "검증 전 상태입니다. 운영 참고용으로만 쓰고 외부 성과 주장에는 사용하지 않습니다."
    return "검증 기준을 통과한 후보입니다. 그래도 현장 실행 전에는 검토 이력을 남깁니다."


def _confidence_label(item: dict[str, Any]) -> str:
    confidence = _as_float(item.get("confidence_score"))
    if confidence <= 0:
        return "계산 전"
    return f"{confidence:.2f}"


def _coordinate_label(item: dict[str, Any]) -> str:
    status = str(item.get("coordinate_status") or "")
    lat = _optional_float(item.get("station_lat"))
    lon = _optional_float(item.get("station_lon"))
    if status == "valid" and lat is not None and lon is not None:
        return f"좌표 확인됨 ({lat:.5f}, {lon:.5f})"
    if status == "out_of_range":
        return "서울 권역 범위를 벗어난 좌표라 지도에서 제외"
    if status == "missing":
        return "좌표가 없어 지도에서 제외"
    return _display(status or "missing")


def _render_impact_evidence(item: dict[str, Any]) -> str:
    captured = item.get("captured_at_kst") or "확인 필요"
    evidence_items = [
        ("권고 이유", _impact_reason(item)),
        ("현재 상태", _impact_current_state(item)),
        ("예상 효과", _impact_expected_effect(item)),
        ("검증 주의", _validation_note(item)),
        ("심각도", f"{_as_float(item.get('severity_score')):.2f}"),
        ("신뢰도", _confidence_label(item)),
        ("좌표 상태", _coordinate_label(item)),
        ("데이터 기준", captured),
        ("사용 데이터", "서울 따릉이 대여소 현황과 재배치 우선순위 산출물"),
    ]
    cards = "".join(
        "<div class=\"evidence-item\">"
        f"<strong>{_escape(label)}</strong>"
        f"<span>{_escape(value)}</span>"
        "</div>"
        for label, value in evidence_items
    )
    return (
        '<details class="evidence-drawer">'
        "<summary>판단 근거 보기</summary>"
        f'<div class="evidence-grid">{cards}</div>'
        '<p class="evidence-note">'
        "이 근거는 현장 작업을 자동 실행하지 않습니다. 승인/반려/근거 요청은 검토 기록으로만 남습니다."
        "</p>"
        "</details>"
    )


def _queue_next_action(item: dict[str, Any]) -> str:
    guardrails = set(str(item.get("guardrail_hits", "")).split("|"))
    if "deployment_no_go" in guardrails:
        return "공개 배포 차단 요인이 해소될 때까지 승인하지 말고 보류 사유를 확인합니다."
    if "unsafe_write_action" in guardrails:
        return "자동 실행 위험이 있으므로 승인 전 실행 범위와 write boundary를 확인합니다."
    if "missing_evidence_request" in guardrails:
        return "근거가 부족하면 근거 요청으로 되돌리고, 충분할 때만 승인합니다."
    if "cross_source_conflict_review" in guardrails:
        return "자료 간 충돌 원인을 확인하고 신뢰할 기준 데이터를 먼저 정합니다."
    if "high_uncertainty_review" in guardrails:
        return "불확실성이 높으므로 추가 근거 요청 또는 반려를 우선 검토합니다."
    return "권고 내용과 근거가 충분하면 승인하고, 부족하면 근거 요청으로 남깁니다."


def _render_queue_evidence(item: dict[str, Any]) -> str:
    review_context = item.get("review_context") or "원천 검토 질문이 비어 있어 guardrail과 우선순위 기준으로 판단합니다."
    evidence_items = [
        ("검토 이유", _queue_review_title(item)),
        ("원천 근거 요약", review_context),
        ("다음 결정 기준", _queue_next_action(item)),
        ("우선순위", _display(item.get("priority", ""))),
        ("현재 상태", _display(item.get("approval_state", ""))),
        ("확인 필요 이유", ", ".join(_display(part) for part in str(item.get("guardrail_hits", "")).split("|") if part) or "없음"),
        ("기록 방식", "승인/반려/근거 요청은 로컬 감사 기록으로만 저장됩니다."),
        ("담당", "운영 검토자"),
        ("현장 영향", "버튼을 눌러도 현장 작업이나 외부 배포는 실행되지 않습니다."),
    ]
    cards = "".join(
        "<div class=\"evidence-item\">"
        f"<strong>{_escape(label)}</strong>"
        f"<span>{_escape(value)}</span>"
        "</div>"
        for label, value in evidence_items
    )
    return (
        '<details class="evidence-drawer">'
        "<summary>검토 기준 보기</summary>"
        f'<div class="evidence-grid">{cards}</div>'
        '<p class="evidence-note">'
        "이 대기열은 모델 권고를 사람이 승인 가능한 상태로 바꾸기 위한 검토 장부입니다."
        "</p>"
        "</details>"
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _impact_map_points(impact_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points = []
    for index, item in enumerate(impact_cards, start=1):
        lat = _optional_float(item.get("station_lat"))
        lon = _optional_float(item.get("station_lon"))
        if lat is None or lon is None:
            continue
        if not (33.0 <= lat <= 39.0 and 124.0 <= lon <= 132.0):
            continue
        points.append(
            {
                "item": item,
                "index": index,
                "lat": lat,
                "lon": lon,
                "units": abs(_as_float(item.get("candidate_units_addressed"))),
            }
        )
    return points


def _render_impact_map(impact_cards: list[dict[str, Any]]) -> str:
    points = _impact_map_points(impact_cards)
    if not points:
        return (
            '<div class="callout">'
            "<h3>대여소 좌표가 아직 연결되지 않았습니다</h3>"
            '<p class="section__intro">'
            "따릉이 후보 조치에 station_lat/station_lon 값이 들어오면 이 영역에 위치 지도가 표시됩니다."
            "</p>"
            "</div>"
        )

    width = 920
    height = 520
    tile_size = 256
    min_lat = min(point["lat"] for point in points)
    max_lat = max(point["lat"] for point in points)
    min_lon = min(point["lon"] for point in points)
    max_lon = max(point["lon"] for point in points)
    lat_span = max(max_lat - min_lat, 0.01)
    lon_span = max(max_lon - min_lon, 0.01)
    min_lat -= lat_span * 0.16
    max_lat += lat_span * 0.16
    min_lon -= lon_span * 0.16
    max_lon += lon_span * 0.16
    invalid_count = max(0, len(impact_cards) - len(points))
    coordinate_note = (
        f"지도 표시 가능 후보 {len(points)}건"
        + (f", 좌표 미확인/범위 오류 {invalid_count}건 제외" if invalid_count else "")
    )

    def tile_x(lon: float, zoom: int) -> float:
        return (lon + 180.0) / 360.0 * (2**zoom)

    def tile_y(lat: float, zoom: int) -> float:
        clipped_lat = max(min(lat, 85.05112878), -85.05112878)
        lat_rad = math.radians(clipped_lat)
        return (
            1.0
            - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi
        ) / 2.0 * (2**zoom)

    zoom = 10
    for candidate_zoom in range(16, 9, -1):
        left = tile_x(min_lon, candidate_zoom) * tile_size
        right = tile_x(max_lon, candidate_zoom) * tile_size
        top = tile_y(max_lat, candidate_zoom) * tile_size
        bottom = tile_y(min_lat, candidate_zoom) * tile_size
        if (right - left) <= width * 0.86 and (bottom - top) <= height * 0.86:
            zoom = candidate_zoom
            break

    left = tile_x(min_lon, zoom) * tile_size
    right = tile_x(max_lon, zoom) * tile_size
    top = tile_y(max_lat, zoom) * tile_size
    bottom = tile_y(min_lat, zoom) * tile_size
    view_min_x = ((left + right) / 2.0) - (width / 2.0)
    view_min_y = ((top + bottom) / 2.0) - (height / 2.0)

    tile_min_x = math.floor(view_min_x / tile_size)
    tile_max_x = math.floor((view_min_x + width) / tile_size)
    tile_min_y = max(0, math.floor(view_min_y / tile_size))
    tile_max_y = min((2**zoom) - 1, math.floor((view_min_y + height) / tile_size))
    tiles = []
    for tile_column in range(tile_min_x, tile_max_x + 1):
        wrapped_column = tile_column % (2**zoom)
        for tile_row in range(tile_min_y, tile_max_y + 1):
            x = tile_column * tile_size - view_min_x
            y = tile_row * tile_size - view_min_y
            tile_href = f"https://tile.openstreetmap.org/{zoom}/{wrapped_column}/{tile_row}.png"
            tiles.append(
                f'<image class="map-tile" href="{_escape(tile_href)}" '
                f'x="{x:.1f}" y="{y:.1f}" width="{tile_size}" height="{tile_size}" '
                'preserveAspectRatio="none" />'
            )

    def project(lat: float, lon: float) -> tuple[float, float]:
        return (
            tile_x(lon, zoom) * tile_size - view_min_x,
            tile_y(lat, zoom) * tile_size - view_min_y,
        )

    markers = []
    for point in points[:20]:
        item = point["item"]
        index = int(point["index"])
        anchor_id = _impact_anchor_id(index)
        x, y = project(point["lat"], point["lon"])
        radius = min(22.0, 8.0 + point["units"] ** 0.5)
        title = _impact_decision_title(item)
        priority = str(item.get("priority", "P2")).lower()
        markers.append(
            f'<a class="map-marker-link" href="#{anchor_id}" '
            f'aria-label="{_escape(title)}">'
            f'<circle class="map-point map-point--{_escape(priority)}" '
            f'cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}">'
            f"<title>{_escape(title)}</title>"
            "</circle>"
            f'<text class="map-marker-label" x="{x:.1f}" y="{y + 4:.1f}" '
            f'text-anchor="middle">{index}</text>'
            "</a>"
        )

    list_items = []
    for point in points[:6]:
        item = point["item"]
        index = int(point["index"])
        anchor_id = _impact_anchor_id(index)
        title = _impact_decision_title(item)
        effect = _impact_expected_effect(item)
        current = _impact_current_state(item)
        lat = point["lat"]
        lon = point["lon"]
        map_href = (
            "https://www.openstreetmap.org/"
            f"?mlat={lat:.6f}&mlon={lon:.6f}#map=16/{lat:.6f}/{lon:.6f}"
        )
        list_items.append(
            "<li>"
            f"<strong>{index}. {_escape(title)}</strong>"
            f"<span>{_escape(effect)}</span>"
            f"<span>{_escape(current)}</span>"
            f'<a class="map-link" href="#{anchor_id}">표에서 세부 보기</a>'
            f'<a class="map-link" href="{_escape(map_href)}" target="_blank" rel="noopener">'
            "외부 지도에서 열기</a>"
            "</li>"
        )

    return (
        '<div class="map-panel">'
        '<figure class="map-figure" aria-label="서울 따릉이 후보 조치 위치 지도">'
        '<div class="map-canvas" aria-label="후보 번호 오버레이 지도">'
        '<svg class="location-map map-overlay" viewBox="0 0 920 520" preserveAspectRatio="none" role="img" '
        'aria-labelledby="map-title map-desc">'
        '<title id="map-title">서울 따릉이 후보 조치 위치 지도</title>'
        '<desc id="map-desc">'
        "서울 공개데이터 좌표를 기준으로 실제 OpenStreetMap 타일 위에 따릉이 후보 번호를 겹쳐 표시합니다. "
        "점이 클수록 예상 완화량이 큽니다."
        "</desc>"
        f'<rect class="map-tile-bg" x="0" y="0" width="{width}" height="{height}" />'
        f"{''.join(tiles)}"
        f'<rect class="map-frame" x="1" y="1" width="{width - 2}" height="{height - 2}" rx="8" />'
        f"{''.join(markers)}"
        "</svg>"
        "</div>"
        f'<p class="map-source-note">{_escape(coordinate_note)}. 후보 번호는 실제 지도 타일 위에 표시됩니다. 지도 타일 © OpenStreetMap contributors.</p>'
        "</figure>"
        "<div>"
        "<h3>지도에서 먼저 볼 위치</h3>"
        '<p class="section__intro">'
        "상위 후보 대여소를 좌표 기준으로 먼저 확인하고, 실제 승인 여부는 아래 표에서 결정합니다."
        "</p>"
        f'<ol class="map-list">{"".join(list_items)}</ol>'
        "</div>"
        "</div>"
    )


def _queue_review_title(item: dict[str, Any]) -> str:
    guardrails = set(str(item.get("guardrail_hits", "")).split("|"))
    if "deployment_no_go" in guardrails:
        return "공개 배포 전에 근거와 차단 사유 확인"
    if "unsafe_write_action" in guardrails:
        return "자동 실행하면 위험한 권고인지 확인"
    if "missing_evidence_request" in guardrails:
        return "근거가 부족한 권고인지 확인"
    if "cross_source_conflict_review" in guardrails:
        return "자료가 서로 충돌하는 권고인지 확인"
    if "high_uncertainty_review" in guardrails:
        return "불확실성이 높은 권고의 근거 확인"
    return "모델 권고를 승인해도 되는지 확인"


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _state_count(queue: list[dict[str, Any]], state: str) -> int:
    return sum(1 for item in queue if item.get("approval_state") == state)


def _priority_count(queue: list[dict[str, Any]], priority: str) -> int:
    return sum(
        1
        for item in queue
        if item.get("approval_state") == "pending_reviewer" and item.get("priority") == priority
    )


def _tone(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"go", "ready", "ready_for_review", "demo ready", "approved", "true", "on"}:
        return "good"
    if text in {"blocked", "no_go", "validation_not_ready", "rejected", "false", "p0"}:
        return "danger"
    if text == "p1" or "pending" in text or "evidence" in text or "not_ready" in text or text == "off":
        return "warn"
    return "neutral"


def _pill(value: Any, label: str | None = None) -> str:
    tone = _tone(value)
    suffix = "" if tone == "neutral" else f" status-pill--{tone}"
    text = _escape(label if label is not None else _display(value))
    return f'<span class="status-pill{suffix}">{text}</span>'


def _metric(label: str, value: Any, detail: str = "", tone: str = "") -> str:
    tone_class = f" metric-card--{tone}" if tone else ""
    detail_html = f'<div class="metric-card__detail">{_escape(detail)}</div>' if detail else ""
    return (
        f'<article class="metric-card{tone_class}">'
        f'<div class="metric-card__label">{_escape(label)}</div>'
        f'<strong class="metric-card__value">{_escape(value)}</strong>'
        f"{detail_html}"
        "</article>"
    )


def _table(headers: list[str], rows: list[str]) -> str:
    head = "".join(f"<th>{_escape(header)}</th>" for header in headers)
    body = "".join(rows)
    return (
        '<div class="table-wrap">'
        '<table class="data-table">'
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
        "</div>"
    )


def _empty_row(colspan: int, text: str) -> str:
    return f'<tr class="empty-row"><td colspan="{colspan}">{_escape(text)}</td></tr>'


def _release_label(public_deploy: Any) -> str:
    return "운영 배포 가능" if str(public_deploy) == "GO" else "운영 배포 보류"


def _release_summary(public_deploy: Any) -> str:
    if str(public_deploy) == "GO":
        return "필수 검증과 readiness gate를 통과했습니다. 그래도 승인 이력은 남기고 배포하세요."
    return "공개 read-only 데모는 사용할 수 있지만, 운영 endpoint와 성과 claim은 아직 검토 단계입니다."


def _render_guardrail_tags(value: Any) -> str:
    labels = [_display(part.strip()) for part in str(value or "").split("|") if part.strip()]
    if not labels:
        labels = ["없음"]
    tags = "".join(f'<span class="soft-tag">{_escape(label)}</span>' for label in labels)
    return f'<div class="tag-list">{tags}</div>'


def _render_blockers(blockers: list[Any]) -> str:
    if not blockers:
        return (
            '<div class="callout callout--good">'
            "<h3>활성 차단 요인이 없습니다</h3>"
            "<p class=\"section__intro\">현재 demo 화면은 검토자 walkthrough에 사용할 수 있습니다.</p>"
            "</div>"
        )
    items = "".join(f"<li>{_escape(BLOCKER_LABELS.get(str(item), item))}</li>" for item in blockers)
    return (
        '<div class="callout">'
        "<h3>릴리스 guardrail이 공개 배포를 차단하고 있습니다</h3>"
        f"<ul>{items}</ul>"
        "</div>"
    )


def _render_agent_brief(agent_brief: dict[str, Any] | None) -> str:
    if not agent_brief:
        return (
            '<div class="callout">'
            "<h3>AI Reviewer Agent brief가 아직 생성되지 않았습니다</h3>"
            '<p class="section__intro">agent API가 준비되면 이 영역에 근거 기반 검토 요약이 표시됩니다.</p>'
            "</div>"
        )
    source_status = agent_brief.get("source_status", {})
    if not isinstance(source_status, dict):
        source_status = {}
    claim_safety = agent_brief.get("claim_safety", {})
    if not isinstance(claim_safety, dict):
        claim_safety = {}
    risks = agent_brief.get("top_risks", [])
    if not isinstance(risks, list):
        risks = []
    actions = agent_brief.get("recommended_next_actions", [])
    if not isinstance(actions, list):
        actions = []
    llm = agent_brief.get("llm", {})
    if not isinstance(llm, dict):
        llm = {}

    def list_item(item: Any, key: str, fallback: str) -> str:
        if isinstance(item, dict):
            text = item.get(key) or item.get("risk") or item.get("action") or fallback
            evidence = item.get("evidence_ref", "")
            note = f" <span class=\"cell-note\">{_escape(evidence)}</span>" if evidence else ""
            return f"<li>{_escape(text)}{note}</li>"
        return f"<li>{_escape(item)}</li>"

    risk_items = "".join(list_item(item, "risk", "확인 필요") for item in risks[:3]) or (
        "<li>현재 agent가 별도 위험을 찾지 못했습니다.</li>"
    )
    action_items = "".join(list_item(item, "action", "다음 action 확인") for item in actions[:3]) or (
        "<li>검토 대기열을 먼저 확인합니다.</li>"
    )
    evidence = [
        ("mode", agent_brief.get("mode", "fallback")),
        ("LLM", llm.get("status", "not_configured")),
        ("public gate", source_status.get("public_deploy_decision", "UNKNOWN")),
        ("queue", source_status.get("queue_total", 0)),
        ("impact cards", source_status.get("impact_card_rows", 0)),
        ("blocked units", claim_safety.get("blocked_public_claim_units", 0)),
    ]
    evidence_rows = "".join(
        f"<dt>{_escape(label)}</dt><dd>{_escape(_display(value))}</dd>" for label, value in evidence
    )
    agent_mode = agent_brief.get("mode", "fallback")
    public_gate = source_status.get("public_deploy_decision", "UNKNOWN")
    return (
        '<div class="agent-panel">'
        '<div class="agent-summary">'
        '<div class="topline">'
        f"{_pill(agent_mode, 'agent mode: ' + _display(agent_mode))}"
        f"{_pill(public_gate, 'deterministic gate: ' + str(public_gate))}"
        "</div>"
        f'<p class="agent-summary__text">{_escape(agent_brief.get("executive_summary", ""))}</p>'
        '<div class="agent-lists">'
        "<div><h3>Top risks</h3>"
        f'<ol class="agent-list">{risk_items}</ol></div>'
        "<div><h3>Next actions</h3>"
        f'<ol class="agent-list">{action_items}</ol></div>'
        "</div>"
        '<p class="agent-note">이 agent는 read-only reviewer assistant입니다. 수치와 GO/NO_GO 판단은 기존 deterministic pipeline이 기준입니다.</p>'
        "</div>"
        '<aside class="agent-evidence" aria-label="Agent evidence">'
        "<h3>Evidence lock</h3>"
        f"<dl>{evidence_rows}</dl>"
        "</aside>"
        "</div>"
    )


def _render_impact_rows(impact_cards: list[dict[str, Any]], limit: int) -> list[str]:
    rows = []
    for index, item in enumerate(impact_cards[:limit], start=1):
        rows.append(
            f'<tr id="{_impact_anchor_id(index)}">'
            f"<td>{_id_cell(_impact_decision_title(item), '현장 실행 전 검토용 후보입니다.')}</td>"
            f"<td>{_pill(item.get('priority', ''))}</td>"
            f"<td>{_escape(_impact_current_state(item))}</td>"
            f"<td>{_escape(_impact_expected_effect(item))}</td>"
            f"<td>{_pill(item.get('guardrail_state', ''))}</td>"
            "</tr>"
        )
        rows.append(f'<tr class="detail-row"><td colspan="5">{_render_impact_evidence(item)}</td></tr>')
    return rows or [_empty_row(5, "사용 가능한 따릉이 후보 조치가 없습니다.")]


def _policy_note(item: dict[str, Any]) -> str:
    if str(item.get("audit_result")) == "fail":
        return "이 기준선은 미검증 성과 claim을 만들 수 있어 운영 정책상 허용하지 않습니다."
    if _as_float(item.get("blocked_public_claim_units")) > 0:
        return "미검증 단위는 공개하지 않고 reviewer evidence로만 묶습니다."
    return "검토 용량 안에서 후보를 정렬하되 public claim boundary를 유지합니다."


def _render_policy_rows(rows: list[dict[str, Any]], limit: int) -> list[str]:
    rendered = []
    for item in rows[:limit]:
        rendered.append(
            "<tr>"
            f"<td>{_id_cell(_display(item.get('policy', '')), _policy_note(item))}</td>"
            f"<td>{_escape(item.get('review_capacity', ''))}</td>"
            f"<td>{_escape(item.get('reviewed_candidate_units', ''))}</td>"
            f"<td>{_escape(item.get('unsupported_claim_units', ''))}</td>"
            f"<td>{_pill(item.get('audit_result', ''))}</td>"
            "</tr>"
        )
    return rendered or [_empty_row(5, "영향 정책 비교 산출물이 없습니다.")]


def _render_robustness_rows(rows: list[dict[str, Any]], limit: int) -> list[str]:
    guarded = [
        row
        for row in rows
        if row.get("policy") == "confidence_weighted_guarded_capacity"
    ]
    rendered = []
    for item in guarded[:limit]:
        rendered.append(
            "<tr>"
            f"<td>{_id_cell(_display(item.get('scenario', '')), '실현 성과가 아닌 deterministic ordering stress scenario입니다.')}</td>"
            f"<td>{_escape(item.get('review_capacity', ''))}</td>"
            f"<td>{_escape(item.get('confidence_adjusted_units', ''))}</td>"
            f"<td>{_escape(item.get('oracle_regret_units', ''))}</td>"
            f"<td>{_escape(item.get('selection_stability_jaccard', ''))}</td>"
            "</tr>"
        )
    return rendered or [_empty_row(5, "Reviewer policy robustness 산출물이 없습니다.")]


def _action_title(item: dict[str, Any]) -> str:
    station = str(item.get("station_name") or "대상 대여소").strip()
    action = _display(item.get("recommended_action", "monitor"))
    units = item.get("candidate_units_addressed", "")
    return f"{station}: {action} {units}대 검토"


def _render_action_plan_rows(rows: list[dict[str, Any]], limit: int) -> list[str]:
    rendered = []
    for item in rows[:limit]:
        rendered.append(
            "<tr>"
            f"<td>{_id_cell(_action_title(item), item.get('next_evidence_needed', ''))}</td>"
            f"<td>{_pill(item.get('priority', ''))}</td>"
            f"<td>{_escape(item.get('cumulative_candidate_units', ''))}</td>"
            f"<td>{_pill(item.get('reviewer_decision', ''))}</td>"
            "</tr>"
        )
    return rendered or [_empty_row(4, "검토 실행 계획 산출물이 없습니다.")]


def _evidence_bundle_title(item: dict[str, Any]) -> str:
    station = str(item.get("station_name") or "대상 대여소").strip()
    action = _display(item.get("recommended_action", "monitor"))
    units = item.get("candidate_units_addressed", "")
    return f"{station}: {action} {units}대 근거"


def _render_evidence_bundle_rows(rows: list[dict[str, Any]], limit: int) -> list[str]:
    rendered = []
    for item in rows[:limit]:
        fingerprint = str(item.get("evidence_fingerprint_sha256", ""))
        fingerprint_note = f"SHA-256 {fingerprint[:12]}…" if fingerprint else "fingerprint 없음"
        source_age = item.get("source_age_hours")
        age_label = "확인 불가" if source_age is None else f"{source_age}시간"
        rendered.append(
            "<tr>"
            f"<td>{_id_cell(_evidence_bundle_title(item), fingerprint_note)}</td>"
            f"<td>{_pill(item.get('freshness_status', ''))}<span class=\"cell-note\">{_escape(age_label)}</span></td>"
            f"<td>{_pill(item.get('evidence_lock_status', ''))}</td>"
            f"<td>{_pill(item.get('reviewer_decision', ''))}</td>"
            "</tr>"
        )
    return rendered or [_empty_row(4, "사용 가능한 심의 근거 패킷이 없습니다.")]


def _render_queue_rows(
    queue: list[dict[str, Any]],
    limit: int,
    include_actions: bool,
) -> list[str]:
    rows = []
    colspan = 5 if include_actions else 4
    for item in queue[:limit]:
        control_id = _escape(item.get("control_id", ""))
        review_title = _queue_review_title(item)
        context = item.get("review_context") or "승인해도 현장 작업은 실행되지 않고 검토 기록만 남습니다."
        cells = [
            f"<td>{_id_cell(review_title, context)}</td>",
            f"<td>{_pill(item.get('priority', ''))}</td>",
            f"<td>{_pill(item.get('approval_state', ''))}</td>",
            f"<td>{_render_guardrail_tags(item.get('guardrail_hits', ''))}</td>",
        ]
        if include_actions:
            actions = ""
            if item.get("approval_state") == "pending_reviewer":
                actions = (
                    '<div class="action-group">'
                    f'<button class="button--small" type="button" data-control-id="{control_id}" '
                    f'data-decision="approve" aria-label="{_escape(review_title)} 승인">승인</button>'
                    f'<button class="button--small" type="button" data-control-id="{control_id}" '
                    f'data-decision="reject" aria-label="{_escape(review_title)} 반려">반려</button>'
                    f'<button class="button--small" type="button" data-control-id="{control_id}" '
                    f'data-decision="needs_more_evidence" aria-label="{_escape(review_title)} 추가 근거 요청">'
                    "근거 요청</button>"
                    "</div>"
                )
            cells.append(f"<td>{actions}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
        rows.append(
            f'<tr class="detail-row queue-detail-row"><td colspan="{colspan}">'
            f"{_render_queue_evidence(item)}</td></tr>"
        )
    return rows or [_empty_row(colspan, "사용 가능한 검토 항목이 없습니다.")]


def _render_history_rows(history: list[dict[str, Any]], limit: int) -> list[str]:
    rows = []
    for item in history[:limit]:
        rows.append(
            "<tr>"
            f'<td class="mono">{_escape(item.get("created_at_utc", ""))}</td>'
            f"<td>{_id_cell(_friendly_record_label(item), '이전에 저장된 검토 결정입니다.')}</td>"
            f"<td>{_pill(item.get('decision', ''))}</td>"
            f"<td>{_escape(item.get('reviewer', ''))}</td>"
            "</tr>"
        )
    return rows or [_empty_row(4, "기록된 승인 이력이 없습니다.")]


def _render_audit_integrity_rows(integrity: dict[str, Any]) -> list[str]:
    checks = [
        ("Hash chain", integrity.get("chain_valid"), "결정 payload와 이전 event hash 연결"),
        ("State replay", integrity.get("replay_valid"), "마지막 결정을 현재 queue 상태와 대조"),
        ("Audit events", integrity.get("event_count", 0), "검증한 reviewer 결정 수"),
        (
            "Replay mismatches",
            integrity.get("replay_mismatch_count", 0),
            "0이 아니면 queue state 변조 또는 불일치",
        ),
    ]
    return [
        "<tr>"
        f"<td>{_escape(name)}</td>"
        f"<td>{_pill(value)}</td>"
        f"<td>{_escape(description)}</td>"
        "</tr>"
        for name, value, description in checks
    ]


def _render_artifact_rows(artifacts: dict[str, Any]) -> list[str]:
    rows = []
    for name, item in artifacts.items():
        if not isinstance(item, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{_escape(ARTIFACT_LABELS.get(name, name))}</td>"
            f"<td>{_pill(item.get('exists'))}</td>"
            f'<td class="mono">{_escape(item.get("mtime_utc"))}</td>'
            "</tr>"
        )
    return rows or [_empty_row(3, "산출물 상태는 live API runtime에서 확인할 수 있습니다.")]


def render_dashboard(
    *,
    state: dict[str, Any],
    queue: list[dict[str, Any]],
    impact_cards: list[dict[str, Any]],
    impact_policy_audit: list[dict[str, Any]] | None = None,
    reviewer_policy_robustness: dict[str, Any] | None = None,
    reviewer_action_plan: list[dict[str, Any]] | None = None,
    reviewer_evidence_bundles: list[dict[str, Any]] | None = None,
    audit_integrity: dict[str, Any] | None = None,
    agent_brief: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
    ops: dict[str, Any] | None = None,
    recorded_chat: dict[str, dict[str, Any]] | None = None,
    include_actions: bool = True,
    include_script: bool = True,
) -> str:
    """Render the Control Tower dashboard as a self-contained HTML document."""

    history = history or []
    impact_policy_audit = impact_policy_audit or []
    reviewer_policy_robustness = reviewer_policy_robustness or {}
    reviewer_action_plan = reviewer_action_plan or []
    reviewer_evidence_bundles = reviewer_evidence_bundles or []
    audit_integrity = audit_integrity or {}
    summary = summary or {}
    ops = ops or {}
    recorded_chat = recorded_chat or {}
    metrics = state.get("metrics", {})
    by_state = summary.get("by_state") if isinstance(summary.get("by_state"), dict) else {}
    total_queue = summary.get("total", len(queue))
    pending = by_state.get("pending_reviewer", _state_count(queue, "pending_reviewer"))
    status = "DEMO READY" if state.get("demo_mode_ready") else "BLOCKED"
    public_deploy = state.get("public_deploy_decision", "UNKNOWN")
    auth_state = "ON" if ops.get("auth_required") else "OFF"
    auth_label = "사용" if ops.get("auth_required") else "미사용"
    blockers = state.get("blockers", [])
    candidate_units = metrics.get("impact_candidate_units_addressed", 0)
    blocked_units = metrics.get("impact_public_claim_blocked_units", 0)
    action_plan_units = metrics.get("reviewer_action_plan_candidate_units", 0)
    fresh_bundle_rows = metrics.get("reviewer_evidence_fresh_rows", 0)
    robustness_summary = reviewer_policy_robustness.get("summary", {})
    robustness_rows = reviewer_policy_robustness.get("rows", [])
    p0_pending = _priority_count(queue, "P0")
    release_label = _release_label(public_deploy)
    audit_status = str(audit_integrity.get("status", "unknown")).upper()
    rag_status = ops.get("rag", {}) if isinstance(ops.get("rag"), dict) else {}
    vector_store = str(rag_status.get("vector_store", "memory"))
    chat_surface = render_chat_surface(
        recorded_chat,
        live_chat=include_actions,
        vector_store=vector_store,
    )

    action_header = ["무엇을 검토하나", "긴급도", "처리 상태", "확인 필요 이유"]
    if include_actions:
        action_header.append("결정")

    metric_cards = [
        _metric("검토 대기", pending, "승인/반려/근거 요청 필요", "risk" if pending else "good"),
        _metric("긴급 항목", p0_pending, "P0부터 먼저 확인", "risk" if p0_pending else "good"),
        _metric("따릉이 후보 조치", metrics.get("impact_card_rows", 0), f"예상 영향 {candidate_units} 단위"),
        _metric("차단한 공개 claim", blocked_units, "대외 성과 주장 금지 단위", "risk" if blocked_units else "good"),
        _metric("검토 계획", len(reviewer_action_plan), f"상위 계획 {action_plan_units} 단위"),
        _metric(
            "Stress 우위율",
            f"{_as_float(robustness_summary.get('guarded_dominance_rate')):.0%}",
            f"선택 안정성 {_as_float(robustness_summary.get('guarded_mean_selection_stability_jaccard')):.2f}",
            "good" if robustness_rows else "risk",
        ),
        _metric(
            "최신 근거 패킷",
            f"{fresh_bundle_rows}/{len(reviewer_evidence_bundles)}",
            "freshness SLA와 SHA-256 잠금",
            "good" if reviewer_evidence_bundles and fresh_bundle_rows == len(reviewer_evidence_bundles) else "risk",
        ),
        _metric(
            "감사 무결성",
            audit_status,
            f"chain/replay · {audit_integrity.get('event_count', 0)} events",
            "good" if audit_status == "PASS" else "risk",
        ),
        _metric("공개 배포", release_label, "외부 공개 가능 여부", "good" if public_deploy == "GO" else "risk"),
    ]

    script = ""
    if include_script:
        script = """
  <script>
    document.addEventListener("click", async (event) => {
      const button = event.target.closest("button[data-decision]");
      if (!button) return;
      button.disabled = true;
      const controlId = button.dataset.controlId;
      const decision = button.dataset.decision;
      const headers = {"Content-Type": "application/json"};
      if (document.body.dataset.authRequired === "true") {
        let approvalCredential = sessionStorage.getItem("controlTowerCredential");
        if (!approvalCredential) {
          approvalCredential = window.prompt("Control Tower 승인 credential");
          if (!approvalCredential) {
            button.disabled = false;
            return;
          }
          sessionStorage.setItem("controlTowerCredential", approvalCredential);
        }
        headers["X-Control-Tower-Token"] = approvalCredential;
      }
      const response = await fetch(`/api/review-queue/${controlId}/decision`, {
        method: "POST",
        headers,
        body: JSON.stringify({decision, reviewer: "dashboard_reviewer"})
      });
      if (!response.ok) {
        button.disabled = false;
        if (response.status === 401) {
          sessionStorage.removeItem("controlTowerCredential");
        }
        alert("결정 저장에 실패했습니다.");
        return;
      }
      window.location.reload();
    });
  </script>
"""

    snapshot_notice = ""
    if not include_actions:
        freshness_note = ""
        if reviewer_evidence_bundles and fresh_bundle_rows < len(reviewer_evidence_bundles):
            freshness_note = (
                f"<br>현재 최신 근거는 {fresh_bundle_rows}/{len(reviewer_evidence_bundles)}건입니다. "
                "나머지는 stale/missing evidence 차단 시나리오로, 실제 approval 대상에서 제외됩니다."
            )
        snapshot_notice = f"""
      <section class="section" aria-label="공개 데모 안내">
        <div class="callout callout--good">
          <strong>Recorded read-only snapshot</strong><br>
          이 GitHub Pages 화면은 public-safe fixture로 생성한 검토 결과입니다.
          승인 버튼과 API write를 포함하지 않으며, 실제 reviewer approval은 인증된 private demo에서만 실행합니다.
          {freshness_note}
        </div>
      </section>
"""

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%230f5f8c'/%3E%3Cpath d='M18 20h28v8H18zM18 36h18v8H18z' fill='white'/%3E%3C/svg%3E">
  <title>AI 운영 의사결정 챗봇 · DecisionOps</title>
  <style>{DASHBOARD_CSS}{CHAT_CSS}</style>
</head>
<body data-auth-required="{str(bool(ops.get("auth_required"))).lower()}">
  <div class="app-shell">
    <header class="hero">
      <div class="hero__inner">
        <div class="topline">
          <span class="eyebrow">DecisionOps Control Tower · Evidence-grounded AI</span>
          {_pill(status)}
          {_pill(public_deploy, f"공개 배포 {public_deploy}")}
        </div>
        <div class="hero__grid">
          <div>
            <h1>AI 운영 의사결정 챗봇</h1>
            <p class="hero__copy">
              주어진 데이터를 자동으로 분석해, 근거가 연결된 판단을 제공하고 위험한 요청은 거부합니다.
              오늘의 결론은 <strong>{_escape(release_label)}</strong>이며, {_escape(_release_summary(public_deploy))}
            </p>
            <nav class="hero__actions" aria-label="주요 dashboard actions">
              <a class="button button--primary" href="#decision-chat">데이터로 질문하기</a>
              <a class="button button--primary" href="#reviewer-queue">검토 대기열 보기</a>
              <a class="button" href="#impact-map">지도에서 보기</a>
              <a class="button" href="#evidence-bundles">근거 패킷 보기</a>
            </nav>
          </div>
          <aside class="readiness-panel" aria-label="지금 해야 할 일">
            <div class="readiness-panel__title">지금 해야 할 일</div>
            <ol class="todo-list">
              <li>
                <span class="todo-index">1</span>
                <span><strong>데이터와 문서를 함께 검색</strong><span class="todo-detail">수치는 API에서, 설명은 vector retrieval에서 찾습니다.</span></span>
              </li>
              <li>
                <span class="todo-index">2</span>
                <span><strong>판단마다 출처 연결</strong><span class="todo-detail">Evidence drawer에서 field, section, freshness를 확인합니다.</span></span>
              </li>
              <li>
                <span class="todo-index">3</span>
                <span><strong>위험한 요청은 사람에게 전달</strong><span class="todo-detail">AI는 실행하지 않고 거부 또는 review 상태로 전환합니다.</span></span>
              </li>
            </ol>
          </aside>
        </div>
      </div>
    </header>
    <main class="main">
      {chat_surface}
      {snapshot_notice}
      <section class="section" aria-label="의사결정 지표">
        <div class="section__header">
          <div>
            <h2>핵심 요약</h2>
            <p class="section__intro">처음 볼 때 필요한 숫자만 남겼습니다. 상세 기술 지표는 아래 운영 상태에서 확인합니다.</p>
          </div>
        </div>
        <div class="metric-grid">{''.join(metric_cards)}</div>
      </section>

      <section class="section" id="ai-reviewer-agent">
        <div class="section__header">
          <div>
            <h2>AI Reviewer Brief</h2>
            <p class="section__intro">
              Agent가 health/API/artifact를 읽고 다음 검토 action을 요약합니다.
              판단과 수치의 원천은 기존 deterministic gate입니다.
            </p>
          </div>
        </div>
        {_render_agent_brief(agent_brief)}
      </section>

      <section class="section" id="blockers">
        <div class="section__header">
          <div>
            <h2>왜 보류인가</h2>
            <p class="section__intro">
              지금은 공개 배포보다 검토와 근거 확인이 우선입니다.
              아래 항목이 해결되기 전까지 외부 공개와 성과 claim은 보류합니다.
            </p>
          </div>
        </div>
        {_render_blockers(blockers if isinstance(blockers, list) else [])}
      </section>

      <section class="section" id="impact-map">
        <div class="section__header">
          <div>
            <h2>지도에서 위치 확인</h2>
            <p class="section__intro">
              후보 조치가 서울 어디에 몰려 있는지 먼저 보고, 아래 표에서 세부 판단을 확인합니다.
            </p>
          </div>
        </div>
        {_render_impact_map(impact_cards)}
      </section>

      <section class="section" id="impact-cards">
        <div class="section__header">
          <div>
            <h2>따릉이 후보 조치</h2>
            <p class="section__intro">
              어느 대여소에서 자전거를 보충하거나 회수해야 하는지 보여줍니다.
              `검증 전` 항목은 운영 판단 참고용이며 대외 성과로 말하면 안 됩니다.
            </p>
          </div>
          <div class="section__meta">{_pill(len(impact_cards), f"{len(impact_cards)}건")}</div>
        </div>
        {_table(
            ["무엇을 판단하나", "긴급도", "현재 상태", "예상 효과", "검증 상태"],
            _render_impact_rows(impact_cards, 20),
        )}
      </section>

      <section class="section" id="policy-audit">
        <div class="section__header">
          <div>
            <h2>영향 정책 비교</h2>
            <p class="section__intro">
              무검토 공개 기준선과 guardrail 정책을 비교합니다.
              목표는 후보 이동량을 숨기는 것이 아니라 미검증 성과 claim을 차단하는 것입니다.
            </p>
          </div>
          <div class="section__meta">{_pill(len(impact_policy_audit), f"{len(impact_policy_audit)}개 정책")}</div>
        </div>
        {_table(
            ["정책", "검토 용량", "검토 후보 단위", "미검증 claim 단위", "결과"],
            _render_policy_rows(impact_policy_audit, 12),
        )}
      </section>

      <section class="section" id="policy-robustness">
        <div class="section__header">
          <div>
            <h2>Reviewer policy robustness</h2>
            <p class="section__intro">
              후보 효과 jitter, confidence 하락, 상위 source 누락과 검토 용량 변화에서
              confidence-weighted guarded ordering의 regret와 선택 안정성을 비교합니다.
              이 값은 실현 효과나 인과 추정치가 아닙니다.
            </p>
          </div>
          <div class="section__meta">{_pill(len(robustness_rows), f"{len(robustness_rows)}개 비교")}</div>
        </div>
        {_table(
            ["Stress scenario", "검토 용량", "Confidence 조정 단위", "Oracle regret", "선택 안정성"],
            _render_robustness_rows(robustness_rows, 12),
        )}
      </section>

      <section class="section" id="action-plan">
        <div class="section__header">
          <div>
            <h2>검토 실행 계획</h2>
            <p class="section__intro">
              검토자가 시간이 제한될 때 먼저 볼 후보를 정렬했습니다.
              승인해도 현장 작업과 public claim은 실행되지 않고 local audit에만 남습니다.
            </p>
          </div>
          <div class="section__meta">{_pill(len(reviewer_action_plan), f"{len(reviewer_action_plan)}건")}</div>
        </div>
        {_table(
            ["먼저 볼 후보", "긴급도", "누적 후보 단위", "권장 결정"],
            _render_action_plan_rows(reviewer_action_plan, 12),
        )}
      </section>

      <section class="section" id="evidence-bundles">
        <div class="section__header">
          <div>
            <h2>심의 근거 패킷</h2>
            <p class="section__intro">
              Impact card와 검토 계획을 하나의 근거 계약으로 묶고 관측 시각, freshness SLA,
              SHA-256 fingerprint를 함께 확인합니다. 최신성 잠금에 실패하면 자동으로 근거 요청 상태가 됩니다.
            </p>
          </div>
          <div class="section__meta">{_pill(len(reviewer_evidence_bundles), f"{len(reviewer_evidence_bundles)}건")}</div>
        </div>
        {_table(
            ["검토 근거", "최신성", "근거 잠금", "권장 결정"],
            _render_evidence_bundle_rows(reviewer_evidence_bundles, 12),
        )}
      </section>

      <section class="section" id="reviewer-queue">
        <div class="section__header">
          <div>
            <h2>검토 대기열</h2>
            <p class="section__intro">
              각 권고에 대해 `승인`, `반려`, `근거 요청` 중 하나를 선택합니다.
              이 조작은 검토 기록만 남기며 현장 작업을 실행하지 않습니다.
              각 행은 시스템 ID가 아니라 실제 확인해야 할 이유를 기준으로 표시됩니다.
            </p>
          </div>
          <div class="section__meta">{_pill(pending, f"{pending}건 대기")}</div>
        </div>
        {_table(action_header, _render_queue_rows(queue, 50, include_actions))}
      </section>

      <section class="section" id="approval-history">
        <div class="section__header">
          <div>
            <h2>승인 이력</h2>
            <p class="section__intro">최근 검토자 결정과 local audit timestamp입니다.</p>
          </div>
        </div>
        {_table(["시간", "검토 기록", "결정", "검토자"], _render_history_rows(history, 12))}
      </section>

      <section class="section" id="approval-audit-integrity">
        <div class="section__header">
          <div>
            <h2>승인 감사 무결성</h2>
            <p class="section__intro">
              각 reviewer 결정을 이전 event hash에 연결하고, 이력을 replay해 현재 queue 상태와 대조합니다.
              이는 local tamper evidence이며 전자서명이나 외부 공증은 아닙니다.
            </p>
          </div>
          <div class="section__meta">{_pill(audit_status)}</div>
        </div>
        {_table(["검증", "결과", "의미"], _render_audit_integrity_rows(audit_integrity))}
      </section>

      <section class="section" id="operations">
        <div class="section__header">
          <div>
            <h2>운영 상태</h2>
            <p class="section__intro">개발자와 운영자가 확인할 산출물 freshness와 runtime 상태입니다.</p>
          </div>
        </div>
        {_table(["산출물", "존재", "갱신 시각(UTC)"], _render_artifact_rows(ops.get("artifacts", {})))}
      </section>
    </main>
  </div>
{script}</body>
</html>
"""
