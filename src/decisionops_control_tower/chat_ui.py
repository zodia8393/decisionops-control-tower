"""Self-contained chat-first UI for live and recorded Control Tower modes."""

from __future__ import annotations

import html
import json
from typing import Any


CHAT_CSS = """
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.chat-section {
  padding: 0;
  overflow: hidden;
  border-color: #bfd1df;
  box-shadow: 0 18px 50px rgba(29, 55, 78, 0.1);
}
.chat-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5);
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(135deg, #f7fbfe 0%, #ffffff 60%);
}
.chat-heading__copy {
  max-width: 720px;
}
.chat-heading__copy h2 {
  font-size: 1.55rem;
}
.chat-heading__copy p {
  margin-top: var(--space-2);
  color: var(--color-muted);
}
.chat-mode {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex: 0 0 auto;
  border: 1px solid #b8d4c9;
  border-radius: 999px;
  background: #f0fbf6;
  color: var(--color-success);
  padding: 6px 10px;
  font-size: 0.78rem;
  font-weight: 800;
}
.chat-mode::before {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  content: "";
}
.chat-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(290px, 0.75fr);
  min-height: 610px;
}
.chat-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  background: #fbfcfe;
}
.chat-presets {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  overflow-x: auto;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-panel);
  scrollbar-width: thin;
}
.chat-preset {
  flex: 0 0 auto;
  min-height: 34px;
  border-color: #c9d8e4;
  border-radius: 999px;
  background: #f7fafc;
  color: #29475f;
  padding: 7px 11px;
  font-size: 0.8rem;
  font-weight: 700;
}
.chat-thread {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 320px;
  max-height: 620px;
  overflow-y: auto;
  padding: var(--space-5);
}
.chat-message {
  max-width: 88%;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: var(--color-panel);
  padding: var(--space-4);
  box-shadow: 0 5px 14px rgba(26, 49, 69, 0.05);
}
.chat-message--user {
  align-self: flex-end;
  border-color: #9fc6de;
  background: #eaf5fb;
}
.chat-message__label {
  display: block;
  margin-bottom: 6px;
  color: var(--color-subtle);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.chat-message__answer {
  color: var(--color-ink);
  font-size: 1rem;
  font-weight: 650;
  line-height: 1.65;
  white-space: pre-wrap;
}
.chat-response-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  margin-top: var(--space-4);
}
.chat-response-card {
  border-radius: var(--radius-md);
  background: var(--color-panel-soft);
  padding: var(--space-3);
}
.chat-response-card strong {
  display: block;
  margin-bottom: 4px;
  color: var(--color-muted);
  font-size: 0.76rem;
}
.chat-response-card p {
  color: var(--color-muted);
  font-size: 0.88rem;
}
.chat-status {
  display: inline-flex;
  margin-bottom: var(--space-3);
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 0.75rem;
  font-weight: 900;
}
.chat-status--answer { background: var(--color-success-bg); color: var(--color-success); }
.chat-status--refuse { background: var(--color-danger-bg); color: var(--color-danger); }
.chat-status--review { background: var(--color-warning-bg); color: var(--color-warning); }
.chat-status--evidence { background: #eef2ff; color: #4338ca; }
.chat-composer {
  border-top: 1px solid var(--color-border);
  background: var(--color-panel);
  padding: var(--space-4) var(--space-5) var(--space-5);
}
.chat-input-row {
  display: flex;
  align-items: flex-end;
  gap: var(--space-3);
}
.chat-input {
  width: 100%;
  min-height: 52px;
  max-height: 160px;
  resize: vertical;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: #ffffff;
  color: var(--color-ink);
  padding: 13px 14px;
  font: inherit;
  line-height: 1.45;
}
.chat-input:focus-visible,
.dataset-file:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}
.chat-submit {
  min-width: 102px;
  min-height: 52px;
}
.chat-help {
  margin-top: var(--space-2);
  color: var(--color-subtle);
  font-size: 0.76rem;
}
.chat-evidence {
  min-width: 0;
  border-left: 1px solid var(--color-border);
  background: var(--color-panel);
  padding: var(--space-5);
}
.chat-evidence h3 {
  font-size: 1.05rem;
}
.chat-evidence__intro {
  margin-top: 6px;
  color: var(--color-muted);
  font-size: 0.84rem;
}
.dataset-panel {
  margin-top: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-panel-soft);
  padding: var(--space-4);
}
.dataset-panel h4 {
  margin: 0;
  font-size: 0.92rem;
}
.dataset-panel p {
  margin-top: 5px;
  color: var(--color-muted);
  font-size: 0.8rem;
}
.dataset-file {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
}
.dataset-file-label {
  width: 100%;
  margin-top: var(--space-3);
  background: var(--color-panel);
}
.dataset-file:focus-visible + .dataset-file-label {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}
.dataset-file-label[aria-disabled="true"] {
  cursor: not-allowed;
  opacity: 0.58;
  pointer-events: none;
}
.dataset-summary {
  margin-top: var(--space-3);
  border-left: 3px solid var(--color-primary);
  padding-left: var(--space-3);
  color: var(--color-muted);
  font-size: 0.82rem;
}
.dataset-clear {
  min-height: 30px;
  margin-top: var(--space-2);
  padding: 5px 8px;
  font-size: 0.76rem;
}
.dataset-clear[hidden] {
  display: none !important;
}
.evidence-list {
  display: grid;
  gap: var(--space-3);
  max-height: 430px;
  margin-top: var(--space-4);
  overflow-y: auto;
  padding-right: 3px;
}
.chat-evidence-item {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}
.chat-evidence-item__number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  margin-right: 6px;
  border-radius: 50%;
  background: #e8f2f8;
  color: var(--color-primary-strong);
  font-size: 0.75rem;
  font-weight: 900;
}
.chat-evidence-item a {
  color: var(--color-ink);
  font-size: 0.86rem;
  font-weight: 800;
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}
.chat-evidence-item p {
  margin-top: 7px;
  color: var(--color-muted);
  font-size: 0.78rem;
  line-height: 1.45;
}
.chat-evidence-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 8px;
  color: var(--color-subtle);
  font-size: 0.7rem;
}
.chat-empty-evidence {
  margin-top: var(--space-4);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-muted);
  padding: var(--space-4);
  font-size: 0.82rem;
}
@media (max-width: 960px) {
  .chat-layout { grid-template-columns: 1fr; }
  .chat-evidence { border-left: 0; border-top: 1px solid var(--color-border); }
}
@media (max-width: 640px) {
  .chat-heading { flex-direction: column; padding: var(--space-4); }
  .chat-presets { flex-wrap: nowrap; padding: var(--space-3) var(--space-4); }
  .chat-thread { min-height: 300px; padding: var(--space-4); }
  .chat-message { max-width: 100%; }
  .chat-response-meta { grid-template-columns: 1fr; }
  .chat-composer { padding: var(--space-4); }
  .chat-input-row { align-items: stretch; flex-direction: column; }
  .chat-submit { width: 100%; }
  .chat-evidence { padding: var(--space-4); }
}
"""


CHAT_SCRIPT = r"""
<script>
(() => {
  const root = document.querySelector("[data-chat-root]");
  if (!root) return;
  const live = root.dataset.liveChat === "true";
  const recordedNode = document.getElementById("chat-recorded-data");
  const recorded = recordedNode ? JSON.parse(recordedNode.textContent) : {};
  const form = root.querySelector("[data-chat-form]");
  const input = root.querySelector("[data-chat-input]");
  const submit = root.querySelector("[data-chat-submit]");
  const thread = root.querySelector("[data-chat-thread]");
  const evidence = root.querySelector("[data-evidence-list]");
  const fileInput = root.querySelector("[data-dataset-file]");
  const datasetSummary = root.querySelector("[data-dataset-summary]");
  const clearDataset = root.querySelector("[data-dataset-clear]");
  let dataset = null;

  const statusLabels = {
    ANSWER: "근거 기반 답변",
    REFUSE: "위험 요청 거부",
    REVIEW_REQUIRED: "사람의 검토 필요",
    NEEDS_MORE_EVIDENCE: "추가 근거 필요"
  };
  const statusClasses = {
    ANSWER: "answer",
    REFUSE: "refuse",
    REVIEW_REQUIRED: "review",
    NEEDS_MORE_EVIDENCE: "evidence"
  };

  function node(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
  }

  function addUserMessage(question) {
    const message = node("article", "chat-message chat-message--user");
    message.append(node("span", "chat-message__label", "사용자"));
    message.append(node("p", "chat-message__answer", question));
    thread.append(message);
    thread.scrollTop = thread.scrollHeight;
  }

  function addAssistantMessage(payload) {
    const message = node("article", "chat-message chat-message--assistant");
    const status = payload.status || "NEEDS_MORE_EVIDENCE";
    message.append(node("span", `chat-status chat-status--${statusClasses[status] || "evidence"}`, statusLabels[status] || status));
    message.append(node("span", "chat-message__label", payload.mode === "llm" ? "AI reviewer · LLM" : "AI reviewer · guarded"));
    message.append(node("p", "chat-message__answer", payload.answer || "답변을 만들지 못했습니다."));
    const meta = node("div", "chat-response-meta");
    const risk = node("div", "chat-response-card");
    risk.append(node("strong", "", "주의할 점"));
    risk.append(node("p", "", payload.risk || "근거의 최신성을 확인하세요."));
    const action = node("div", "chat-response-card");
    action.append(node("strong", "", "다음 조치"));
    action.append(node("p", "", payload.next_action || "근거를 추가로 확인하세요."));
    meta.append(risk, action);
    message.append(meta);
    thread.append(message);
    thread.scrollTop = thread.scrollHeight;
    renderEvidence(payload.citations || []);
  }

  function safeCitationUrl(value) {
    if (typeof value !== "string") return "#decision-chat";
    if (value.startsWith("#") || value.startsWith("/api/") || value.startsWith("https://github.com/zodia8393/")) return value;
    return "#decision-chat";
  }

  function renderEvidence(items) {
    evidence.replaceChildren();
    if (!items.length) {
      evidence.append(node("div", "chat-empty-evidence", "연결할 수 있는 근거가 없습니다. 시스템이 답변을 보류해야 하는 상태입니다."));
      return;
    }
    items.forEach((item, index) => {
      const card = node("article", "chat-evidence-item");
      const number = node("span", "chat-evidence-item__number", String(index + 1));
      const link = node("a", "", item.title || item.source_id || "근거");
      link.href = safeCitationUrl(item.url);
      if (link.href.startsWith("http")) {
        link.target = "_blank";
        link.rel = "noreferrer";
      }
      card.append(number, link);
      const excerpt = item.excerpt || "근거 요약 없음";
      card.append(node("p", "", excerpt.length > 240 ? `${excerpt.slice(0, 240)}…` : excerpt));
      const meta = node("div", "chat-evidence-item__meta");
      const score = Number(item.retrieval_score);
      meta.append(
        node("span", "", item.source_type || "source"),
        node("span", "", `· ${item.freshness_status || "unknown"}`),
        node("span", "", `· ${item.section || item.path || ""}`),
        ...(Number.isFinite(score) ? [node("span", "", `· hybrid ${score.toFixed(3)}`)] : [])
      );
      card.append(meta);
      evidence.append(card);
    });
  }

  async function fetchJson(url, options) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, {...options, signal: controller.signal});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      return payload;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function recordedAnswer(question) {
    if (recorded[question]) return recorded[question];
    return {
      status: "NEEDS_MORE_EVIDENCE",
      mode: "recorded",
      answer: "공개 페이지는 기록된 질문만 재생합니다. 자유 질문과 데이터 업로드는 로컬 Docker demo에서 사용할 수 있습니다.",
      risk: "정적 페이지에서 live LLM이나 secret을 호출하지 않습니다.",
      next_action: "추천 질문을 선택하거나 README의 로컬 실행 방법을 이용하세요.",
      citations: []
    };
  }

  async function ask(question) {
    const trimmed = question.trim();
    if (trimmed.length < 3) return;
    addUserMessage(trimmed);
    submit.disabled = true;
    submit.textContent = "분석 중";
    try {
      const payload = live
        ? await fetchJson("/api/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({question: trimmed, dataset})
          })
        : recordedAnswer(trimmed);
      addAssistantMessage(payload);
    } catch (err) {
      addAssistantMessage({
        status: "NEEDS_MORE_EVIDENCE",
        mode: "fallback",
        answer: "질문을 처리하지 못했습니다.",
        risk: err && err.name === "AbortError" ? "응답 시간이 15초를 초과했습니다." : String(err.message || err),
        next_action: "잠시 후 다시 시도하거나 시스템 상태를 확인하세요.",
        citations: []
      });
    } finally {
      submit.disabled = false;
      submit.textContent = "질문하기";
      input.value = "";
      input.focus();
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    ask(input.value);
  });
  root.querySelectorAll("[data-chat-question]").forEach((button) => {
    button.addEventListener("click", () => ask(button.dataset.chatQuestion || button.textContent));
  });
  input.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") form.requestSubmit();
  });

  if (fileInput) {
    fileInput.addEventListener("change", async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      if (!live) {
        datasetSummary.textContent = "공개 snapshot에서는 업로드하지 않습니다. 로컬 live demo를 사용하세요.";
        return;
      }
      if (file.size > 1000000) {
        datasetSummary.textContent = "파일은 1MB 이하여야 합니다.";
        fileInput.value = "";
        return;
      }
      const format = file.name.toLowerCase().endsWith(".json") ? "json" : file.name.toLowerCase().endsWith(".csv") ? "csv" : "";
      if (!format) {
        datasetSummary.textContent = "CSV와 JSON 파일만 지원합니다.";
        fileInput.value = "";
        return;
      }
      try {
        const content = await file.text();
        dataset = {filename: file.name, format, content};
        const profile = await fetchJson("/api/data/analyze", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(dataset)
        });
        datasetSummary.textContent = `${profile.filename} · ${profile.row_count}행 × ${profile.column_count}열 · 결측 ${profile.missing_cell_count}개 · 원본 미저장`;
        clearDataset.hidden = false;
      } catch (err) {
        dataset = null;
        datasetSummary.textContent = String(err.message || err);
        fileInput.value = "";
      }
    });
  }
  if (clearDataset) {
    clearDataset.addEventListener("click", () => {
      dataset = null;
      if (fileInput) fileInput.value = "";
      datasetSummary.textContent = live ? "기본 DecisionOps demo data를 사용합니다." : "공개 snapshot은 기본 demo data만 사용합니다.";
      clearDataset.hidden = true;
    });
  }
})();
</script>
"""


def _script_json(payload: dict[str, Any]) -> str:
    value = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return value.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _public_safe_answers(recorded_chat: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    safe = json.loads(json.dumps(recorded_chat, ensure_ascii=False))
    anchor_map = {
        "/api/control-state": "#blockers",
        "/api/impact-cards": "#impact-cards",
        "/api/reviewer-action-plan": "#action-plan",
        "/api/reviewer-evidence-bundles": "#evidence-bundles",
        "/api/review-queue": "#reviewer-queue",
        "/api/impact-policy-audit": "#policy-audit",
    }
    for payload in safe.values():
        for citation in payload.get("citations", []):
            url = str(citation.get("url", ""))
            mapped = False
            for prefix, anchor in anchor_map.items():
                if url.startswith(prefix):
                    citation["url"] = anchor
                    mapped = True
                    break
            if not mapped and not (
                url.startswith("#") or url.startswith("https://github.com/zodia8393/")
            ):
                citation["url"] = "#decision-chat"
    return safe


def render_chat_surface(
    recorded_chat: dict[str, dict[str, Any]],
    *,
    live_chat: bool,
    vector_store: str,
) -> str:
    questions = list(recorded_chat)
    presets = "".join(
        f'<button class="chat-preset" type="button" data-chat-question="{html.escape(question, quote=True)}">{html.escape(question)}</button>'
        for question in questions
    )
    disabled = "" if live_chat else " disabled"
    disabled_label = "" if live_chat else ' aria-disabled="true"'
    mode_label = f"Live · {vector_store}" if live_chat else "Recorded · read-only"
    dataset_note = (
        "CSV/JSON을 선택하면 원본을 저장하지 않고 profile을 근거로 사용합니다."
        if live_chat
        else "공개 snapshot에서는 업로드하지 않습니다. 로컬 Docker demo에서 사용할 수 있습니다."
    )
    safe_answers = _public_safe_answers(recorded_chat) if not live_chat else recorded_chat
    return f"""
      <section class="section chat-section" id="decision-chat" data-chat-root data-live-chat="{str(live_chat).lower()}">
        <div class="chat-heading">
          <div class="chat-heading__copy">
            <h2>데이터로 바로 질문해 보세요</h2>
            <p>정형 지표와 문서 근거를 함께 찾고, 답변의 각 판단을 실제 source에 연결합니다.</p>
          </div>
          <span class="chat-mode">{html.escape(mode_label)}</span>
        </div>
        <div class="chat-layout">
          <div class="chat-main">
            <div class="chat-presets" aria-label="추천 질문">{presets}</div>
            <div class="chat-thread" data-chat-thread aria-live="polite">
              <article class="chat-message chat-message--assistant">
                <span class="chat-status chat-status--answer">Evidence-grounded</span>
                <span class="chat-message__label">AI reviewer</span>
                <p class="chat-message__answer">운영 데이터와 문서를 근거로 답합니다. 위험한 실행 요청은 거부하고, 근거가 부족하면 사람의 검토가 필요하다고 표시합니다.</p>
              </article>
            </div>
            <form class="chat-composer" data-chat-form>
              <label class="sr-only" for="decision-chat-question">운영 데이터에 질문하기</label>
              <div class="chat-input-row">
                <textarea class="chat-input" id="decision-chat-question" data-chat-input maxlength="1000" placeholder="예: 오늘 가장 먼저 검토할 후보는?" required></textarea>
                <button class="button button--primary chat-submit" type="submit" data-chat-submit>질문하기</button>
              </div>
              <p class="chat-help">Ctrl/⌘ + Enter로 전송 · 답변은 advisory이며 deterministic gate가 최종 기준입니다.</p>
            </form>
          </div>
          <aside class="chat-evidence" aria-label="답변 근거">
            <h3>연결된 근거</h3>
            <p class="chat-evidence__intro">답변에 사용한 API field, 문서 section, freshness를 확인할 수 있습니다.</p>
            <div class="dataset-panel" id="uploaded-dataset">
              <h4>분석할 데이터</h4>
              <p>{html.escape(dataset_note)}</p>
              <input class="dataset-file" id="decision-chat-file" data-dataset-file type="file" accept=".csv,.json,text/csv,application/json"{disabled}>
              <label class="button dataset-file-label" for="decision-chat-file"{disabled_label}>CSV 또는 JSON 파일 선택</label>
              <div class="dataset-summary" data-dataset-summary>{'기본 DecisionOps demo data를 사용합니다.' if live_chat else '공개 snapshot은 기본 demo data만 사용합니다.'}</div>
              <button class="dataset-clear" data-dataset-clear type="button" hidden>업로드 해제</button>
            </div>
            <div class="evidence-list" data-evidence-list>
              <div class="chat-empty-evidence">추천 질문을 선택하면 출처와 판단 근거가 여기에 표시됩니다.</div>
            </div>
          </aside>
        </div>
      </section>
      <script type="application/json" id="chat-recorded-data">{_script_json(safe_answers)}</script>
      {CHAT_SCRIPT}
"""
