#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate lightweight project-level benchmark reports.")
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


def maybe_load_json(path: Path) -> dict[str, object] | None:
    return load_json(path) if path.exists() else None


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

    run_manifest_path = Path(args.run_manifest)
    run_manifest = load_json(run_manifest_path)
    benchmark_cases = read_tsv_rows(Path(args.input_manifest))
    enabled_cases = [row for row in benchmark_cases if row.get("enabled", "").strip().lower() == "true"]

    module_dir = Path("07_results/modules")
    module_statuses = {
        path.parent.name: load_json(path)
        for path in sorted(module_dir.glob("*/done.json"))
    }

    target_summary = maybe_load_json(module_dir / "target_preparation" / "target_summary.json")
    library_summary = maybe_load_json(module_dir / "compound_library_preparation" / "library_summary.json")
    docking_summary = maybe_load_json(module_dir / "classical_docking" / "docking_summary.json")
    reranking_summary = maybe_load_json(module_dir / "ai_reranking" / "reranking_summary.json")
    filtering_summary = maybe_load_json(module_dir / "filtering" / "filter_summary.json")
    clustering_summary = maybe_load_json(module_dir / "clustering_and_prioritization" / "clustering_summary.json")
    evaluation_summary = maybe_load_json(Path("09_reports/benchmark_evaluation.json"))
    comparison_summary = maybe_load_json(Path("09_reports/benchmark_comparison.json"))

    benchmark_summary_json = Path("09_reports/benchmark_summary.json")
    benchmark_summary_md = Path("09_reports/benchmark_summary.md")
    project_summary_json = Path("09_reports/project_summary.json")
    project_summary_md = Path("09_reports/project_summary.md")
    benchmark_summary_json.parent.mkdir(parents=True, exist_ok=True)

    module_overview = {
        module_name: {
            "status": payload.get("status"),
            "timestamp_utc": payload.get("timestamp_utc"),
        }
        for module_name, payload in module_statuses.items()
    }

    summary_payload = {
        "project_name": run_manifest["project_name"],
        "project_root": args.project_root,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_manifest": args.run_manifest,
        "benchmark_case_count": len(benchmark_cases),
        "enabled_benchmark_case_count": len(enabled_cases),
        "case_ids": [row["case_id"] for row in benchmark_cases],
        "module_overview": module_overview,
        "module_summaries": {
            "target_preparation": target_summary,
            "compound_library_preparation": library_summary,
            "classical_docking": docking_summary,
            "ai_reranking": reranking_summary,
            "filtering": filtering_summary,
            "clustering_and_prioritization": clustering_summary,
            "benchmark_evaluation": evaluation_summary,
            "benchmark_comparison": comparison_summary,
        },
    }

    benchmark_summary_json.write_text(json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8")
    project_summary_json.write_text(json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8")

    markdown_lines = [
        "# Project Summary",
        "",
        f"- Project: `{run_manifest['project_name']}`",
        f"- Project root: `{args.project_root}`",
        f"- Generated at: `{summary_payload['generated_at_utc']}`",
        f"- Benchmark cases: `{len(benchmark_cases)}`",
        f"- Enabled benchmark cases: `{len(enabled_cases)}`",
        "",
        "## Module Status",
        "",
    ]
    for module_name, payload in module_overview.items():
        markdown_lines.append(f"- `{module_name}`: `{payload['status']}`")

    markdown_lines.extend(
        [
            "",
            "## Key Outputs",
            "",
            (
                f"- Targets prepared: `{target_summary['prepared_target_count']}`"
                if target_summary
                else "- Targets prepared: unavailable"
            ),
            (
                f"- Library records prepared: `{library_summary['prepared_record_count']}`"
                if library_summary
                else "- Library records prepared: unavailable"
            ),
            (
                f"- Docking rows: `{docking_summary['result_row_count']}`"
                if docking_summary
                else "- Docking rows: unavailable"
            ),
            (
                f"- Reranked rows: `{reranking_summary['reranked_row_count']}`"
                if reranking_summary
                else "- Reranked rows: unavailable"
            ),
            (
                f"- Filtered candidate count: `{filtering_summary['candidate_count']}`"
                if filtering_summary
                else "- Filtered candidate count: unavailable"
            ),
            (
                f"- Prioritized candidate count: `{clustering_summary['prioritized_candidate_count']}`"
                if clustering_summary
                else "- Prioritized candidate count: unavailable"
            ),
            (
                f"- Evaluation status: `{evaluation_summary['evaluation_status']}`"
                if evaluation_summary
                else "- Evaluation status: unavailable"
            ),
            (
                f"- Comparison cases summarized: `{len(comparison_summary['case_module_counts'])}`"
                if comparison_summary
                else "- Comparison cases summarized: unavailable"
            ),
            "",
            "## Cases",
            "",
        ]
    )
    markdown_lines.extend(
        [f"- `{row['case_id']}` -> target `{row['target_id']}`, library `{row['library_id']}`" for row in benchmark_cases]
    )
    if comparison_summary:
        comparison_rows = comparison_summary.get("comparison_overview_rows") or comparison_summary.get(
            "case_module_counts", []
        )
        markdown_lines.extend(
            [
                "",
                "## Comparison Snapshot",
                "",
                *markdown_table(
                    [
                        "Case",
                        "Type",
                        "Purpose",
                        "Docking",
                        "Reranked",
                        "Filtered",
                        "Keep",
                        "Shortlist",
                    ],
                    [
                        [
                            row["case_id"],
                            row.get("case_type", "unspecified"),
                            row.get("run_purpose", "unspecified"),
                            row["docking_candidate_count"],
                            row["reranked_candidate_count"],
                            row["filtered_candidate_count"],
                            row["filter_keep_count"],
                            row["shortlist_count"],
                        ]
                        for row in comparison_rows
                    ],
                ),
                "",
                f"- Comparison markdown: `09_reports/benchmark_comparison.md`",
                f"- Comparison json: `09_reports/benchmark_comparison.json`",
            ]
        )
    markdown = "\n".join(markdown_lines) + "\n"
    benchmark_summary_md.write_text(markdown, encoding="utf-8")
    project_summary_md.write_text(markdown, encoding="utf-8")

    payload = {
        "module": args.module,
        "status": "report_generated",
        "config": args.config,
        "project_root": args.project_root,
        "run_manifest": args.run_manifest,
        "input_manifest": args.input_manifest,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validation": {
            "run_manifest_exists": run_manifest_path.exists(),
            "input_manifest_exists": Path(args.input_manifest).exists(),
            "benchmark_summary_json_written": benchmark_summary_json.exists(),
            "benchmark_summary_markdown_written": benchmark_summary_md.exists(),
            "project_summary_json_written": project_summary_json.exists(),
            "project_summary_markdown_written": project_summary_md.exists(),
        },
        "run_context": {
            "run_mode": run_manifest.get("mode"),
            "enabled_benchmark_cases": run_manifest.get("counts", {}).get("enabled_benchmark_cases"),
        },
        "module_profile": {
            "stage_type": "report_generation",
            "primary_inputs": ["module summaries", "benchmark case metadata", "run manifest"],
            "primary_outputs": [
                str(benchmark_summary_json),
                str(benchmark_summary_md),
                str(project_summary_json),
                str(project_summary_md),
                args.output,
            ],
            "next_action_hint": "attach richer tables and cross-module provenance once upstream modules become more detailed",
        },
        "input_summary": {
            "row_count": len(benchmark_cases),
            "preview_ids": [row["case_id"] for row in benchmark_cases[:3]],
        },
        "report_outputs": {
            "benchmark_json": str(benchmark_summary_json),
            "benchmark_markdown": str(benchmark_summary_md),
            "project_json": str(project_summary_json),
            "project_markdown": str(project_summary_md),
            "comparison_json": "09_reports/benchmark_comparison.json",
            "comparison_markdown": "09_reports/benchmark_comparison.md",
        },
        "notes": [
            "Report generation now creates project-level summaries by aggregating concrete module outputs.",
            "Top-level summaries now expose benchmark comparison outputs for case-level reporting.",
            "Comparison snapshot is formatted as a stable table for manuscript-style reuse.",
            "Keep both benchmark_summary and project_summary artifacts for backward compatibility.",
        ],
    }

    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"[module] wrote benchmark summary json: {benchmark_summary_json}")
    print(f"[module] wrote benchmark summary markdown: {benchmark_summary_md}")
    print(f"[module] wrote project summary json: {project_summary_json}")
    print(f"[module] wrote project summary markdown: {project_summary_md}")
    print(f"[module] wrote module artifact: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
