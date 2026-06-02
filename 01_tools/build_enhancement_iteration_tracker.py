#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a lightweight enhancement-line iteration tracker from a v2 vs v3 comparison snapshot."
    )
    parser.add_argument(
        "--input-json",
        default="09_reports/enhancement_line_v2_vs_v3_comparison.json",
        help="Source comparison JSON",
    )
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_line_iteration_tracker.json",
        help="Tracker JSON output path",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_line_iteration_tracker.md",
        help="Tracker markdown output path",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def top_gap(case_payload: dict[str, object]) -> float:
    top_rerank = case_payload.get("top_rerank", [])
    if not isinstance(top_rerank, list) or len(top_rerank) < 2:
        return 0.0
    top_1 = float(top_rerank[0]["rerank_score"])
    top_2 = float(top_rerank[1]["rerank_score"])
    return round(top_2 - top_1, 3)


def active_margin(case_payload: dict[str, object]) -> float | None:
    payload = case_payload.get("active_margin", {})
    if not isinstance(payload, dict):
        return None
    value = payload.get("known_active_to_best_background_gap")
    if value is None:
        return None
    return float(value)


def compression_ratio(case_payload: dict[str, object]) -> float:
    keep_count = int(case_payload.get("filter_keep_count", 0) or 0)
    shortlist_count = int(case_payload.get("shortlist_count", 0) or 0)
    if keep_count == 0:
        return 0.0
    return round(shortlist_count / keep_count, 3)


def cache_runtime(perf_payload: dict[str, object], module_key: str) -> float | None:
    module_payload = perf_payload.get(module_key, {})
    cache_hits = module_payload.get("cache_hit_case_runtime_seconds", {})
    if not isinstance(cache_hits, dict) or not cache_hits:
        return None
    first_value = next(iter(cache_hits.values()))
    if not isinstance(first_value, dict):
        return None
    value = first_value.get("runtime_seconds")
    return float(value) if value is not None else None


def build_tracker(comparison: dict[str, object]) -> dict[str, object]:
    baseline = comparison["baseline_case"]
    enhancement = comparison["enhancement_case"]
    performance = comparison.get("performance", {})
    baseline_gap = top_gap(baseline)
    enhancement_gap = top_gap(enhancement)
    baseline_active_margin = active_margin(baseline)
    enhancement_active_margin = active_margin(enhancement)
    baseline_ratio = compression_ratio(baseline)
    enhancement_ratio = compression_ratio(enhancement)
    tracker = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_report": "09_reports/enhancement_line_v2_vs_v3_comparison.json",
        "comparison_scope": {
            "baseline_case_id": baseline["case_id"],
            "enhancement_case_id": enhancement["case_id"],
        },
        "headline_metrics": {
            "baseline_top12_rerank_gap": baseline_gap,
            "enhancement_top12_rerank_gap": enhancement_gap,
            "rerank_gap_improvement": round(enhancement_gap - baseline_gap, 3),
            "baseline_active_best_background_gap": baseline_active_margin,
            "enhancement_active_best_background_gap": enhancement_active_margin,
            "active_margin_improvement": (
                round(float(enhancement_active_margin) - float(baseline_active_margin), 3)
                if enhancement_active_margin is not None and baseline_active_margin is not None
                else None
            ),
            "baseline_shortlist_compression_ratio": baseline_ratio,
            "enhancement_shortlist_compression_ratio": enhancement_ratio,
            "shortlist_compression_improvement": round(baseline_ratio - enhancement_ratio, 3),
        },
        "shortlist_behavior": {
            "baseline_filter_keep_count": baseline["filter_keep_count"],
            "baseline_shortlist_count": baseline["shortlist_count"],
            "enhancement_filter_keep_count": enhancement["filter_keep_count"],
            "enhancement_shortlist_count": enhancement["shortlist_count"],
            "baseline_shortlist_ids": baseline["shortlist_ids"],
            "enhancement_shortlist_ids": enhancement["shortlist_ids"],
            "baseline_known_active_shortlisted": baseline.get("active_margin", {}).get("known_active_shortlisted"),
            "enhancement_known_active_shortlisted": enhancement.get("active_margin", {}).get("known_active_shortlisted"),
        },
        "cache_behavior": {
            "ai_reranking_cache_hit_runtime_seconds": cache_runtime(performance, "ai_reranking"),
            "clustering_cache_hit_runtime_seconds": cache_runtime(performance, "clustering_and_prioritization"),
        },
        "decision": {
            "did_rerank_gap_improve": enhancement_gap > baseline_gap,
            "did_active_margin_improve": (
                enhancement_active_margin > baseline_active_margin
                if enhancement_active_margin is not None and baseline_active_margin is not None
                else False
            ),
            "did_shortlist_compress": enhancement_ratio < baseline_ratio,
            "should_continue_v3_line": True,
        },
    }
    return tracker


def build_markdown(tracker: dict[str, object]) -> str:
    scope = tracker["comparison_scope"]
    metrics = tracker["headline_metrics"]
    shortlist = tracker["shortlist_behavior"]
    cache = tracker["cache_behavior"]
    decision = tracker["decision"]
    lines = [
        "# Enhancement Line Iteration Tracker",
        "",
        f"- Generated at: `{tracker['generated_at_utc']}`",
        f"- Source report: `{tracker['source_report']}`",
        f"- Baseline case: `{scope['baseline_case_id']}`",
        f"- Enhancement case: `{scope['enhancement_case_id']}`",
        "",
        "## Headline Metrics",
        "",
        "| Metric | Baseline | Enhancement | Delta |",
        "| --- | --- | --- | --- |",
        f"| Top1-Top2 rerank gap | `{metrics['baseline_top12_rerank_gap']}` | `{metrics['enhancement_top12_rerank_gap']}` | `{metrics['rerank_gap_improvement']}` |",
        f"| Active-best-background gap | `{metrics['baseline_active_best_background_gap']}` | `{metrics['enhancement_active_best_background_gap']}` | `{metrics['active_margin_improvement']}` |",
        f"| Shortlist compression ratio | `{metrics['baseline_shortlist_compression_ratio']}` | `{metrics['enhancement_shortlist_compression_ratio']}` | `{metrics['shortlist_compression_improvement']}` |",
        "",
        "## Shortlist Behavior",
        "",
        f"- Baseline filter keep / shortlist: `{shortlist['baseline_filter_keep_count']}` / `{shortlist['baseline_shortlist_count']}`",
        f"- Enhancement filter keep / shortlist: `{shortlist['enhancement_filter_keep_count']}` / `{shortlist['enhancement_shortlist_count']}`",
        f"- Baseline shortlist ids: `{', '.join(shortlist['baseline_shortlist_ids'])}`",
        f"- Enhancement shortlist ids: `{', '.join(shortlist['enhancement_shortlist_ids'])}`",
        f"- Baseline known active shortlisted: `{shortlist['baseline_known_active_shortlisted']}`",
        f"- Enhancement known active shortlisted: `{shortlist['enhancement_known_active_shortlisted']}`",
        "",
        "## Cache Behavior",
        "",
        f"- `ai_reranking` cache-hit runtime seconds: `{cache['ai_reranking_cache_hit_runtime_seconds']}`",
        f"- `clustering_and_prioritization` cache-hit runtime seconds: `{cache['clustering_cache_hit_runtime_seconds']}`",
        "",
        "## Decision",
        "",
        f"- Rerank gap improved: `{decision['did_rerank_gap_improve']}`",
        f"- Active margin improved: `{decision['did_active_margin_improve']}`",
        f"- Shortlist compressed: `{decision['did_shortlist_compress']}`",
        f"- Continue `v3` line: `{decision['should_continue_v3_line']}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    comparison = load_json(Path(args.input_json))
    tracker = build_tracker(comparison)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_json, tracker)
    output_md.write_text(build_markdown(tracker), encoding="utf-8")
    print(f"[tracker] wrote json: {output_json}")
    print(f"[tracker] wrote markdown: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
