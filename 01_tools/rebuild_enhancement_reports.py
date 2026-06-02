#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serially rebuild enhancement-line reports and validate consistency."
    )
    parser.add_argument("--project-root", default=".", help="Project root containing 01_tools/ and 09_reports/")
    parser.add_argument("--baseline-case-id", default="BRD4_BD1_LIT002")
    parser.add_argument("--enhancement-case-id", default="BRD4_BD1_LIT002_V3EXP")
    parser.add_argument(
        "--skip-comparison",
        action="store_true",
        help="Skip comparison rebuild and only refresh downstream derived reports.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if consistency checks fail.",
    )
    parser.add_argument(
        "--skip-archive",
        action="store_true",
        help="Skip archiving the current enhancement snapshot after successful rebuild.",
    )
    parser.add_argument(
        "--fetch-remote-root",
        default="",
        help="Optional remote isolated enhancement root; if set, fetch enhancement comparison/delta reports before rebuilding.",
    )
    return parser.parse_args()


def run_step(project_root: Path, args: list[str]) -> None:
    subprocess.run(args, cwd=project_root, check=True)


def read_case_ids_from_tsv(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {
            row["case_id"]
            for row in csv.DictReader(handle, delimiter="\t")
            if row.get("case_id")
        }


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def rebuild_reports(project_root: Path, baseline_case_id: str, enhancement_case_id: str, skip_comparison: bool) -> None:
    tools_dir = project_root / "01_tools"
    comparison_tool = tools_dir / "build_enhancement_comparison.py"
    delta_tool = tools_dir / "build_enhancement_background_delta.py"
    tracker_tool = tools_dir / "build_enhancement_iteration_tracker.py"
    checklist_tool = tools_dir / "build_enhancement_diagnostic_checklist.py"
    flag_tool = tools_dir / "build_enhancement_flag_impact_summary.py"
    watchlist_tool = tools_dir / "build_enhancement_background_watchlist.py"
    archive_tool = tools_dir / "archive_enhancement_snapshot.py"

    rerank_case_ids = read_case_ids_from_tsv(project_root / "07_results/modules/ai_reranking/reranked_candidates.tsv")
    cluster_case_ids = read_case_ids_from_tsv(
        project_root / "07_results/modules/clustering_and_prioritization/clustered_priorities.tsv"
    )
    can_rebuild_case_outputs = (
        baseline_case_id in rerank_case_ids
        and enhancement_case_id in rerank_case_ids
        and baseline_case_id in cluster_case_ids
        and enhancement_case_id in cluster_case_ids
    )

    if not skip_comparison and can_rebuild_case_outputs:
        run_step(
            project_root,
            [
                sys.executable,
                str(comparison_tool),
                "--project-root",
                str(project_root),
                "--baseline-case-id",
                baseline_case_id,
                "--enhancement-case-id",
                enhancement_case_id,
            ],
        )
    elif not skip_comparison:
        comparison_json = project_root / "09_reports/enhancement_line_v2_vs_v3_comparison.json"
        if not comparison_json.exists():
            raise FileNotFoundError(
                "Cannot rebuild enhancement comparison from local 07_results and no existing comparison JSON is available."
            )
        print(
            "[enhancement-rebuild] comparison rebuild skipped; local 07_results do not contain both enhancement cases. "
            "Using existing 09_reports/enhancement_line_v2_vs_v3_comparison.json"
        )

    if can_rebuild_case_outputs:
        run_step(
            project_root,
            [
                sys.executable,
                str(delta_tool),
                "--project-root",
                str(project_root),
                "--baseline-case-id",
                baseline_case_id,
                "--enhancement-case-id",
                enhancement_case_id,
            ],
        )
    else:
        delta_json = project_root / "09_reports/enhancement_line_background_delta.json"
        if not delta_json.exists():
            raise FileNotFoundError(
                "Cannot rebuild enhancement background delta from local 07_results and no existing delta JSON is available."
            )
        print(
            "[enhancement-rebuild] background delta rebuild skipped; local 07_results do not contain both enhancement cases. "
            "Using existing 09_reports/enhancement_line_background_delta.json"
        )
    run_step(project_root, [sys.executable, str(tracker_tool)])
    run_step(project_root, [sys.executable, str(checklist_tool)])
    run_step(project_root, [sys.executable, str(flag_tool)])
    run_step(project_root, [sys.executable, str(watchlist_tool)])
    return archive_tool


def evaluate_outputs(project_root: Path) -> dict[str, object]:
    comparison = load_json(project_root / "09_reports/enhancement_line_v2_vs_v3_comparison.json")
    background_delta = load_json(project_root / "09_reports/enhancement_line_background_delta.json")
    tracker = load_json(project_root / "09_reports/enhancement_line_iteration_tracker.json")
    checklist = load_json(project_root / "09_reports/enhancement_line_diagnostic_checklist.json")
    flag_summary = load_json(project_root / "09_reports/enhancement_line_flag_impact_summary.json")
    watchlist = load_json(project_root / "09_reports/enhancement_line_background_watchlist.json")

    enhancement = comparison["enhancement_case"]
    margin = enhancement.get("active_margin", {})
    headline_metrics = tracker.get("headline_metrics", {})
    shortlist_behavior = tracker.get("shortlist_behavior", {})
    consistency_checks = checklist.get("consistency_checks", {})
    quality_gates = checklist.get("quality_gates", {})

    return {
        "best_background_compound_id": margin.get("best_background_compound_id"),
        "comparison_active_best_background_gap": margin.get("known_active_to_best_background_gap"),
        "background_delta_best_background_compound_id": background_delta.get("best_background_compound_id"),
        "background_delta_active_best_background_gap": background_delta.get("active_best_background_gap"),
        "tracker_active_best_background_gap": headline_metrics.get("enhancement_active_best_background_gap"),
        "comparison_shortlist_count": enhancement.get("shortlist_count"),
        "tracker_shortlist_count": shortlist_behavior.get("enhancement_shortlist_count"),
        "shortlist_ids": enhancement.get("shortlist_ids", []),
        "checklist_status": checklist.get("overall_status"),
        "consistency_checks": consistency_checks,
        "quality_gates": quality_gates,
        "strongest_flag_by_average_score_delta": flag_summary.get("strongest_flag_by_average_score_delta"),
        "watchlist_best_background_compound_id": watchlist.get("best_background_compound_id"),
        "watchlist_active_best_background_gap": watchlist.get("active_best_background_gap"),
    }


def print_summary(payload: dict[str, object]) -> None:
    print("[enhancement-rebuild] summary")
    print(f"  best_background_compound_id: {payload['best_background_compound_id']}")
    print(f"  active_best_background_gap (comparison): {payload['comparison_active_best_background_gap']}")
    print(
        f"  active_best_background_gap (background_delta): {payload['background_delta_active_best_background_gap']}"
    )
    print(f"  active_best_background_gap (tracker): {payload['tracker_active_best_background_gap']}")
    print(f"  active_best_background_gap (watchlist): {payload['watchlist_active_best_background_gap']}")
    print(f"  shortlist_count (comparison): {payload['comparison_shortlist_count']}")
    print(f"  shortlist_count (tracker): {payload['tracker_shortlist_count']}")
    print(f"  shortlist_ids: {payload['shortlist_ids']}")
    print(f"  strongest_flag_by_average_score_delta: {payload['strongest_flag_by_average_score_delta']}")
    print(f"  checklist_status: {payload['checklist_status']}")
    print(f"  consistency_checks: {payload['consistency_checks']}")
    print(f"  quality_gates: {payload['quality_gates']}")


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    if args.fetch_remote_root:
        run_step(
            project_root,
            [
                sys.executable,
                str(project_root / "01_tools" / "fetch_enhancement_reports_from_hpc.py"),
                "--project-root",
                str(project_root),
                "--remote-root",
                args.fetch_remote_root,
            ],
        )
    archive_tool = rebuild_reports(project_root, args.baseline_case_id, args.enhancement_case_id, args.skip_comparison)
    summary = evaluate_outputs(project_root)
    print_summary(summary)
    is_consistent = (
        summary["comparison_active_best_background_gap"] == summary["tracker_active_best_background_gap"]
        and summary["comparison_active_best_background_gap"] == summary["background_delta_active_best_background_gap"]
        and summary["comparison_active_best_background_gap"] == summary["watchlist_active_best_background_gap"]
        and summary["best_background_compound_id"] == summary["background_delta_best_background_compound_id"]
        and summary["best_background_compound_id"] == summary["watchlist_best_background_compound_id"]
        and summary["comparison_shortlist_count"] == summary["tracker_shortlist_count"]
        and all(bool(v) for v in summary["consistency_checks"].values())
        and all(bool(v) for v in summary["quality_gates"].values())
        and summary["checklist_status"] == "healthy"
    )
    if args.strict and not is_consistent:
        print("[enhancement-rebuild] consistency validation failed", file=sys.stderr)
        return 1
    if not args.skip_archive:
        run_step(project_root, [sys.executable, str(archive_tool), "--project-root", str(project_root), "--label", "auto"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
