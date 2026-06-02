#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_FILES = [
    "04_metadata/benchmark_cases.tsv",
    "04_metadata/compound_libraries.tsv",
    "07_results/modules/classical_docking/docking_results.tsv",
    "07_results/modules/compound_library_preparation/prepared_library.tsv",
    "07_results/modules/ai_reranking/reranked_candidates.tsv",
    "07_results/modules/filtering/filtered_candidates.tsv",
    "07_results/modules/clustering_and_prioritization/clustered_priorities.tsv",
]


@dataclass
class LoadedModules:
    ai_reranking: Any
    filtering: Any
    clustering: Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local enhancement-line compatibility check on a frozen/root case without overwriting remote outputs."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--remote-root",
        default="/shared/shen/cpu_ai_drug_design",
        help="Remote root containing the reference frozen/root case outputs",
    )
    parser.add_argument("--case-id", default="BRD4_BD1_LIT001")
    parser.add_argument(
        "--cache-dir",
        default="11_tmp/enhancement_cross_case_check",
        help="Local cache root for fetched remote source files and localized artifacts",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional output JSON path; defaults to 09_reports/enhancement_cross_case_check_<case>.json",
    )
    parser.add_argument(
        "--output-md",
        default="",
        help="Optional output markdown path; defaults to 09_reports/enhancement_cross_case_check_<case>.md",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Reuse cached inputs instead of fetching remote files again",
    )
    return parser.parse_args()


def load_module(module_path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_modules(project_root: Path) -> LoadedModules:
    modules_root = project_root / "06_scripts" / "modules"
    return LoadedModules(
        ai_reranking=load_module(modules_root / "ai_reranking.py", "cross_case_ai_reranking"),
        filtering=load_module(modules_root / "filtering.py", "cross_case_filtering"),
        clustering=load_module(modules_root / "clustering_and_prioritization.py", "cross_case_clustering"),
    )


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def hpc_get(remote_path: str, local_path: Path, cwd: Path) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["hpc-get", remote_path, str(local_path)], cwd=cwd, check=True)


def normalize_remote_path(remote_root: str, path_value: str) -> str:
    stripped = path_value.strip()
    if stripped.startswith("/"):
        return stripped
    return f"{remote_root.rstrip('/')}/{stripped.lstrip('./')}"


def fetch_source_files(project_root: Path, remote_root: str, cache_dir: Path) -> None:
    for rel_path in SOURCE_FILES:
        hpc_get(f"{remote_root.rstrip('/')}/{rel_path}", cache_dir / rel_path, project_root)


def case_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["case_id"]: row for row in rows}


def library_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row["library_id"], row["compound_id"]): row for row in rows}


def parse_known_active_id(case_row: dict[str, str]) -> str:
    raw = case_row.get("known_active_definition", "").strip()
    if raw.startswith("compound_id="):
        return raw.split("=", 1)[1].strip()
    return ""


def localize_case_artifacts(
    project_root: Path,
    remote_root: str,
    cache_dir: Path,
    case_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    localized_rows: list[dict[str, str]] = []
    for row in case_rows:
        localized = dict(row)
        for key in ("ligand_pdbqt_path", "pose_pdbqt_path"):
            raw_path = row.get(key, "").strip()
            if not raw_path:
                continue
            suffix = "ligand" if key == "ligand_pdbqt_path" else "pose"
            local_path = (
                cache_dir
                / "artifacts"
                / row["case_id"]
                / f"{row['compound_id']}.{suffix}.pdbqt"
            )
            hpc_get(normalize_remote_path(remote_root, raw_path), local_path, project_root)
            localized[key] = str(local_path)
        localized_rows.append(localized)
    return localized_rows


def build_reference_metrics(
    case_id: str,
    rerank_rows: list[dict[str, str]],
    filtered_rows: list[dict[str, str]],
    clustered_rows: list[dict[str, str]],
    known_active_compound_id: str,
) -> dict[str, object]:
    case_rerank = [row for row in rerank_rows if row["case_id"] == case_id]
    case_rerank.sort(key=lambda row: int(row["rerank_rank"]))
    keep_rows = [row for row in filtered_rows if row["case_id"] == case_id and row["filter_decision"] == "keep"]
    shortlist_rows = [row for row in clustered_rows if row["case_id"] == case_id]
    known_active = next((row for row in case_rerank if row["compound_id"] == known_active_compound_id), None)
    best_background = next((row for row in case_rerank if row["compound_id"] != known_active_compound_id), None)
    active_gap = None
    if known_active and best_background:
        active_gap = round(float(best_background["rerank_score"]) - float(known_active["rerank_score"]), 3)
    return {
        "known_active_compound_id": known_active_compound_id,
        "known_active_rank": int(known_active["rerank_rank"]) if known_active else None,
        "known_active_rerank_score": float(known_active["rerank_score"]) if known_active else None,
        "known_active_shortlisted": any(row["compound_id"] == known_active_compound_id for row in shortlist_rows),
        "best_background_compound_id": best_background["compound_id"] if best_background else None,
        "best_background_rank": int(best_background["rerank_rank"]) if best_background else None,
        "best_background_rerank_score": float(best_background["rerank_score"]) if best_background else None,
        "active_best_background_gap": active_gap,
        "filter_keep_count": len(keep_rows),
        "shortlist_count": len(shortlist_rows),
        "shortlist_ids": [row["compound_id"] for row in shortlist_rows],
    }


def score_case_rows(
    modules: LoadedModules,
    case_row: dict[str, str],
    docking_rows: list[dict[str, str]],
    library_by_key: dict[tuple[str, str], dict[str, str]],
    prepared_library_rows: list[dict[str, str]],
    library_manifest_by_id: dict[str, dict[str, str]],
    gating_config: dict[str, object],
    tuning: dict[str, float],
) -> list[dict[str, object]]:
    scored_rows: list[dict[str, object]] = []
    case_library_type = library_manifest_by_id.get(case_row["library_id"], {}).get("library_type", "")
    case_library_rows = [row for row in prepared_library_rows if row["library_id"] == case_row["library_id"]]
    case_panel_gating = modules.ai_reranking.build_case_panel_gating(
        case_row,
        case_library_rows,
        case_library_type,
        gating_config,
    )
    for row in docking_rows:
        library_row = library_by_key.get((row["library_id"], row["compound_id"]))
        score_payload = modules.ai_reranking.score_row_v3(
            row,
            case_row,
            library_row,
            tuning,
            case_panel_gating=case_panel_gating,
        )
        scored_rows.append({**row, **score_payload})
    scored_rows.sort(key=lambda row: float(row["rerank_score"]))
    for rank, row in enumerate(scored_rows, start=1):
        row["rerank_rank"] = rank
    return scored_rows


def evaluate_filtering(
    modules: LoadedModules,
    case_row: dict[str, str],
    scored_rows: list[dict[str, object]],
    library_by_key: dict[tuple[str, str], dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    case_best_vina_affinity = None
    if modules.filtering.use_literature_filter_v2(case_row):
        case_vina_values = []
        for row in scored_rows:
            vina_affinity = modules.filtering.parse_float(str(row.get("vina_affinity_kcal_mol", "")).strip())
            if vina_affinity is not None:
                case_vina_values.append(vina_affinity)
        case_best_vina_affinity = min(case_vina_values) if case_vina_values else None
    filtered_rows: list[dict[str, object]] = []
    kept_records: list[dict[str, object]] = []
    for row in scored_rows:
        library_row = library_by_key.get((row["library_id"], row["compound_id"]))
        rerank_row = {
            "rerank_score": str(row["rerank_score"]),
            "rerank_rank": str(row["rerank_rank"]),
        }
        decision, reason = modules.filtering.evaluate_candidate(
            case_row,
            row,
            rerank_row,
            library_row,
            case_best_vina_affinity=case_best_vina_affinity,
        )
        filtered_rows.append(
            {
                "compound_id": row["compound_id"],
                "filter_decision": decision,
                "filter_reason": reason,
            }
        )
        if decision == "keep":
            kept_records.append({**row, "filter_reason": reason})
    return filtered_rows, kept_records


def evaluate_shortlist(
    modules: LoadedModules,
    case_row: dict[str, str],
    kept_records: list[dict[str, object]],
    config_payload: dict[str, object],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    v3_priority_tuning = modules.clustering.load_v3_priority_tuning(config_payload)
    case_records = [
        {
            **row,
            "rerank_bonus": str(row.get("rerank_bonus", "0")),
            "rerank_score": str(row["rerank_score"]),
            "rerank_rank": str(row["rerank_rank"]),
            "vina_affinity_kcal_mol": str(row.get("vina_affinity_kcal_mol", "")),
            "docking_score": str(row["docking_score"]),
            "rerank_model": row.get("rerank_model", ""),
        }
        for row in kept_records
    ]
    v3_priority_policy = modules.clustering.use_v3_priority_policy(
        {**case_row, "rerank_strategy": "ai_rerank_v3"},
        case_records,
    )
    if v3_priority_policy:
        case_records.sort(key=modules.clustering.rerank_key_v3_aware)
        shortlist_cap = modules.clustering.shortlist_cap_v3(case_records, v3_priority_tuning)
        selected = case_records[:shortlist_cap]
        selection_policy = "filter_keep_then_v3_rerank_margin_then_vina_v2"
    else:
        case_records.sort(key=modules.clustering.rerank_key)
        shortlist_cap = len(case_records)
        selected = case_records
        selection_policy = "filter_keep_then_rerank_score_then_vina_affinity_v1"
    return selected, {
        "selection_policy": selection_policy,
        "filter_keep_input_count": len(case_records),
        "shortlist_count": len(selected),
        "shortlist_cap": shortlist_cap,
        "top_score_gap": modules.clustering.top_score_gap(case_records),
        "v3_priority_policy": v3_priority_policy,
        "v3_priority_tuning": v3_priority_tuning if v3_priority_policy else {},
    }


def build_simulated_metrics(
    modules: LoadedModules,
    case_row: dict[str, str],
    scoring_rows: list[dict[str, object]],
    filtered_rows: list[dict[str, object]],
    shortlist_rows: list[dict[str, object]],
    shortlist_diag: dict[str, object],
    known_active_compound_id: str,
) -> dict[str, object]:
    known_active = next((row for row in scoring_rows if row["compound_id"] == known_active_compound_id), None)
    best_background = next((row for row in scoring_rows if row["compound_id"] != known_active_compound_id), None)
    active_gap = None
    if known_active and best_background:
        active_gap = round(float(best_background["rerank_score"]) - float(known_active["rerank_score"]), 3)
    return {
        "known_active_compound_id": known_active_compound_id,
        "known_active_rank": known_active["rerank_rank"] if known_active else None,
        "known_active_rerank_score": known_active["rerank_score"] if known_active else None,
        "known_active_shortlisted": any(row["compound_id"] == known_active_compound_id for row in shortlist_rows),
        "best_background_compound_id": best_background["compound_id"] if best_background else None,
        "best_background_rank": best_background["rerank_rank"] if best_background else None,
        "best_background_rerank_score": best_background["rerank_score"] if best_background else None,
        "active_best_background_gap": active_gap,
        "filter_keep_count": sum(1 for row in filtered_rows if row["filter_decision"] == "keep"),
        "shortlist_count": len(shortlist_rows),
        "shortlist_ids": [row["compound_id"] for row in shortlist_rows],
        "top_rerank": [
            {
                "compound_id": row["compound_id"],
                "rerank_rank": row["rerank_rank"],
                "rerank_score": row["rerank_score"],
                "rerank_bonus": row["rerank_bonus"],
                "physchem_flags": modules.ai_reranking.summarize_v3_preview_row(row, int(row["rerank_rank"]))["physchem_flags"],
            }
            for row in scoring_rows[:3]
        ],
        "shortlist_diagnostics": shortlist_diag,
    }


def build_payload(
    case_id: str,
    remote_root: str,
    current_tuning: dict[str, float],
    reference_metrics: dict[str, object],
    simulated_metrics: dict[str, object],
) -> dict[str, object]:
    compatibility = {
        "known_active_rank_preserved": simulated_metrics["known_active_rank"] == reference_metrics["known_active_rank"],
        "known_active_shortlisted_preserved": simulated_metrics["known_active_shortlisted"] == reference_metrics["known_active_shortlisted"],
        "shortlist_count_not_expanded": simulated_metrics["shortlist_count"] <= reference_metrics["shortlist_count"],
    }
    compatibility["overall_pass"] = all(bool(v) for v in compatibility.values())
    gap_delta = None
    if (
        simulated_metrics["active_best_background_gap"] is not None
        and reference_metrics["active_best_background_gap"] is not None
    ):
        gap_delta = round(
            float(simulated_metrics["active_best_background_gap"]) - float(reference_metrics["active_best_background_gap"]),
            3,
        )
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope_note": (
            "Enhancement-line cross-case compatibility check only. This does not modify or replace frozen benchmark/manuscript claims."
        ),
        "remote_root": remote_root,
        "case_id": case_id,
        "current_v3_tuning": current_tuning,
        "reference_metrics": reference_metrics,
        "simulated_v3_metrics": simulated_metrics,
        "compatibility": compatibility,
        "delta_vs_reference": {
            "active_best_background_gap": gap_delta,
            "filter_keep_count": simulated_metrics["filter_keep_count"] - reference_metrics["filter_keep_count"],
            "shortlist_count": simulated_metrics["shortlist_count"] - reference_metrics["shortlist_count"],
        },
    }


def build_markdown(payload: dict[str, object]) -> str:
    ref = payload["reference_metrics"]
    sim = payload["simulated_v3_metrics"]
    comp = payload["compatibility"]
    delta = payload["delta_vs_reference"]
    lines = [
        "# Enhancement Line Cross-Case Compatibility Check",
        "",
        f"- Generated at: `{payload['generated_at_utc']}`",
        f"- Scope: {payload['scope_note']}",
        f"- Remote root: `{payload['remote_root']}`",
        f"- Case id: `{payload['case_id']}`",
        "",
        "## Current Enhancement Tuning",
        "",
        f"- `{json.dumps(payload['current_v3_tuning'], sort_keys=True)}`",
        "",
        "## Reference vs Simulated v3",
        "",
        "| Dimension | Reference frozen/root line | Simulated current v3 tuning |",
        "| --- | --- | --- |",
        f"| Known active rank | `{ref['known_active_rank']}` | `{sim['known_active_rank']}` |",
        f"| Known active shortlisted | `{ref['known_active_shortlisted']}` | `{sim['known_active_shortlisted']}` |",
        f"| Filter keep count | `{ref['filter_keep_count']}` | `{sim['filter_keep_count']}` |",
        f"| Shortlist count | `{ref['shortlist_count']}` | `{sim['shortlist_count']}` |",
        f"| Shortlist ids | `{', '.join(ref['shortlist_ids'])}` | `{', '.join(sim['shortlist_ids'])}` |",
        f"| Best background | `{ref['best_background_compound_id']}` | `{sim['best_background_compound_id']}` |",
        f"| Active-best-background gap | `{ref['active_best_background_gap']}` | `{sim['active_best_background_gap']}` |",
        "",
        "## Compatibility Gates",
        "",
        f"- Known active rank preserved: `{comp['known_active_rank_preserved']}`",
        f"- Known active shortlisted preserved: `{comp['known_active_shortlisted_preserved']}`",
        f"- Shortlist count not expanded: `{comp['shortlist_count_not_expanded']}`",
        f"- Overall pass: `{comp['overall_pass']}`",
        "",
        "## Delta vs Reference",
        "",
        f"- Active-best-background gap delta: `{delta['active_best_background_gap']}`",
        f"- Filter keep count delta: `{delta['filter_keep_count']}`",
        f"- Shortlist count delta: `{delta['shortlist_count']}`",
        "",
        "## Simulated v3 Top Preview",
        "",
    ]
    for row in sim["top_rerank"]:
        lines.append(
            f"- `{row['compound_id']}` rank `{row['rerank_rank']}` score `{row['rerank_score']}` flags `{', '.join(row['physchem_flags']) or 'none'}`"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    cache_root = (project_root / args.cache_dir / args.case_id).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    if not args.skip_fetch:
        fetch_source_files(project_root, args.remote_root, cache_root)

    modules = load_modules(project_root)
    case_rows = read_tsv_rows(cache_root / "04_metadata/benchmark_cases.tsv")
    compound_library_rows = read_tsv_rows(cache_root / "04_metadata/compound_libraries.tsv")
    docking_rows = read_tsv_rows(cache_root / "07_results/modules/classical_docking/docking_results.tsv")
    prepared_library_rows = read_tsv_rows(cache_root / "07_results/modules/compound_library_preparation/prepared_library.tsv")
    rerank_rows = read_tsv_rows(cache_root / "07_results/modules/ai_reranking/reranked_candidates.tsv")
    filtered_rows = read_tsv_rows(cache_root / "07_results/modules/filtering/filtered_candidates.tsv")
    clustered_rows = read_tsv_rows(cache_root / "07_results/modules/clustering_and_prioritization/clustered_priorities.tsv")

    case_row = case_lookup(case_rows)[args.case_id]
    known_active_compound_id = parse_known_active_id(case_row)
    case_docking_rows = [row for row in docking_rows if row["case_id"] == args.case_id]
    localized_case_rows = localize_case_artifacts(project_root, args.remote_root, cache_root, case_docking_rows)
    library_by_key = library_lookup(prepared_library_rows)
    library_manifest_by_id = {row["library_id"]: row for row in compound_library_rows}
    local_config_payload = modules.clustering.parse_simple_yaml_config(project_root / "config.yaml")
    current_tuning = modules.ai_reranking.load_v3_tuning(local_config_payload)
    gating_config = modules.ai_reranking.load_v3_case_gating(local_config_payload)

    reference_metrics = build_reference_metrics(
        args.case_id,
        rerank_rows,
        filtered_rows,
        clustered_rows,
        known_active_compound_id,
    )
    scored_rows = score_case_rows(
        modules,
        case_row,
        localized_case_rows,
        library_by_key,
        prepared_library_rows,
        library_manifest_by_id,
        gating_config,
        current_tuning,
    )
    simulated_filtered_rows, kept_records = evaluate_filtering(modules, case_row, scored_rows, library_by_key)
    simulated_shortlist_rows, shortlist_diag = evaluate_shortlist(modules, case_row, kept_records, local_config_payload)
    simulated_metrics = build_simulated_metrics(
        modules,
        case_row,
        scored_rows,
        simulated_filtered_rows,
        simulated_shortlist_rows,
        shortlist_diag,
        known_active_compound_id,
    )
    payload = build_payload(
        args.case_id,
        args.remote_root,
        current_tuning,
        reference_metrics,
        simulated_metrics,
    )
    output_json = Path(args.output_json) if args.output_json else project_root / f"09_reports/enhancement_cross_case_check_{args.case_id}.json"
    output_md = Path(args.output_md) if args.output_md else project_root / f"09_reports/enhancement_cross_case_check_{args.case_id}.md"
    write_json(output_json, payload)
    output_md.write_text(build_markdown(payload), encoding="utf-8")
    print(f"[cross-case-check] wrote json: {output_json}")
    print(f"[cross-case-check] wrote markdown: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
