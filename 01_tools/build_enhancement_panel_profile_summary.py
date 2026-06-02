#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize enhancement-panel composition using prepared library descriptors and current v3 tuning."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--prepared-library",
        default="11_tmp/enhancement_case_fetch/prepared_library.tsv",
    )
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_panel_profile_summary.json",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_panel_profile_summary.md",
    )
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def parse_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return default


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def current_v3_tuning(config: dict[str, Any]) -> dict[str, float]:
    v3 = (((config or {}).get("modules") or {}).get("ai_reranking") or {}).get("v3") or {}
    return {
        "hetero_floor": float(v3.get("hetero_floor", 2.0)),
        "aromatic_fraction_threshold": float(v3.get("aromatic_fraction_threshold", 0.75)),
        "simple_aromatic_penalty": float(v3.get("simple_aromatic_penalty", 0.0)),
        "polyaryl_hydrophobe_penalty": float(v3.get("polyaryl_hydrophobe_penalty", 0.0)),
        "single_ring_background_penalty": float(v3.get("single_ring_background_penalty", 0.0)),
    }


def classify_row(row: dict[str, str], tuning: dict[str, float]) -> dict[str, Any]:
    heavy_atom_count = parse_float(row.get("heavy_atom_count"))
    hetero_atom_count = parse_float(row.get("hetero_atom_count"))
    aromatic_atom_count = parse_float(row.get("aromatic_atom_count"))
    ring_index_count = parse_float(row.get("ring_index_count"))
    molecular_weight = parse_float(row.get("molecular_weight_estimate"))
    aromatic_fraction = (aromatic_atom_count / heavy_atom_count) if heavy_atom_count > 0 else 0.0

    simple_aromatic_background = hetero_atom_count <= 1.0 and aromatic_atom_count >= 8.0 and ring_index_count <= 2.0
    polyaryl_hydrophobe_background = (
        hetero_atom_count <= 1.0
        and ring_index_count >= 2.0
        and aromatic_atom_count >= 8.0
        and aromatic_fraction > 0.7
    )
    single_ring_background = ring_index_count <= 1.0 and aromatic_atom_count >= 6.0 and molecular_weight < 150.0

    return {
        "compound_id": row["compound_id"],
        "molecular_weight_estimate": round(molecular_weight, 3),
        "heavy_atom_count": int(heavy_atom_count),
        "hetero_atom_count": int(hetero_atom_count),
        "aromatic_atom_count": int(aromatic_atom_count),
        "ring_index_count": int(ring_index_count),
        "aromatic_fraction": round(aromatic_fraction, 3),
        "simple_aromatic_background": simple_aromatic_background,
        "polyaryl_hydrophobe_background": polyaryl_hydrophobe_background,
        "single_ring_background": single_ring_background,
        "any_background_flag": bool(
            simple_aromatic_background or polyaryl_hydrophobe_background or single_ring_background
        ),
        "active_current_penalty_knobs": {
            "simple_aromatic_penalty": tuning["simple_aromatic_penalty"] if simple_aromatic_background else 0.0,
            "polyaryl_hydrophobe_penalty": tuning["polyaryl_hydrophobe_penalty"] if polyaryl_hydrophobe_background else 0.0,
            "single_ring_background_penalty": tuning["single_ring_background_penalty"] if single_ring_background else 0.0,
        },
    }


def parse_known_active(case_row: dict[str, str]) -> str:
    raw = case_row.get("known_active_definition", "")
    if raw.startswith("compound_id="):
        return raw.split("=", 1)[1]
    return raw


def summarize_case(
    case_row: dict[str, str],
    library_rows: list[dict[str, str]],
    tuning: dict[str, float],
    dual_case_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    known_active = parse_known_active(case_row)
    profiled = [classify_row(row, tuning) for row in library_rows]
    active_row = next((row for row in profiled if row["compound_id"] == known_active), None)
    background_rows = [row for row in profiled if row["compound_id"] != known_active]

    def collect(flag_name: str) -> list[str]:
        return [row["compound_id"] for row in background_rows if row.get(flag_name)]

    simple_ids = collect("simple_aromatic_background")
    polyaryl_ids = collect("polyaryl_hydrophobe_background")
    single_ring_ids = collect("single_ring_background")
    any_ids = [row["compound_id"] for row in background_rows if row["any_background_flag"]]

    best_background = dual_case_lookup.get(case_row["case_id"], {}).get("best_background_compound_id")

    interpretation_bits: list[str] = []
    if best_background in simple_ids:
        interpretation_bits.append("best background matches simple_aromatic rule")
    if best_background in polyaryl_ids:
        interpretation_bits.append("best background matches polyaryl_hydrophobe rule")
    if best_background in single_ring_ids:
        interpretation_bits.append("best background matches single_ring rule")
    if not interpretation_bits:
        interpretation_bits.append("best background is not directly captured by current background flags")

    return {
        "case_id": case_row["case_id"],
        "library_id": case_row["library_id"],
        "known_active_compound_id": known_active,
        "panel_size": len(profiled),
        "background_count": len(background_rows),
        "active_profile": active_row,
        "flag_counts": {
            "simple_aromatic_background": len(simple_ids),
            "polyaryl_hydrophobe_background": len(polyaryl_ids),
            "single_ring_background": len(single_ring_ids),
            "any_background_flag": len(any_ids),
        },
        "flagged_background_ids": {
            "simple_aromatic_background": simple_ids,
            "polyaryl_hydrophobe_background": polyaryl_ids,
            "single_ring_background": single_ring_ids,
            "any_background_flag": any_ids,
        },
        "background_flag_coverage": round((len(any_ids) / len(background_rows)) if background_rows else 0.0, 3),
        "best_background_compound_id": best_background,
        "best_background_interpretation": interpretation_bits,
    }


def build_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Enhancement Panel Profile Summary")
    lines.append("")
    lines.append(f"- Generated at: `{payload['generated_at_utc']}`")
    lines.append("- Scope: Enhancement-line panel-composition summary only. This does not change tuning or frozen benchmark/manuscript claims.")
    lines.append("- Input source: workflow-prepared library descriptors plus current v3 tuning.")
    lines.append("")
    lines.append("## Current Tuning")
    lines.append("")
    for key, value in payload["current_v3_tuning"].items():
        lines.append(f"- `{key} = {value}`")
    lines.append("")
    lines.append("## Case Table")
    lines.append("")
    lines.append("| Case | Panel size | Background count | Any-flag coverage | Best background | Interpretation |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for case in payload["cases"]:
        lines.append(
            f"| `{case['case_id']}` | `{case['panel_size']}` | `{case['background_count']}` | "
            f"`{case['background_flag_coverage']}` | `{case['best_background_compound_id']}` | "
            f"`{'; '.join(case['best_background_interpretation'])}` |"
        )
    lines.append("")
    for case in payload["cases"]:
        lines.append(f"## `{case['case_id']}`")
        lines.append("")
        lines.append(f"- Known active: `{case['known_active_compound_id']}`")
        lines.append(f"- Best background: `{case['best_background_compound_id']}`")
        lines.append(f"- Background flag coverage: `{case['background_flag_coverage']}`")
        lines.append(
            f"- `simple_aromatic_background`: `{case['flag_counts']['simple_aromatic_background']}` -> "
            f"`{', '.join(case['flagged_background_ids']['simple_aromatic_background']) if case['flagged_background_ids']['simple_aromatic_background'] else 'none'}`"
        )
        lines.append(
            f"- `polyaryl_hydrophobe_background`: `{case['flag_counts']['polyaryl_hydrophobe_background']}` -> "
            f"`{', '.join(case['flagged_background_ids']['polyaryl_hydrophobe_background']) if case['flagged_background_ids']['polyaryl_hydrophobe_background'] else 'none'}`"
        )
        lines.append(
            f"- `single_ring_background`: `{case['flag_counts']['single_ring_background']}` -> "
            f"`{', '.join(case['flagged_background_ids']['single_ring_background']) if case['flagged_background_ids']['single_ring_background'] else 'none'}`"
        )
        lines.append(
            f"- Best-background interpretation: `{' ; '.join(case['best_background_interpretation'])}`"
        )
        lines.append("")
    lines.append("## Reading")
    lines.append("")
    for note in payload["reading_notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    config = load_config(project_root / "config.yaml")
    tuning = current_v3_tuning(config)

    prepared_rows = read_tsv(project_root / args.prepared_library)
    case_rows = read_tsv(project_root / "04_metadata/benchmark_cases.tsv")
    dual_case = json.loads((project_root / "09_reports/enhancement_dual_case_validation_summary.json").read_text(encoding="utf-8"))
    dual_case_lookup = {case["case_id"]: case for case in dual_case.get("cases", [])}

    enhancement_cases = [
        row for row in case_rows
        if row.get("enabled") == "true" and row.get("rerank_strategy") == "ai_rerank_v3"
    ]

    case_payloads = []
    for case_row in enhancement_cases:
        library_rows = [row for row in prepared_rows if row["library_id"] == case_row["library_id"]]
        case_payloads.append(summarize_case(case_row, library_rows, tuning, dual_case_lookup))

    reading_notes = [
        "Panel composition is asymmetric across the two enhancement-only BRD4 cases: `BRD4_BD1_LIT002_V3EXP` contains multiple backgrounds that directly match the current v3 aromatic/hydrophobe heuristics, while `BRD4_BD1_LIT001_V3EXP` has much broader and softer background chemistry.",
        "This explains why the same penalty family is material on `LIT002_V3EXP` but weak on `LIT001_V3EXP` without requiring a change to frozen-line logic.",
        "Use this panel-profile summary together with the dual-case validation summary before proposing case-aware gating or broader rollout.",
    ]

    payload = {
        "generated_at_utc": dual_case.get("generated_at_utc"),
        "current_v3_tuning": tuning,
        "cases": case_payloads,
        "reading_notes": reading_notes,
    }

    output_json = project_root / args.output_json
    output_md = project_root / args.output_md
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(build_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
