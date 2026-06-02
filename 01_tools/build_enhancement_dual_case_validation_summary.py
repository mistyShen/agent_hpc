#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a dual-case enhancement validation summary bounded to enhancement-only evidence."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_dual_case_validation_summary.json",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_dual_case_validation_summary.md",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def summarize_case(case_id: str, audit: dict[str, Any], case_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    current = audit.get("current_metrics", {})
    top_contributors = audit.get("main_driver_ranking", [])
    positive = [row for row in top_contributors if float(row.get("gap_loss_vs_current", 0.0) or 0.0) > 0]
    dominant = next(
        (
            row
            for row in positive
            if row.get("contribution_class") == "dominant_on_current_panel"
            and row.get("variant_name") != "ablate_all_background_penalties"
        ),
        None,
    )
    if dominant is None:
        dominant = next((row for row in positive if row.get("variant_name") != "ablate_all_background_penalties"), None)

    material = [
        {
            "variant_name": row.get("variant_name"),
            "gap_loss_vs_current": row.get("gap_loss_vs_current"),
            "contribution_class": row.get("contribution_class"),
        }
        for row in positive
        if row.get("variant_name") not in {"ablate_all_background_penalties", dominant.get("variant_name") if dominant else ""}
    ]

    if positive:
        effect_class = "material_on_panel"
        interpretation = (
            "Current v3 penalties materially widen the active-best-background gap on this focused panel."
        )
    else:
        effect_class = "weak_on_panel"
        interpretation = (
            "Current v3 penalties preserve shortlist/rank on this panel, but the audited penalty family does not materially change the gap."
        )

    top_preview = case_summary.get("top_rerank", []) if case_summary else current.get("top_rerank", [])

    return {
        "case_id": case_id,
        "known_active_compound_id": current.get("known_active_compound_id") or (case_summary or {}).get("known_active_compound_id"),
        "known_active_rank": current.get("known_active_rank") or (case_summary or {}).get("known_active_rank"),
        "known_active_shortlisted": current.get("known_active_shortlisted")
        if current.get("known_active_shortlisted") is not None
        else (case_summary or {}).get("known_active_shortlisted"),
        "filter_keep_count": current.get("filter_keep_count") or (case_summary or {}).get("filter_keep_count"),
        "shortlist_count": current.get("shortlist_count") or (case_summary or {}).get("shortlist_count"),
        "shortlist_ids": current.get("shortlist_ids") or (case_summary or {}).get("shortlist_ids", []),
        "best_background_compound_id": current.get("best_background_compound_id")
        or (case_summary or {}).get("best_background_compound_id"),
        "active_best_background_gap": current.get("active_best_background_gap")
        or (case_summary or {}).get("active_best_background_gap"),
        "best_background_flags": current.get("best_background_flags", []),
        "effect_class": effect_class,
        "dominant_driver": dominant,
        "material_drivers": material,
        "interpretation": interpretation,
        "top_rerank_preview": top_preview[:3],
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Enhancement Dual-Case Validation Summary")
    lines.append("")
    lines.append(f"- Generated at: `{summary['generated_at_utc']}`")
    lines.append("- Scope: Enhancement-line synthesis only. This does not modify or replace frozen benchmark/manuscript claims.")
    lines.append("- Boundary: Conclusions below are limited to the explicitly checked BRD4 enhancement-only cases and bounded frozen-case compatibility checks.")
    lines.append("")
    lines.append("## Current Readout")
    lines.append("")
    lines.append(f"- Current validation status: `{summary['current_validation_status']}`")
    lines.append(f"- Expansion readiness: `{summary['expansion_readiness']}`")
    lines.append(f"- Recommended next action: `{summary['recommended_next_action']}`")
    lines.append("")
    lines.append("## Case Table")
    lines.append("")
    lines.append("| Case | Known active | Shortlist count | Best background | Active-best-background gap | Effect class | Dominant driver |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for case in summary["cases"]:
        dominant = case.get("dominant_driver") or {}
        dominant_name = dominant.get("variant_name", "none")
        lines.append(
            f"| `{case['case_id']}` | `{case['known_active_compound_id']}` | `{case['shortlist_count']}` | "
            f"`{case['best_background_compound_id']}` | `{case['active_best_background_gap']}` | "
            f"`{case['effect_class']}` | `{dominant_name}` |"
        )
    lines.append("")
    lines.append("## Case Reading")
    lines.append("")
    for case in summary["cases"]:
        lines.append(f"### `{case['case_id']}`")
        lines.append("")
        lines.append(f"- Interpretation: {case['interpretation']}")
        lines.append(f"- Known active rank/shortlist: `{case['known_active_rank']}` / `{case['known_active_shortlisted']}`")
        lines.append(f"- Best background: `{case['best_background_compound_id']}`")
        lines.append(f"- Best background flags: `{', '.join(case['best_background_flags']) if case['best_background_flags'] else 'none'}`")
        if case.get("dominant_driver"):
            lines.append(
                f"- Dominant driver: `{case['dominant_driver']['variant_name']}` "
                f"(gap loss `{case['dominant_driver']['gap_loss_vs_current']}`)"
            )
        else:
            lines.append("- Dominant driver: `none`")
        if case.get("material_drivers"):
            material_bits = ", ".join(
                f"`{row['variant_name']}` ({row['gap_loss_vs_current']})" for row in case["material_drivers"]
            )
            lines.append(f"- Additional material drivers: {material_bits}")
        else:
            lines.append("- Additional material drivers: `none`")
        preview_bits = ", ".join(
            f"`{row['compound_id']}` rank `{row['rerank_rank']}` score `{row['rerank_score']}`"
            for row in case.get("top_rerank_preview", [])
        )
        if preview_bits:
            lines.append(f"- Top rerank preview: {preview_bits}")
        lines.append("")
    lines.append("## Synthesis")
    lines.append("")
    for note in summary["synthesis_notes"]:
        lines.append(f"- {note}")
    lines.append("")
    lines.append("## Boundary Notes")
    lines.append("")
    for note in summary["boundary_notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    report_dir = project_root / "09_reports"

    lit002_audit = read_json(report_dir / "enhancement_line_rule_audit.json")
    lit001_audit = read_json(report_dir / "enhancement_line_rule_audit_LIT001.json")
    lit001_summary = read_json(report_dir / "enhancement_case_BRD4_BD1_LIT001_V3EXP_summary.json")
    validation_summary = read_json(report_dir / "enhancement_line_validation_summary.json")
    readiness = read_json(report_dir / "enhancement_expansion_readiness.json")
    cross_case_lit001 = read_json(report_dir / "enhancement_cross_case_check_BRD4_BD1_LIT001.json")
    cross_case_lit002 = read_json(report_dir / "enhancement_cross_case_check_BRD4_BD1_LIT002.json")

    cases = [
        summarize_case("BRD4_BD1_LIT002_V3EXP", lit002_audit),
        summarize_case("BRD4_BD1_LIT001_V3EXP", lit001_audit, lit001_summary),
    ]

    synthesis_notes = [
        "Current v3 behavior is panel-sensitive: it materially widens the active margin on `BRD4_BD1_LIT002_V3EXP`, but behaves mainly as a compatibility-preserving reranker on `BRD4_BD1_LIT001_V3EXP`.",
        "Both explicitly checked frozen cases (`BRD4_BD1_LIT001` and `BRD4_BD1_LIT002`) still pass bounded cross-case compatibility under the current v3 tuning.",
        "The current penalty family should therefore be treated as enhancement-line, bounded, and panel-aware rather than as a generally validated improvement.",
        "Do not use the generic single-case LIT001 comparison headline as the main decision surface; use this dual-case synthesis plus rule audit instead.",
    ]

    summary = {
        "generated_at_utc": validation_summary.get("generated_at_utc"),
        "current_validation_status": validation_summary.get("decision", {}).get("validation_status"),
        "expansion_readiness": readiness.get("expansion_readiness"),
        "recommended_next_action": "pause_same_panel_tuning_and_prepare_case-aware_or_additional_validation",
        "cases": cases,
        "cross_case_compatibility": [
            {
                "case_id": cross_case_lit001.get("case_id"),
                "overall_pass": cross_case_lit001.get("compatibility", {}).get("overall_pass"),
                "delta_active_gap": cross_case_lit001.get("delta_vs_reference", {}).get("active_best_background_gap"),
            },
            {
                "case_id": cross_case_lit002.get("case_id"),
                "overall_pass": cross_case_lit002.get("compatibility", {}).get("overall_pass"),
                "delta_active_gap": cross_case_lit002.get("delta_vs_reference", {}).get("active_best_background_gap"),
            },
        ],
        "synthesis_notes": synthesis_notes,
        "boundary_notes": [
            "This summary remains bounded to the enhancement line and the explicitly checked BRD4 literature-backed cases.",
            "The observed benefit on `BRD4_BD1_LIT002_V3EXP` should not be generalized as a cross-target or universal reranking improvement.",
            "The weak-on-panel result for `BRD4_BD1_LIT001_V3EXP` argues against broad claims and supports either case-aware gating or further validation before rollout.",
        ],
    }

    output_json = project_root / args.output_json
    output_md = project_root / args.output_md
    write_json(output_json, summary)
    write_text(output_md, build_markdown(summary))


if __name__ == "__main__":
    main()
