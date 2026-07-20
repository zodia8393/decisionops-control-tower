#!/usr/bin/env python3
"""Evaluate DecisionOps RAG contracts against the versioned golden set."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from decisionops_control_tower.pipeline import DEFAULT_OUTPUT_ROOT
from decisionops_control_tower.rag import MemoryVectorStore, QdrantVectorStore, RagService
from decisionops_control_tower.rag_evaluation import (
    evaluate_cases,
    golden_set_identity,
    load_golden_cases,
    load_runtime_sources,
    render_markdown_report,
)


DEFAULT_GOLDEN_SET = PROJECT_ROOT / "tests" / "fixtures" / "rag_golden_questions.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--golden-set", type=Path, default=DEFAULT_GOLDEN_SET)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--vector-store", choices=["memory", "qdrant"], default="memory")
    parser.add_argument(
        "--qdrant-url",
        default=os.environ.get("QDRANT_URL", "http://127.0.0.1:6333"),
    )
    parser.add_argument(
        "--qdrant-collection",
        default=os.environ.get("QDRANT_COLLECTION", "decisionops_evidence_eval"),
    )
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    parser.add_argument("--baseline-json", type=Path)
    parser.add_argument(
        "--minimum-pass-rate",
        type=float,
        default=0.0,
        help="Exit non-zero when the end-to-end pass rate is below this 0..1 threshold.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.top_k <= 8:
        raise SystemExit("--top-k must be between 1 and 8")
    if not 0.0 <= args.minimum_pass_rate <= 1.0:
        raise SystemExit("--minimum-pass-rate must be between 0 and 1")
    cases = load_golden_cases(args.golden_set)
    sources = load_runtime_sources(args.output_root)
    if not sources["state"]:
        raise SystemExit(f"control_state.json not found under {args.output_root / 'reports'}")
    store = (
        MemoryVectorStore()
        if args.vector_store == "memory"
        else QdrantVectorStore(args.qdrant_url, collection=args.qdrant_collection)
    )
    report = evaluate_cases(
        service=RagService(store=store),
        cases=cases,
        sources=sources,
        project_root=PROJECT_ROOT,
        top_k=args.top_k,
    )
    report["configuration"].update(golden_set_identity(args.golden_set))
    baseline = None
    if args.baseline_json:
        baseline = json.loads(args.baseline_json.read_text(encoding="utf-8"))
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.report_md:
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(
            render_markdown_report(report, baseline=baseline),
            encoding="utf-8",
        )
    metrics = report["metrics"]
    print(
        "rag evaluation complete: "
        f"cases={metrics['case_count']}, "
        f"pass_rate={metrics['pass_rate']:.3f}, "
        f"status={metrics['status_accuracy']:.3f}, "
        f"recall@{args.top_k}={metrics['retrieval_recall_at_k']:.3f}, "
        f"citation_precision={metrics['citation_precision']:.3f}, "
        f"refusal={metrics['unsafe_refusal_accuracy']:.3f}, "
        f"abstention={metrics['abstention_accuracy']:.3f}, "
        f"p95_ms={metrics['latency_ms_p95']:.3f}"
    )
    if metrics["pass_rate"] < args.minimum_pass_rate:
        raise SystemExit(
            f"RAG pass rate {metrics['pass_rate']:.3f} is below {args.minimum_pass_rate:.3f}"
        )


if __name__ == "__main__":
    main()
