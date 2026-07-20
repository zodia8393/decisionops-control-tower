"""Reproducible golden-set evaluation for evidence-grounded chat."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any

from decisionops_control_tower.rag import RagService


MIN_GOLDEN_CASES = 30
GOLDEN_DATASET_PROFILE: dict[str, Any] = {
    "filename": "golden_stations.csv",
    "fingerprint_sha256": "7" * 64,
    "generated_at": "2026-07-16T00:00:00Z",
    "row_count": 4,
    "column_count": 3,
    "numeric_column_count": 1,
    "missing_cell_count": 1,
    "missing_cell_rate": 0.083333,
    "columns": [
        {"name": "station", "dtype": "object", "missing_count": 0, "unique_count": 4},
        {"name": "district", "dtype": "object", "missing_count": 0, "unique_count": 3},
        {
            "name": "available_bikes",
            "dtype": "float64",
            "missing_count": 1,
            "unique_count": 3,
            "numeric": {"min": 1.0, "max": 9.0, "mean": 4.333333},
        },
    ],
}


def load_golden_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    if not isinstance(cases, list) or len(cases) < MIN_GOLDEN_CASES:
        raise ValueError(f"golden set must contain at least {MIN_GOLDEN_CASES} cases")
    required = {"id", "category", "question", "expected_status"}
    identifiers: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not required.issubset(case):
            raise ValueError(f"every golden case requires {sorted(required)}")
        identifier = str(case["id"])
        if identifier in identifiers:
            raise ValueError(f"duplicate golden case id: {identifier}")
        identifiers.add(identifier)
    return cases


def golden_set_identity(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    version = payload.get("version") if isinstance(payload, dict) else None
    if not isinstance(version, str) or not version.strip():
        raise ValueError("golden set requires a non-empty version")
    return {
        "golden_set_version": version,
        "golden_set_sha256": hashlib.sha256(raw).hexdigest(),
    }


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_runtime_sources(output_root: Path) -> dict[str, Any]:
    """Load the same public-safe artifacts used by the application."""

    reports = output_root / "reports"
    return {
        "state": _read_json(reports / "control_state.json", {}),
        "queue": _read_csv(reports / "control_review_queue.csv"),
        "impact_cards": _read_json(reports / "impact_cards.json", []),
        "impact_policy_audit": _read_json(reports / "impact_policy_audit.json", []),
        "reviewer_policy_robustness": _read_json(
            reports / "reviewer_policy_robustness.json", {}
        ),
        "reviewer_action_plan": _read_json(reports / "reviewer_action_plan.json", []),
        "reviewer_evidence_bundles": _read_json(
            reports / "reviewer_evidence_bundles.json", []
        ),
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
    return round(ordered[index], 3)


def _citation_quality(response: dict[str, Any]) -> tuple[bool, bool]:
    citations = response.get("citations", [])
    claims = response.get("claims", [])
    if not isinstance(citations, list) or not isinstance(claims, list):
        return False, False
    source_ids = [item.get("source_id") for item in citations if isinstance(item, dict)]
    required_metadata = {"source_id", "title", "content_hash", "url", "freshness_status"}
    valid = (
        len(source_ids) == len(set(source_ids))
        and all(
            isinstance(item, dict)
            and required_metadata.issubset(item)
            and all(item.get(key) not in (None, "") for key in required_metadata)
            for item in citations
        )
    )
    referenced: list[str] = []
    claim_shapes_valid = True
    for claim in claims:
        ids = claim.get("citation_ids", []) if isinstance(claim, dict) else []
        if not isinstance(ids, list):
            claim_shapes_valid = False
            continue
        referenced.extend(str(source_id) for source_id in ids)
    valid = valid and claim_shapes_valid and all(source_id in source_ids for source_id in referenced)

    needs_claims = response.get("status") in {"ANSWER", "REVIEW_REQUIRED"}
    complete = (not needs_claims) or (
        bool(claims)
        and all(
            isinstance(claim, dict)
            and bool(claim.get("text"))
            and bool(claim.get("citation_ids"))
            for claim in claims
        )
    )
    return valid, complete


def evaluate_cases(
    *,
    service: RagService,
    cases: list[dict[str, Any]],
    sources: dict[str, Any],
    project_root: Path,
    top_k: int = 3,
) -> dict[str, Any]:
    warmup = service.answer(
        question="현재 배포 상태를 알려줘.",
        sources=sources,
        project_root=project_root,
        top_k=top_k,
        allow_llm=False,
    )
    cold_start_index_latency_ms = float(
        warmup.get("retrieval", {}).get("latency_ms", 0.0)
    )
    rows: list[dict[str, Any]] = []
    for case in cases:
        expected_status = case["expected_status"]
        allowed_statuses = (
            {str(item) for item in expected_status}
            if isinstance(expected_status, list)
            else {str(expected_status)}
        )
        expected_prefixes = tuple(str(item) for item in case.get("expected_source_prefixes", []))
        response = service.answer(
            question=str(case["question"]),
            sources=sources,
            project_root=project_root,
            top_k=top_k,
            dataset_profile=(
                case.get("dataset_profile")
                or (GOLDEN_DATASET_PROFILE if case.get("category") == "dataset" else None)
            ),
            allow_llm=False,
        )
        citation_ids = [str(item.get("source_id", "")) for item in response.get("citations", [])]
        relevant = [
            source_id
            for source_id in citation_ids
            if any(source_id.startswith(prefix) for prefix in expected_prefixes)
        ]
        retrieval_required = bool(expected_prefixes)
        retrieval_pass = (not retrieval_required) or bool(relevant)
        citation_precision = (
            len(relevant) / len(citation_ids)
            if retrieval_required and citation_ids
            else 1.0 if not retrieval_required else 0.0
        )
        citation_valid, citation_complete = _citation_quality(response)
        status_pass = str(response.get("status")) in allowed_statuses
        category = str(case["category"])
        safety_pass = category != "refusal" or (
            response.get("status") == "REFUSE"
            and response.get("safety", {}).get("unsafe_request_detected") is True
        )
        abstention_pass = category != "abstention" or (
            response.get("status") == "NEEDS_MORE_EVIDENCE"
            and response.get("citations") == []
        )
        passed = all(
            [
                status_pass,
                retrieval_pass,
                citation_valid,
                citation_complete,
                safety_pass,
                abstention_pass,
            ]
        )
        rows.append(
            {
                "id": case["id"],
                "category": category,
                "question": case["question"],
                "expected_status": sorted(allowed_statuses),
                "actual_status": response.get("status"),
                "status_pass": status_pass,
                "retrieval_pass": retrieval_pass,
                "citation_precision": round(citation_precision, 6),
                "citation_valid": citation_valid,
                "citation_complete": citation_complete,
                "safety_pass": safety_pass,
                "abstention_pass": abstention_pass,
                "citation_ids": citation_ids,
                "latency_ms": float(response.get("retrieval", {}).get("latency_ms", 0.0)),
                "passed": passed,
            }
        )

    retrieval_rows = [
        row for row, case in zip(rows, cases, strict=True) if case.get("expected_source_prefixes")
    ]
    refusal_rows = [row for row in rows if row["category"] == "refusal"]
    abstention_rows = [row for row in rows if row["category"] == "abstention"]
    metrics = {
        "case_count": len(rows),
        "pass_rate": round(mean(row["passed"] for row in rows), 6),
        "status_accuracy": round(mean(row["status_pass"] for row in rows), 6),
        "retrieval_recall_at_k": round(
            mean(row["retrieval_pass"] for row in retrieval_rows), 6
        ) if retrieval_rows else 1.0,
        "citation_precision": round(
            mean(row["citation_precision"] for row in retrieval_rows), 6
        ) if retrieval_rows else 1.0,
        "citation_validity": round(mean(row["citation_valid"] for row in rows), 6),
        "citation_completeness": round(mean(row["citation_complete"] for row in rows), 6),
        "unsafe_refusal_accuracy": round(
            mean(row["safety_pass"] for row in refusal_rows), 6
        ) if refusal_rows else 1.0,
        "abstention_accuracy": round(
            mean(row["abstention_pass"] for row in abstention_rows), 6
        ) if abstention_rows else 1.0,
        "cold_start_index_latency_ms": round(cold_start_index_latency_ms, 3),
        "latency_ms_mean": round(mean(row["latency_ms"] for row in rows), 3),
        "latency_ms_p95": _percentile([row["latency_ms"] for row in rows], 0.95),
    }
    category_metrics = {}
    for category in sorted({row["category"] for row in rows}):
        category_rows = [row for row in rows if row["category"] == category]
        category_metrics[category] = {
            "count": len(category_rows),
            "pass_rate": round(mean(row["passed"] for row in category_rows), 6),
        }
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "configuration": {
            "top_k": top_k,
            "vector_store": service.store.mode,
            "embedding_provider": service.embedding.name,
            "llm_called": False,
        },
        "metrics": metrics,
        "categories": category_metrics,
        "failures": [row for row in rows if not row["passed"]],
        "cases": rows,
    }


def render_markdown_report(
    report: dict[str, Any],
    *,
    title: str = "RAG golden-set evaluation",
    baseline: dict[str, Any] | None = None,
) -> str:
    metrics = report["metrics"]
    configuration = report["configuration"]
    lines = [
        f"# {title}",
        "",
        f"- generated: `{report['generated_at_utc']}`",
        f"- cases: **{metrics['case_count']}**",
        f"- vector store: `{configuration['vector_store']}`",
        f"- embedding: `{configuration['embedding_provider']}`",
        "- generation: deterministic fallback only (`LLM called = false`)",
    ]
    if configuration.get("golden_set_version"):
        fingerprint = str(configuration.get("golden_set_sha256", "unknown"))[:12]
        lines.append(
            f"- golden set: `v{configuration['golden_set_version']}` (`sha256:{fingerprint}…`)"
        )
    lines.extend(["", "## Scorecard", "", "| Metric | Result |", "|---|---:|"])
    labels = {
        "pass_rate": "End-to-end pass rate",
        "status_accuracy": "Status accuracy",
        "retrieval_recall_at_k": "Retrieval recall@k",
        "citation_precision": "Citation precision",
        "citation_validity": "Citation validity",
        "citation_completeness": "Claim citation completeness",
        "unsafe_refusal_accuracy": "Unsafe refusal accuracy",
        "abstention_accuracy": "Abstention accuracy",
    }
    for key, label in labels.items():
        lines.append(f"| {label} | {metrics[key] * 100:.1f}% |")
    lines.extend(
        [
            f"| Mean retrieval latency | {metrics['latency_ms_mean']:.3f} ms |",
            f"| p95 retrieval latency | {metrics['latency_ms_p95']:.3f} ms |",
            f"| Cold-start index + retrieval | {metrics['cold_start_index_latency_ms']:.3f} ms |",
        ]
    )
    if baseline:
        baseline_metrics = baseline["metrics"]
        lines.extend(
            [
                "",
                "## Improvement from baseline",
                "",
                "| Metric | Baseline | Current | Delta |",
                "|---|---:|---:|---:|",
            ]
        )
        for key, label in labels.items():
            before = float(baseline_metrics[key])
            after = float(metrics[key])
            lines.append(
                f"| {label} | {before * 100:.1f}% | {after * 100:.1f}% | {(after - before) * 100:+.1f} pp |"
            )
    lines.extend(["", "## Category results", "", "| Category | Cases | Pass rate |", "|---|---:|---:|"])
    for category, values in report["categories"].items():
        lines.append(f"| {category} | {values['count']} | {values['pass_rate'] * 100:.1f}% |")
    lines.extend(["", "## Failed cases", ""])
    failures = report.get("failures", [])
    if not failures:
        lines.append("All golden cases passed.")
    else:
        lines.extend(["| ID | Expected | Actual | Retrieval | Citations |", "|---|---|---|---:|---:|"])
        for row in failures:
            lines.append(
                f"| `{row['id']}` | {', '.join(row['expected_status'])} | {row['actual_status']} | "
                f"{'pass' if row['retrieval_pass'] else 'fail'} | {row['citation_precision'] * 100:.1f}% |"
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "이 평가는 실제 운영 산출물과 versioned documentation을 대상으로 수행한다. "
            "LLM 문장 품질과 외부 provider availability는 분리하고, application-owned status·retrieval·citation·safety contract를 재현 가능하게 측정한다. "
            "Citation precision은 golden question에 지정한 source family와 provenance의 일치율이며, claim의 semantic entailment를 판정하는 별도 judge 점수는 아니다.",
            "",
        ]
    )
    return "\n".join(lines)
