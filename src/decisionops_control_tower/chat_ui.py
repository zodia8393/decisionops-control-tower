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
  padding: 20px 22px;
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(135deg, #f7fbfe 0%, #ffffff 60%);
}
.chat-heading__copy {
  max-width: 720px;
}
.chat-heading__copy h2 {
  margin: 0;
  font-size: clamp(1.28rem, 2vw, 1.55rem);
  letter-spacing: -0.025em;
}
.chat-heading__copy p {
  margin-top: var(--space-2);
  color: var(--color-muted);
}
.chat-heading__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
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
.chat-reset {
  min-height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-panel);
  color: var(--color-muted);
  padding: 6px 10px;
  font-size: 0.76rem;
  font-weight: 800;
}
.chat-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 342px);
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
  padding: 12px 20px;
  overflow-x: auto;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-panel);
  scrollbar-width: thin;
}
.chat-presets::before {
  align-self: center;
  color: var(--color-subtle);
  content: "추천";
  flex: 0 0 auto;
  font-size: 0.7rem;
  font-weight: 900;
  letter-spacing: 0.06em;
  text-transform: uppercase;
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
.chat-root--dataset-empty .chat-preset {
  border-style: dashed;
  color: var(--color-subtle);
}
.chat-contextbar {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 54px;
  border-bottom: 1px solid var(--color-border);
  background: #f8fafc;
  padding: 9px 20px;
}
.chat-contextbar__state {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 1px;
}
.chat-contextbar__state strong,
.chat-contextbar__state span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chat-contextbar__state strong { font-size: 0.8rem; }
.chat-contextbar__state span { color: var(--color-muted); font-size: 0.72rem; }
.chat-contextbar__dot {
  width: 9px;
  height: 9px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #a2acba;
  box-shadow: 0 0 0 4px #e8ebef;
}
.chat-root--dataset-active .chat-contextbar__dot {
  background: var(--color-success);
  box-shadow: 0 0 0 4px #dff5ec;
}
.chat-contextbar__actions { display: flex; flex: 0 0 auto; gap: 7px; }
.chat-contextbar__button {
  min-height: 34px;
  border: 1px solid var(--color-border-strong);
  border-radius: 9px;
  background: #fff;
  color: var(--color-ink);
  padding: 6px 10px;
  font-size: 0.75rem;
  font-weight: 800;
}
.chat-evidence-toggle { display: none; }
.chat-thread {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 350px;
  height: clamp(440px, 58vh, 680px);
  max-height: 680px;
  overflow-y: auto;
  padding: var(--space-5);
}
.chat-message {
  max-width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: var(--color-panel);
  padding: var(--space-4);
  box-shadow: 0 5px 14px rgba(26, 49, 69, 0.05);
}
.chat-message--assistant { width: 100%; }
.chat-message--user {
  width: fit-content;
  max-width: 78%;
  align-self: flex-end;
  border-color: #9fc6de;
  background: #eaf5fb;
}
.chat-onboarding {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  margin-top: var(--space-4);
  border: 1px dashed #a8bfd1;
  border-radius: 12px;
  background: #f7fbfe;
  padding: 14px;
}
.chat-onboarding.is-dragover,
.dataset-panel.is-dragover {
  border-color: var(--color-primary);
  background: #f1efff;
  box-shadow: inset 0 0 0 2px rgba(91, 78, 229, 0.12);
}
.chat-onboarding__copy strong { display: block; font-size: 0.88rem; }
.chat-onboarding__copy span {
  display: block;
  margin-top: 3px;
  color: var(--color-muted);
  font-size: 0.75rem;
}
.chat-upload-trigger { white-space: nowrap; }
.chat-root--dataset-active .chat-onboarding { display: none; }
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
.analysis-result {
  margin-top: var(--space-4);
  border: 1px solid #b9d5e5;
  border-radius: var(--radius-md);
  background: #f5fbff;
  padding: var(--space-3);
}
.analysis-result__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin: 9px 0 4px;
}
.analysis-action {
  min-height: 32px;
  border: 1px solid #b8cddd;
  border-radius: 8px;
  background: #fff;
  color: #29475f;
  padding: 5px 9px;
  font-size: 0.74rem;
  font-weight: 800;
}
.analysis-details,
.analysis-provenance {
  margin-top: var(--space-3);
  border-top: 1px solid var(--color-border);
  padding-top: 9px;
}
.analysis-details > summary,
.analysis-provenance > summary {
  cursor: pointer;
  color: var(--color-muted);
  font-size: 0.8rem;
  font-weight: 800;
}
.analysis-result summary {
  cursor: pointer;
  color: var(--color-ink);
  font-weight: 850;
}
.analysis-result__meta {
  margin: 8px 0;
  color: var(--color-muted);
  font-size: 0.82rem;
}
.dataset-overview {
  margin-top: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-panel-soft);
  padding: var(--space-3);
}
.dataset-overview > summary {
  cursor: pointer;
  color: var(--color-ink);
  font-weight: 850;
}
.overview-quality {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: var(--space-3);
}
.overview-quality span {
  border-radius: 999px;
  background: #ffffff;
  padding: 5px 9px;
  color: var(--color-muted);
  font-size: 0.76rem;
  font-weight: 750;
}
.chat-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: var(--space-3);
}
.chat-suggestion {
  min-height: 34px;
  border: 1px solid #9bc7dc;
  border-radius: 999px;
  background: #f2f9fc;
  color: var(--color-primary-strong);
  padding: 6px 10px;
  font: inherit;
  font-size: 0.78rem;
  font-weight: 800;
  cursor: pointer;
}
.chat-suggestion:hover { background: #e3f2f8; }
.chat-suggestion:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 2px;
}
.analysis-table-wrap {
  overflow: auto;
  max-height: 340px;
  margin-top: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: 9px;
}
.analysis-table {
  width: 100%;
  border-collapse: collapse;
  background: #ffffff;
  font-size: 0.82rem;
}
.analysis-table th,
.analysis-table td {
  border: 1px solid var(--color-border);
  padding: 7px 9px;
  text-align: left;
  white-space: nowrap;
}
.analysis-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--color-panel-soft);
}
.analysis-table tr:last-child td { border-bottom: 0; }
.analysis-chart {
  margin: var(--space-3) 0;
  border-radius: 10px;
  background: #ffffff;
  padding: var(--space-3);
}
.analysis-chart figcaption {
  margin-bottom: 8px;
  color: var(--color-muted);
  font-size: 0.78rem;
  font-weight: 800;
}
.analysis-chart__svg {
  display: block;
  width: 100%;
  height: auto;
  min-height: 190px;
}
.model-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
  gap: 8px;
  margin: var(--space-3) 0;
}
.model-metric {
  border: 1px solid var(--color-border);
  border-radius: 9px;
  background: #ffffff;
  padding: 9px;
}
.model-metric strong,
.model-metric span { display: block; }
.model-metric strong { color: var(--color-muted); font-size: 0.72rem; }
.model-metric span { margin-top: 4px; color: var(--color-ink); font-weight: 850; }
.model-warning {
  margin-top: 8px;
  border-left: 3px solid var(--color-warning);
  padding-left: 9px;
  color: var(--color-muted);
  font-size: 0.8rem;
}
.analysis-chart__row {
  display: grid;
  grid-template-columns: minmax(72px, 0.8fr) minmax(120px, 3fr) auto;
  gap: 8px;
  align-items: center;
  margin: 6px 0;
  font-size: 0.78rem;
}
.analysis-chart__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.analysis-chart__track {
  position: relative;
  height: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: #dcecf5;
}
.analysis-chart__bar {
  height: 100%;
  border-radius: inherit;
  background: #1677a6;
}
.analysis-chart__track--signed {
  background: linear-gradient(to right, #f5dede 0 49.5%, #8da8b8 49.5% 50.5%, #dcecf5 50.5% 100%);
}
.analysis-chart__track--signed .analysis-chart__bar { position: absolute; top: 0; }
.analysis-chart__bar--negative { background: #b84d5f; }
.analysis-query {
  display: block;
  overflow-x: auto;
  margin-top: var(--space-3);
  border-radius: 8px;
  background: #102536;
  color: #e7f4fb;
  padding: 10px;
  font-size: 0.75rem;
  white-space: pre;
}
.analysis-plan {
  margin-top: var(--space-3);
}
.analysis-plan summary {
  color: var(--color-muted);
  font-size: 0.8rem;
}
.analysis-plan code {
  display: block;
  overflow-x: auto;
  margin-top: 8px;
  white-space: pre;
  font-size: 0.72rem;
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
  position: sticky;
  bottom: 0;
  z-index: 5;
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
  white-space: nowrap;
}
.chat-help {
  margin-top: var(--space-2);
  color: var(--color-subtle);
  font-size: 0.76rem;
}
.chat-pending {
  display: flex;
  width: fit-content;
  align-items: center;
  gap: 9px;
  color: var(--color-muted);
  font-size: 0.82rem;
}
.chat-pending__dots { display: inline-flex; gap: 3px; }
.chat-pending__dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: chat-pulse 1s infinite ease-in-out;
}
.chat-pending__dots i:nth-child(2) { animation-delay: 0.12s; }
.chat-pending__dots i:nth-child(3) { animation-delay: 0.24s; }
@keyframes chat-pulse {
  0%, 60%, 100% { opacity: .35; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-3px); }
}
.chat-toast {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 80;
  max-width: min(340px, calc(100vw - 32px));
  border-radius: 10px;
  background: #172033;
  color: #fff;
  padding: 10px 13px;
  box-shadow: 0 12px 30px rgba(23, 32, 51, .25);
  font-size: .8rem;
  font-weight: 750;
}
.chat-toast[hidden] { display: none !important; }
.chat-evidence {
  min-width: 0;
  border-left: 1px solid var(--color-border);
  background: #fcfdff;
  padding: 22px;
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
.dataset-panel[data-drop-target] { transition: background 120ms ease, border-color 120ms ease; }
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
.dataset-summary--pending {
  border-left-color: var(--color-warning);
  color: var(--color-warning);
}
.dataset-summary--error {
  border-left-color: var(--color-danger);
  color: var(--color-danger);
  font-weight: 700;
}
.dataset-summary--success {
  border-left-color: var(--color-success);
  color: var(--color-success);
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
.analysis-session {
  margin-top: var(--space-3);
  border: 1px solid #b8d4c9;
  border-radius: 10px;
  background: #f0fbf6;
  padding: var(--space-3);
}
.analysis-session[hidden] { display: none !important; }
.analysis-session strong {
  display: block;
  color: var(--color-success);
  font-size: 0.8rem;
}
.analysis-session p {
  margin-top: 5px;
  color: #355c4d;
  line-height: 1.45;
}
.analysis-session__reset {
  min-height: 30px;
  margin-top: var(--space-2);
  border-color: #9bcab8;
  background: #ffffff;
  padding: 5px 8px;
  font-size: 0.76rem;
}
.analysis-session__reset[hidden] { display: none !important; }
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
  .chat-evidence {
    display: none;
    border-left: 0;
    border-top: 1px solid var(--color-border);
  }
  .chat-root--evidence-open .chat-evidence { display: block; }
  .chat-evidence-toggle { display: inline-flex; align-items: center; }
}
@media (max-width: 640px) {
  .chat-heading { flex-direction: column; padding: var(--space-4); }
  .chat-heading__actions { width: 100%; justify-content: space-between; }
  .chat-mode { display: none; }
  .chat-contextbar { padding: 9px 12px; }
  .chat-contextbar__state span { max-width: 160px; }
  .chat-contextbar__button { padding: 6px 8px; }
  .chat-presets { flex-wrap: nowrap; padding: var(--space-3) var(--space-4); }
  .chat-thread { min-height: 320px; height: min(54vh, 520px); padding: 14px 12px; }
  .chat-message { max-width: 100%; }
  .chat-message--user { max-width: 88%; }
  .chat-onboarding { grid-template-columns: 1fr; }
  .chat-upload-trigger { width: 100%; }
  .chat-response-meta { grid-template-columns: 1fr; }
  .chat-composer { padding: 12px; }
  .chat-input-row { align-items: end; gap: 8px; }
  .chat-input { min-height: 46px; max-height: 110px; padding: 11px 12px; }
  .chat-submit { min-width: 92px; min-height: 46px; }
  .chat-help { display: none; }
  .chat-evidence { padding: var(--space-4); }
  .analysis-result { padding: 10px; }
  .analysis-table { font-size: .75rem; }
  .analysis-chart__row { grid-template-columns: minmax(58px, .7fr) minmax(90px, 2fr) auto; }
  .model-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (prefers-reduced-motion: reduce) {
  .chat-pending__dots i { animation: none; }
}

/* ChatGPT-inspired conversation surface: results first, evidence on demand. */
.chat-section {
  position: relative;
  min-height: calc(100dvh - 56px);
  margin: 0;
  border: 0;
  border-radius: 0;
  background: #ffffff;
  box-shadow: none;
}
.chat-layout { display: block; min-height: calc(100dvh - 56px); }
.chat-main { min-width: 0; min-height: calc(100dvh - 56px); background: #ffffff; }
.chat-thread {
  display: flex;
  height: auto;
  min-height: clamp(390px, 58vh, 660px);
  max-height: none;
  gap: 28px;
  overflow-y: visible;
  padding: 48px max(20px, calc((100% - 820px) / 2)) 24px;
  background: #ffffff;
}
.chat-message {
  width: 100%;
  max-width: 100%;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.chat-message--assistant { align-self: stretch; }
.chat-message--user {
  width: fit-content;
  max-width: min(70%, 620px);
  margin-left: auto;
  padding: 10px 16px;
  border-radius: 20px;
  background: #f4f4f4;
}
.chat-message[data-chat-welcome] {
  align-self: center;
  padding-top: 8vh;
  text-align: center;
}
.chat-message[data-chat-welcome] > .chat-status,
.chat-message[data-chat-welcome] > .chat-message__label { display: none; }
.chat-message[data-chat-welcome] > .chat-message__answer {
  font-size: clamp(1.55rem, 3vw, 2rem);
  font-weight: 550;
  line-height: 1.25;
  letter-spacing: -.035em;
}
.chat-message__label {
  margin-bottom: 7px;
  color: #555555;
  font-size: .73rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: none;
}
.chat-message__question { font-size: .94rem; font-weight: 450; line-height: 1.55; }
.chat-message__answer { font-size: .96rem; font-weight: 400; line-height: 1.75; }
.chat-onboarding {
  width: min(680px, 100%);
  margin: 28px auto 0;
  padding: 15px 16px;
  border: 1px solid #e5e5e5;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 2px 10px rgba(0, 0, 0, .04);
  text-align: left;
}
.chat-onboarding__copy strong { color: #222222; font-size: .84rem; }
.chat-onboarding__copy span { color: #777777; font-size: .72rem; }
.chat-upload-trigger { border-radius: 999px; border-color: #111111; background: #111111; }
.chat-presets {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  width: min(820px, 100%);
  margin: 0 auto;
  padding: 10px 20px 14px;
  gap: 8px;
  overflow: visible;
  border: 0;
  background: #ffffff;
}
.chat-presets::before {
  content: "빠른 시작";
  grid-column: 1 / -1;
  padding: 0 3px 2px;
  color: #858585;
  font-size: .68rem;
  font-weight: 700;
}
.chat-preset {
  min-height: 52px;
  padding: 10px 14px !important;
  border: 1px solid #e5e5e5 !important;
  border-radius: 16px !important;
  background: #ffffff !important;
  color: #3b3b3b !important;
  box-shadow: none !important;
  text-align: left;
  white-space: normal;
}
.chat-preset:hover { border-color: #d7d7d7 !important; background: #f7f7f8 !important; }
.chat-root--dataset-empty .chat-preset { opacity: .58; border-style: solid !important; }
.chat-contextbar {
  width: min(780px, calc(100% - 40px));
  min-height: 40px;
  margin: 0 auto 6px;
  padding: 3px 0;
  border: 0;
  background: transparent;
}
.chat-contextbar__state { color: #777777; font-size: .71rem; }
.chat-contextbar__state::before { width: 7px; height: 7px; background: #b8b8b8; }
.chat-root--dataset-active .chat-contextbar__state::before { background: #10a37f; }
.chat-contextbar__state strong { color: #4b4b4b; font-size: .72rem; }
.chat-contextbar__button {
  min-height: 31px;
  padding: 6px 10px;
  border: 0;
  border-radius: 999px;
  background: #f4f4f4;
  color: #5f5f5f;
  font-size: .68rem;
}
.chat-contextbar__button:hover { border-color: transparent; background: #e9e9e9; color: #111111; }
.chat-evidence-toggle { display: inline-flex; align-items: center; }
.chat-composer {
  position: sticky;
  z-index: 20;
  bottom: 0;
  padding: 8px 20px 20px;
  border: 0;
  background: linear-gradient(to bottom, rgba(255,255,255,0), #ffffff 28%, #ffffff 100%);
}
.chat-input-row {
  width: min(780px, 100%);
  margin: 0 auto;
  padding: 7px 8px;
  gap: 6px;
  align-items: end;
  border: 1px solid #d1d1d1;
  border-radius: 28px;
  background: #ffffff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, .08);
}
.chat-input-row:focus-within { border-color: #8f8f8f; box-shadow: 0 2px 14px rgba(0, 0, 0, .11); }
.chat-input {
  min-height: 40px;
  max-height: 180px;
  padding: 10px 6px 8px;
  border: 0;
  border-radius: 0;
  background: transparent;
  font-size: .92rem;
  line-height: 1.4;
  resize: none;
}
.chat-input:focus-visible { outline: none; box-shadow: none; }
.chat-attach {
  display: grid;
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #333333;
  font: inherit;
  font-size: 1.35rem;
  line-height: 1;
  cursor: pointer;
}
.chat-attach:hover { background: #f0f0f0; }
.chat-attach:focus-visible { outline: 3px solid rgba(134, 183, 254, .5); outline-offset: 1px; }
.chat-submit {
  display: grid;
  flex: 0 0 auto;
  width: 40px;
  min-width: 40px;
  height: 40px;
  min-height: 40px;
  place-items: center;
  padding: 0;
  border-radius: 50%;
  background: #111111;
  font-size: 1.08rem;
  line-height: 1;
}
.chat-submit:hover { background: #292929; }
.chat-submit:disabled { border-color: #d0d0d0; background: #d0d0d0; }
.chat-help {
  width: min(780px, 100%);
  margin: 7px auto 0;
  color: #999999;
  font-size: .65rem;
  text-align: center;
}
.chat-status {
  margin-bottom: 5px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent !important;
  color: #777777 !important;
  font-size: .68rem;
}
.chat-response-card, .dataset-overview {
  border: 0;
  border-radius: 16px;
  background: #f7f7f8;
  box-shadow: none;
}
.analysis-result {
  margin-top: 15px;
  padding: 16px;
  border: 0;
  border-radius: 18px;
  background: #f7f7f8;
}
.analysis-chart { border-color: #e5e5e5; border-radius: 14px; background: #ffffff; }
.model-metric { border: 0; border-radius: 12px; background: #ffffff; }
.analysis-action {
  border: 0;
  border-radius: 999px;
  background: #eaeaea;
  color: #333333;
}
.analysis-action:hover { background: #dfdfdf; color: #111111; }
.chat-evidence {
  display: none;
  position: fixed;
  z-index: 80;
  inset: 0 0 0 auto;
  width: min(420px, 100vw);
  height: 100dvh;
  overflow-y: auto;
  padding: 22px;
  border: 0;
  background: #ffffff;
  box-shadow: -16px 0 50px rgba(0, 0, 0, .16);
}
.chat-root--evidence-open .chat-evidence { display: block; }
.chat-evidence__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.chat-evidence h3 { margin: 3px 0 0; font-size: 1rem; }
.chat-evidence__intro { margin: 5px 0 0; color: #777777; font-size: .72rem; }
.chat-evidence__close {
  display: grid;
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: #f4f4f4;
  color: #333333;
  font: inherit;
  font-size: 1.3rem;
  cursor: pointer;
}
.chat-evidence__close:hover { background: #e9e9e9; }
.chat-evidence-backdrop {
  display: none;
  position: fixed;
  z-index: 75;
  inset: 0;
  padding: 0;
  border: 0;
  background: rgba(0, 0, 0, .24);
}
.chat-root--evidence-open .chat-evidence-backdrop { display: block; }
body.evidence-drawer-open { overflow: hidden; }
.dataset-panel {
  margin-top: 20px;
  padding: 15px;
  border: 0;
  border-radius: 16px;
  background: #f7f7f8;
}
.dataset-panel--dragover { border-color: #111111; background: #f0f0f0; }
.dataset-file-label, .dataset-clear, .analysis-session__reset { border-color: #d8d8d8; color: #333333; }
.analysis-session { border-color: #e0e0e0; background: #ffffff; }
.evidence-list { max-height: none; overflow: visible; }
.chat-evidence-item { border-color: #e5e5e5; border-radius: 14px; }
.chat-evidence-item__number { background: #ececec; color: #333333; }
.chat-toast { border-color: #d8d8d8; border-radius: 999px; background: #222222; color: #ffffff; }
@media (max-width: 640px) {
  .chat-section, .chat-layout, .chat-main { min-height: calc(100dvh - 52px); }
  .chat-thread {
    min-height: 360px;
    height: auto;
    max-height: none;
    gap: 22px;
    overflow-y: visible;
    padding: 28px 14px 18px;
  }
  .chat-message--user { max-width: 88%; }
  .chat-message[data-chat-welcome] { padding-top: 5vh; }
  .chat-onboarding { width: 100%; margin-top: 22px; text-align: left; }
  .chat-upload-trigger { width: auto; }
  .chat-presets { grid-template-columns: repeat(2, minmax(0, 1fr)); padding: 8px 12px 12px; }
  .chat-preset { min-height: 48px; padding: 9px 10px !important; font-size: .68rem; }
  .chat-contextbar { width: calc(100% - 24px); overflow-x: auto; }
  .chat-contextbar__state span { max-width: 120px; }
  .chat-contextbar__button { white-space: nowrap; }
  .chat-composer { padding: 6px 10px 10px; }
  .chat-input-row { gap: 4px; padding: 6px; }
  .chat-input { min-height: 40px; max-height: 140px; padding: 9px 4px 7px; }
  .chat-attach, .chat-submit { width: 40px; min-width: 40px; height: 40px; min-height: 40px; }
  .chat-help { display: none; }
  .chat-evidence { width: 100vw; padding: 18px; }
  .analysis-result { padding: 11px; }
}
"""


CHAT_SCRIPT = r"""
<script>
(() => {
  const root = document.querySelector("[data-chat-root]");
  if (!root) return;
  const live = root.dataset.liveChat === "true";
  const requiresDataset = root.dataset.requiresDataset === "true";
  const recordedNode = document.getElementById("chat-recorded-data");
  const recorded = recordedNode ? JSON.parse(recordedNode.textContent) : {};
  const form = root.querySelector("[data-chat-form]");
  const input = root.querySelector("[data-chat-input]");
  const submit = root.querySelector("[data-chat-submit]");
  const thread = root.querySelector("[data-chat-thread]");
  const evidence = root.querySelector("[data-evidence-list]");
  const fileInput = root.querySelector("[data-dataset-file]");
  const datasetSummary = root.querySelector("[data-dataset-summary]");
  const emptyDatasetLabel = root.dataset.emptyDatasetLabel || "파일을 선택하지 않았습니다.";
  const clearDataset = root.querySelector("[data-dataset-clear]");
  const resetConversation = root.querySelector("[data-chat-reset]");
  const analysisSession = root.querySelector("[data-analysis-session]");
  const analysisSessionTitle = root.querySelector("[data-analysis-session-title]");
  const analysisSessionState = root.querySelector("[data-analysis-session-state]");
  const resetAnalysis = root.querySelector("[data-analysis-reset]");
  const contextTitle = root.querySelector("[data-chat-context-title]");
  const contextDetail = root.querySelector("[data-chat-context-detail]");
  const uploadTriggers = Array.from(root.querySelectorAll("[data-upload-trigger]"));
  const evidenceToggles = Array.from(root.querySelectorAll("[data-evidence-toggle]"));
  const evidencePanel = root.querySelector("[data-chat-evidence]");
  const toast = root.querySelector("[data-chat-toast]");
  let pendingMessage = null;
  let toastTimer = null;
  let dataset = null;
  let datasetProfile = null;
  let conversationHistory = [];
  let lastAssistantPayload = null;
  let previousAnalysisPlan = null;
  let previousAdvancedPlan = null;
  let previousPredictionPlan = null;
  let requestInFlight = false;

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

  function setRequestState(inFlight, label = "분석 중") {
    requestInFlight = inFlight;
    submit.disabled = inFlight;
    submit.textContent = inFlight ? "…" : (submit.dataset.idleLabel || "질문하기");
    submit.setAttribute("aria-label", inFlight ? label : "질문 보내기");
    [fileInput, resetConversation, clearDataset, resetAnalysis].forEach((control) => {
      if (control) control.disabled = inFlight;
    });
    uploadTriggers.forEach((button) => { button.disabled = inFlight || !live; });
    root.querySelectorAll("[data-chat-question], .chat-suggestion").forEach((button) => {
      button.disabled = inFlight;
    });
  }

  function showPendingMessage(label = "데이터를 확인하고 있습니다") {
    if (pendingMessage) pendingMessage.remove();
    pendingMessage = node("article", "chat-message chat-message--assistant chat-pending");
    pendingMessage.setAttribute("role", "status");
    const dots = node("span", "chat-pending__dots");
    dots.setAttribute("aria-hidden", "true");
    dots.append(node("i"), node("i"), node("i"));
    pendingMessage.append(dots, node("span", "", label));
    thread.append(pendingMessage);
    thread.scrollTop = thread.scrollHeight;
  }

  function clearPendingMessage() {
    if (pendingMessage) pendingMessage.remove();
    pendingMessage = null;
  }

  function showToast(message) {
    if (!toast) return;
    window.clearTimeout(toastTimer);
    toast.textContent = message;
    toast.hidden = false;
    toastTimer = window.setTimeout(() => { toast.hidden = true; }, 2400);
  }

  function apiErrorMessage(payload, status) {
    const detail = payload && payload.detail;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
    if (Array.isArray(detail)) {
      const messages = detail.map((item) => {
        if (!item || typeof item !== "object") return String(item || "");
        const path = Array.isArray(item.loc)
          ? item.loc.filter((part) => part !== "body").join(".")
          : "";
        const message = String(item.msg || item.message || "입력값이 올바르지 않습니다.");
        return path ? `${path}: ${message}` : message;
      }).filter(Boolean);
      if (messages.length) return messages.join(" · ");
    }
    return `HTTP ${status}`;
  }

  function friendlyDatasetError(error) {
    const message = String(error && error.message ? error.message : error || "알 수 없는 오류");
    const rules = [
      [/10000-row limit|10,?000.*row/i, "10,000행 제한을 초과했습니다. 파일을 나누거나 표본을 줄여 주세요."],
      [/100-column limit|100.*column/i, "100열 제한을 초과했습니다. 분석에 필요한 열만 남겨 주세요."],
      [/content exceeds|at most 1400000 characters/i, "1MB 파일 제한을 초과했습니다. 더 작은 파일을 선택해 주세요."],
      [/credential columns/i, "비밀번호·token·주민등록번호 같은 민감 컬럼은 업로드할 수 없습니다."],
      [/nested JSON/i, "중첩 JSON은 지원하지 않습니다. object 배열 형태의 평면 record로 바꿔 주세요."],
      [/at least one data row/i, "데이터 행이 없습니다. header 아래에 한 행 이상 넣어 주세요."],
      [/could not be parsed|content is invalid/i, "파일을 해석하지 못했습니다. 형식과 인코딩을 확인해 주세요."],
      [/filename.*120|at most 120 characters/i, "파일명이 너무 깁니다. 120자 이하로 바꿔 주세요."],
    ];
    const matched = rules.find(([pattern]) => pattern.test(message));
    return `업로드 실패: ${matched ? matched[1] : message}`;
  }

  function columnNameNormalizationLabel(profile) {
    const normalization = profile && profile.column_name_normalization;
    const changes = normalization && Array.isArray(normalization.changes)
      ? normalization.changes
      : [];
    if (!normalization || !normalization.applied || !changes.length) return "";
    const examples = changes.slice(0, 3).map((change) => {
      const raw = change.original === null || String(change.original).trim() === ""
        ? `${change.position}열(빈 이름)`
        : String(change.original).slice(0, 24);
      return `${raw} → ${change.normalized}`;
    });
    const remaining = changes.length > examples.length
      ? ` 외 ${changes.length - examples.length}개`
      : "";
    return ` · 컬럼명 자동 정리 ${changes.length}개 (${examples.join(", ")}${remaining})`;
  }

  function tableStructureNormalizationLabel(profile) {
    const structure = profile && profile.table_structure_normalization;
    if (!structure || !structure.applied) return "";
    const changes = [];
    if (Number(structure.header_row) > 1) {
      changes.push(`${structure.header_row}행을 header로 사용`);
      changes.push(`앞 ${structure.preamble_rows_removed || 0}행 제외`);
    }
    if (Number(structure.blank_rows_removed) > 0) {
      changes.push(`빈 행 ${structure.blank_rows_removed}개 제외`);
    }
    return changes.length ? ` · 표 구조 자동 정리 (${changes.join(", ")})` : "";
  }

  function setDatasetSummary(message, state = "") {
    datasetSummary.textContent = message;
    datasetSummary.classList.remove(
      "dataset-summary--pending",
      "dataset-summary--error",
      "dataset-summary--success"
    );
    if (state) datasetSummary.classList.add(`dataset-summary--${state}`);
  }

  function setDatasetUploadError(message) {
    const detail = friendlyDatasetError(message);
    if (dataset && datasetProfile) {
      setDatasetSummary(
        `${detail} 기존 ${datasetProfile.filename}은 이 대화에 계속 연결되어 있습니다.`,
        "error"
      );
      return;
    }
    setDatasetSummary(detail, "error");
  }

  function analysisPlanLabel(plan) {
    if (!plan) return `원본 ${datasetProfile ? datasetProfile.row_count : "—"}행 기준 · 누적 조건 없음`;
    const operationLabels = {
      count: "건수", share: "비율", count_distinct: "고유값 수",
      sum: "합계", mean: "평균", median: "중앙값", stddev: "표준편차",
      correlation: "상관계수", min: "최소", max: "최대"
    };
    const parts = [];
    if (Array.isArray(plan.group_by) && plan.group_by.length) {
      parts.push(`그룹 ${plan.group_by.join(", ")}`);
    }
    if (Array.isArray(plan.metrics) && plan.metrics.length) {
      const metric = plan.metrics[0];
      const columns = [metric.column, metric.secondary_column].filter(Boolean).join(" ↔ ");
      parts.push(`${columns ? `${columns} ` : ""}${operationLabels[metric.operation] || metric.operation}`);
    } else if (plan.operation === "select") {
      parts.push("행 조회");
    }
    if (Array.isArray(plan.filters) && plan.filters.length) {
      const filters = plan.filters.slice(0, 3).map((item) =>
        `${item.column} ${item.operator} ${item.value === null ? "NULL" : item.value}`
      );
      parts.push(`조건 ${filters.join(", ")}${plan.filters.length > 3 ? ` 외 ${plan.filters.length - 3}개` : ""}`);
    }
    if (Number(plan.limit) > 0) parts.push(`최대 ${plan.limit}행`);
    return `현재 누적 분석 · ${parts.join(" · ")}`;
  }

  function currentPlanLabel() {
    if (previousPredictionPlan) {
      const features = Array.isArray(previousPredictionPlan.features) && previousPredictionPlan.features.length
        ? previousPredictionPlan.features.join(", ")
        : "safe auto";
      return `현재 예측 · ${previousPredictionPlan.task} · target ${previousPredictionPlan.target} · features ${features}${previousPredictionPlan.task === "forecasting" ? ` · horizon ${previousPredictionPlan.horizon}` : ""}`;
    }
    if (previousAdvancedPlan) {
      return `현재 심화 분석 · ${previousAdvancedPlan.operation} · ${previousAdvancedPlan.columns.join(" ↔ ")}${previousAdvancedPlan.group_by ? ` · group ${previousAdvancedPlan.group_by}` : ""}${previousAdvancedPlan.time_column ? ` · time ${previousAdvancedPlan.time_column}` : ""}`;
    }
    return analysisPlanLabel(previousAnalysisPlan);
  }

  function renderAnalysisSession() {
    const active = Boolean(dataset && datasetProfile);
    root.classList.toggle("chat-root--dataset-active", active);
    root.classList.toggle("chat-root--dataset-empty", !active && requiresDataset);
    uploadTriggers.forEach((button) => {
      if (button.hasAttribute("data-upload-trigger-label")) {
        button.textContent = active ? "파일 교체" : "파일 선택";
      }
    });
    if (contextTitle) {
      contextTitle.textContent = active
        ? `${datasetProfile.filename} · ${datasetProfile.row_count}행 × ${datasetProfile.column_count}열`
        : "분석 데이터가 아직 없습니다";
    }
    if (contextDetail) {
      contextDetail.textContent = active
        ? currentPlanLabel()
        : "파일을 연결하면 설명·품질 점검·기초 통계를 자동 실행합니다.";
    }
    if (!analysisSession) return;
    analysisSession.hidden = !active;
    if (active) {
      analysisSessionTitle.textContent = `${datasetProfile.filename} · 현재 채팅에 계속 연결됨`;
      analysisSessionState.textContent = currentPlanLabel();
    }
    if (resetAnalysis) {
      resetAnalysis.hidden = !active || !(previousAnalysisPlan || previousAdvancedPlan || previousPredictionPlan);
    }
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
    const contextUsed = Boolean(payload.conversation && payload.conversation.context_used);
    const modeLabel = payload.prediction
      ? "Analysis Copilot · Prediction"
      : payload.advanced_analysis
      ? "Analysis Copilot · Advanced"
      : payload.analysis
      ? "Analysis Copilot · DuckDB"
      : payload.mode === "deterministic-overview"
      ? "Analysis Copilot · overview"
      : payload.mode === "deterministic-profile"
      ? "Analysis Copilot · profile"
      : payload.mode === "deterministic-capabilities"
      ? "Analysis Copilot · guide"
      : payload.mode === "dataset-conversation"
      ? "Analysis Copilot"
      : payload.mode === "analysis-clarification"
      ? "Analysis Copilot · 조건 확인"
      : payload.mode === "data-science-clarification"
      ? "Analysis Copilot · 조건 확인"
      : payload.mode === "data-science-guardrail"
      ? "Analysis Copilot · 실행 조건"
      : payload.mode === "analysis-session-reset"
      ? "Analysis Copilot · 원본 복원"
      : payload.mode === "llm"
      ? "Decision Copilot · LLM"
      : contextUsed
      ? "Decision Copilot · 이어서 답변"
      : "Decision Copilot · guarded";
    message.append(node("span", "chat-message__label", modeLabel));
    message.append(node("p", "chat-message__answer", payload.answer || "답변을 만들지 못했습니다."));
    if (payload.overview) addDatasetOverview(message, payload.overview);
    if (payload.analysis) addAnalysisResult(message, payload.analysis);
    if (payload.advanced_analysis) addAdvancedResult(message, payload.advanced_analysis);
    if (payload.prediction) addPredictionResult(message, payload.prediction);
    if (Array.isArray(payload.suggested_questions)) {
      addSuggestedQuestions(message, payload.suggested_questions);
    }
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
    return message;
  }

  function displayValue(value) {
    if (value === null || value === undefined) return "—";
    if (typeof value === "number" && Number.isFinite(value)) {
      if (Number.isInteger(value)) return value.toLocaleString("ko-KR");
      if (value !== 0 && Math.abs(value) < 0.000001) return value.toExponential(3);
      return value.toLocaleString("ko-KR", {maximumFractionDigits: 6});
    }
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function escapeCsvCell(value) {
    let text = value === null || value === undefined
      ? ""
      : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
    if (typeof value === "string" && /^[=+\-@\t\r]/.test(text)) text = `'${text}`;
    return `"${text.replaceAll('"', '""')}"`;
  }

  function downloadRows(rows, filename = "analysis-result.csv") {
    if (!Array.isArray(rows) || !rows.length) return;
    const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row || {}))));
    const lines = [columns.map(escapeCsvCell).join(",")];
    rows.forEach((row) => lines.push(columns.map((column) => escapeCsvCell(row[column])).join(",")));
    const blob = new Blob(["\ufeff", lines.join("\n")], {type: "text/csv;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
    showToast(`표시된 ${rows.length}행을 CSV로 저장했습니다.`);
  }

  async function copyText(value) {
    let copied = false;
    try {
      await navigator.clipboard.writeText(value);
      copied = true;
    } catch (_) {}
    if (!copied) {
      const helper = node("textarea", "sr-only", value);
      document.body.append(helper);
      helper.select();
      copied = document.execCommand("copy");
      helper.remove();
    }
    showToast(copied ? "SQL을 클립보드에 복사했습니다." : "SQL을 복사하지 못했습니다.");
  }

  function addResultActions(parent, rows, sql, filename) {
    if ((!Array.isArray(rows) || !rows.length) && !sql) return;
    const toolbar = node("div", "analysis-result__toolbar");
    if (Array.isArray(rows) && rows.length) {
      const exportButton = node("button", "analysis-action", `CSV 저장 · ${rows.length}행`);
      exportButton.type = "button";
      exportButton.dataset.exportCsv = "true";
      exportButton.addEventListener("click", () => downloadRows(rows, filename));
      toolbar.append(exportButton);
    }
    if (sql) {
      const copyButton = node("button", "analysis-action", "SQL 복사");
      copyButton.type = "button";
      copyButton.dataset.copySql = "true";
      copyButton.addEventListener("click", () => copyText(sql));
      toolbar.append(copyButton);
    }
    parent.append(toolbar);
  }

  function addProvenance(parent, sql, plan, planLabel) {
    if (!sql && !plan) return;
    const provenance = node("details", "analysis-provenance");
    provenance.append(node("summary", "", "SQL · 실행 계획 보기"));
    if (sql) provenance.append(node("code", "analysis-query", sql));
    if (plan) {
      const planDetails = node("details", "analysis-plan");
      planDetails.append(node("summary", "", planLabel));
      planDetails.append(node("code", "", JSON.stringify(plan, null, 2)));
      provenance.append(planDetails);
    }
    parent.append(provenance);
  }

  function addDatasetOverview(message, overview) {
    const details = node("details", "dataset-overview");
    details.open = true;
    details.append(node("summary", "", "자동 데이터 점검 · 품질과 기초 통계"));
    const quality = overview.quality || {};
    const qualityRow = node("div", "overview-quality");
    qualityRow.append(
      node("span", "", `결측 셀 ${quality.missing_cell_count || 0}개`),
      node("span", "", `중복 행 ${quality.duplicate_row_count || 0}개`),
      node("span", "", `합계·요약 행 ${quality.summary_row_count || 0}개`)
    );
    details.append(qualityRow);
    const statistics = overview.statistics || {};
    qualityRow.append(node(
      "span",
      "",
      `기초통계 분모 ${statistics.denominator_row_count || 0}/${statistics.input_row_count || 0}행`
    ));
    const columns = Array.isArray(statistics.columns) ? statistics.columns : [];
    const rows = Array.isArray(statistics.rows) ? statistics.rows : [];
    const labels = {
      column: "컬럼", count: "유효", missing: "결측", min: "최소",
      q1: "Q1", mean: "평균", median: "중앙값", q3: "Q3",
      max: "최대", stddev: "표준편차"
    };
    if (rows.length) {
      const wrap = node("div", "analysis-table-wrap");
      const table = node("table", "analysis-table overview-statistics");
      const head = node("thead", "");
      const headerRow = node("tr", "");
      columns.forEach((column) => headerRow.append(node("th", "", labels[column] || column)));
      head.append(headerRow);
      const body = node("tbody", "");
      rows.forEach((row) => {
        const item = node("tr", "");
        columns.forEach((column) => item.append(node("td", "", displayValue(row[column]))));
        body.append(item);
      });
      table.append(head, body);
      wrap.append(table);
      details.append(wrap);
    } else {
      details.append(node("p", "analysis-result__meta", "수치형 컬럼이 없어 범주 빈도 중심으로 분석합니다."));
    }
    message.append(details);
  }

  function addSuggestedQuestions(message, suggestions) {
    const valid = suggestions.filter((item) => item && typeof item.question === "string");
    if (!valid.length) return;
    const wrap = node("div", "chat-suggestions");
    valid.forEach((item) => {
      const button = node("button", "chat-suggestion", `${item.label || "분석"} · ${item.question}`);
      button.type = "button";
      button.addEventListener("click", () => ask(item.question));
      wrap.append(button);
    });
    message.append(wrap);
  }

  function addAnalysisResult(message, analysis) {
    const details = node("details", "analysis-result");
    details.open = true;
    details.append(node("summary", "", `검증된 분석 결과 · ${analysis.output_row_count || 0}행`));
    details.append(node(
      "p",
      "analysis-result__meta",
      `입력 ${analysis.input_row_count || 0}행 · 조건 통과 ${analysis.denominator_row_count || 0}행 · numeric source: ${analysis.numeric_source_of_truth || "unknown"}`
    ));
    const columns = Array.isArray(analysis.columns) ? analysis.columns : [];
    const rows = Array.isArray(analysis.rows) ? analysis.rows.slice(0, 50) : [];
    const sql = analysis.provenance && analysis.provenance.sql;
    addResultActions(details, rows, sql, "analysis-result.csv");
    const chart = buildAnalysisChart(columns, rows);
    if (chart) details.append(chart);
    if (columns.length) {
      const wrap = node("div", "analysis-table-wrap");
      const table = node("table", "analysis-table");
      const head = node("thead", "");
      const headerRow = node("tr", "");
      columns.forEach((column) => headerRow.append(node("th", "", column)));
      head.append(headerRow);
      const body = node("tbody", "");
      rows.forEach((row) => {
        const item = node("tr", "");
        columns.forEach((column) => item.append(node("td", "", displayValue(row[column]))));
        body.append(item);
      });
      table.append(head, body);
      wrap.append(table);
      details.append(wrap);
    }
    addProvenance(details, sql, analysis.plan, "검증된 AnalysisPlan 보기");
    message.append(details);
  }

  function addRowsTable(parent, rows, preferredColumns = []) {
    if (!Array.isArray(rows) || !rows.length) return;
    const allColumns = Array.from(new Set(rows.flatMap((row) => Object.keys(row || {}))));
    const columns = preferredColumns.length
      ? [...preferredColumns.filter((column) => allColumns.includes(column)), ...allColumns.filter((column) => !preferredColumns.includes(column))]
      : allColumns;
    const wrap = node("div", "analysis-table-wrap");
    const table = node("table", "analysis-table");
    const head = node("thead", "");
    const header = node("tr", "");
    columns.forEach((column) => header.append(node("th", "", column)));
    head.append(header);
    const body = node("tbody", "");
    rows.slice(0, 50).forEach((row) => {
      const tr = node("tr", "");
      columns.forEach((column) => tr.append(node("td", "", displayValue(row[column]))));
      body.append(tr);
    });
    table.append(head, body);
    wrap.append(table);
    parent.append(wrap);
  }

  function svgElement(tag, attributes = {}) {
    const item = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attributes).forEach(([key, value]) => item.setAttribute(key, String(value)));
    return item;
  }

  function buildSeriesChart(title, rows, xColumn, yColumns, scatter = false) {
    const points = rows.slice(0, 500).map((row, index) => {
      const rawX = row[xColumn];
      const parsed = typeof rawX === "number" ? rawX : Date.parse(rawX);
      return {row, x: Number.isFinite(parsed) ? parsed : index};
    }).filter((item) => yColumns.some((column) => Number.isFinite(Number(item.row[column]))));
    if (points.length < 2) return null;
    const xValues = points.map((item) => item.x);
    const yValues = points.flatMap((item) => yColumns.map((column) => Number(item.row[column])).filter(Number.isFinite));
    const xMin = Math.min(...xValues), xMax = Math.max(...xValues);
    const yMin = Math.min(...yValues), yMax = Math.max(...yValues);
    const width = 640, height = 230, pad = 28;
    const scaleX = (value) => pad + ((value - xMin) / (xMax - xMin || 1)) * (width - pad * 2);
    const scaleY = (value) => height - pad - ((value - yMin) / (yMax - yMin || 1)) * (height - pad * 2);
    const colors = ["#1677a6", "#d97706", "#6d4fc2"];
    const figure = node("figure", "analysis-chart");
    figure.append(node("figcaption", "", title));
    const svg = svgElement("svg", {viewBox: `0 0 ${width} ${height}`, class: "analysis-chart__svg", role: "img", "aria-label": title});
    svg.append(svgElement("line", {x1: pad, y1: height - pad, x2: width - pad, y2: height - pad, stroke: "#9fb3c1"}));
    svg.append(svgElement("line", {x1: pad, y1: pad, x2: pad, y2: height - pad, stroke: "#9fb3c1"}));
    yColumns.forEach((column, colorIndex) => {
      const valid = points.filter((item) => Number.isFinite(Number(item.row[column])));
      if (scatter) {
        valid.forEach((item) => svg.append(svgElement("circle", {cx: scaleX(item.x), cy: scaleY(Number(item.row[column])), r: 3.2, fill: colors[colorIndex % colors.length], opacity: 0.8})));
      } else if (valid.length > 1) {
        const path = valid.map((item, index) => `${index ? "L" : "M"}${scaleX(item.x).toFixed(1)},${scaleY(Number(item.row[column])).toFixed(1)}`).join(" ");
        svg.append(svgElement("path", {d: path, fill: "none", stroke: colors[colorIndex % colors.length], "stroke-width": 2.2}));
      }
    });
    figure.append(svg);
    return figure;
  }

  function buildStructuredChart(chart) {
    if (!chart || !Array.isArray(chart.data) || !chart.data.length) return null;
    if (chart.chart_type === "histogram") {
      const rows = chart.data.map((item) => ({
        bin: `${Number(item.bin_start).toPrecision(4)}–${Number(item.bin_end).toPrecision(4)}`,
        count: item.count
      }));
      return buildAnalysisChart(["bin", "count"], rows, true);
    }
    if (chart.chart_type === "bar") return buildAnalysisChart(["group", "mean"], chart.data);
    if (chart.chart_type === "scatter") {
      return buildSeriesChart(chart.title, chart.data, chart.x_label, [chart.y_label], true);
    }
    if (chart.chart_type === "line") {
      return buildSeriesChart(chart.title, chart.data, chart.x_label, ["value", "rolling_value"], false);
    }
    return null;
  }

  function addAdvancedResult(message, analysis) {
    const details = node("details", "analysis-result");
    details.open = true;
    details.append(node("summary", "", `검증된 심화 분석 · ${analysis.plan.operation}`));
    details.append(node("p", "analysis-result__meta", `입력 ${analysis.input_row_count}행 · 필터 후 ${analysis.denominator_row_count}행 · 계산 분모 ${analysis.valid_row_count}행 · numeric source: ${analysis.numeric_source_of_truth}`));
    const rows = Array.isArray(analysis.rows) ? analysis.rows.slice(0, 50) : [];
    const sql = analysis.provenance && analysis.provenance.sql;
    addResultActions(details, rows, sql, "advanced-analysis-result.csv");
    const chart = buildStructuredChart(analysis.chart);
    if (chart) details.append(chart);
    addRowsTable(details, [analysis.statistics]);
    (analysis.warnings || []).forEach((warning) => details.append(node("p", "model-warning", warning)));
    (analysis.assumptions || []).forEach((assumption) => details.append(node("p", "analysis-result__meta", `가정 · ${assumption}`)));
    const rawDetails = node("details", "analysis-details");
    rawDetails.append(node("summary", "", `상세 결과 ${rows.length}행 · 재현 근거 보기`));
    addRowsTable(rawDetails, rows);
    addProvenance(rawDetails, sql, analysis.plan, "검증된 AdvancedAnalysisPlan 보기");
    details.append(rawDetails);
    message.append(details);
  }

  function addMetricCards(parent, title, metrics) {
    if (!metrics) return;
    const wrap = node("div", "model-metrics");
    Object.entries(metrics).forEach(([key, value]) => {
      const card = node("div", "model-metric");
      card.append(node("strong", "", `${title} · ${key}`), node("span", "", displayValue(value)));
      wrap.append(card);
    });
    parent.append(wrap);
  }

  function addPredictionResult(message, prediction) {
    const details = node("details", "analysis-result");
    details.open = true;
    details.append(node("summary", "", `${prediction.status === "MODEL_READY" ? "검증된 예측 결과" : "모델 승격 보류"} · ${prediction.plan.task}`));
    details.append(node("p", "analysis-result__meta", `사용 가능 ${prediction.usable_row_count}/${prediction.denominator_row_count}행 · split ${prediction.split_evidence.strategy} · selected ${prediction.selected_model || "없음"}`));
    const predictionRows = Array.isArray(prediction.predictions) ? prediction.predictions.slice(0, 50) : [];
    const sql = prediction.provenance && prediction.provenance.sql;
    addResultActions(details, predictionRows, sql, "prediction-result.csv");
    addMetricCards(details, `Baseline validation (${prediction.baseline.model})`, prediction.baseline.validation_metrics);
    (prediction.candidates || []).forEach((candidate) => addMetricCards(details, `${candidate.model} validation`, candidate.validation_metrics));
    addMetricCards(details, "Held-out test", prediction.test_metrics);
    if (prediction.chart && prediction.chart.chart_type === "actual_vs_predicted") {
      const chart = buildSeriesChart(prediction.chart.title, prediction.chart.data, "__decisionops_source_row__", ["actual", "predicted"]);
      if (chart) details.append(chart);
    } else if (prediction.chart && prediction.chart.chart_type === "forecast") {
      const chart = buildSeriesChart(prediction.chart.title, prediction.chart.data, "time", ["actual", "predicted"]);
      if (chart) details.append(chart);
    }
    if (prediction.feature_importance && prediction.feature_importance.length) {
      const importanceRows = prediction.feature_importance.slice(0, 12).map((item) => ({feature: item.feature, importance: item.importance_mean}));
      const chart = buildAnalysisChart(["feature", "importance"], importanceRows);
      if (chart) {
        chart.querySelector("figcaption").textContent = "Permutation importance · validation 기준";
        details.append(chart);
      }
    }
    const card = prediction.model_card || {};
    (prediction.warnings || []).forEach((warning) => details.append(node("p", "model-warning", warning)));
    if (prediction.bounded_shap) details.append(node("p", "analysis-result__meta", `설명 · ${prediction.bounded_shap.method} · ${prediction.bounded_shap.sample_rows}행 · 최대 ${prediction.bounded_shap.feature_limit} features`));
    const technicalDetails = node("details", "analysis-details");
    technicalDetails.append(node("summary", "", `예측값 ${predictionRows.length}행 · model card · 재현 근거 보기`));
    addRowsTable(technicalDetails, predictionRows, ["time", "__decisionops_source_row__", "actual", "predicted", "lower", "upper", "confidence"]);
    addRowsTable(technicalDetails, [{
      status: card.status,
      selected_model: card.selected_model,
      primary_metric: card.primary_metric,
      baseline: card.baseline,
      training_rows: card.training_rows,
      validation_rows: card.validation_rows,
      test_rows: card.test_rows,
      features_used: (card.features_used || []).join(", "),
      features_excluded: (card.features_excluded || []).join(", ")
    }]);
    addProvenance(technicalDetails, sql, prediction.plan, "검증된 PredictionPlan 보기");
    details.append(technicalDetails);
    message.append(details);
  }

  function buildAnalysisChart(columns, rows, allowUniform = false) {
    if (columns.length < 2 || rows.length < 1) return null;
    const numericColumn = columns.find((column) => rows.some((row) => typeof row[column] === "number" && Number.isFinite(row[column])));
    const labelColumn = columns.find((column) => column !== numericColumn);
    if (!numericColumn || !labelColumn) return null;
    const numericRows = rows.filter((row) => typeof row[numericColumn] === "number" && Number.isFinite(row[numericColumn]));
    if (!numericRows.length || (!allowUniform && new Set(numericRows.map((row) => row[numericColumn])).size <= 1)) return null;
    const points = numericRows.slice(0, 12);
    const maximum = Math.max(...points.map((row) => Math.abs(row[numericColumn])), 0);
    const signed = points.some((row) => row[numericColumn] < 0);
    const figure = node("figure", "analysis-chart");
    figure.append(node("figcaption", "", `${labelColumn}별 ${numericColumn} 비교 · 결과 payload 기준`));
    points.forEach((row) => {
      const item = node("div", "analysis-chart__row");
      item.append(node("span", "analysis-chart__label", displayValue(row[labelColumn])));
      const track = node("span", "analysis-chart__track");
      const bar = node("span", "analysis-chart__bar");
      const width = maximum > 0 ? (Math.abs(row[numericColumn]) / maximum) * (signed ? 50 : 100) : 0;
      bar.style.width = `${Math.max(0, Math.min(width, signed ? 50 : 100))}%`;
      if (signed) {
        track.classList.add("analysis-chart__track--signed");
        if (row[numericColumn] < 0) {
          bar.classList.add("analysis-chart__bar--negative");
          bar.style.right = "50%";
        } else {
          bar.style.left = "50%";
        }
      }
      track.append(bar);
      item.append(track, node("span", "", displayValue(row[numericColumn])));
      figure.append(item);
    });
    return figure;
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
      if (!response.ok) throw new Error(apiErrorMessage(payload, response.status));
      return payload;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    const chunks = [];
    for (let offset = 0; offset < bytes.length; offset += 32768) {
      chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + 32768)));
    }
    return window.btoa(chunks.join(""));
  }

  function recordedAnswer(question) {
    if (recorded[question]) return recorded[question];
    if (lastAssistantPayload) {
      const normalized = question.toLowerCase().replace(/\s+/g, " ").trim();
      const followUp = /^(왜|더|자세히|쉽게|계속|다음|그건|그럼|그러면|앞서|방금)|그\s*(이유|근거|위험|후보|정책|상태|조치)/.test(normalized);
      if (followUp) {
        let answer = `앞선 답변을 이어서 말씀드리면, ${lastAssistantPayload.answer || "확인할 답변이 없습니다."}`;
        if (/왜|이유/.test(normalized) && lastAssistantPayload.risk) {
          answer = `앞선 판단의 핵심 이유는 ${lastAssistantPayload.risk}`;
        } else if (/다음|어떻게|조치/.test(normalized) && lastAssistantPayload.next_action) {
          answer = `다음 단계는 ${lastAssistantPayload.next_action}`;
        } else if (/근거/.test(normalized)) {
          const count = (lastAssistantPayload.citations || []).length;
          answer = `앞선 답변에는 ${count}개의 근거가 연결되어 있습니다. 오른쪽 근거 목록에서 출처와 freshness를 확인할 수 있습니다.`;
        }
        return {
          ...lastAssistantPayload,
          mode: "recorded-context",
          answer,
          conversation: {
            context_used: true,
            history_turns_received: conversationHistory.length,
            user_turns_used: 1,
            scope: "recorded_previous_answer"
          }
        };
      }
    }
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
    if (!trimmed || requestInFlight) return;
    const requestHistory = conversationHistory.slice(-12);
    addUserMessage(trimmed);
    conversationHistory.push({role: "user", content: trimmed});
    setRequestState(true);
    showPendingMessage("질문을 검증 가능한 계획으로 바꾸고 있습니다");
    try {
      const payload = live
        ? await fetchJson("/api/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
              question: trimmed,
              dataset,
              history: requestHistory,
              previous_analysis_plan: previousAnalysisPlan,
              previous_advanced_plan: previousAdvancedPlan,
              previous_prediction_plan: previousPredictionPlan
            })
          })
        : recordedAnswer(trimmed);
      clearPendingMessage();
      addAssistantMessage(payload);
      lastAssistantPayload = payload;
      if (payload.dataset_profile) datasetProfile = payload.dataset_profile;
      if (payload.mode === "analysis-session-reset") {
        previousAnalysisPlan = null;
        previousAdvancedPlan = null;
        previousPredictionPlan = null;
      } else if (payload.prediction && payload.prediction.plan) {
        previousPredictionPlan = payload.prediction.plan;
        previousAdvancedPlan = null;
        previousAnalysisPlan = null;
      } else if (payload.advanced_analysis && payload.advanced_analysis.plan) {
        previousAdvancedPlan = payload.advanced_analysis.plan;
        previousPredictionPlan = null;
        previousAnalysisPlan = null;
      } else if (payload.analysis && payload.analysis.plan) {
        previousAnalysisPlan = payload.analysis.plan;
        previousAdvancedPlan = null;
        previousPredictionPlan = null;
      }
      renderAnalysisSession();
      conversationHistory.push({
        role: "assistant",
        content: String(payload.answer || "").slice(0, 1000)
      });
    } catch (err) {
      clearPendingMessage();
      addAssistantMessage({
        status: "NEEDS_MORE_EVIDENCE",
        mode: "fallback",
        answer: "질문을 처리하지 못했습니다.",
        risk: err && err.name === "AbortError" ? "응답 시간이 15초를 초과했습니다." : String(err.message || err),
        next_action: "잠시 후 다시 시도하거나 시스템 상태를 확인하세요.",
        citations: []
      });
    } finally {
      clearPendingMessage();
      setRequestState(false);
      input.value = "";
      input.style.height = "";
      input.focus();
    }
  }

  async function runAutomaticOverview(lockHeld = false) {
    if (requestInFlight && !lockHeld) return;
    if (lockHeld) {
      submit.textContent = "…";
      submit.setAttribute("aria-label", "기본 분석 중");
    } else {
      setRequestState(true, "기본 분석 중");
    }
    showPendingMessage("파일 구조·품질·기초 통계를 점검하고 있습니다");
    try {
      const payload = await fetchJson("/api/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          question: "업로드 데이터 자동 분석 시작",
          dataset,
          history: [],
          previous_analysis_plan: null,
          previous_advanced_plan: null,
          previous_prediction_plan: null
        })
      });
      clearPendingMessage();
      const overviewMessage = addAssistantMessage(payload);
      const firstMessage = thread.firstElementChild;
      thread.scrollTop = Math.max(
        0,
        overviewMessage.offsetTop - (firstMessage ? firstMessage.offsetTop : 0)
      );
      lastAssistantPayload = payload;
      conversationHistory.push({
        role: "assistant",
        content: String(payload.answer || "").slice(0, 1000)
      });
    } catch (err) {
      clearPendingMessage();
      addAssistantMessage({
        status: "NEEDS_MORE_EVIDENCE",
        mode: "fallback",
        answer: "파일은 연결됐지만 자동 기본 분석을 완료하지 못했습니다.",
        risk: String(err.message || err),
        next_action: "‘데이터를 설명해줘’라고 질문하거나 파일을 다시 선택하세요.",
        citations: []
      });
    } finally {
      clearPendingMessage();
      if (!lockHeld) setRequestState(false);
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    ask(input.value);
  });
  root.querySelectorAll("[data-chat-question]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.requiresDataset === "true" && !dataset) {
        setDatasetSummary("먼저 분석할 파일을 선택해 주세요.", "error");
        if (fileInput) fileInput.focus();
        return;
      }
      ask(button.dataset.chatQuestion || button.textContent);
    });
  });
  input.addEventListener("keydown", (event) => {
    const submitWithEnter = event.key === "Enter" && !event.shiftKey && !event.isComposing;
    if (submitWithEnter || ((event.ctrlKey || event.metaKey) && event.key === "Enter")) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
  });
  uploadTriggers.forEach((button) => {
    button.addEventListener("click", () => {
      if (!live || requestInFlight || !fileInput) return;
      fileInput.click();
    });
  });
  function setEvidenceOpen(open) {
    root.classList.toggle("chat-root--evidence-open", open);
    document.body.classList.toggle("evidence-drawer-open", open);
    evidenceToggles.forEach((item) => item.setAttribute("aria-expanded", String(open)));
    if (open && evidencePanel) {
      const closeButton = evidencePanel.querySelector(".chat-evidence__close");
      requestAnimationFrame(() => closeButton && closeButton.focus());
    }
  }
  evidenceToggles.forEach((button) => {
    button.addEventListener("click", () => {
      const open = !root.classList.contains("chat-root--evidence-open");
      setEvidenceOpen(open);
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && root.classList.contains("chat-root--evidence-open")) {
      setEvidenceOpen(false);
      const evidenceButton = root.querySelector(".chat-contextbar .chat-evidence-toggle");
      if (evidenceButton) evidenceButton.focus();
    }
  });
  root.querySelectorAll("[data-drop-target]").forEach((dropTarget) => {
    ["dragenter", "dragover"].forEach((eventName) => {
      dropTarget.addEventListener(eventName, (event) => {
        if (!live || requestInFlight) return;
        event.preventDefault();
        dropTarget.classList.add("is-dragover");
      });
    });
    ["dragleave", "drop"].forEach((eventName) => {
      dropTarget.addEventListener(eventName, (event) => {
        dropTarget.classList.remove("is-dragover");
        if (eventName !== "drop" || !live || requestInFlight || !fileInput) return;
        event.preventDefault();
        const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
        if (!file) return;
        const transfer = new DataTransfer();
        transfer.items.add(file);
        fileInput.files = transfer.files;
        fileInput.dispatchEvent(new Event("change", {bubbles: true}));
      });
    });
  });
  if (resetConversation) {
    resetConversation.addEventListener("click", () => {
      conversationHistory = [];
      lastAssistantPayload = null;
      previousAnalysisPlan = null;
      previousAdvancedPlan = null;
      previousPredictionPlan = null;
      renderAnalysisSession();
      thread.querySelectorAll(".chat-message:not([data-chat-welcome])").forEach((item) => item.remove());
      evidence.replaceChildren(
        node("div", "chat-empty-evidence", "추천 질문을 선택하면 출처와 판단 근거가 여기에 표시됩니다.")
      );
      input.value = "";
      input.style.height = "";
      input.focus();
    });
  }
  if (resetAnalysis) {
    resetAnalysis.addEventListener("click", () => ask("분석 조건 초기화"));
  }

  if (fileInput) {
    fileInput.addEventListener("change", async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      if (!live) {
        setDatasetSummary(
          "공개 snapshot에서는 업로드하지 않습니다. 로컬 live demo를 사용하세요.",
          "error"
        );
        return;
      }
      if (file.size === 0) {
        setDatasetUploadError("빈 파일입니다. 데이터 행이 있는 파일을 선택해 주세요.");
        fileInput.value = "";
        return;
      }
      if (file.size > 1000000) {
        setDatasetUploadError("파일은 1MB 이하여야 합니다.");
        fileInput.value = "";
        return;
      }
      if (file.name.length > 120) {
        setDatasetUploadError("파일명을 120자 이하로 바꿔 주세요.");
        fileInput.value = "";
        return;
      }
      const extension = file.name.toLowerCase().split(".").pop();
      const format = ["csv", "json", "xlsx", "parquet"].includes(extension) ? extension : "";
      if (!format) {
        setDatasetUploadError("CSV, JSON, XLSX, Parquet 파일만 지원합니다.");
        fileInput.value = "";
        return;
      }
      try {
        setRequestState(true, "파일 확인 중");
        setDatasetSummary(`${file.name} 확인 중…`, "pending");
        const binary = format === "xlsx" || format === "parquet";
        const content = binary ? arrayBufferToBase64(await file.arrayBuffer()) : await file.text();
        const candidateDataset = {filename: file.name, format, content, content_encoding: binary ? "base64" : "utf-8"};
        const validation = await fetchJson("/api/data/analyze?response_envelope=true", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(candidateDataset)
        });
        if (validation.status !== "accepted" || !validation.profile) {
          throw new Error(
            validation.error && validation.error.message
              ? validation.error.message
              : "데이터셋 검증을 통과하지 못했습니다."
          );
        }
        const profile = validation.profile;
        dataset = candidateDataset;
        datasetProfile = profile;
        setDatasetSummary(
          `${profile.filename} · ${profile.row_count}행 × ${profile.column_count}열 · 결측 ${profile.missing_cell_count}개${tableStructureNormalizationLabel(profile)}${columnNameNormalizationLabel(profile)} · 이 대화에 계속 연결 · 원본 미저장`,
          "success"
        );
        clearDataset.hidden = false;
        conversationHistory = [];
        lastAssistantPayload = null;
        previousAnalysisPlan = null;
        previousAdvancedPlan = null;
        previousPredictionPlan = null;
        renderAnalysisSession();
        thread.querySelectorAll(".chat-message:not([data-chat-welcome])").forEach((item) => item.remove());
        await runAutomaticOverview(true);
      } catch (err) {
        setDatasetUploadError(err);
        clearDataset.hidden = !dataset;
        renderAnalysisSession();
        fileInput.value = "";
      } finally {
        setRequestState(false);
      }
    });
  }
  if (clearDataset) {
    clearDataset.addEventListener("click", () => {
      dataset = null;
      datasetProfile = null;
      conversationHistory = [];
      lastAssistantPayload = null;
      previousAnalysisPlan = null;
      previousAdvancedPlan = null;
      previousPredictionPlan = null;
      if (fileInput) fileInput.value = "";
      setDatasetSummary(emptyDatasetLabel);
      clearDataset.hidden = true;
      renderAnalysisSession();
      thread.querySelectorAll(".chat-message:not([data-chat-welcome])").forEach((item) => item.remove());
      evidence.replaceChildren(
        node("div", "chat-empty-evidence", "파일을 선택하면 자동 분석 근거가 여기에 표시됩니다.")
      );
    });
  }
  renderAnalysisSession();
})();
</script>
"""


def _script_json(payload: dict[str, Any]) -> str:
    value = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return value.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _public_safe_answers(recorded_chat: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    safe = json.loads(json.dumps(recorded_chat, ensure_ascii=False))
    anchor_map = {
        "/api/control-state": "#technical-boundaries",
        "/api/impact-cards": "#validation-results",
        "/api/reviewer-action-plan": "#validation-results",
        "/api/reviewer-evidence-bundles": "#validation-results",
        "/api/review-queue": "#validation-results",
        "/api/impact-policy-audit": "#validation-results",
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
    preset_questions: list[str] | None = None,
    require_dataset_for_presets: bool = False,
    heading: str = "데이터로 바로 질문해 보세요",
    introduction: str = "정형 지표와 문서 근거를 함께 찾고, 답변의 각 판단을 실제 source에 연결합니다.",
    welcome: str = "운영 데이터와 문서를 근거로 답합니다. 위험한 요청은 거부하고, 근거가 부족하면 사람의 검토가 필요하다고 표시합니다.",
) -> str:
    questions = preset_questions if preset_questions is not None else list(recorded_chat)
    dataset_attribute = ' data-requires-dataset="true"' if require_dataset_for_presets else ""
    preset_disabled = " disabled" if require_dataset_for_presets and not live_chat else ""
    presets = "".join(
        f'<button class="chat-preset" type="button" data-chat-question="{html.escape(question, quote=True)}"{dataset_attribute}{preset_disabled}>{html.escape(question)}</button>'
        for question in questions
    )
    disabled = "" if live_chat else " disabled"
    disabled_label = "" if live_chat else ' aria-disabled="true"'
    mode_label = f"Live · {vector_store}" if live_chat else "Recorded · read-only"
    dataset_note = (
        "한 번 올리면 업로드 해제 전까지 이 채팅에 계속 연결 · CSV/JSON/XLSX/Parquet · 제목/빈 행 뒤 실제 header와 빈·중복 컬럼명 자동 정리 · 최대 1MB, 10,000행, 100열 · 원본 미저장"
        if live_chat
        else "공개 snapshot에서는 업로드하지 않습니다. 로컬 Docker demo에서 사용할 수 있습니다."
    )
    empty_dataset_label = (
        "파일을 선택하지 않았습니다. 먼저 분석할 파일을 올려 주세요."
        if require_dataset_for_presets and live_chat
        else "공개 snapshot에서는 파일을 업로드하지 않습니다."
        if require_dataset_for_presets
        else "기본 demo data를 사용합니다."
        if live_chat
        else "공개 snapshot은 기본 demo data만 사용합니다."
    )
    contextbar = (
        f"""
            <div class="chat-contextbar" aria-label="현재 분석 데이터">
              <span class="chat-contextbar__dot" aria-hidden="true"></span>
              <span class="chat-contextbar__state">
                <strong data-chat-context-title>분석 데이터가 아직 없습니다</strong>
                <span data-chat-context-detail>파일을 연결하면 설명·품질 점검·기초 통계를 자동 실행합니다.</span>
              </span>
              <span class="chat-contextbar__actions">
                <button class="chat-contextbar__button" type="button" data-upload-trigger data-upload-trigger-label{disabled}>파일 선택</button>
                <button class="chat-contextbar__button chat-evidence-toggle" type="button" data-evidence-toggle aria-controls="chat-evidence-panel" aria-expanded="false">데이터·근거</button>
                <button class="chat-contextbar__button" type="button" data-chat-reset>새 대화</button>
              </span>
            </div>
        """
        if require_dataset_for_presets
        else ""
    )
    onboarding = (
        f"""
                <div class="chat-onboarding" data-drop-target>
                  <span class="chat-onboarding__copy">
                    <strong>먼저 데이터 파일을 연결하세요</strong>
                    <span>끌어다 놓거나 파일을 선택하면 설명·품질·기초 통계부터 자동으로 보여드립니다.</span>
                  </span>
                  <button class="button button--primary chat-upload-trigger" type="button" data-upload-trigger data-upload-trigger-label{disabled}>파일 선택</button>
                </div>
        """
        if require_dataset_for_presets
        else ""
    )
    dataset_file_label = (
        '<label class="sr-only" for="decision-chat-file">CSV · JSON · XLSX · Parquet 선택</label>'
        if require_dataset_for_presets
        else f'<label class="button dataset-file-label" for="decision-chat-file"{disabled_label}>CSV · JSON · XLSX · Parquet 선택</label>'
    )
    heading_block = (
        ""
        if require_dataset_for_presets
        else f"""
        <div class="chat-heading">
          <div class="chat-heading__copy">
            <h2>{html.escape(heading)}</h2>
            <p>{html.escape(introduction)}</p>
          </div>
          <div class="chat-heading__actions">
            <span class="chat-mode">{html.escape(mode_label)}</span>
            <button class="chat-reset" type="button" data-chat-reset>새 대화</button>
          </div>
        </div>
        """
    )
    safe_answers = _public_safe_answers(recorded_chat) if not live_chat else recorded_chat
    return f"""
      <section class="section chat-section{' chat-root--dataset-empty' if require_dataset_for_presets else ''}" id="decision-chat" data-chat-root data-live-chat="{str(live_chat).lower()}" data-requires-dataset="{str(require_dataset_for_presets).lower()}" data-empty-dataset-label="{html.escape(empty_dataset_label, quote=True)}">
        {heading_block}
        <div class="chat-layout">
          <div class="chat-main">
            <div class="chat-thread" data-chat-thread aria-live="polite">
              <article class="chat-message chat-message--assistant" data-chat-welcome>
                <span class="chat-status chat-status--answer">Evidence-grounded</span>
                <span class="chat-message__label">Analysis Copilot</span>
                <p class="chat-message__answer">{html.escape(welcome)}</p>
                {onboarding}
              </article>
            </div>
            <div class="chat-presets" aria-label="추천 질문">{presets}</div>
            {contextbar}
            <form class="chat-composer" data-chat-form>
              <label class="sr-only" for="decision-chat-question">업로드 데이터에 질문하기</label>
              <div class="chat-input-row">
                <button class="chat-attach" type="button" data-upload-trigger aria-label="분석 파일 선택"{disabled}>＋</button>
                <textarea class="chat-input" id="decision-chat-question" data-chat-input maxlength="1000" placeholder="예: region별 revenue 합계 상위 5개" required></textarea>
                <button class="button button--primary chat-submit" type="submit" data-chat-submit data-idle-label="↑" aria-label="질문 보내기">↑</button>
              </div>
              <p class="chat-help">예: 지역별 매출 합계 → web만 보기 → 평균으로 변경 · 앞선 질문을 이어서 이해합니다 · 파일은 업로드 해제 전까지 유지 · Enter 전송 · Shift+Enter 줄바꿈 · Ctrl/⌘ + Enter도 지원</p>
            </form>
          </div>
          <aside class="chat-evidence" id="chat-evidence-panel" data-chat-evidence aria-label="데이터와 답변 근거">
            <div class="chat-evidence__header">
              <div><h3>데이터와 근거</h3><p class="chat-evidence__intro">현재 파일 상태와 답변에 사용한 실행 근거를 확인합니다.</p></div>
              <button class="chat-evidence__close" type="button" data-evidence-toggle aria-controls="chat-evidence-panel" aria-expanded="false" aria-label="데이터와 근거 닫기">×</button>
            </div>
            <div class="dataset-panel" id="uploaded-dataset" data-drop-target>
              <h4>분석할 데이터</h4>
              <p>{html.escape(dataset_note)}</p>
              <input class="dataset-file" id="decision-chat-file" data-dataset-file type="file" aria-describedby="decision-chat-dataset-summary" accept=".csv,.json,.xlsx,.parquet,text/csv,application/json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.apache.parquet"{disabled}>
              {dataset_file_label}
              <div class="dataset-summary" id="decision-chat-dataset-summary" data-dataset-summary role="status" aria-live="polite">{html.escape(empty_dataset_label)}</div>
              <button class="dataset-clear" data-dataset-clear type="button" hidden>업로드 해제</button>
              <div class="analysis-session" data-analysis-session role="status" aria-live="polite" hidden>
                <strong data-analysis-session-title>현재 채팅에 연결됨</strong>
                <p data-analysis-session-state>원본 기준 · 누적 조건 없음</p>
                <button class="analysis-session__reset" data-analysis-reset type="button" hidden>분석 조건만 초기화</button>
              </div>
            </div>
            <div class="evidence-list" data-evidence-list>
              <div class="chat-empty-evidence">추천 질문을 선택하면 출처와 판단 근거가 여기에 표시됩니다.</div>
            </div>
          </aside>
          <button class="chat-evidence-backdrop" type="button" data-evidence-toggle aria-controls="chat-evidence-panel" aria-expanded="false" aria-label="데이터와 근거 닫기"></button>
        </div>
        <div class="chat-toast" data-chat-toast role="status" aria-live="polite" hidden></div>
      </section>
      <script type="application/json" id="chat-recorded-data">{_script_json(safe_answers)}</script>
      {CHAT_SCRIPT}
"""
