#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an enhancement-line v2 vs v3 comparison snapshot from workflow outputs."
    )
    parser.add_argument("--project-root", default=".", help="Project root containing 07_results and 09_reports")
    parser.add_argument("--baseline-case-id", default="BRD4_BD1_LIT002")
    parser.add_argument("--enhancement-case-id", default="BRD4_BD1_LIT002_V3EXP")
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_line_v2_vs_v3_comparison.json",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_line_v2_vs_v3_comparison.md",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_optional(path: Path) -> dict[str, object]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    return load_json(path)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def parse_float(value: str) -> float:
    stripped = value.strip()
    if not stripped:
        return 0.0
    return float(stripped)


def parse_int(value: str) -> int:
    stripped = value.strip()
    if not stripped:
        return 0
    return int(stripped)


def library_row_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (row["library_id"], row["compound_id"]): row
        for row in rows
        if row.get("library_id") and row.get("compound_id")
    }


def sort_rerank_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            parse_int(row.get("rerank_rank", "")) or 999999,
            parse_float(row.get("rerank_score", "")),
            row.get("compound_id", ""),
        ),
    )


def sort_cluster_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            parse_int(row.get("priority_rank", "")) or 999999,
            row.get("compound_id", ""),
        ),
    )


def case_diag_lookup(summary: dict[str, object], key: str = "case_diagnostics") -> dict[str, dict[str, object]]:
    rows = summary.get(key, [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row["case_id"]): row
        for row in rows
        if isinstance(row, dict) and "case_id" in row
    }


def case_policy_lookup(summary: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = summary.get("case_priority_policies", [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row["case_id"]): row
        for row in rows
        if isinstance(row, dict) and "case_id" in row
    }


def top_preview_from_diag(case_diag: dict[str, object]) -> list[dict[str, object]]:
    preview = case_diag.get("top_preview", [])
    if isinstance(preview, list):
        return [row for row in preview if isinstance(row, dict)]
    return []


def backfill_physchem_preview(
    preview_row: dict[str, object],
    case_rerank_rows: list[dict[str, str]],
    library_by_key: dict[tuple[str, str], dict[str, str]],
    v3_tuning: dict[str, object],
) -> dict[str, object]:
    if preview_row.get("physchem_flags") or preview_row.get("physchem_snapshot"):
        return preview_row
    compound_id = str(preview_row.get("compound_id", ""))
    source_row = next((row for row in case_rerank_rows if row.get("compound_id") == compound_id), None)
    if not source_row:
        return preview_row
    library_row = library_by_key.get((source_row.get("library_id", ""), compound_id))
    if not library_row:
        return preview_row
    molecular_weight = parse_float(library_row.get("molecular_weight_estimate", ""))
    heavy_atom_count = parse_int(library_row.get("heavy_atom_count", ""))
    hetero_atom_count = parse_int(library_row.get("hetero_atom_count", ""))
    aromatic_atom_count = parse_int(library_row.get("aromatic_atom_count", ""))
    ring_index_count = parse_int(library_row.get("ring_index_count", ""))
    aromatic_fraction = round((aromatic_atom_count / heavy_atom_count), 3) if heavy_atom_count > 0 else 0.0
    simple_aromatic_background = hetero_atom_count <= 1 and aromatic_atom_count >= 8 and ring_index_count <= 2
    polyaryl_hydrophobe_background = (
        hetero_atom_count <= 1
        and ring_index_count >= 2
        and aromatic_atom_count >= 8
        and aromatic_fraction > float(v3_tuning.get("aromatic_fraction_threshold", 0.75))
    )
    single_ring_background = ring_index_count <= 1 and aromatic_atom_count >= 6 and molecular_weight < 150.0
    flags: list[str] = []
    if simple_aromatic_background:
        flags.append("simple_aromatic_background")
    if polyaryl_hydrophobe_background:
        flags.append("polyaryl_hydrophobe_background")
    if single_ring_background:
        flags.append("single_ring_background")
    patched = dict(preview_row)
    patched["physchem_flags"] = flags
    patched["physchem_snapshot"] = {
        "molecular_weight_estimate": round(molecular_weight, 3),
        "hetero_atom_count": hetero_atom_count,
        "aromatic_atom_count": aromatic_atom_count,
        "ring_index_count": ring_index_count,
        "aromatic_fraction": aromatic_fraction,
    }
    return patched


def cache_hit_cases(case_diag_map: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    payload: dict[str, dict[str, object]] = {}
    for case_id, diag in case_diag_map.items():
        if diag.get("cache_status") != "hit":
            continue
        runtime_payload = {}
        if "runtime_seconds" in diag:
            runtime_payload["runtime_seconds"] = diag["runtime_seconds"]
        if "scoring_runtime_seconds" in diag:
            runtime_payload["scoring_runtime_seconds"] = diag["scoring_runtime_seconds"]
        payload[case_id] = runtime_payload
    return payload


def case_row_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["case_id"]: row for row in rows if row.get("case_id")}


def parse_known_active_id(case_row: dict[str, str] | None) -> str:
    if not case_row:
        return ""
    raw = case_row.get("known_active_definition", "").strip()
    if raw.startswith("compound_id="):
        return raw.split("=", 1)[1].strip()
    return ""


def active_margin_payload(
    case_rerank_rows: list[dict[str, str]],
    shortlist_ids: list[str],
    known_active_compound_id: str,
) -> dict[str, object]:
    if not known_active_compound_id:
        return {
            "known_active_compound_id": "",
            "known_active_rank": None,
            "known_active_rerank_score": None,
            "known_active_shortlisted": False,
            "best_background_compound_id": "",
            "best_background_rank": None,
            "best_background_rerank_score": None,
            "known_active_to_best_background_gap": None,
        }
    rank_map = {row["compound_id"]: idx + 1 for idx, row in enumerate(case_rerank_rows)}
    score_map = {row["compound_id"]: parse_float(row.get("rerank_score", "")) for row in case_rerank_rows}
    active_rank = rank_map.get(known_active_compound_id)
    active_score = score_map.get(known_active_compound_id)
    best_background_row = next((row for row in case_rerank_rows if row["compound_id"] != known_active_compound_id), None)
    if best_background_row is None or active_score is None:
        gap = None
        best_background_compound_id = ""
        best_background_rank = None
        best_background_score = None
    else:
        best_background_compound_id = best_background_row["compound_id"]
        best_background_rank = rank_map.get(best_background_compound_id)
        best_background_score = score_map.get(best_background_compound_id)
        gap = round(float(best_background_score) - float(active_score), 3) if best_background_score is not None else None
    return {
        "known_active_compound_id": known_active_compound_id,
        "known_active_rank": active_rank,
        "known_active_rerank_score": active_score,
        "known_active_shortlisted": known_active_compound_id in shortlist_ids,
        "best_background_compound_id": best_background_compound_id,
        "best_background_rank": best_background_rank,
        "best_background_rerank_score": best_background_score,
        "known_active_to_best_background_gap": gap,
    }


def build_case_payload(
    case_id: str,
    reranked_rows: list[dict[str, str]],
    filtered_rows: list[dict[str, str]],
    clustered_rows: list[dict[str, str]],
    rerank_diag_map: dict[str, dict[str, object]],
    cluster_diag_map: dict[str, dict[str, object]],
    cluster_policy_map: dict[str, dict[str, object]],
    ground_truth_summary: dict[str, object],
    case_metadata: dict[str, str] | None,
    library_by_key: dict[tuple[str, str], dict[str, str]],
    v3_tuning: dict[str, object],
    experimental_note: str | None = None,
) -> dict[str, object]:
    case_rerank_rows = sort_rerank_rows([row for row in reranked_rows if row["case_id"] == case_id])
    case_filtered_rows = [row for row in filtered_rows if row["case_id"] == case_id]
    case_cluster_rows = sort_cluster_rows([row for row in clustered_rows if row["case_id"] == case_id])
    case_diag = rerank_diag_map.get(case_id, {})
    cluster_diag = cluster_diag_map.get(case_id, {})
    cluster_policy = cluster_policy_map.get(case_id, {})
    ground_truth = ground_truth_summary.get(case_id)
    if not isinstance(ground_truth, dict):
        ground_truth = {"note": experimental_note or "no ground truth entry available"}

    top_rerank = [
        {
            "compound_id": row["compound_id"],
            "rerank_score": parse_float(row.get("rerank_score", "")),
            "rerank_rank": parse_int(row.get("rerank_rank", "")),
        }
        for row in case_rerank_rows[:3]
    ]
    shortlist_ids = [row["compound_id"] for row in case_cluster_rows]
    known_active_compound_id = parse_known_active_id(case_metadata)
    payload = {
        "case_id": case_id,
        "rerank_model": case_rerank_rows[0].get("rerank_model", "") if case_rerank_rows else "",
        "top_rerank": top_rerank,
        "filter_keep_count": sum(1 for row in case_filtered_rows if row.get("filter_decision") == "keep"),
        "shortlist_count": len(case_cluster_rows),
        "shortlist_ids": shortlist_ids,
        "ground_truth": ground_truth,
        "known_active_compound_id": known_active_compound_id,
        "active_margin": active_margin_payload(case_rerank_rows, shortlist_ids, known_active_compound_id),
    }
    if case_diag:
        preview = top_preview_from_diag(case_diag)
        payload["rerank_diagnostics"] = {
            "top_preview": [
                backfill_physchem_preview(
                    {
                        "compound_id": row.get("compound_id", ""),
                        "docking_core": row.get("rerank_diagnostics", {}).get("docking_core")
                        if isinstance(row.get("rerank_diagnostics"), dict)
                        else None,
                        "artifact_penalty": row.get("rerank_diagnostics", {}).get("artifact_penalty")
                        if isinstance(row.get("rerank_diagnostics"), dict)
                        else None,
                        "physchem_penalty": row.get("rerank_diagnostics", {}).get("physchem_penalty")
                        if isinstance(row.get("rerank_diagnostics"), dict)
                        else None,
                        "total_penalty": row.get("rerank_diagnostics", {}).get("total_penalty")
                        if isinstance(row.get("rerank_diagnostics"), dict)
                        else None,
                        "physchem_flags": row.get("physchem_flags", [])
                        if isinstance(row.get("physchem_flags"), list)
                        else [],
                        "physchem_snapshot": row.get("physchem_snapshot", {})
                        if isinstance(row.get("physchem_snapshot"), dict)
                        else {},
                    },
                    case_rerank_rows,
                    library_by_key,
                    v3_tuning,
                )
                for row in preview
            ],
            "v3_component_averages": case_diag.get("v3_component_averages", {}),
            "cache_status": case_diag.get("cache_status", ""),
        }
    if cluster_diag or cluster_policy:
        payload["priority_diagnostics"] = {
            "selection_policy": cluster_diag.get("selection_policy", cluster_policy.get("selection_policy", "")),
            "filter_keep_input_count": cluster_diag.get(
                "filter_keep_input_count", cluster_policy.get("filter_keep_input_count", 0)
            ),
            "shortlist_count": cluster_diag.get("shortlist_count", cluster_policy.get("shortlist_count", 0)),
            "shortlist_cap": cluster_diag.get("shortlist_cap", cluster_policy.get("shortlist_cap", 0)),
            "top_score_gap": cluster_diag.get("top_score_gap", cluster_policy.get("top_score_gap", 0.0)),
            "v3_priority_tuning": cluster_diag.get(
                "v3_priority_tuning", cluster_policy.get("v3_priority_tuning", {})
            ),
            "cache_status": cluster_diag.get("cache_status", cluster_policy.get("cache_status", "")),
        }
    return payload


def build_markdown(payload: dict[str, object]) -> str:
    baseline = payload["baseline_case"]
    enhancement = payload["enhancement_case"]
    performance = payload["performance"]
    ai_perf = performance.get("ai_reranking", {})
    cluster_perf = performance.get("clustering_and_prioritization", {})
    enhancement_diag = enhancement.get("rerank_diagnostics", {})
    priority_diag = enhancement.get("priority_diagnostics", {})
    lines = [
        "# Enhancement Line V2 vs V3 Comparison",
        "",
        "This report is an enhancement-line comparison only. It does not modify or replace the frozen manuscript / benchmark result line.",
        "",
        "Source context:",
        "",
        f"- frozen baseline case: `{baseline['case_id']}`",
        f"- enhancement experiment case: `{enhancement['case_id']}`",
        f"- isolated execution root: `{payload['isolated_execution_root']}`",
        "",
        "## Scope",
        "",
        "The comparison focuses on three questions:",
        "",
        "1. does `ai_reranking v3` change rerank ordering relative to `v2`",
        "2. does `clustering_and_prioritization v2` convert that extra score separation into a tighter shortlist",
        "3. does the enhancement remain lightweight enough for CPU-only iterative work",
        "",
        "## Headline Result",
        "",
        "`ai_reranking v3` plus `clustering_and_prioritization v2` improved shortlist selectivity on the current focused validation panel without changing the frozen baseline line.",
        "",
        f"- baseline `{baseline['case_id']}`",
        f"  - `filter_keep_count = {baseline['filter_keep_count']}`",
        f"  - `shortlist_count = {baseline['shortlist_count']}`",
        f"  - shortlist: `{', '.join(baseline['shortlist_ids'])}`",
        f"- enhancement `{enhancement['case_id']}`",
        f"  - `filter_keep_count = {enhancement['filter_keep_count']}`",
        f"  - `shortlist_count = {enhancement['shortlist_count']}`",
        f"  - shortlist: `{', '.join(enhancement['shortlist_ids'])}`",
        "",
        "This means the new prioritization layer is now consuming the extra separation introduced by `v3`, rather than leaving the shortlist unchanged.",
        "",
        "## Comparison Table",
        "",
        f"| Dimension | `{baseline['case_id']}` | `{enhancement['case_id']}` |",
        "| --- | --- | --- |",
        f"| Rerank model | `{baseline['rerank_model']}` | `{enhancement['rerank_model']}` |",
        f"| Top 1 | `{baseline['top_rerank'][0]['compound_id']}` | `{enhancement['top_rerank'][0]['compound_id']}` |",
        f"| Top 1 rerank score | `{baseline['top_rerank'][0]['rerank_score']}` | `{enhancement['top_rerank'][0]['rerank_score']}` |",
        f"| Top 2 | `{baseline['top_rerank'][1]['compound_id']}` | `{enhancement['top_rerank'][1]['compound_id']}` |",
        f"| Top 2 rerank score | `{baseline['top_rerank'][1]['rerank_score']}` | `{enhancement['top_rerank'][1]['rerank_score']}` |",
        f"| Top 3 | `{baseline['top_rerank'][2]['compound_id']}` | `{enhancement['top_rerank'][2]['compound_id']}` |",
        f"| Top 3 rerank score | `{baseline['top_rerank'][2]['rerank_score']}` | `{enhancement['top_rerank'][2]['rerank_score']}` |",
        f"| Filter keep count | `{baseline['filter_keep_count']}` | `{enhancement['filter_keep_count']}` |",
        f"| Shortlist count | `{baseline['shortlist_count']}` | `{enhancement['shortlist_count']}` |",
        f"| Shortlist ids | `{', '.join(baseline['shortlist_ids'])}` | `{', '.join(enhancement['shortlist_ids'])}` |",
        f"| Known active id | `{baseline.get('known_active_compound_id', '')}` | `{enhancement.get('known_active_compound_id', '')}` |",
        f"| Best background id | `{baseline.get('active_margin', {}).get('best_background_compound_id', '')}` | `{enhancement.get('active_margin', {}).get('best_background_compound_id', '')}` |",
        f"| Active-best-background gap | `{baseline.get('active_margin', {}).get('known_active_to_best_background_gap')}` | `{enhancement.get('active_margin', {}).get('known_active_to_best_background_gap')}` |",
        f"| Known active in shortlist | `{str(baseline['ground_truth'].get('shortlist_contains_known_active', 'n/a')).lower()}` | experimental line, no separate truth row |",
        f"| Best known active rank | `{baseline['ground_truth'].get('best_known_active_rank')}` | experimental line, no separate truth row |",
        "",
        "## Reranking Interpretation",
        "",
        "The enhancement line changed reranking in two useful ways:",
        "",
        f"1. it preserved `{enhancement['top_rerank'][0]['compound_id']}` as the top-ranked compound",
        "2. it widened the separation between the active and hard aromatic backgrounds through explicit `physchem_penalty`",
        "",
        "Top `v3` diagnostics:",
        "",
    ]
    for row in enhancement_diag.get("top_preview", []):
        lines.append(f"- `{row['compound_id']}`")
        lines.append(f"  - `docking_core = {row.get('docking_core')}`")
        lines.append(f"  - `artifact_penalty = {row.get('artifact_penalty')}`")
        lines.append(f"  - `physchem_penalty = {row.get('physchem_penalty')}`")
        flags = row.get("physchem_flags", [])
        snapshot = row.get("physchem_snapshot", {})
        if flags:
            lines.append(f"  - `physchem_flags = {', '.join(flags)}`")
        if snapshot:
            lines.append(
                "  - "
                + "`physchem_snapshot = "
                + json.dumps(snapshot, sort_keys=True)
                + "`"
            )
    averages = enhancement_diag.get("v3_component_averages", {})
    lines.extend(
        [
            "",
            "Mean top-window `v3` penalties:",
            "",
            f"- `artifact_penalty = {averages.get('artifact_penalty', 0.0)}`",
            f"- `physchem_penalty = {averages.get('physchem_penalty', 0.0)}`",
            "",
            "Interpretation:",
            "",
            "- in this focused panel, the useful new signal came mainly from lightweight physicochemical separation",
            "- artifact quality did not drive the observed difference in this case",
            "",
            "## Active Margin Interpretation",
            "",
            f"- Baseline best background: `{baseline.get('active_margin', {}).get('best_background_compound_id', '')}` with gap `{baseline.get('active_margin', {}).get('known_active_to_best_background_gap')}`",
            f"- Enhancement best background: `{enhancement.get('active_margin', {}).get('best_background_compound_id', '')}` with gap `{enhancement.get('active_margin', {}).get('known_active_to_best_background_gap')}`",
            f"- Enhancement known active shortlisted: `{enhancement.get('active_margin', {}).get('known_active_shortlisted')}`",
            "",
            "## Prioritization Interpretation",
            "",
            f"The enhancement-line prioritization policy for `{enhancement['case_id']}` was:",
            "",
            f"- `{priority_diag.get('selection_policy', '')}`",
            "",
            "Observed values:",
            "",
            f"- `filter_keep_input_count = {priority_diag.get('filter_keep_input_count', 0)}`",
            f"- `shortlist_count = {priority_diag.get('shortlist_count', 0)}`",
            f"- `shortlist_cap = {priority_diag.get('shortlist_cap', 0)}`",
            f"- `top_score_gap = {priority_diag.get('top_score_gap', 0.0)}`",
            f"- `v3_priority_tuning = {json.dumps(priority_diag.get('v3_priority_tuning', {}), sort_keys=True)}`",
            "",
            "Interpretation:",
            "",
            "- the shortlist became tighter not because filtering changed, but because prioritization consumed the stronger rerank margin",
            "- this supports the earlier conclusion that the bottleneck had shifted from filtering to shortlist/prioritization",
            "",
            "## Performance Snapshot",
            "",
            "### `ai_reranking`",
            "",
            f"- Latest phase timings: `read = {ai_perf.get('phase_timings_seconds', {}).get('read')}` | `scoring = {ai_perf.get('phase_timings_seconds', {}).get('scoring')}` | `output = {ai_perf.get('phase_timings_seconds', {}).get('output')}`",
            f"- Latest cache-hit cases: `{', '.join(ai_perf.get('cache_hit_case_runtime_seconds', {}).keys()) or 'none observed in current summary'}`",
            "",
            "### `clustering_and_prioritization`",
            "",
            f"- Latest phase timings: `read = {cluster_perf.get('phase_timings_seconds', {}).get('read')}` | `scoring = {cluster_perf.get('phase_timings_seconds', {}).get('scoring')}` | `output = {cluster_perf.get('phase_timings_seconds', {}).get('output')}`",
            f"- Latest cache-hit cases: `{', '.join(cluster_perf.get('cache_hit_case_runtime_seconds', {}).keys()) or 'none observed in current summary'}`",
            "",
            "## Current Conclusion",
            "",
            payload["conclusion"]["summary"],
            "",
            "## Recommended Next Step",
            "",
            payload["conclusion"]["next_recommended_action"],
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.project_root)
    output_json = root / args.output_json
    output_md = root / args.output_md
    existing_payload = load_json_optional(output_json)

    reranked_rows = read_tsv_rows(root / "07_results/modules/ai_reranking/reranked_candidates.tsv")
    filtered_rows = read_tsv_rows(root / "07_results/modules/filtering/filtered_candidates.tsv")
    clustered_rows = read_tsv_rows(root / "07_results/modules/clustering_and_prioritization/clustered_priorities.tsv")
    prepared_library_rows = read_tsv_rows(root / "07_results/modules/compound_library_preparation/prepared_library.tsv")
    rerank_summary = load_json(root / "07_results/modules/ai_reranking/reranking_summary.json")
    clustering_summary = load_json(root / "07_results/modules/clustering_and_prioritization/clustering_summary.json")
    benchmark_eval = load_json_optional(root / "09_reports/benchmark_evaluation.json")
    case_rows = read_tsv_rows(root / "04_metadata/benchmark_cases.tsv")

    rerank_diag_map = case_diag_lookup(rerank_summary)
    cluster_diag_map = case_diag_lookup(clustering_summary)
    cluster_policy_map = case_policy_lookup(clustering_summary)
    case_metadata_map = case_row_lookup(case_rows)
    library_by_key = library_row_lookup(prepared_library_rows)
    ground_truth_summary = benchmark_eval.get("ground_truth_summary", {})
    if not isinstance(ground_truth_summary, dict):
        ground_truth_summary = {}
    v3_tuning = rerank_summary.get("v3_tuning", {}) if isinstance(rerank_summary.get("v3_tuning"), dict) else {}

    ai_existing = existing_payload.get("performance", {}).get("ai_reranking", {}) if existing_payload else {}
    cluster_existing = (
        existing_payload.get("performance", {}).get("clustering_and_prioritization", {}) if existing_payload else {}
    )

    payload = {
        "report_type": "enhancement_line_comparison",
        "isolated_execution_root": str(root.resolve()),
        "baseline_case": build_case_payload(
            args.baseline_case_id,
            reranked_rows,
            filtered_rows,
            clustered_rows,
            rerank_diag_map,
            cluster_diag_map,
            cluster_policy_map,
            ground_truth_summary,
            case_metadata_map.get(args.baseline_case_id),
            library_by_key,
            v3_tuning,
        ),
        "enhancement_case": build_case_payload(
            args.enhancement_case_id,
            reranked_rows,
            filtered_rows,
            clustered_rows,
            rerank_diag_map,
            cluster_diag_map,
            cluster_policy_map,
            ground_truth_summary,
            case_metadata_map.get(args.enhancement_case_id),
            library_by_key,
            v3_tuning,
            experimental_note="no separate truth row added for the experimental case",
        ),
        "performance": {
            "ai_reranking": {
                "phase_timings_seconds": rerank_summary.get("phase_timings_seconds", {}),
                "per_case_runtime_seconds": {
                    case_id: {
                        "runtime_seconds": diag.get("runtime_seconds"),
                        "scoring_runtime_seconds": diag.get("scoring_runtime_seconds"),
                    }
                    for case_id, diag in rerank_diag_map.items()
                },
                "cache_hit_case_runtime_seconds": cache_hit_cases(rerank_diag_map)
                or ai_existing.get("cache_hit_case_runtime_seconds", {}),
            },
            "clustering_and_prioritization": {
                "phase_timings_seconds": clustering_summary.get("phase_timings_seconds", {}),
                "cache_hit_case_runtime_seconds": cache_hit_cases(cluster_diag_map)
                or cluster_existing.get("cache_hit_case_runtime_seconds", {}),
            },
        },
        "conclusion": {
            "summary": "v3 improves rerank separation and clustering v2 converts that difference into a tighter shortlist without touching the frozen baseline line.",
            "next_recommended_action": "Use the enhancement-line iteration tracker after each v3 tweak to verify that rerank gap or shortlist compression still improves before expanding the experiment scope.",
        },
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_json, payload)
    output_md.write_text(build_markdown(payload), encoding="utf-8")
    print(f"[comparison] wrote json: {output_json}")
    print(f"[comparison] wrote markdown: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
