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
    "config.yaml",
    "04_metadata/benchmark_cases.tsv",
    "04_metadata/compound_libraries.tsv",
    "07_results/modules/classical_docking/docking_results.tsv",
    "07_results/modules/compound_library_preparation/prepared_library.tsv",
]


@dataclass
class LoadedModules:
    ai_reranking: Any
    filtering: Any
    clustering: Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded enhancement-line rule audit/ablation without overwriting remote enhancement outputs."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--remote-root",
        default="/shared/shen/cpu_ai_drug_design_v3exp",
        help="Remote isolated enhancement workspace root used only for source-file fetches",
    )
    parser.add_argument("--baseline-case-id", default="BRD4_BD1_LIT002")
    parser.add_argument("--enhancement-case-id", default="BRD4_BD1_LIT002_V3EXP")
    parser.add_argument(
        "--cache-dir",
        default="11_tmp/enhancement_rule_audit_inputs",
        help="Local cache directory for fetched remote inputs and copied docking artifacts",
    )
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_line_rule_audit.json",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_line_rule_audit.md",
    )
    parser.add_argument(
        "--comparison-json",
        default="09_reports/enhancement_line_v2_vs_v3_comparison.json",
        help="Local comparison JSON used only to verify current-gap reproduction for the audited enhancement case pair.",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Reuse cached source files instead of fetching the remote enhancement inputs again",
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
        ai_reranking=load_module(modules_root / "ai_reranking.py", "enhancement_audit_ai_reranking"),
        filtering=load_module(modules_root / "filtering.py", "enhancement_audit_filtering"),
        clustering=load_module(
            modules_root / "clustering_and_prioritization.py",
            "enhancement_audit_clustering",
        ),
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
    localized: list[dict[str, str]] = []
    for row in case_rows:
        localized_row = dict(row)
        for key in ("ligand_pdbqt_path", "pose_pdbqt_path"):
            remote_path = row.get(key, "").strip()
            if not remote_path:
                continue
            suffix = "ligand" if key == "ligand_pdbqt_path" else "pose"
            local_path = (
                cache_dir
                / "artifacts"
                / row["case_id"]
                / f"{row['compound_id']}.{suffix}.pdbqt"
            )
            hpc_get(normalize_remote_path(remote_root, remote_path), local_path, project_root)
            localized_row[key] = str(local_path)
        localized.append(localized_row)
    return localized


def library_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row["library_id"], row["compound_id"]): row for row in rows}


def case_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["case_id"]: row for row in rows}


def with_overrides(base_tuning: dict[str, float], overrides: dict[str, float]) -> dict[str, float]:
    payload = dict(base_tuning)
    payload.update(overrides)
    return payload


def current_and_ablation_tunings(base_tuning: dict[str, float]) -> list[dict[str, object]]:
    return [
        {"name": "current", "overrides": {}, "tuning": dict(base_tuning)},
        {
            "name": "ablate_simple_aromatic_penalty",
            "overrides": {"simple_aromatic_penalty": 0.0},
            "tuning": with_overrides(base_tuning, {"simple_aromatic_penalty": 0.0}),
        },
        {
            "name": "ablate_polyaryl_hydrophobe_penalty",
            "overrides": {"polyaryl_hydrophobe_penalty": 0.0},
            "tuning": with_overrides(base_tuning, {"polyaryl_hydrophobe_penalty": 0.0}),
        },
        {
            "name": "ablate_single_ring_background_penalty",
            "overrides": {"single_ring_background_penalty": 0.0},
            "tuning": with_overrides(base_tuning, {"single_ring_background_penalty": 0.0}),
        },
        {
            "name": "ablate_all_background_penalties",
            "overrides": {
                "simple_aromatic_penalty": 0.0,
                "polyaryl_hydrophobe_penalty": 0.0,
                "single_ring_background_penalty": 0.0,
            },
            "tuning": with_overrides(
                base_tuning,
                {
                    "simple_aromatic_penalty": 0.0,
                    "polyaryl_hydrophobe_penalty": 0.0,
                    "single_ring_background_penalty": 0.0,
                },
            ),
        },
    ]


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
) -> tuple[list[dict[str, object]], list[dict[str, object]], float | None]:
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
            kept_records.append(
                {
                    **row,
                    "filter_reason": reason,
                }
            )
    return filtered_rows, kept_records, case_best_vina_affinity


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
    v3_priority_policy = modules.clustering.use_v3_priority_policy(case_row, case_records)
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


def build_variant_metrics(
    modules: LoadedModules,
    case_row: dict[str, str],
    scored_rows: list[dict[str, object]],
    filtered_rows: list[dict[str, object]],
    kept_records: list[dict[str, object]],
    shortlist_records: list[dict[str, object]],
    shortlist_diagnostics: dict[str, object],
    known_active_compound_id: str,
) -> dict[str, object]:
    best_background = next((row for row in scored_rows if row["compound_id"] != known_active_compound_id), None)
    known_active = next((row for row in scored_rows if row["compound_id"] == known_active_compound_id), None)
    active_gap = None
    if best_background and known_active:
        active_gap = round(float(best_background["rerank_score"]) - float(known_active["rerank_score"]), 3)
    return {
        "known_active_compound_id": known_active_compound_id,
        "known_active_rank": known_active["rerank_rank"] if known_active else None,
        "known_active_rerank_score": known_active["rerank_score"] if known_active else None,
        "known_active_shortlisted": any(row["compound_id"] == known_active_compound_id for row in shortlist_records),
        "best_background_compound_id": best_background["compound_id"] if best_background else None,
        "best_background_rank": best_background["rerank_rank"] if best_background else None,
        "best_background_rerank_score": best_background["rerank_score"] if best_background else None,
        "active_best_background_gap": active_gap,
        "best_background_flags": (
            modules.ai_reranking.summarize_v3_preview_row(best_background, int(best_background["rerank_rank"]))["physchem_flags"]
            if best_background
            else []
        ),
        "filter_keep_count": sum(1 for row in filtered_rows if row["filter_decision"] == "keep"),
        "shortlist_count": len(shortlist_records),
        "shortlist_ids": [row["compound_id"] for row in shortlist_records],
        "top_rerank": [
            {
                "compound_id": row["compound_id"],
                "rerank_rank": row["rerank_rank"],
                "rerank_score": row["rerank_score"],
                "rerank_bonus": row["rerank_bonus"],
                "physchem_flags": modules.ai_reranking.summarize_v3_preview_row(row, int(row["rerank_rank"]))["physchem_flags"],
            }
            for row in scored_rows[:3]
        ],
        "shortlist_diagnostics": shortlist_diagnostics,
    }


def classify_contribution(gap_loss: float) -> str:
    if gap_loss >= 2.0:
        return "dominant_on_current_panel"
    if gap_loss >= 0.5:
        return "material_on_current_panel"
    if gap_loss >= 0.1:
        return "modest_on_current_panel"
    return "weak_on_current_panel"


def build_audit_payload(
    current_label: str,
    current_metrics: dict[str, object],
    variants: list[dict[str, object]],
    existing_comparison_gap: float | None,
    enhancement_case_id: str,
) -> dict[str, object]:
    current_gap = float(current_metrics["active_best_background_gap"]) if current_metrics["active_best_background_gap"] is not None else None
    ablation_rows: list[dict[str, object]] = []
    for variant in variants:
        if variant["name"] == current_label:
            continue
        metrics = variant["metrics"]
        variant_gap = metrics["active_best_background_gap"]
        gap_loss = round(float(current_gap) - float(variant_gap), 3) if current_gap is not None and variant_gap is not None else None
        shortlist_expanded = (
            metrics["shortlist_count"] > current_metrics["shortlist_count"]
            if metrics["shortlist_count"] is not None and current_metrics["shortlist_count"] is not None
            else None
        )
        ablation_rows.append(
            {
                "variant_name": variant["name"],
                "overrides": variant["overrides"],
                "active_best_background_gap": variant_gap,
                "gap_loss_vs_current": gap_loss,
                "best_background_compound_id": metrics["best_background_compound_id"],
                "best_background_flags": metrics["best_background_flags"],
                "filter_keep_count": metrics["filter_keep_count"],
                "shortlist_count": metrics["shortlist_count"],
                "shortlist_ids": metrics["shortlist_ids"],
                "known_active_rank": metrics["known_active_rank"],
                "known_active_shortlisted": metrics["known_active_shortlisted"],
                "top_score_gap": metrics["shortlist_diagnostics"]["top_score_gap"],
                "contribution_class": classify_contribution(gap_loss if gap_loss is not None else 0.0),
                "shortlist_expanded_vs_current": shortlist_expanded,
            }
        )
    ablation_rows.sort(
        key=lambda row: (
            -(row["gap_loss_vs_current"] if row["gap_loss_vs_current"] is not None else -999.0),
            row["variant_name"],
        )
    )
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope_note": (
            f"Enhancement-line rule audit only. Results are limited to {enhancement_case_id} and must not be promoted to frozen benchmark/manuscript claims."
        ),
        "current_label": current_label,
        "current_metrics": current_metrics,
        "reproduces_existing_comparison_gap": existing_comparison_gap == current_metrics["active_best_background_gap"],
        "ablation_rows": ablation_rows,
        "main_driver_ranking": [
            {
                "variant_name": row["variant_name"],
                "gap_loss_vs_current": row["gap_loss_vs_current"],
                "contribution_class": row["contribution_class"],
            }
            for row in ablation_rows
        ],
    }


def build_markdown(payload: dict[str, object]) -> str:
    current = payload["current_metrics"]
    lines = [
        "# Enhancement Line Rule Audit",
        "",
        f"- Generated at: `{payload['generated_at_utc']}`",
        f"- Scope: {payload['scope_note']}",
        f"- Current label: `{payload['current_label']}`",
        f"- Current best background: `{current['best_background_compound_id']}`",
        f"- Current active-best-background gap: `{current['active_best_background_gap']}`",
        f"- Current shortlist ids: `{', '.join(current['shortlist_ids'])}`",
        f"- Reproduces existing comparison gap: `{payload['reproduces_existing_comparison_gap']}`",
        "",
        "## Current Tuning",
        "",
        f"- Known active rank: `{current['known_active_rank']}`",
        f"- Filter keep count: `{current['filter_keep_count']}`",
        f"- Shortlist count: `{current['shortlist_count']}`",
        f"- Best background flags: `{', '.join(current['best_background_flags']) or 'none'}`",
        "",
        "## Ablation Table",
        "",
        "| Variant | Overrides | Gap | Gap loss vs current | Best background | Flags | Keep count | Shortlist count | Shortlist ids | Contribution |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["ablation_rows"]:
        lines.append(
            f"| `{row['variant_name']}` | `{json.dumps(row['overrides'], sort_keys=True)}` | "
            f"`{row['active_best_background_gap']}` | `{row['gap_loss_vs_current']}` | "
            f"`{row['best_background_compound_id']}` | `{', '.join(row['best_background_flags']) or 'none'}` | "
            f"`{row['filter_keep_count']}` | `{row['shortlist_count']}` | "
            f"`{', '.join(row['shortlist_ids'])}` | `{row['contribution_class']}` |"
        )
    lines.extend(
        [
            "",
            "## Audit Reading",
            "",
            "- Treat larger `gap loss vs current` as stronger evidence that the ablated rule is materially contributing on the current focused panel.",
            "- Treat stable `shortlist_count = 1` under ablation as evidence that the shortlisted active remains robust even when a rule is removed.",
            "- Do not generalize these findings beyond this single enhancement panel without cross-case validation.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    cache_dir = (project_root / args.cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    if not args.skip_fetch:
        fetch_source_files(project_root, args.remote_root, cache_dir)

    modules = load_modules(project_root)
    config_path = cache_dir / "config.yaml"
    case_rows = read_tsv_rows(cache_dir / "04_metadata/benchmark_cases.tsv")
    compound_library_rows = read_tsv_rows(cache_dir / "04_metadata/compound_libraries.tsv")
    docking_rows = read_tsv_rows(cache_dir / "07_results/modules/classical_docking/docking_results.tsv")
    prepared_library_rows = read_tsv_rows(cache_dir / "07_results/modules/compound_library_preparation/prepared_library.tsv")
    case_row = case_lookup(case_rows)[args.enhancement_case_id]
    known_active_compound_id = parse_known_active_id(case_row)
    case_docking_rows = [row for row in docking_rows if row["case_id"] == args.enhancement_case_id]
    localized_case_rows = localize_case_artifacts(project_root, args.remote_root, cache_dir, case_docking_rows)
    library_by_key = library_lookup(prepared_library_rows)
    library_manifest_by_id = {row["library_id"]: row for row in compound_library_rows}
    config_payload = modules.clustering.parse_simple_yaml_config(config_path)
    base_tuning = modules.ai_reranking.load_v3_tuning(config_payload)
    gating_config = modules.ai_reranking.load_v3_case_gating(config_payload)
    comparison_json = json.loads((project_root / args.comparison_json).read_text(encoding="utf-8"))
    existing_comparison_gap = (
        comparison_json.get("enhancement_case", {})
        .get("active_margin", {})
        .get("known_active_to_best_background_gap")
    )

    variants: list[dict[str, object]] = []
    for variant in current_and_ablation_tunings(base_tuning):
        scored_rows = score_case_rows(
            modules,
            case_row,
            localized_case_rows,
            library_by_key,
            prepared_library_rows,
            library_manifest_by_id,
            gating_config,
            variant["tuning"],
        )
        filtered_rows, kept_records, _ = evaluate_filtering(modules, case_row, scored_rows, library_by_key)
        shortlist_records, shortlist_diagnostics = evaluate_shortlist(modules, case_row, kept_records, config_payload)
        metrics = build_variant_metrics(
            modules,
            case_row,
            scored_rows,
            filtered_rows,
            kept_records,
            shortlist_records,
            shortlist_diagnostics,
            known_active_compound_id,
        )
        variants.append(
            {
                "name": variant["name"],
                "overrides": variant["overrides"],
                "tuning": variant["tuning"],
                "metrics": metrics,
            }
        )

    current_variant = next(variant for variant in variants if variant["name"] == "current")
    payload = build_audit_payload(
        current_variant["name"],
        current_variant["metrics"],
        variants,
        existing_comparison_gap,
        args.enhancement_case_id,
    )
    output_json = project_root / args.output_json
    output_md = project_root / args.output_md
    write_json(output_json, payload)
    output_md.write_text(build_markdown(payload), encoding="utf-8")
    print(f"[rule-audit] wrote json: {output_json}")
    print(f"[rule-audit] wrote markdown: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
