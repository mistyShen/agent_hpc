#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a compact case-level summary for an enhancement-only case from fetched module outputs."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
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


def maybe_float(value: str) -> float | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def known_active_from_case_row(case_row: dict[str, str]) -> str | None:
    raw = case_row.get("known_active_definition", "").strip()
    if raw.startswith("compound_id="):
        return raw.split("=", 1)[1].strip()
    return None


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    results_root = Path(args.results_root).resolve()
    case_id = args.case_id

    cases = read_tsv(project_root / "04_metadata" / "benchmark_cases.tsv")
    truth = read_tsv(project_root / "04_metadata" / "benchmark_case_truth.tsv")
    docking = read_tsv(results_root / "07_results" / "modules" / "classical_docking" / "docking_results.tsv")
    reranked = read_tsv(results_root / "07_results" / "modules" / "ai_reranking" / "reranked_candidates.tsv")
    filtered = read_tsv(results_root / "07_results" / "modules" / "filtering" / "filtered_candidates.tsv")
    clustered = read_tsv(results_root / "07_results" / "modules" / "clustering_and_prioritization" / "clustered_priorities.tsv")

    case_row = next(row for row in cases if row["case_id"] == case_id)
    truth_rows = [row for row in truth if row["case_id"] == case_id]
    known_active = known_active_from_case_row(case_row)

    docking_rows = [row for row in docking if row["case_id"] == case_id]
    docking_by_compound = {row["compound_id"]: row for row in docking_rows}
    reranked_rows = [row for row in reranked if row["case_id"] == case_id]
    reranked_rows.sort(key=lambda row: int(row.get("rerank_rank", "999999")))
    filtered_rows = [row for row in filtered if row["case_id"] == case_id]
    keep_rows = [row for row in filtered_rows if row.get("filter_decision") == "keep"]
    shortlist_rows = [row for row in clustered if row["case_id"] == case_id]

    known_active_row = next((row for row in reranked_rows if row["compound_id"] == known_active), None)
    best_background_row = next(
        (row for row in reranked_rows if row["compound_id"] != known_active),
        None,
    )
    active_gap = None
    if known_active_row and best_background_row:
        known_active_score = maybe_float(known_active_row.get("rerank_score", ""))
        background_score = maybe_float(best_background_row.get("rerank_score", ""))
        if known_active_score is not None and background_score is not None:
            active_gap = round(background_score - known_active_score, 3)

    summary = {
        "case_id": case_id,
        "case_type": case_row.get("case_type"),
        "rerank_strategy": case_row.get("rerank_strategy"),
        "target_id": case_row.get("target_id"),
        "library_id": case_row.get("library_id"),
        "known_active_compound_id": known_active,
        "truth_row_count": len(truth_rows),
        "docking_candidate_count": len(docking_rows),
        "reranked_candidate_count": len(reranked_rows),
        "filter_keep_count": len(keep_rows),
        "shortlist_count": len(shortlist_rows),
        "shortlist_ids": [row["compound_id"] for row in shortlist_rows],
        "known_active_rank": int(known_active_row["rerank_rank"]) if known_active_row else None,
        "known_active_shortlisted": any(row["compound_id"] == known_active for row in shortlist_rows),
        "best_background_compound_id": best_background_row["compound_id"] if best_background_row else None,
        "active_best_background_gap": active_gap,
        "top_rerank": [
            {
                "compound_id": row["compound_id"],
                "rerank_rank": int(row["rerank_rank"]),
                "rerank_score": maybe_float(row.get("rerank_score", "")),
                "vina_affinity_kcal_mol": (
                    maybe_float(row.get("vina_affinity_kcal_mol", ""))
                    if maybe_float(row.get("vina_affinity_kcal_mol", "")) is not None
                    else maybe_float(docking_by_compound.get(row["compound_id"], {}).get("vina_affinity_kcal_mol", ""))
                ),
            }
            for row in reranked_rows[:5]
        ],
    }

    output_json = Path(args.output_json) if args.output_json else project_root / "09_reports" / f"enhancement_case_{case_id}_summary.json"
    output_md = Path(args.output_md) if args.output_md else project_root / "09_reports" / f"enhancement_case_{case_id}_summary.md"

    write_json(output_json, summary)

    lines = [
        "# Enhancement Case Summary",
        "",
        f"- Case id: `{summary['case_id']}`",
        f"- Target: `{summary['target_id']}`",
        f"- Library: `{summary['library_id']}`",
        f"- Rerank strategy: `{summary['rerank_strategy']}`",
        f"- Known active: `{summary['known_active_compound_id']}`",
        "",
        "## Core Metrics",
        "",
        f"- Docking candidate count: `{summary['docking_candidate_count']}`",
        f"- Filter keep count: `{summary['filter_keep_count']}`",
        f"- Shortlist count: `{summary['shortlist_count']}`",
        f"- Shortlist ids: `{', '.join(summary['shortlist_ids'])}`",
        f"- Known active rank: `{summary['known_active_rank']}`",
        f"- Known active shortlisted: `{summary['known_active_shortlisted']}`",
        f"- Best background: `{summary['best_background_compound_id']}`",
        f"- Active-best-background gap: `{summary['active_best_background_gap']}`",
        "",
        "## Top Rerank Preview",
        "",
    ]
    for row in summary["top_rerank"]:
        lines.append(
            f"- `{row['compound_id']}` rank `{row['rerank_rank']}` score `{row['rerank_score']}` vina `{row['vina_affinity_kcal_mol']}`"
        )
    lines.append("")
    write_text(output_md, "\n".join(lines))
    print(f"[enhancement-case-summary] wrote json: {output_json}")
    print(f"[enhancement-case-summary] wrote markdown: {output_md}")


if __name__ == "__main__":
    main()
