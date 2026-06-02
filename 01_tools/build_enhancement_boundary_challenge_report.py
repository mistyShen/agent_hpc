#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a focused diagnostic report for an enhancement-line boundary challenge surface."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--base-case-id", required=True)
    parser.add_argument(
        "--results-root",
        default="11_tmp/enhancement_case_fetch/current_v3exp/07_results/modules",
    )
    parser.add_argument(
        "--output-json",
        default=None,
    )
    parser.add_argument(
        "--output-md",
        default=None,
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_filtering_helpers(project_root: Path) -> tuple[Any, Any]:
    module_path = project_root / "06_scripts" / "modules" / "filtering.py"
    spec = importlib.util.spec_from_file_location("challenge_filtering_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load filtering module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.use_literature_filter_v2, module.filter_policy


def find_case_row(case_rows: list[dict[str, str]], case_id: str) -> dict[str, str]:
    for row in case_rows:
        if row.get("case_id") == case_id:
            return row
    raise KeyError(f"Case {case_id} not found in benchmark_cases.tsv")


def build_candidate_table(
    case_id: str,
    docking_rows: list[dict[str, str]],
    rerank_rows: list[dict[str, str]],
    filter_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    docking_by_key = {(row["case_id"], row["compound_id"]): row for row in docking_rows}
    rerank_by_key = {(row["case_id"], row["compound_id"]): row for row in rerank_rows}
    candidates: list[dict[str, Any]] = []
    for row in filter_rows:
        if row["case_id"] != case_id:
            continue
        compound_id = row["candidate_id"]
        docking = docking_by_key[(case_id, compound_id)]
        rerank = rerank_by_key[(case_id, compound_id)]
        candidates.append(
            {
                "compound_id": compound_id,
                "filter_decision": row["filter_decision"],
                "filter_reason": row["filter_reason"],
                "priority_tier": row["priority_tier"],
                "vina_affinity_kcal_mol": float(docking["vina_affinity_kcal_mol"]),
                "rerank_score": float(rerank["rerank_score"]),
                "rerank_rank": int(rerank["rerank_rank"]),
                "rerank_model": rerank["rerank_model"],
            }
        )
    candidates.sort(key=lambda item: item["rerank_rank"])
    return candidates


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Enhancement Boundary Challenge Report",
        "",
        f"- Generated at: `{payload['generated_at_utc']}`",
        f"- Base case: `{payload['base_case_id']}`",
        f"- Enhancement case: `{payload['enhancement_case_id']}`",
        "- Scope: enhancement-line diagnostic only. This report is for boundary review and must not be promoted into frozen claims.",
        "",
        "## Challenge Readout",
        "",
        f"- Challenge class: `{payload['challenge_class']}`",
        f"- Effective filter policy: `{payload['effective_filter_policy']}`",
        f"- Configured case filter_policy field: `{payload['configured_filter_policy_field']}`",
        f"- Rollout preserved: `{payload['rollout_preserved']}`",
        f"- Boundary impact: `{payload['boundary_impact']}`",
        "",
        "## Baseline vs Enhancement",
        "",
        "| Case | Known active rank | Known active shortlisted | Filter keep count | Shortlist count | Best background | Gap |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["case_comparison"]:
        lines.append(
            f"| `{row['case_id']}` | `{row['known_active_rank']}` | `{row['known_active_shortlisted']}` | "
            f"`{row['filter_keep_count']}` | `{row['shortlist_count']}` | `{row['best_background_compound_id']}` | `{row['active_best_background_gap']}` |"
        )
    lines.extend(
        [
            "",
            "## Root Cause",
            "",
        ]
    )
    for note in payload["root_cause_notes"]:
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## Filter Thresholds",
            "",
            f"- `max_vina_affinity = {payload['filter_thresholds']['max_vina_affinity']}`",
            f"- `relative_vina_window = {payload['filter_thresholds'].get('relative_vina_window', 'n/a')}`",
            f"- `max_rerank_rank = {payload['filter_thresholds'].get('max_rerank_rank', 'n/a')}`",
            "",
            "## Enhancement Candidate Decisions",
            "",
            "| Compound | Rerank rank | Rerank score | Vina affinity | Filter decision | Filter reason |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["enhancement_candidates"]:
        lines.append(
            f"| `{row['compound_id']}` | `{row['rerank_rank']}` | `{row['rerank_score']}` | "
            f"`{row['vina_affinity_kcal_mol']}` | `{row['filter_decision']}` | `{row['filter_reason']}` |"
        )
    lines.extend(
        [
            "",
            "## Audit Context",
            "",
            f"- Current best background: `{payload['audit_context']['best_background_compound_id']}`",
            f"- Current best-background flags: `{', '.join(payload['audit_context']['best_background_flags']) if payload['audit_context']['best_background_flags'] else 'none'}`",
            f"- Current shortlist ids: `{', '.join(payload['audit_context']['shortlist_ids']) if payload['audit_context']['shortlist_ids'] else 'none'}`",
            "",
            "## Recommendation",
            "",
        ]
    )
    for note in payload["recommendation_notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    report_dir = project_root / "09_reports"
    results_root = (project_root / args.results_root).resolve()
    base_case_id = args.base_case_id
    enhancement_case_id = f"{base_case_id}_V3EXP"

    output_json = Path(args.output_json).resolve() if args.output_json else report_dir / f"enhancement_boundary_challenge_{base_case_id}.json"
    output_md = Path(args.output_md).resolve() if args.output_md else report_dir / f"enhancement_boundary_challenge_{base_case_id}.md"

    case_rows = read_tsv(project_root / "04_metadata" / "benchmark_cases.tsv")
    base_case_row = find_case_row(case_rows, base_case_id)
    enhancement_case_row = find_case_row(case_rows, enhancement_case_id)

    use_literature_filter_v2, filter_policy = load_filtering_helpers(project_root)
    effective_filter_policy = (
        "literature_comparison_filter_v2" if use_literature_filter_v2(enhancement_case_row) else "lightweight_real_filter_v1"
    )
    thresholds = filter_policy(enhancement_case_row)

    baseline_summary = read_json(report_dir / f"enhancement_case_{base_case_id}_summary.json")
    enhancement_summary = read_json(report_dir / f"enhancement_case_{enhancement_case_id}_summary.json")
    comparison = read_json(report_dir / f"enhancement_line_v2_vs_v3_comparison_{base_case_id}.json")
    audit = read_json(report_dir / f"enhancement_line_rule_audit_{base_case_id}.json")

    docking_rows = read_tsv(results_root / "classical_docking" / "docking_results.tsv")
    rerank_rows = read_tsv(results_root / "ai_reranking" / "reranked_candidates.tsv")
    filter_rows = read_tsv(results_root / "filtering" / "filtered_candidates.tsv")

    enhancement_candidates = build_candidate_table(enhancement_case_id, docking_rows, rerank_rows, filter_rows)
    baseline_candidates = build_candidate_table(base_case_id, docking_rows, rerank_rows, filter_rows)

    baseline_reason_counts = Counter(row["filter_reason"] for row in baseline_candidates)
    enhancement_reason_counts = Counter(row["filter_reason"] for row in enhancement_candidates)
    best_enhancement_vina = min(row["vina_affinity_kcal_mol"] for row in enhancement_candidates)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_case_id": base_case_id,
        "enhancement_case_id": enhancement_case_id,
        "challenge_class": "filter_gated_after_rerank_gain",
        "effective_filter_policy": effective_filter_policy,
        "configured_filter_policy_field": enhancement_case_row.get("filter_policy", ""),
        "rollout_preserved": False,
        "boundary_impact": "exclude_from_current_approved_boundary",
        "case_comparison": [
            {
                "case_id": base_case_id,
                "known_active_rank": baseline_summary.get("known_active_rank"),
                "known_active_shortlisted": baseline_summary.get("known_active_shortlisted"),
                "filter_keep_count": baseline_summary.get("filter_keep_count"),
                "shortlist_count": baseline_summary.get("shortlist_count"),
                "best_background_compound_id": baseline_summary.get("best_background_compound_id"),
                "active_best_background_gap": baseline_summary.get("active_best_background_gap"),
            },
            {
                "case_id": enhancement_case_id,
                "known_active_rank": enhancement_summary.get("known_active_rank"),
                "known_active_shortlisted": enhancement_summary.get("known_active_shortlisted"),
                "filter_keep_count": enhancement_summary.get("filter_keep_count"),
                "shortlist_count": enhancement_summary.get("shortlist_count"),
                "best_background_compound_id": enhancement_summary.get("best_background_compound_id"),
                "active_best_background_gap": enhancement_summary.get("active_best_background_gap"),
            },
        ],
        "filter_thresholds": thresholds,
        "baseline_filter_reason_counts": dict(baseline_reason_counts),
        "enhancement_filter_reason_counts": dict(enhancement_reason_counts),
        "enhancement_candidates": enhancement_candidates,
        "audit_context": {
            "best_background_compound_id": audit.get("current_metrics", {}).get("best_background_compound_id"),
            "best_background_flags": audit.get("current_metrics", {}).get("best_background_flags", []),
            "shortlist_ids": audit.get("current_metrics", {}).get("shortlist_ids", []),
        },
        "root_cause_notes": [
            f"Enhancement reranking clearly improves ordering: `{enhancement_case_id}` moves `I-BET762` from baseline rank `{baseline_summary.get('known_active_rank')}` to enhancement rank `{enhancement_summary.get('known_active_rank')}` and raises the active-best-background gap from `{comparison['baseline_case']['active_margin']['known_active_to_best_background_gap']}` to `{comparison['enhancement_case']['active_margin']['known_active_to_best_background_gap']}`.",
            f"Filtering blocks the gain because the effective policy is `{effective_filter_policy}`, not the literal metadata field `{enhancement_case_row.get('filter_policy', '')}`.",
            f"The first hard gate is `vina_affinity <= {thresholds['max_vina_affinity']}`; the best enhancement vina in this surface is only `{best_enhancement_vina}`, so every candidate is excluded before shortlist construction.",
            f"All enhancement candidates were excluded for the same reason: `{', '.join(f'{key}={value}' for key, value in enhancement_reason_counts.items())}`.",
            "Clustering is therefore downstream-empty rather than independently failing: it receives `filter_keep_input_count = 0`, so shortlist generation never gets a candidate set to prioritize.",
        ],
        "recommendation_notes": [
            "Keep this surface logged as a boundary challenge rather than a rollout-safe material case.",
            "Do not use its rerank gain alone to expand the approved enhancement-line boundary while shortlist preservation is still broken.",
            "If we revisit it later, the right review surface is the literature-comparison filtering gate on this target/panel pairing, not more v3 rerank tuning.",
        ],
    }

    write_json(output_json, payload)
    write_text(output_md, build_markdown(payload))


if __name__ == "__main__":
    main()
