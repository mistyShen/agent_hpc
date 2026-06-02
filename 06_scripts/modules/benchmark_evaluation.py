#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


CASE_TYPE_BUCKETS = ["toy", "debug", "realistic", "literature_backed"]
BRINGUP_PURPOSES = {"debug"}
BRINGUP_TIERS = {"bringup", "smoke"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate lightweight benchmark evaluation outputs.")
    parser.add_argument("--module", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--input-manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def count_by_field(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(field, "").strip() or "unspecified"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def ensure_case_type_buckets(counts: dict[str, int]) -> dict[str, int]:
    payload = {bucket: 0 for bucket in CASE_TYPE_BUCKETS}
    payload.update(counts)
    return payload


def enabled_flag(row: dict[str, str]) -> bool:
    return row.get("enabled", "").strip().lower() == "true"


def build_case_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["case_id"]: row for row in rows}


def case_id_set(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {row["case_id"] for row in read_tsv_rows(path) if row.get("case_id", "").strip()}


def classify_comparison_band(row: dict[str, str]) -> str:
    run_purpose = row.get("run_purpose", "").strip()
    case_tier = row.get("case_tier", "").strip()
    if run_purpose in BRINGUP_PURPOSES or case_tier in BRINGUP_TIERS:
        return "bringup_debug"
    return "comparison_oriented"


def summarize_group(
    rows: list[dict[str, str]],
    field: str,
    completed_case_ids: set[str],
    valid_case_ids: set[str],
) -> dict[str, dict[str, int]]:
    grouped: dict[str, dict[str, int]] = {}
    for row in rows:
        key = row.get(field, "").strip() or "unspecified"
        bucket = grouped.setdefault(
            key,
            {
                "case_count": 0,
                "enabled_case_count": 0,
                "completed_case_count": 0,
                "valid_artifact_case_count": 0,
            },
        )
        case_id = row["case_id"]
        bucket["case_count"] += 1
        if enabled_flag(row):
            bucket["enabled_case_count"] += 1
        if case_id in completed_case_ids:
            bucket["completed_case_count"] += 1
        if case_id in valid_case_ids:
            bucket["valid_artifact_case_count"] += 1
    return dict(sorted(grouped.items()))


def rows_by_case(path: Path) -> dict[str, list[dict[str, str]]]:
    if not path.exists():
        return {}
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in read_tsv_rows(path):
        case_id = row.get("case_id", "").strip()
        if not case_id:
            continue
        grouped.setdefault(case_id, []).append(row)
    return grouped


def truth_rows_by_case(path: Path) -> dict[str, list[dict[str, str]]]:
    if not path.exists():
        return {}
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in read_tsv_rows(path):
        case_id = row.get("case_id", "").strip()
        if not case_id:
            continue
        grouped.setdefault(case_id, []).append(row)
    return grouped


def markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    if not rows:
        return ["_No rows_"]
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
        *["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows],
    ]


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_manifest = load_json(Path(args.run_manifest))
    benchmark_cases = read_tsv_rows(Path(args.input_manifest))

    filtering_summary_path = Path("07_results/modules/filtering/filter_summary.json")
    report_summary_path = Path("09_reports/benchmark_summary.json")
    filtering_summary = load_json(filtering_summary_path) if filtering_summary_path.exists() else None
    report_summary = load_json(report_summary_path) if report_summary_path.exists() else None
    docking_path = Path("07_results/modules/classical_docking/docking_results.tsv")
    reranking_path = Path("07_results/modules/ai_reranking/reranked_candidates.tsv")
    filtering_path = Path("07_results/modules/filtering/filtered_candidates.tsv")
    clustering_path = Path("07_results/modules/clustering_and_prioritization/clustered_priorities.tsv")
    truth_table_path = Path("04_metadata/benchmark_case_truth.tsv")
    docking_case_ids = case_id_set(docking_path)
    reranking_case_ids = case_id_set(reranking_path)
    filtering_case_ids = case_id_set(filtering_path)
    clustering_case_ids = case_id_set(clustering_path)
    docking_rows_by_case = rows_by_case(docking_path)
    reranking_rows_by_case = rows_by_case(reranking_path)
    filtering_rows_by_case = rows_by_case(filtering_path)
    clustering_rows_by_case = rows_by_case(clustering_path)
    truth_by_case = truth_rows_by_case(truth_table_path)
    docking_by_key = {
        (row["case_id"], row["compound_id"]): row
        for case_rows in docking_rows_by_case.values()
        for row in case_rows
    }
    reranking_by_key = {
        (row["case_id"], row["compound_id"]): row
        for case_rows in reranking_rows_by_case.values()
        for row in case_rows
    }

    eval_json_path = Path("09_reports/benchmark_evaluation.json")
    eval_md_path = Path("09_reports/benchmark_evaluation.md")
    comparison_json_path = Path("09_reports/benchmark_comparison.json")
    comparison_md_path = Path("09_reports/benchmark_comparison.md")
    eval_json_path.parent.mkdir(parents=True, exist_ok=True)

    enabled_cases = [row for row in benchmark_cases if row.get("enabled", "").strip().lower() == "true"]
    case_index = build_case_index(benchmark_cases)
    candidate_count = filtering_summary.get("candidate_count", 0) if filtering_summary else 0
    enabled_case_count = len(enabled_cases)
    enabled_case_type_counts = ensure_case_type_buckets(count_by_field(enabled_cases, "case_type"))
    enabled_case_tier_counts = count_by_field(enabled_cases, "case_tier")
    enabled_run_purpose_counts = count_by_field(enabled_cases, "run_purpose")
    enabled_primary_metric_counts = count_by_field(enabled_cases, "primary_metric")
    case_catalog = [
        {
            "case_id": row["case_id"],
            "case_type": row.get("case_type", "").strip() or "unspecified",
            "case_tier": row.get("case_tier", "").strip() or "unspecified",
            "run_purpose": row.get("run_purpose", "").strip() or "unspecified",
            "primary_metric": row.get("primary_metric", "").strip() or "unspecified",
            "enabled": row.get("enabled", "").strip().lower() == "true",
            "comparison_band": classify_comparison_band(row),
        }
        for row in benchmark_cases
    ]
    completed_case_ids = {
        case_id
        for case_id in case_index
        if case_id in docking_case_ids and case_id in reranking_case_ids and case_id in filtering_case_ids
    }
    valid_artifact_case_ids = {
        case_id
        for case_id in completed_case_ids
        if case_id in clustering_case_ids
    }
    grouped_by_case_type = summarize_group(
        benchmark_cases,
        "case_type",
        completed_case_ids,
        valid_artifact_case_ids,
    )
    grouped_by_run_purpose = summarize_group(
        benchmark_cases,
        "run_purpose",
        completed_case_ids,
        valid_artifact_case_ids,
    )
    grouped_by_primary_metric = summarize_group(
        benchmark_cases,
        "primary_metric",
        completed_case_ids,
        valid_artifact_case_ids,
    )
    grouped_by_comparison_band = summarize_group(
        [
            {
                **row,
                "comparison_band": classify_comparison_band(row),
            }
            for row in benchmark_cases
        ],
        "comparison_band",
        completed_case_ids,
        valid_artifact_case_ids,
    )
    case_module_counts: list[dict[str, object]] = []
    case_final_shortlists: list[dict[str, object]] = []
    ground_truth_summary: dict[str, dict[str, object]] = {}
    for row in enabled_cases:
        case_id = row["case_id"]
        shortlisted_rows = sorted(
            clustering_rows_by_case.get(case_id, []),
            key=lambda item: int(item.get("priority_rank", "999") or "999"),
        )
        known_active_ids = {
            truth_row["compound_id"]
            for truth_row in truth_by_case.get(case_id, [])
            if truth_row.get("truth_label", "").strip() == "known_active"
        }
        keep_ids = {
            item.get("compound_id", "") or item.get("candidate_id", "")
            for item in filtering_rows_by_case.get(case_id, [])
            if item.get("filter_decision", "") == "keep"
        }
        shortlist_ids = {item["compound_id"] for item in shortlisted_rows}
        best_known_active_rank = None
        for shortlist_row in shortlisted_rows:
            if shortlist_row["compound_id"] in known_active_ids:
                best_known_active_rank = int(shortlist_row.get("priority_rank", "0") or "0")
                break
        if known_active_ids:
            ground_truth_summary[case_id] = {
                "known_active_count": len(known_active_ids),
                "known_active_recovered_in_filter_keep": len(known_active_ids & keep_ids),
                "known_active_recovered_in_shortlist": len(known_active_ids & shortlist_ids),
                "shortlist_contains_known_active": bool(known_active_ids & shortlist_ids),
                "best_known_active_rank": best_known_active_rank,
            }
        case_module_counts.append(
            {
                "case_id": case_id,
                "case_type": row.get("case_type", "").strip() or "unspecified",
                "run_purpose": row.get("run_purpose", "").strip() or "unspecified",
                "primary_metric": row.get("primary_metric", "").strip() or "unspecified",
                "docking_candidate_count": len(docking_rows_by_case.get(case_id, [])),
                "reranked_candidate_count": len(reranking_rows_by_case.get(case_id, [])),
                "filtered_candidate_count": len(filtering_rows_by_case.get(case_id, [])),
                "filter_keep_count": sum(
                    item.get("filter_decision", "") == "keep" for item in filtering_rows_by_case.get(case_id, [])
                ),
                "shortlist_count": len(shortlisted_rows),
            }
        )
        case_final_shortlists.append(
            {
                "case_id": case_id,
                "shortlist": [
                    {
                        "compound_id": shortlist_row["compound_id"],
                        "priority_rank": int(shortlist_row.get("priority_rank", "0") or "0"),
                        "priority_tier": shortlist_row.get("priority_tier", ""),
                        "cluster_id": shortlist_row.get("cluster_id", ""),
                        "selection_reason": shortlist_row.get("selection_reason", ""),
                        "rerank_score": reranking_by_key.get((case_id, shortlist_row["compound_id"]), {}).get(
                            "rerank_score", ""
                        ),
                        "vina_affinity_kcal_mol": docking_by_key.get(
                            (case_id, shortlist_row["compound_id"]), {}
                        ).get("vina_affinity_kcal_mol", ""),
                    }
                    for shortlist_row in shortlisted_rows
                ],
            }
        )

    summary_payload = {
        "project_name": run_manifest["project_name"],
        "project_root": args.project_root,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_manifest": args.run_manifest,
        "enabled_benchmark_case_count": enabled_case_count,
        "candidate_count": candidate_count,
        "avg_candidates_per_enabled_case": (
            round(candidate_count / enabled_case_count, 2) if enabled_case_count else 0.0
        ),
        "enabled_case_type_counts": enabled_case_type_counts,
        "enabled_case_tier_counts": enabled_case_tier_counts,
        "enabled_run_purpose_counts": enabled_run_purpose_counts,
        "enabled_primary_metric_counts": enabled_primary_metric_counts,
        "completed_case_count": len(completed_case_ids),
        "valid_artifact_case_count": len(valid_artifact_case_ids),
        "grouped_comparisons": {
            "by_case_type": grouped_by_case_type,
            "by_run_purpose": grouped_by_run_purpose,
            "by_primary_metric": grouped_by_primary_metric,
            "by_comparison_band": grouped_by_comparison_band,
        },
        "ground_truth_summary": ground_truth_summary,
        "case_module_counts": case_module_counts,
        "case_final_shortlists": case_final_shortlists,
        "case_catalog": case_catalog,
        "report_available": bool(report_summary),
        "filtering_available": bool(filtering_summary),
        "evaluation_status": "typed_lightweight_complete" if report_summary and filtering_summary else "partial",
    }
    eval_json_path.write_text(json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8")
    markdown = "\n".join(
        [
            "# Benchmark Evaluation",
            "",
            f"- Project: `{run_manifest['project_name']}`",
            f"- Enabled benchmark cases: `{enabled_case_count}`",
            f"- Completed cases: `{len(completed_case_ids)}`",
            f"- Valid artifact cases: `{len(valid_artifact_case_ids)}`",
            f"- Candidate count: `{candidate_count}`",
            f"- Avg candidates per enabled case: `{summary_payload['avg_candidates_per_enabled_case']}`",
            f"- Report available: `{summary_payload['report_available']}`",
            f"- Filtering available: `{summary_payload['filtering_available']}`",
            f"- Evaluation status: `{summary_payload['evaluation_status']}`",
            "",
            "## Enabled Case Types",
            "",
            *[f"- `{case_type}`: `{count}`" for case_type, count in enabled_case_type_counts.items()],
            "",
            "## Enabled Run Purposes",
            "",
            *[f"- `{purpose}`: `{count}`" for purpose, count in enabled_run_purpose_counts.items()],
            "",
            "## Enabled Primary Metrics",
            "",
            *[f"- `{metric}`: `{count}`" for metric, count in enabled_primary_metric_counts.items()],
            "",
            "## Case Catalog",
            "",
            *[
                f"- `{row['case_id']}`: type `{row['case_type']}`, tier `{row['case_tier']}`, purpose `{row['run_purpose']}`, metric `{row['primary_metric']}`, band `{row['comparison_band']}`, enabled `{row['enabled']}`"
                for row in case_catalog
            ],
            "",
            "## Grouped Comparisons By Case Type",
            "",
            *[
                f"- `{group}`: cases `{stats['case_count']}`, enabled `{stats['enabled_case_count']}`, completed `{stats['completed_case_count']}`, valid artifacts `{stats['valid_artifact_case_count']}`"
                for group, stats in grouped_by_case_type.items()
            ],
            "",
            "## Grouped Comparisons By Run Purpose",
            "",
            *[
                f"- `{group}`: cases `{stats['case_count']}`, enabled `{stats['enabled_case_count']}`, completed `{stats['completed_case_count']}`, valid artifacts `{stats['valid_artifact_case_count']}`"
                for group, stats in grouped_by_run_purpose.items()
            ],
            "",
            "## Grouped Comparisons By Primary Metric",
            "",
            *[
                f"- `{group}`: cases `{stats['case_count']}`, enabled `{stats['enabled_case_count']}`, completed `{stats['completed_case_count']}`, valid artifacts `{stats['valid_artifact_case_count']}`"
                for group, stats in grouped_by_primary_metric.items()
            ],
            "",
            "## Bringup And Comparison Bands",
            "",
            *[
                f"- `{group}`: cases `{stats['case_count']}`, enabled `{stats['enabled_case_count']}`, completed `{stats['completed_case_count']}`, valid artifacts `{stats['valid_artifact_case_count']}`"
                for group, stats in grouped_by_comparison_band.items()
            ],
            "",
            "## Ground Truth Recovery Summary",
            "",
            *(
                markdown_table(
                    [
                        "Case",
                        "Known Active Count",
                        "In Filter Keep",
                        "In Shortlist",
                        "Shortlist Contains Known Active",
                        "Best Known Active Rank",
                    ],
                    [
                        [
                            case_id,
                            stats["known_active_count"],
                            stats["known_active_recovered_in_filter_keep"],
                            stats["known_active_recovered_in_shortlist"],
                            stats["shortlist_contains_known_active"],
                            stats["best_known_active_rank"] if stats["best_known_active_rank"] is not None else "",
                        ]
                        for case_id, stats in sorted(ground_truth_summary.items())
                    ],
                )
                if ground_truth_summary
                else ["_No case-level ground truth rows available_"]
            ),
            "",
        ]
    )
    eval_md_path.write_text(markdown + "\n", encoding="utf-8")
    comparison_overview_rows = []
    for row, shortlist_payload in zip(case_module_counts, case_final_shortlists):
        shortlist = shortlist_payload["shortlist"]
        top_1 = shortlist[0]["compound_id"] if len(shortlist) >= 1 else "-"
        top_2 = shortlist[1]["compound_id"] if len(shortlist) >= 2 else "-"
        comparison_overview_rows.append(
            [
                row["case_id"],
                case_index.get(row["case_id"], {}).get("target_id", ""),
                case_index.get(row["case_id"], {}).get("library_id", ""),
                row["case_type"],
                case_index.get(row["case_id"], {}).get("case_tier", "") or "unspecified",
                row["run_purpose"],
                row["primary_metric"],
                row["docking_candidate_count"],
                row["reranked_candidate_count"],
                row["filtered_candidate_count"],
                row["filter_keep_count"],
                row["shortlist_count"],
                top_1,
                top_2,
            ]
        )
    comparison_payload = {
        "project_name": run_manifest["project_name"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "comparison_overview_rows": [
            {
                "case_id": row[0],
                "target_id": row[1],
                "library_id": row[2],
                "case_type": row[3],
                "case_tier": row[4],
                "run_purpose": row[5],
                "primary_metric": row[6],
                "docking_candidate_count": row[7],
                "reranked_candidate_count": row[8],
                "filtered_candidate_count": row[9],
                "filter_keep_count": row[10],
                "shortlist_count": row[11],
                "top_1_compound": row[12],
                "top_2_compound": row[13],
            }
            for row in comparison_overview_rows
        ],
        "case_module_counts": case_module_counts,
        "case_final_shortlists": case_final_shortlists,
        "grouped_summary_tables": summary_payload["grouped_comparisons"],
        "ground_truth_summary": ground_truth_summary,
    }
    comparison_json_path.write_text(json.dumps(comparison_payload, indent=2) + "\n", encoding="utf-8")

    comparison_markdown_lines = [
        "# Benchmark Comparison",
        "",
        f"- Project: `{run_manifest['project_name']}`",
        f"- Enabled cases: `{enabled_case_count}`",
        f"- Completed cases: `{len(completed_case_ids)}`",
        f"- Valid artifact cases: `{len(valid_artifact_case_ids)}`",
        "",
        "## Manuscript Comparison Table",
        "",
        *markdown_table(
            [
                "Case",
                "Target",
                "Library",
                "Type",
                "Tier",
                "Purpose",
                "Metric",
                "Docking",
                "Reranked",
                "Filtered",
                "Keep",
                "Shortlist",
                "Top 1",
                "Top 2",
            ],
            comparison_overview_rows,
        ),
        "",
        "## Candidate Counts By Case",
        "",
        *markdown_table(
            [
                "Case",
                "Type",
                "Purpose",
                "Metric",
                "Docking",
                "Reranked",
                "Filtered",
                "Keep",
                "Shortlist",
            ],
            [
                [
                    row["case_id"],
                    row["case_type"],
                    row["run_purpose"],
                    row["primary_metric"],
                    row["docking_candidate_count"],
                    row["reranked_candidate_count"],
                    row["filtered_candidate_count"],
                    row["filter_keep_count"],
                    row["shortlist_count"],
                ]
                for row in case_module_counts
            ],
        ),
        "",
        "## Final Shortlist Tables",
        "",
    ]
    for case_shortlist in case_final_shortlists:
        comparison_markdown_lines.append(f"### {case_shortlist['case_id']}")
        comparison_markdown_lines.append("")
        shortlist = case_shortlist["shortlist"]
        if not shortlist:
            comparison_markdown_lines.append("_No shortlisted candidates_")
            comparison_markdown_lines.append("")
            continue
        comparison_markdown_lines.extend(
            markdown_table(
                ["Rank", "Compound", "Tier", "Cluster", "Rerank Score", "Vina Affinity", "Reason"],
                [
                    [
                        row["priority_rank"],
                        row["compound_id"],
                        row["priority_tier"],
                        row["cluster_id"],
                        row["rerank_score"],
                        row["vina_affinity_kcal_mol"],
                        row["selection_reason"],
                    ]
                    for row in shortlist
                ],
            )
        )
        comparison_markdown_lines.append("")
    comparison_markdown_lines.extend(
        [
            "## Grouped Summary By Case Type",
            "",
            *markdown_table(
                ["Case Type", "Cases", "Enabled", "Completed", "Valid Artifacts"],
                [
                    [
                        group,
                        stats["case_count"],
                        stats["enabled_case_count"],
                        stats["completed_case_count"],
                        stats["valid_artifact_case_count"],
                    ]
                    for group, stats in grouped_by_case_type.items()
                ],
            ),
            "",
            "## Grouped Summary By Run Purpose",
            "",
            *markdown_table(
                ["Run Purpose", "Cases", "Enabled", "Completed", "Valid Artifacts"],
                [
                    [
                        group,
                        stats["case_count"],
                        stats["enabled_case_count"],
                        stats["completed_case_count"],
                        stats["valid_artifact_case_count"],
                    ]
                    for group, stats in grouped_by_run_purpose.items()
                ],
            ),
            "",
            "## Grouped Summary By Primary Metric",
            "",
            *markdown_table(
                ["Primary Metric", "Cases", "Enabled", "Completed", "Valid Artifacts"],
                [
                    [
                        group,
                        stats["case_count"],
                        stats["enabled_case_count"],
                        stats["completed_case_count"],
                        stats["valid_artifact_case_count"],
                    ]
                    for group, stats in grouped_by_primary_metric.items()
                ],
            ),
            "",
            "## Ground Truth Recovery",
            "",
            *(
                markdown_table(
                    [
                        "Case",
                        "Known Active Count",
                        "In Filter Keep",
                        "In Shortlist",
                        "Shortlist Contains Known Active",
                        "Best Known Active Rank",
                    ],
                    [
                        [
                            case_id,
                            stats["known_active_count"],
                            stats["known_active_recovered_in_filter_keep"],
                            stats["known_active_recovered_in_shortlist"],
                            stats["shortlist_contains_known_active"],
                            stats["best_known_active_rank"] if stats["best_known_active_rank"] is not None else "",
                        ]
                        for case_id, stats in sorted(ground_truth_summary.items())
                    ],
                )
                if ground_truth_summary
                else ["_No case-level ground truth rows available_"]
            ),
            "",
            "## Comparison Notes",
            "",
            "- This comparison report is manuscript-friendly but still demo-scale.",
            "- Current tables summarize case-level flow from docking through shortlist generation.",
            "- Ground-truth recovery metrics are only populated for cases with rows in benchmark_case_truth.tsv.",
            "- Interpretation should remain limited to toy/debug benchmark behavior unless realistic or literature-backed cases are added.",
            "",
        ]
    )
    comparison_md_path.write_text("\n".join(comparison_markdown_lines).rstrip() + "\n", encoding="utf-8")

    payload = {
        "module": args.module,
        "status": "evaluation_completed",
        "config": args.config,
        "project_root": args.project_root,
        "run_manifest": args.run_manifest,
        "input_manifest": args.input_manifest,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validation": {
            "run_manifest_exists": Path(args.run_manifest).exists(),
            "input_manifest_exists": Path(args.input_manifest).exists(),
            "filtering_summary_exists": filtering_summary_path.exists(),
            "report_summary_exists": report_summary_path.exists(),
            "evaluation_json_written": eval_json_path.exists(),
            "evaluation_markdown_written": eval_md_path.exists(),
            "comparison_json_written": comparison_json_path.exists(),
            "comparison_markdown_written": comparison_md_path.exists(),
        },
        "run_context": {
            "run_mode": run_manifest.get("mode"),
            "enabled_benchmark_cases": run_manifest.get("counts", {}).get("enabled_benchmark_cases"),
        },
        "module_profile": {
            "stage_type": "benchmark_evaluation",
            "primary_inputs": ["run manifest", "filter summary", "benchmark summary"],
            "primary_outputs": [
                str(eval_json_path),
                str(eval_md_path),
                str(comparison_json_path),
                str(comparison_md_path),
                args.output,
            ],
            "next_action_hint": "use case typing to separate debug runs from future comparison-grade benchmark cases",
        },
        "input_summary": {
            "row_count": len(benchmark_cases),
            "preview_ids": [row["case_id"] for row in benchmark_cases[:3]],
        },
        "evaluation_outputs": {
            "json": str(eval_json_path),
            "markdown": str(eval_md_path),
            "comparison_json": str(comparison_json_path),
            "comparison_markdown": str(comparison_md_path),
        },
        "notes": [
            "Benchmark evaluation now produces grouped comparison views by case type, run purpose, and primary metric.",
            "Bringup/debug cases are explicitly separated from more comparison-oriented cases using case tier and run purpose.",
            "Case-level comparison outputs now include final shortlist summaries and candidate counts across docking, reranking, filtering, and clustering stages.",
        ],
    }

    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"[module] wrote evaluation json: {eval_json_path}")
    print(f"[module] wrote evaluation markdown: {eval_md_path}")
    print(f"[module] wrote comparison json: {comparison_json_path}")
    print(f"[module] wrote comparison markdown: {comparison_md_path}")
    print(f"[module] wrote module artifact: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
