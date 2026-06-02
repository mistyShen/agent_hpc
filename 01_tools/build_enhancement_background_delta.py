#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a per-compound delta table for the enhancement line baseline vs v3 experiment."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--baseline-case-id", default="BRD4_BD1_LIT002")
    parser.add_argument("--enhancement-case-id", default="BRD4_BD1_LIT002_V3EXP")
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_line_background_delta.json",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_line_background_delta.md",
    )
    return parser.parse_args()


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return float(stripped)


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return int(stripped)


def case_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["case_id"]: row for row in rows if row.get("case_id")}


def parse_known_active_id(case_row: dict[str, str] | None) -> str:
    if not case_row:
        return ""
    raw = case_row.get("known_active_definition", "").strip()
    if raw.startswith("compound_id="):
        return raw.split("=", 1)[1].strip()
    return ""


def library_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (row["library_id"], row["compound_id"]): row
        for row in rows
        if row.get("library_id") and row.get("compound_id")
    }


def shortlist_lookup(rows: list[dict[str, str]], case_id: str) -> set[str]:
    return {row["compound_id"] for row in rows if row.get("case_id") == case_id}


def rerank_lookup(rows: list[dict[str, str]], case_id: str) -> dict[str, dict[str, str]]:
    return {
        row["compound_id"]: row
        for row in rows
        if row.get("case_id") == case_id and row.get("compound_id")
    }


def derive_physchem_flags(library_row: dict[str, str] | None, v3_tuning: dict[str, object]) -> tuple[list[str], dict[str, object]]:
    if not library_row:
        return [], {}
    molecular_weight = parse_float(library_row.get("molecular_weight_estimate")) or 0.0
    heavy_atom_count = parse_int(library_row.get("heavy_atom_count")) or 0
    hetero_atom_count = parse_int(library_row.get("hetero_atom_count")) or 0
    aromatic_atom_count = parse_int(library_row.get("aromatic_atom_count")) or 0
    ring_index_count = parse_int(library_row.get("ring_index_count")) or 0
    aromatic_fraction = round((aromatic_atom_count / heavy_atom_count), 3) if heavy_atom_count > 0 else 0.0
    aromatic_fraction_threshold = float(v3_tuning.get("aromatic_fraction_threshold", 0.75))
    flags: list[str] = []
    if hetero_atom_count <= 1 and aromatic_atom_count >= 8 and ring_index_count <= 2:
        flags.append("simple_aromatic_background")
    if (
        hetero_atom_count <= 1
        and ring_index_count >= 2
        and aromatic_atom_count >= 8
        and aromatic_fraction > aromatic_fraction_threshold
    ):
        flags.append("polyaryl_hydrophobe_background")
    if ring_index_count <= 1 and aromatic_atom_count >= 6 and molecular_weight < 150.0:
        flags.append("single_ring_background")
    snapshot = {
        "molecular_weight_estimate": round(molecular_weight, 3),
        "heavy_atom_count": heavy_atom_count,
        "hetero_atom_count": hetero_atom_count,
        "aromatic_atom_count": aromatic_atom_count,
        "ring_index_count": ring_index_count,
        "aromatic_fraction": aromatic_fraction,
    }
    return flags, snapshot


def build_markdown(payload: dict[str, object]) -> str:
    rows = payload["rows"]
    lines = [
        "# Enhancement Line Background Delta",
        "",
        f"- Generated at: `{payload['generated_at_utc']}`",
        f"- Baseline case: `{payload['baseline_case_id']}`",
        f"- Enhancement case: `{payload['enhancement_case_id']}`",
        f"- Known active: `{payload['known_active_compound_id']}`",
        "",
        "## Delta Table",
        "",
        "| Compound | Baseline rank | Enhancement rank | Rank delta | Baseline score | Enhancement score | Score delta | Baseline shortlist | Enhancement shortlist | Flags |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['compound_id']}` | `{row['baseline_rank']}` | `{row['enhancement_rank']}` | `{row['rank_delta']}` | "
            f"`{row['baseline_score']}` | `{row['enhancement_score']}` | `{row['score_delta']}` | "
            f"`{row['baseline_shortlisted']}` | `{row['enhancement_shortlisted']}` | "
            f"`{', '.join(row['physchem_flags']) or 'none'}` |"
        )
    lines.extend(
        [
            "",
            "## Headline",
            "",
            f"- Best background after enhancement: `{payload['best_background_compound_id']}`",
            f"- Active-best-background gap after enhancement: `{payload['active_best_background_gap']}`",
            f"- Hard-background rows with flags: `{payload['flagged_background_count']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.project_root)
    reranked_rows = read_tsv_rows(root / "07_results/modules/ai_reranking/reranked_candidates.tsv")
    clustered_rows = read_tsv_rows(root / "07_results/modules/clustering_and_prioritization/clustered_priorities.tsv")
    prepared_library_rows = read_tsv_rows(root / "07_results/modules/compound_library_preparation/prepared_library.tsv")
    case_rows = read_tsv_rows(root / "04_metadata/benchmark_cases.tsv")
    rerank_summary = load_json(root / "07_results/modules/ai_reranking/reranking_summary.json")

    case_map = case_lookup(case_rows)
    library_by_key = library_lookup(prepared_library_rows)
    v3_tuning = rerank_summary.get("v3_tuning", {}) if isinstance(rerank_summary.get("v3_tuning"), dict) else {}

    baseline_case = case_map[args.baseline_case_id]
    enhancement_case = case_map[args.enhancement_case_id]
    known_active_compound_id = parse_known_active_id(enhancement_case) or parse_known_active_id(baseline_case)

    baseline_rerank = rerank_lookup(reranked_rows, args.baseline_case_id)
    enhancement_rerank = rerank_lookup(reranked_rows, args.enhancement_case_id)
    baseline_shortlist = shortlist_lookup(clustered_rows, args.baseline_case_id)
    enhancement_shortlist = shortlist_lookup(clustered_rows, args.enhancement_case_id)

    all_compounds = sorted(set(baseline_rerank) | set(enhancement_rerank))
    rows: list[dict[str, object]] = []
    for compound_id in all_compounds:
        base = baseline_rerank.get(compound_id, {})
        enh = enhancement_rerank.get(compound_id, {})
        library_id = enh.get("library_id") or base.get("library_id") or enhancement_case.get("library_id", "")
        library_row = library_by_key.get((library_id, compound_id))
        flags, snapshot = derive_physchem_flags(library_row, v3_tuning)
        baseline_rank = parse_int(base.get("rerank_rank"))
        enhancement_rank = parse_int(enh.get("rerank_rank"))
        baseline_score = parse_float(base.get("rerank_score"))
        enhancement_score = parse_float(enh.get("rerank_score"))
        rows.append(
            {
                "compound_id": compound_id,
                "is_known_active": compound_id == known_active_compound_id,
                "baseline_rank": baseline_rank,
                "enhancement_rank": enhancement_rank,
                "rank_delta": (
                    baseline_rank - enhancement_rank
                    if baseline_rank is not None and enhancement_rank is not None
                    else None
                ),
                "baseline_score": baseline_score,
                "enhancement_score": enhancement_score,
                "score_delta": (
                    round((enhancement_score - baseline_score), 3)
                    if baseline_score is not None and enhancement_score is not None
                    else None
                ),
                "baseline_shortlisted": compound_id in baseline_shortlist,
                "enhancement_shortlisted": compound_id in enhancement_shortlist,
                "physchem_flags": flags,
                "physchem_snapshot": snapshot,
            }
        )

    rows.sort(
        key=lambda row: (
            0 if row["is_known_active"] else 1,
            row["enhancement_rank"] if row["enhancement_rank"] is not None else 999999,
            row["compound_id"],
        )
    )

    best_background = next((row for row in rows if not row["is_known_active"]), None)
    active_row = next((row for row in rows if row["is_known_active"]), None)
    active_best_background_gap = None
    if best_background and active_row:
        if best_background["enhancement_score"] is not None and active_row["enhancement_score"] is not None:
            active_best_background_gap = round(
                float(best_background["enhancement_score"]) - float(active_row["enhancement_score"]), 3
            )

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_case_id": args.baseline_case_id,
        "enhancement_case_id": args.enhancement_case_id,
        "known_active_compound_id": known_active_compound_id,
        "best_background_compound_id": best_background["compound_id"] if best_background else "",
        "active_best_background_gap": active_best_background_gap,
        "flagged_background_count": sum(1 for row in rows if row["physchem_flags"] and not row["is_known_active"]),
        "rows": rows,
    }

    output_json = root / args.output_json
    output_md = root / args.output_md
    output_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_json, payload)
    output_md.write_text(build_markdown(payload), encoding="utf-8")
    print(f"[background-delta] wrote json: {output_json}")
    print(f"[background-delta] wrote markdown: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
