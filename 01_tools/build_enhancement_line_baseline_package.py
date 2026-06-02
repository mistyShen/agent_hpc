#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a formal baseline package summary for the current enhancement line."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_line_baseline_package.json",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_line_baseline_package.md",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_optional(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return read_json(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Enhancement Line Baseline Package")
    lines.append("")
    lines.append(f"- Generated at: `{summary['generated_at_utc']}`")
    lines.append("- Scope: enhancement-line only. This package is a formal baseline snapshot for ongoing enhancement validation and tool evolution.")
    lines.append("- Boundary: this package must not modify or replace frozen manuscript / benchmark claims.")
    lines.append("")
    lines.append("## Fixed Reading")
    lines.append("")
    lines.append(f"- Package status: `{summary['package_status']}`")
    lines.append(f"- Frozen line untouched: `{summary['frozen_line_untouched']}`")
    lines.append(f"- Gating status: `{summary['gating_status']}`")
    lines.append(f"- Current validation status: `{summary['current_validation_status']}`")
    lines.append(f"- Current bounded headline: `{summary['bounded_headline']}`")
    lines.append("")
    lines.append("## Current Case Classes")
    lines.append("")
    lines.append(f"- Material-on-panel cases: `{', '.join(summary['material_cases']) if summary['material_cases'] else 'none'}`")
    lines.append(f"- Weak-on-panel cases: `{', '.join(summary['weak_cases']) if summary['weak_cases'] else 'none'}`")
    lines.append(f"- Failed shortlist-preservation cases: `{', '.join(summary['failed_cases']) if summary['failed_cases'] else 'none'}`")
    lines.append(f"- Non-BRD4 bounded surfaces: `{', '.join(summary['non_brd4_cases']) if summary['non_brd4_cases'] else 'none'}`")
    lines.append("")
    lines.append("## Surface Table")
    lines.append("")
    lines.append("| Case | Target | Known active | Gap | Rollout preserved | Effect class | Dominant driver |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for row in summary["surface_table"]:
        lines.append(
            f"| `{row['case_id']}` | `{row['target_id']}` | `{row['known_active_compound_id']}` | "
            f"`{row['active_best_background_gap']}` | `{row['rollout_preserved']}` | `{row['effect_class']}` | `{row['dominant_driver']}` |"
        )
    lines.append("")
    lines.append("## Current Interpretation")
    lines.append("")
    for item in summary["interpretation_points"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Allowed Uses")
    lines.append("")
    for item in summary["allowed_uses"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Disallowed Uses")
    lines.append("")
    for item in summary["disallowed_uses"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Included Components")
    lines.append("")
    for item in summary["included_components"]:
        lines.append(f"- `{item['label']}` -> `{item['path']}`")
    lines.append("")
    lines.append("## Next Recommended Action")
    lines.append("")
    lines.append(f"- `{summary['recommended_next_action']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    report_dir = project_root / "09_reports"

    gating = read_json(report_dir / "enhancement_case_aware_gating_implementation_summary.json")
    non_brd4 = read_json(report_dir / "enhancement_non_brd4_bounded_validation_summary.json")
    multi = read_json(report_dir / "enhancement_multi_case_validation_summary.json")
    readiness = read_json(report_dir / "enhancement_expansion_readiness.json")
    promotion_review = read_json_optional(report_dir / "enhancement_boundary_promotion_review_BRD3.json")

    cases = multi.get("cases", [])
    material_cases = [row["case_id"] for row in cases if row.get("effect_class") == "material_on_panel"]
    weak_cases = [row["case_id"] for row in cases if row.get("effect_class") == "weak_on_panel"]
    failed_cases = [row["case_id"] for row in cases if row.get("effect_class") == "failed_shortlist_preservation"]
    case_inventory = {row["case_id"]: row for row in readiness.get("enabled_literature_backed_cases", [])}
    non_brd4_weak_cases = [row["case_id"] for row in cases if row.get("effect_class") == "weak_on_panel" and not str(row.get("case_id", "")).startswith("BRD4_")]

    surface_table = []
    for row in cases:
        case_id = row["case_id"]
        case_meta = case_inventory.get(case_id, {})
        dominant = row.get("dominant_driver") or {}
        surface_table.append(
            {
                "case_id": case_id,
                "target_id": case_meta.get("target_id", ""),
                "known_active_compound_id": row.get("known_active_compound_id"),
                "active_best_background_gap": row.get("active_best_background_gap"),
                "rollout_preserved": row.get("rollout_preserved"),
                "effect_class": row.get("effect_class"),
                "dominant_driver": dominant.get("variant_name", "none"),
            }
        )

    non_brd4_cases = readiness.get("non_brd4_cases", [])
    promotion_decision = (promotion_review or {}).get("decision", {})
    bounded_headline = (
        "bounded_material_gain_supported_in_BRD4_and_BRD3_IBET762_focused_surfaces"
        if promotion_decision.get("retire_brd4_only_internal_reading")
        else (
            "weak_outside_BRD4__material_on_BRD4_IBET_focused_panels"
            if material_cases and non_brd4_cases
            else "bounded_panel_aware_enhancement_line"
        )
    )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "package_status": "formal_enhancement_line_baseline",
        "frozen_line_untouched": True,
        "gating_status": "implemented_and_bounded",
        "current_validation_status": multi.get("current_validation_status"),
        "bounded_headline": bounded_headline,
        "material_cases": material_cases,
        "weak_cases": weak_cases,
        "failed_cases": failed_cases,
        "non_brd4_cases": non_brd4_cases,
        "surface_table": surface_table,
        "interpretation_points": [
            "Current v3 behavior remains bounded and panel-aware rather than generally validated across targets.",
            f"Material-on-panel behavior is currently limited to `{', '.join(material_cases) if material_cases else 'none'}`.",
            (
                f"BRD3 I-BET762-focused surfaces now support the interim boundary `{promotion_decision.get('recommended_interim_headline')}`."
                if promotion_decision.get("retire_brd4_only_internal_reading")
                else f"Rollout-eligible non-BRD4 surfaces `{', '.join(non_brd4_weak_cases) if non_brd4_weak_cases else 'none'}` remain weak_on_panel, which supports a restrained outside-BRD4 reading."
            ),
            (
                f"Boundary-challenge surfaces `{', '.join(failed_cases)}` currently improve rerank separation without preserving shortlist/rank, so they are excluded from rollout-safe material evidence."
                if failed_cases
                else "No current enhancement surface is failing shortlist/rank preservation."
            ),
            "Current non-BRD4 evidence is mixed: BRD3 I-BET762-focused surfaces are material, while other checked non-BRD4 surfaces remain weak or challenge cases.",
            "The interim BRD4+BRD3 boundary is not a full BET-family or cross-target claim.",
        ],
        "allowed_uses": [
            "Use as the current enhancement-line handoff and audit baseline.",
            "Use as the reference point for future bounded validation surfaces.",
            "Use to justify pausing same-panel tuning while preserving current enhancement evidence.",
        ],
        "disallowed_uses": [
            "Do not move these results into frozen manuscript or benchmark claims.",
            "Do not describe the current enhancement result as cross-target generalization.",
            "Do not use this package as evidence that v3 is a generally validated reranking improvement.",
            "Do not count failed shortlist-preservation surfaces as rollout-safe material evidence.",
        ],
        "included_components": [
            {
                "label": "gating_implementation_summary",
                "path": "09_reports/enhancement_case_aware_gating_implementation_summary.md",
            },
            {
                "label": "non_brd4_bounded_validation_summary",
                "path": "09_reports/enhancement_non_brd4_bounded_validation_summary.md",
            },
            {
                "label": "multi_case_validation_summary",
                "path": "09_reports/enhancement_multi_case_validation_summary.md",
            },
            {
                "label": "expansion_readiness",
                "path": "09_reports/enhancement_expansion_readiness.md",
            },
            {
                "label": "boundary_promotion_review_brd3",
                "path": "09_reports/enhancement_boundary_promotion_review_BRD3.md",
            },
            {
                "label": "pxr_bounded_surface_comparison",
                "path": "09_reports/enhancement_line_v2_vs_v3_comparison_PXR_LBD_LIT001.md",
            },
            {
                "label": "pxr_bounded_surface_rule_audit",
                "path": "09_reports/enhancement_line_rule_audit_PXR_LBD_LIT001.md",
            },
        ],
        "recommended_next_action": readiness.get("recommended_next_action"),
        "source_snapshots": {
            "gating_summary_generated_at": gating.get("generated_at_utc"),
            "non_brd4_summary_generated_at": non_brd4.get("generated_at_utc"),
            "multi_case_summary_generated_at": multi.get("generated_at_utc"),
            "readiness_generated_at": readiness.get("generated_at_utc"),
            "promotion_review_generated_at": (promotion_review or {}).get("generated_at"),
        },
    }

    output_json = project_root / args.output_json
    output_md = project_root / args.output_md
    write_json(output_json, summary)
    write_text(output_md, build_markdown(summary))


if __name__ == "__main__":
    main()
