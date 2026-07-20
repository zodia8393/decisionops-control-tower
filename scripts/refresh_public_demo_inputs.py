#!/usr/bin/env python3
"""Refresh the versioned public demo inputs from validated local aggregates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from decisionops_control_tower.pipeline import (
    DEFAULT_BIKE_ROOT,
    DEFAULT_WORKBENCH_ROOT,
    PROJECT_ROOT,
    PUBLIC_INPUTS_SCHEMA_VERSION,
    _build_control_state,
    _build_impact_cards,
    _build_impact_policy_audit,
    _build_reviewer_action_plan,
    _build_reviewer_evidence_bundles,
    _build_reviewer_policy_robustness,
    _collect_inputs,
    _validate_public_inputs,
)


DEFAULT_OUTPUT = PROJECT_ROOT / "tests" / "fixtures" / "public_demo_inputs.json"
SEOUL_PRIORITY_FIELDS = (
    "priority_rank",
    "station_id",
    "station_name",
    "issue_type",
    "recommended_action",
    "severity_score",
    "recommended_bikes_delta",
    "capacity",
    "bikes_available",
    "docks_available",
    "bike_shortage_threshold",
    "dock_shortage_threshold",
    "bike_fill_rate",
    "dock_fill_rate",
    "shared_rate",
    "captured_at_kst",
    "station_lat",
    "station_lon",
    "source",
)


def _select(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: item.get(field) for field in fields if field in item}


def _state(inputs: dict[str, Any]) -> dict[str, Any]:
    cards = _build_impact_cards(inputs)
    policy = _build_impact_policy_audit(cards)
    robustness = _build_reviewer_policy_robustness(cards)
    plan = _build_reviewer_action_plan(cards)
    bundles = _build_reviewer_evidence_bundles(cards, plan)
    return _build_control_state(inputs, cards, policy, robustness, plan, bundles)


def _public_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "queue_id": f"PUBLIC-HRQ-{index:04d}",
            "priority": row.get("priority", "P2"),
            "requested_action": row.get("requested_action", "escalate"),
            "guardrail_hits": row.get("guardrail_hits", ""),
            "review_question": row.get("review_question", ""),
        }
        for index, row in enumerate(rows, start=1)
    ]


def build_public_inputs(bike_root: Path, workbench_root: Path) -> dict[str, Any]:
    inputs = _collect_inputs(bike_root, workbench_root)
    actual_state = _state(inputs)
    if actual_state["public_deploy_decision"] != "GO":
        blockers = "; ".join(actual_state.get("blockers", [])) or "unknown blocker"
        raise ValueError(f"refusing to refresh a NO_GO public snapshot: {blockers}")

    bike = inputs["bike"]
    workbench = inputs["workbench"]
    validation = bike["seoul_validation_summary"]
    priority_rows = bike["seoul_priority"]
    source_observed_at = (
        priority_rows[0].get("captured_at_kst")
        if priority_rows
        else validation.get("generated_at_kst")
    )
    station_snapshot_fields = (
        "generated_at_kst",
        "ready_for_prospective_validation",
        "reason",
        "status",
        "target_days",
        "target_snapshots",
        "min_required_snapshots",
        "snapshot_count",
        "remaining_snapshots",
        "coverage_ratio",
        "first_snapshot_at",
        "latest_snapshot_at",
    )
    validation_fields = (
        "generated_at_kst",
        "validation_status",
        "evaluation_status",
        "reason",
        "source",
        "snapshot_count",
        "min_snapshots_for_validation",
        "total_label_snapshots",
        "evaluated_snapshots",
        "label_rows",
        "coverage",
        "precision_at_10",
        "precision_at_50",
        "balanced_precision_at_50",
        "balanced_issue_hit_rate",
    )
    model_fields = (
        "generated_at_kst",
        "model_status",
        "reason",
        "source",
        "split",
        "snapshot_count",
        "label_rows",
        "train_rows",
        "test_rows",
        "best_target",
        "best_model",
        "best_f1",
        "best_average_precision",
        "best_brier",
    )
    summary_fields = (
        "ok",
        "status",
        "source",
        "input_rows",
        "candidate_rows",
        "priority_rows",
        "top_n",
        "shortage_ratio",
        "action_counts",
        "issue_counts",
        "total_send_bikes",
        "total_remove_bikes",
        "max_severity_score",
    )
    station_priority_fields = (
        "station_short_name",
        "station_name",
        "capacity",
        "risk_score",
        "recommended_buffer_bikes",
        "current_bike_shortage",
        "current_dock_shortage",
    )
    inventory_fields = (
        "station_short_name",
        "station_name",
        "capacity",
        "current_bike_shortage",
        "current_dock_shortage",
        "inventory_pressure",
        "inventory_joined",
    )
    run_summary = workbench["run_summary"]
    incident_surface = workbench["incident_surface"]
    incidents = incident_surface.get("incidents", [])
    mcp_contract = workbench["mcp_contract"]
    payload = {
        "_snapshot": {
            "schema_version": PUBLIC_INPUTS_SCHEMA_VERSION,
            "source_observed_at": source_observed_at,
            "source_kind": "allowlisted aggregate artifacts",
            "bike_root_fallback": False,
            "workbench_root_fallback": False,
        },
        "bike": {
            "snapshot_readiness": _select(
                bike["snapshot_readiness"], station_snapshot_fields
            ),
            "public_deploy": _select(
                bike["public_deploy"],
                ("generated_at_kst", "decision", "blockers", "tracked_publication_risks"),
            ),
            "station_priority": [
                _select(row, station_priority_fields) for row in bike["station_priority"]
            ],
            "inventory_snapshot": [
                _select(row, inventory_fields) for row in bike["inventory_snapshot"]
            ],
            "seoul_priority": [
                _select(row, SEOUL_PRIORITY_FIELDS) for row in priority_rows
            ],
            "seoul_priority_summary": _select(
                bike["seoul_priority_summary"], summary_fields
            ),
            "seoul_validation_summary": _select(validation, validation_fields),
            "seoul_model_metrics": _select(bike["seoul_model_metrics"], model_fields),
        },
        "workbench": {
            "run_summary": {
                "status": run_summary.get("status"),
                "source_count": run_summary.get("source_count"),
                "agents": run_summary.get("agents", []),
                "domains": run_summary.get("domains", []),
                "guarded_success_lift": run_summary.get("guarded_success_lift"),
                "holdout": run_summary.get("holdout", {}),
                "impact": run_summary.get("impact", {}),
                "review_queue": {
                    "queue_items": len(workbench["review_queue"]),
                    "priority_counts": run_summary.get("review_queue", {}).get(
                        "priority_counts", {}
                    ),
                },
            },
            "prepublish_audit": workbench["prepublish_audit"],
            "eval_metrics": workbench["eval_metrics"],
            "holdout_metrics": workbench["holdout_metrics"],
            "review_queue": _public_queue(workbench["review_queue"]),
            "mcp_contract": {
                "name": mcp_contract.get("name"),
                "version": mcp_contract.get("version"),
                "tool_count": len(mcp_contract.get("tools", [])),
                "resource_count": len(mcp_contract.get("resources", [])),
                "prompt_count": len(mcp_contract.get("prompts", [])),
            },
            "incident_surface": {
                "source_status": incident_surface.get("source_status"),
                "source_count": incident_surface.get("source_count", len(incidents)),
                "incidents": [
                    {"incident_id": f"PUBLIC-INCIDENT-{index:04d}"}
                    for index in range(1, len(incidents) + 1)
                ],
            },
        },
        "_fallbacks": {"bike": False, "workbench": False},
    }
    payload = _validate_public_inputs(payload)
    public_state = _state(payload)
    compared_metrics = (
        "station_priority_rows",
        "inventory_snapshot_rows",
        "review_queue_items",
        "incident_rows",
        "impact_card_rows",
        "impact_candidate_units_addressed",
        "impact_verified_units",
        "reviewer_evidence_fresh_rows",
        "seoul_priority_rows",
        "seoul_snapshot_count",
    )
    mismatches = {
        metric: (
            actual_state["metrics"].get(metric),
            public_state["metrics"].get(metric),
        )
        for metric in compared_metrics
        if actual_state["metrics"].get(metric) != public_state["metrics"].get(metric)
    }
    if public_state["public_deploy_decision"] != "GO" or mismatches:
        raise ValueError(
            "public snapshot cross-check failed: "
            f"decision={public_state['public_deploy_decision']}, mismatches={mismatches}"
        )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bike-root", default=str(DEFAULT_BIKE_ROOT))
    parser.add_argument("--workbench-root", default=str(DEFAULT_WORKBENCH_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the committed fixture differs from current validated aggregates.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.output)
    payload = build_public_inputs(Path(args.bike_root), Path(args.workbench_root))
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"public demo inputs are stale: {output}")
        print(f"public demo inputs are current: {output}")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    state = _state(payload)
    print(
        "public demo inputs refreshed: "
        f"observed_at={payload['_snapshot']['source_observed_at']}, "
        f"public_deploy_decision={state['public_deploy_decision']}, "
        f"seoul_snapshots={state['metrics']['seoul_snapshot_count']}, "
        f"queue_items={state['metrics']['review_queue_items']}, "
        f"output={output}"
    )


if __name__ == "__main__":
    main()
