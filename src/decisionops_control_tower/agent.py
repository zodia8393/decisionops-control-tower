"""Evidence-grounded reviewer agent for DecisionOps Control Tower."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from typing import Any
from urllib import error, request


AGENT_NAME = "Evidence-Gated Reviewer Agent"
CLAIM_SAFETY_RULE = (
    "Agent는 reviewer evidence를 요약할 수 있지만, GO/NO_GO와 public claim safety의 "
    "source of truth는 deterministic policy gate입니다."
)

REVIEWER_BRIEF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "generated_at",
        "mode",
        "source_status",
        "executive_summary",
        "top_risks",
        "recommended_next_actions",
        "evidence_refs",
        "claim_safety",
        "limitations",
    ],
    "properties": {
        "generated_at": {"type": "string"},
        "mode": {"type": "string", "enum": ["fallback", "llm"]},
        "source_status": {"type": "object"},
        "executive_summary": {"type": "string"},
        "top_risks": {"type": "array"},
        "recommended_next_actions": {"type": "array"},
        "evidence_refs": {"type": "array"},
        "claim_safety": {"type": "object"},
        "limitations": {"type": "array"},
    },
    "additionalProperties": True,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_source_status(
    state: dict[str, Any],
    queue: list[dict[str, Any]],
    impact_cards: list[dict[str, Any]],
    policy_audit: list[dict[str, Any]],
    action_plan: list[dict[str, Any]],
    ops: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = state.get("metrics", {}) if isinstance(state.get("metrics"), dict) else {}
    source = state.get("source_status", {}) if isinstance(state.get("source_status"), dict) else {}
    queue_summary = ops.get("queue", {}) if isinstance(ops, dict) and isinstance(ops.get("queue"), dict) else {}
    queue_total = queue_summary.get("total", len(queue))
    return {
        "project": state.get("project", "decisionops-control-tower"),
        "demo_mode_ready": bool(state.get("demo_mode_ready")),
        "public_deploy_decision": state.get("public_deploy_decision", "UNKNOWN"),
        "impact_card_rows": metrics.get("impact_card_rows", len(impact_cards)),
        "impact_cards_loaded": len(impact_cards),
        "impact_policy_audit_rows": metrics.get("impact_policy_audit_rows", len(policy_audit)),
        "impact_policy_audit_loaded": len(policy_audit),
        "reviewer_action_plan_rows": metrics.get("reviewer_action_plan_rows", len(action_plan)),
        "reviewer_action_plan_loaded": len(action_plan),
        "queue_total": queue_total,
        "queue_loaded": len(queue),
        "seoul_validation_status": source.get("seoul_validation_status", "UNKNOWN"),
        "auth_required": bool(ops.get("auth_required")) if isinstance(ops, dict) else False,
    }


def build_claim_safety(state: dict[str, Any]) -> dict[str, Any]:
    metrics = state.get("metrics", {}) if isinstance(state.get("metrics"), dict) else {}
    public_deploy_decision = str(state.get("public_deploy_decision", "UNKNOWN"))
    blocked_units = int(metrics.get("impact_public_claim_blocked_units", 0) or 0)
    unsupported_avoided = int(metrics.get("impact_unsupported_claim_units_avoided", 0) or 0)
    return {
        "public_deploy_decision": public_deploy_decision,
        "allowed_public_claim": public_deploy_decision == "GO" and blocked_units == 0,
        "blocked_public_claim_units": blocked_units,
        "unsupported_claim_units_avoided": unsupported_avoided,
        "rule": CLAIM_SAFETY_RULE,
    }


def build_evidence_refs(
    state: dict[str, Any],
    queue: list[dict[str, Any]],
    impact_cards: list[dict[str, Any]],
    policy_audit: list[dict[str, Any]],
    action_plan: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metrics = state.get("metrics", {}) if isinstance(state.get("metrics"), dict) else {}
    refs: list[dict[str, Any]] = [
        {
            "source": "/api/control-state",
            "field": "public_deploy_decision",
            "value": state.get("public_deploy_decision", "UNKNOWN"),
        },
        {
            "source": "/api/control-state",
            "field": "metrics.impact_card_rows",
            "value": metrics.get("impact_card_rows", len(impact_cards)),
        },
        {
            "source": "/api/control-state",
            "field": "metrics.impact_public_claim_blocked_units",
            "value": metrics.get("impact_public_claim_blocked_units", 0),
        },
        {"source": "/api/review-queue", "field": "count", "value": len(queue)},
        {"source": "/api/impact-cards", "field": "count", "value": len(impact_cards)},
        {"source": "/api/impact-policy-audit", "field": "count", "value": len(policy_audit)},
        {"source": "/api/reviewer-action-plan", "field": "count", "value": len(action_plan)},
    ]
    return refs


def _unsafe_policy(policy_audit: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in policy_audit:
        if item.get("policy") == "unsafe_auto_publish":
            return item
    return None


def _first_action_plan(action_plan: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not action_plan:
        return None
    return sorted(action_plan, key=lambda item: int(item.get("plan_rank", 9999) or 9999))[0]


def _risk_item(title: str, severity: str, evidence_ref: str) -> dict[str, str]:
    return {"risk": title, "severity": severity, "evidence_ref": evidence_ref}


def _action_item(title: str, owner: str, evidence_ref: str) -> dict[str, str]:
    return {"action": title, "owner": owner, "evidence_ref": evidence_ref}


def build_fallback_reviewer_brief(
    state: dict[str, Any],
    queue: list[dict[str, Any]],
    impact_cards: list[dict[str, Any]],
    policy_audit: list[dict[str, Any]],
    action_plan: list[dict[str, Any]],
    ops: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_status = build_source_status(state, queue, impact_cards, policy_audit, action_plan, ops)
    claim_safety = build_claim_safety(state)
    public_deploy = source_status["public_deploy_decision"]
    queue_total = source_status["queue_total"]
    impact_rows = source_status["impact_card_rows"]
    blocked_units = claim_safety["blocked_public_claim_units"]
    unsafe = _unsafe_policy(policy_audit)
    first_plan = _first_action_plan(action_plan)

    risks = []
    if public_deploy != "GO":
        risks.append(
            _risk_item(
                "Public deploy가 준비되지 않았으므로 local evidence를 외부 성과 claim으로 바꾸면 안 됩니다.",
                "high",
                "/api/control-state.public_deploy_decision",
            )
        )
    if blocked_units:
        risks.append(
            _risk_item(
                f"{blocked_units}개 candidate unit은 public claim 용도로 차단되어 있습니다.",
                "high",
                "/api/control-state.metrics.impact_public_claim_blocked_units",
            )
        )
    if queue_total:
        risks.append(
            _risk_item(
                f"{queue_total}개 review queue 항목은 아직 승인, 반려, 근거 요청 중 하나의 human decision이 필요합니다.",
                "medium",
                "/api/review-queue.count",
            )
        )
    if unsafe and unsafe.get("audit_result") == "fail":
        risks.append(
            _risk_item(
                "무검토 자동 공개 기준선은 policy audit에서 실패합니다.",
                "high",
                "/api/impact-policy-audit[policy=unsafe_auto_publish]",
            )
        )

    actions = []
    if first_plan:
        actions.append(
            _action_item(
                f"{first_plan.get('station_name', '상위 action-plan 후보')}부터 확인하고 local review decision만 기록합니다.",
                "ops_reviewer",
                "/api/reviewer-action-plan[0]",
            )
        )
    if queue_total:
        actions.append(
            _action_item(
                "낮은 우선순위보다 P0/P1 review queue 항목을 먼저 처리합니다.",
                "ops_reviewer",
                "/api/review-queue",
            )
        )
    actions.append(
        _action_item(
            "대외 문구는 agent summary가 아니라 deterministic policy gate에 맞춥니다.",
            "demo_owner",
            "/api/control-state.public_deploy_decision",
        )
    )

    return {
        "agent_name": AGENT_NAME,
        "generated_at": utc_now(),
        "mode": "fallback",
        "source_status": source_status,
        "executive_summary": (
            f"{impact_rows}개 impact card와 {queue_total}개 queue 항목이 local review 대상입니다. "
            f"Public deploy는 {public_deploy}이므로 agent는 reviewer brief만 제공하고 "
            "외부 성과 claim을 만들거나 승인하지 않습니다."
        ),
        "top_risks": risks[:4],
        "recommended_next_actions": actions[:4],
        "evidence_refs": build_evidence_refs(state, queue, impact_cards, policy_audit, action_plan),
        "claim_safety": claim_safety,
        "limitations": [
            "Agent output은 advisory/read-only입니다.",
            "Agent는 승인, 반려, 현장 dispatch, GO/NO_GO 변경을 수행하지 않습니다.",
            "숫자는 기존 API/artifact에서 복사하며 새 추정치를 만들지 않습니다.",
        ],
        "llm": {
            "provider": os.environ.get("CONTROL_TOWER_LLM_PROVIDER", "fallback"),
            "status": "not_configured",
        },
    }


def _openai_json_schema_payload() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "executive_summary",
            "top_risks",
            "recommended_next_actions",
            "limitations",
        ],
        "properties": {
            "executive_summary": {"type": "string"},
            "top_risks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["risk", "severity", "evidence_ref"],
                    "properties": {
                        "risk": {"type": "string"},
                        "severity": {"type": "string"},
                        "evidence_ref": {"type": "string"},
                    },
                },
            },
            "recommended_next_actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action", "owner", "evidence_ref"],
                    "properties": {
                        "action": {"type": "string"},
                        "owner": {"type": "string"},
                        "evidence_ref": {"type": "string"},
                    },
                },
            },
            "limitations": {"type": "array", "items": {"type": "string"}},
        },
    }


def _extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    for output in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
        for content in output.get("content", []) if isinstance(output.get("content"), list) else []:
            text = content.get("text")
            if isinstance(text, str):
                return text
    return ""


def _call_openai_reviewer_brief(source_payload: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    model = os.environ.get("CONTROL_TOWER_LLM_MODEL", "gpt-5.1").strip()
    body = {
        "model": model,
        "store": False,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are an evidence-grounded reviewer assistant. Summarize only the JSON facts. "
                    "Answer in Korean. Do not invent numbers. Do not approve or reject items. "
                    "Do not change GO/NO_GO."
                ),
            },
            {"role": "user", "content": json.dumps(source_payload, ensure_ascii=False)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "decisionops_reviewer_brief",
                "schema": _openai_json_schema_payload(),
                "strict": True,
            }
        },
    }
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=12) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    text = _extract_response_text(response_payload)
    if not text:
        raise RuntimeError("OpenAI response did not include output text")
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise RuntimeError("OpenAI response was not a JSON object")
    return parsed


def _apply_llm_summary(fallback: dict[str, Any], llm_payload: dict[str, Any]) -> dict[str, Any]:
    brief = deepcopy(fallback)
    brief["mode"] = "llm"
    for key in ["executive_summary", "top_risks", "recommended_next_actions", "limitations"]:
        if key in llm_payload:
            brief[key] = llm_payload[key]
    brief["source_status"] = fallback["source_status"]
    brief["claim_safety"] = fallback["claim_safety"]
    brief["evidence_refs"] = fallback["evidence_refs"]
    brief["llm"] = {
        "provider": "openai",
        "model": os.environ.get("CONTROL_TOWER_LLM_MODEL", "gpt-5.1"),
        "status": "completed",
        "safety": "source_status, claim_safety, and evidence_refs were restored from deterministic sources",
    }
    return brief


def build_reviewer_brief(
    state: dict[str, Any],
    queue: list[dict[str, Any]],
    impact_cards: list[dict[str, Any]],
    policy_audit: list[dict[str, Any]],
    action_plan: list[dict[str, Any]],
    ops: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fallback = build_fallback_reviewer_brief(state, queue, impact_cards, policy_audit, action_plan, ops)
    provider = os.environ.get("CONTROL_TOWER_LLM_PROVIDER", "").strip().lower()
    if provider != "openai":
        return fallback
    source_payload = {
        "source_status": fallback["source_status"],
        "claim_safety": fallback["claim_safety"],
        "evidence_refs": fallback["evidence_refs"],
        "top_action_plan": action_plan[:3],
        "top_policy_audit": policy_audit[:3],
    }
    try:
        return _apply_llm_summary(fallback, _call_openai_reviewer_brief(source_payload))
    except (RuntimeError, ValueError, json.JSONDecodeError, error.URLError) as exc:
        fallback["llm"] = {
            "provider": "openai",
            "model": os.environ.get("CONTROL_TOWER_LLM_MODEL", "gpt-5.1"),
            "status": "fallback_after_error",
            "error_type": exc.__class__.__name__,
        }
        return fallback


def _candidate_matches(item: dict[str, Any], candidate_id: str, index: int) -> bool:
    aliases = {
        str(item.get("impact_card_id", "")),
        str(item.get("station_id", "")),
        f"ddareungi-action-{index}",
        str(index),
    }
    return candidate_id in {alias for alias in aliases if alias}


def find_candidate(impact_cards: list[dict[str, Any]], candidate_id: str) -> tuple[int, dict[str, Any]] | None:
    for index, item in enumerate(impact_cards, start=1):
        if _candidate_matches(item, candidate_id, index):
            return index, item
    return None


def build_candidate_review_notes(
    candidate_id: str,
    state: dict[str, Any],
    impact_cards: list[dict[str, Any]],
    action_plan: list[dict[str, Any]],
) -> dict[str, Any] | None:
    found = find_candidate(impact_cards, candidate_id)
    if found is None:
        return None
    index, item = found
    claim_safety = build_claim_safety(state)
    station_name = str(item.get("station_name", "unknown station"))
    station_action = str(item.get("recommended_action", "review"))
    candidate_units = int(item.get("candidate_units_addressed", 0) or 0)
    matching_plan = next(
        (plan for plan in action_plan if plan.get("station_name") == item.get("station_name")),
        {},
    )
    review_notes = [
        f"{station_name}은 {candidate_units}개 candidate unit을 다루는 {index}번 후보입니다.",
        f"권장 action은 {station_action}이며, 근거가 완성될 때까지 reviewer decision은 local-only로 유지해야 합니다.",
        str(item.get("blocker") or matching_plan.get("next_evidence_needed") or "승인 전 validation과 confidence 근거를 확인합니다."),
    ]
    return {
        "agent_name": AGENT_NAME,
        "generated_at": utc_now(),
        "mode": "fallback",
        "candidate_id": candidate_id,
        "matched_aliases": {
            "impact_card_id": item.get("impact_card_id"),
            "station_id": item.get("station_id"),
            "dashboard_anchor": f"ddareungi-action-{index}",
        },
        "candidate_title": station_name,
        "priority": item.get("priority", "UNKNOWN"),
        "review_notes": review_notes,
        "recommended_next_actions": [
            _action_item("결정을 기록하기 전에 dashboard row의 evidence text를 확인합니다.", "ops_reviewer", f"/api/impact-cards[{index - 1}]"),
            _action_item("승인은 local-only로 유지하고 이 후보를 public impact claim으로 쓰지 않습니다.", "demo_owner", "/api/control-state.public_deploy_decision"),
        ],
        "evidence_refs": [
            {"source": "/api/impact-cards", "field": f"items[{index - 1}].station_name", "value": item.get("station_name")},
            {"source": "/api/impact-cards", "field": f"items[{index - 1}].candidate_units_addressed", "value": candidate_units},
            {"source": "/api/impact-cards", "field": f"items[{index - 1}].public_claim_state", "value": item.get("public_claim_state")},
            {"source": "/api/reviewer-action-plan", "field": "matching.station_name", "value": matching_plan.get("station_name", "")},
        ],
        "claim_safety": claim_safety,
        "limitations": [
            "Candidate note는 advisory이며 approval history를 쓰지 않습니다.",
            "Agent는 새 효과 추정치나 verified impact claim을 만들지 않습니다.",
        ],
    }
