"""Shared HTML renderer for the DecisionOps reviewer dashboard."""

from __future__ import annotations

import html
from typing import Any


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
.tile-map {
  display: block;
  width: 100%;
  height: 280px;
  border: 0;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-panel-soft);
}
.map-fallback-label {
  padding: var(--space-3) var(--space-3) 0;
  color: var(--color-muted);
  font-size: 0.82rem;
  font-weight: 800;
}
.map-source-note {
  padding: 0 var(--space-3) var(--space-3);
  color: var(--color-subtle);
  font-size: 0.8rem;
}
.map-panel > div {
  min-width: 0;
}
.location-map {
  display: block;
  width: 100%;
  height: auto;
}
.map-grid {
  stroke: #dbe4ef;
  stroke-width: 1;
}
.map-frame {
  fill: #fbfdff;
  stroke: #b7c3d2;
  stroke-width: 2;
}
.map-point {
  fill: var(--color-danger);
  fill-opacity: 0.82;
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
    "deployment_no_go": "배포 보류",
    "high_uncertainty_review": "불확실성 높음",
    "unsafe_write_action": "쓰기 위험",
    "missing_evidence_request": "근거 부족",
    "cross_source_conflict_review": "자료 충돌",
    "publication_restricted": "공개 제한",
    "valid": "좌표 확인됨",
    "missing": "좌표 없음",
    "out_of_range": "좌표 범위 오류",
}


BLOCKER_LABELS = {
    "review queue has no actionable items": "검토자가 처리할 수 있는 queue 항목이 없습니다.",
    "bike-share public deploy decision is not GO": "bike-share 공개 배포 결정이 GO가 아닙니다.",
    "Seoul Ddareungi impact cards are local-review only until validation is READY": (
        "서울 따릉이 impact card는 검증 상태가 READY가 될 때까지 로컬 검토 전용입니다."
    ),
}


ARTIFACT_LABELS = {
    "control_state": "운영 판단 상태 JSON",
    "review_queue": "검토 대기열 CSV",
    "api_contract": "API 계약 JSON",
    "impact_cards": "따릉이 후보 조치 JSON",
    "dashboard": "대시보드 HTML",
    "sqlite_database": "승인 이력 SQLite",
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
    pad = 58
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
    lat_span = max_lat - min_lat
    lon_span = max_lon - min_lon
    map_width = width - pad * 2
    map_height = height - pad * 2
    first_point = points[0]
    invalid_count = max(0, len(impact_cards) - len(points))
    coordinate_note = (
        f"지도 표시 가능 후보 {len(points)}건"
        + (f", 좌표 미확인/범위 오류 {invalid_count}건 제외" if invalid_count else "")
    )
    tile_map_src = (
        "https://www.openstreetmap.org/export/embed.html"
        f"?bbox={min_lon:.6f},{min_lat:.6f},{max_lon:.6f},{max_lat:.6f}"
        f"&layer=mapnik&marker={first_point['lat']:.6f},{first_point['lon']:.6f}"
    )

    def project(lat: float, lon: float) -> tuple[float, float]:
        x = pad + ((lon - min_lon) / lon_span) * map_width
        y = height - pad - ((lat - min_lat) / lat_span) * map_height
        return x, y

    grid_lines = []
    for index in range(1, 4):
        x = pad + map_width * index / 4
        y = pad + map_height * index / 4
        grid_lines.append(
            f'<line class="map-grid" x1="{x:.1f}" y1="{pad}" x2="{x:.1f}" y2="{height - pad}" />'
        )
        grid_lines.append(
            f'<line class="map-grid" x1="{pad}" y1="{y:.1f}" x2="{width - pad}" y2="{y:.1f}" />'
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
        f'<iframe class="tile-map" title="서울 따릉이 후보 조치 실제 지도 타일" src="{_escape(tile_map_src)}" '
        'loading="lazy" referrerpolicy="no-referrer"></iframe>'
        '<div class="map-fallback-label">후보 번호 지도</div>'
        f'<p class="map-source-note">{_escape(coordinate_note)}. 외부 지도 타일이 차단되면 아래 번호 지도를 사용합니다.</p>'
        '<svg class="location-map" viewBox="0 0 920 520" role="img" '
        'aria-labelledby="map-title map-desc">'
        '<title id="map-title">서울 따릉이 후보 조치 위치 지도</title>'
        '<desc id="map-desc">'
        "서울 공개데이터 좌표를 기준으로 따릉이 후보 조치 대여소를 표시합니다. "
        "점이 클수록 예상 완화량이 큽니다."
        "</desc>"
        f'<rect class="map-frame" x="{pad}" y="{pad}" width="{map_width}" height="{map_height}" rx="8" />'
        f"{''.join(grid_lines)}"
        f'<text class="map-axis-label" x="{width / 2:.1f}" y="34" text-anchor="middle">북쪽</text>'
        f'<text class="map-axis-label" x="{width / 2:.1f}" y="{height - 20}" text-anchor="middle">남쪽</text>'
        f'<text class="map-axis-label" x="22" y="{height / 2:.1f}" text-anchor="middle">서쪽</text>'
        f'<text class="map-axis-label" x="{width - 22}" y="{height / 2:.1f}" text-anchor="middle">동쪽</text>'
        f"{''.join(markers)}"
        f'<text class="map-caption" x="{pad}" y="{height - 30}">'
        "점 크기 = 후보 이동량, 번호 = 아래 목록 순서"
        "</text>"
        "</svg>"
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
    return "공개 배포 가능" if str(public_deploy) == "GO" else "공개 배포 보류"


def _release_summary(public_deploy: Any) -> str:
    if str(public_deploy) == "GO":
        return "필수 검증과 readiness gate를 통과했습니다. 그래도 승인 이력은 남기고 배포하세요."
    return "아직 외부 공개나 성과 claim을 하면 안 됩니다. 검토자는 후보 조치와 근거만 확인합니다."


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
    history: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
    ops: dict[str, Any] | None = None,
    include_actions: bool = True,
    include_script: bool = True,
) -> str:
    """Render the Control Tower dashboard as a self-contained HTML document."""

    history = history or []
    summary = summary or {}
    ops = ops or {}
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
    p0_pending = _priority_count(queue, "P0")
    release_label = _release_label(public_deploy)

    action_header = ["무엇을 검토하나", "긴급도", "처리 상태", "확인 필요 이유"]
    if include_actions:
        action_header.append("결정")

    metric_cards = [
        _metric("검토 대기", pending, "승인/반려/근거 요청 필요", "risk" if pending else "good"),
        _metric("긴급 항목", p0_pending, "P0부터 먼저 확인", "risk" if p0_pending else "good"),
        _metric("따릉이 후보 조치", metrics.get("impact_card_rows", 0), f"예상 영향 {candidate_units} 단위"),
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

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DecisionOps Control Tower</title>
  <style>{DASHBOARD_CSS}</style>
</head>
<body data-auth-required="{str(bool(ops.get("auth_required"))).lower()}">
  <div class="app-shell">
    <header class="hero">
      <div class="hero__inner">
        <div class="topline">
          <span class="eyebrow">DecisionOps Control Tower</span>
          {_pill(status)}
          {_pill(public_deploy, f"공개 배포 {public_deploy}")}
        </div>
        <div class="hero__grid">
          <div>
            <h1>오늘의 결론: {release_label}</h1>
            <p class="hero__copy">
              {_escape(_release_summary(public_deploy))}
              이 화면은 서울 따릉이 후보 조치와 모델 권고를 검토하고, 승인 이력을 남기기 위한 운영용 dashboard입니다.
            </p>
            <nav class="hero__actions" aria-label="주요 dashboard actions">
              <a class="button button--primary" href="#reviewer-queue">검토 대기열 보기</a>
              <a class="button" href="#impact-map">지도에서 보기</a>
              <a class="button" href="#impact-cards">따릉이 후보 조치 보기</a>
              <a class="button" href="#blockers">보류 이유 보기</a>
            </nav>
          </div>
          <aside class="readiness-panel" aria-label="지금 해야 할 일">
            <div class="readiness-panel__title">지금 해야 할 일</div>
            <ol class="todo-list">
              <li>
                <span class="todo-index">1</span>
                <span><strong>{p0_pending}건의 긴급 항목부터 확인</strong><span class="todo-detail">P0 항목은 먼저 승인/반려/근거 요청을 결정합니다.</span></span>
              </li>
              <li>
                <span class="todo-index">2</span>
                <span><strong>따릉이 후보 조치의 근거 확인</strong><span class="todo-detail">검증 전 상태이면 외부 성과 claim으로 쓰지 않습니다.</span></span>
              </li>
              <li>
                <span class="todo-index">3</span>
                <span><strong>결정은 local audit에만 저장</strong><span class="todo-detail">버튼은 현장 작업을 실행하지 않고 검토 기록만 남깁니다.</span></span>
              </li>
            </ol>
          </aside>
        </div>
      </div>
    </header>
    <main class="main">
      <section class="section" aria-label="의사결정 지표">
        <div class="section__header">
          <div>
            <h2>핵심 요약</h2>
            <p class="section__intro">처음 볼 때 필요한 숫자만 남겼습니다. 상세 기술 지표는 아래 운영 상태에서 확인합니다.</p>
          </div>
        </div>
        <div class="metric-grid">{''.join(metric_cards)}</div>
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
