#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a compact enhancement-line validation summary from current audit and compatibility outputs."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_line_validation_summary.json",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_line_validation_summary.md",
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


def load_optional_cross_case(report_dir: Path, case_id: str) -> dict[str, Any] | None:
    path = report_dir / f"enhancement_cross_case_check_{case_id}.json"
    if not path.exists():
        return None
    return read_json(path)


def summarize_audit(audit_payload: dict[str, Any]) -> dict[str, Any]:
    ablations = audit_payload.get("ablation_rows", [])
    sorted_ablations = sorted(
        ablations,
        key=lambda row: float(row.get("gap_loss_vs_current", 0.0) or 0.0),
        reverse=True,
    )
    max_gap_loss = float(sorted_ablations[0].get("gap_loss_vs_current", 0.0) or 0.0) if sorted_ablations else 0.0
    top_contributors = [
        {
            "variant": row.get("variant_name"),
            "gap_loss_vs_current": row.get("gap_loss_vs_current"),
            "contribution": row.get("contribution")
            or (
                "dominant_on_current_panel"
                if float(row.get("gap_loss_vs_current", 0.0) or 0.0) == max_gap_loss and max_gap_loss > 0
                else (
                    "material_on_current_panel"
                    if float(row.get("gap_loss_vs_current", 0.0) or 0.0) > 0
                    else "inactive_on_current_panel"
                )
            ),
        }
        for row in sorted_ablations
    ]
    dominant_candidates = [
        row
        for row in top_contributors
        if row.get("contribution") == "dominant_on_current_panel"
        and row.get("variant") != "ablate_all_background_penalties"
    ]
    dominant = dominant_candidates[0] if dominant_candidates else next(
        (row for row in top_contributors if row.get("contribution") == "dominant_on_current_panel"),
        None,
    )
    material = [
        row for row in top_contributors if row.get("contribution") == "material_on_current_panel"
    ]
    return {
        "current_gap": audit_payload.get("current_metrics", {}).get("active_best_background_gap"),
        "current_best_background": audit_payload.get("current_metrics", {}).get("best_background_compound_id"),
        "current_shortlist_ids": audit_payload.get("current_metrics", {}).get("shortlist_ids", []),
        "reproduces_existing_comparison_gap": audit_payload.get("reproduces_existing_comparison_gap"),
        "dominant_current_panel_driver": dominant,
        "material_current_panel_drivers": material,
        "top_contributors": top_contributors,
    }


def summarize_cross_case(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    return {
        "case_id": payload.get("case_id"),
        "overall_pass": payload.get("compatibility", {}).get("overall_pass"),
        "known_active_rank_preserved": payload.get("compatibility", {}).get("known_active_rank_preserved"),
        "known_active_shortlisted_preserved": payload.get("compatibility", {}).get(
            "known_active_shortlisted_preserved"
        ),
        "shortlist_count_not_expanded": payload.get("compatibility", {}).get("shortlist_count_not_expanded"),
        "reference_shortlist_count": payload.get("reference_metrics", {}).get("shortlist_count"),
        "simulated_shortlist_count": payload.get("simulated_v3_metrics", {}).get("shortlist_count"),
        "reference_active_gap": payload.get("reference_metrics", {}).get("active_best_background_gap"),
        "simulated_active_gap": payload.get("simulated_v3_metrics", {}).get("active_best_background_gap"),
        "delta_active_gap": payload.get("delta_vs_reference", {}).get("active_best_background_gap"),
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Enhancement Line Validation Summary")
    lines.append("")
    lines.append(f"- Generated at: `{summary['generated_at_utc']}`")
    lines.append(
        "- Scope: Enhancement-line validation only. This does not modify or replace frozen benchmark/manuscript claims."
    )
    lines.append(
        "- Boundary: Current conclusions remain bounded to the enhancement line and the explicitly checked frozen literature-backed cases."
    )
    lines.append("")
    lines.append("## Current Enhancement State")
    lines.append("")
    lines.append(f"- Case: `{summary['current_state']['case_id']}`")
    lines.append(f"- Current label: `{summary['current_state']['latest_label']}`")
    lines.append(f"- Current best background: `{summary['current_state']['best_background']}`")
    lines.append(f"- Current active-best-background gap: `{summary['current_state']['active_best_background_gap']}`")
    lines.append(f"- Current shortlist ids: `{', '.join(summary['current_state']['shortlist_ids'])}`")
    lines.append("")
    lines.append("## Rule Audit")
    lines.append("")
    lines.append(
        f"- Reproduces comparison gap: `{summary['rule_audit']['reproduces_existing_comparison_gap']}`"
    )
    dominant = summary["rule_audit"]["dominant_current_panel_driver"]
    if dominant:
        lines.append(
            f"- Dominant current-panel driver: `{dominant['variant']}` with gap loss `{dominant['gap_loss_vs_current']}`"
        )
    material = summary["rule_audit"]["material_current_panel_drivers"]
    if material:
        material_bits = ", ".join(
            f"`{row['variant']}` ({row['gap_loss_vs_current']})" for row in material
        )
        lines.append(f"- Material current-panel drivers: {material_bits}")
    lines.append("")
    lines.append("## Cross-Case Compatibility")
    lines.append("")
    lines.append("| Case | Overall pass | Rank preserved | Shortlisted preserved | Shortlist not expanded | Gap delta vs reference |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for case_summary in summary["cross_case_checks"]:
        lines.append(
            f"| `{case_summary['case_id']}` | `{case_summary['overall_pass']}` | "
            f"`{case_summary['known_active_rank_preserved']}` | "
            f"`{case_summary['known_active_shortlisted_preserved']}` | "
            f"`{case_summary['shortlist_count_not_expanded']}` | "
            f"`{case_summary['delta_active_gap']}` |"
        )
    lines.append("")
    lines.append("## Decision Readout")
    lines.append("")
    lines.append(
        f"- Validation status: `{summary['decision']['validation_status']}`"
    )
    lines.append(
        f"- Recommended next action: `{summary['decision']['recommended_next_action']}`"
    )
    lines.append(
        f"- Tuning recommendation: `{summary['decision']['tuning_recommendation']}`"
    )
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

    comparison = read_json(report_dir / "enhancement_line_v2_vs_v3_comparison.json")
    trend = read_json(report_dir / "enhancement_line_trend_summary.json")
    audit = read_json(report_dir / "enhancement_line_rule_audit.json")

    cross_case_payloads = []
    for case_id in ("BRD4_BD1_LIT001", "BRD4_BD1_LIT002"):
        payload = load_optional_cross_case(report_dir, case_id)
        if payload is not None:
            cross_case_payloads.append(payload)

    cross_case_summaries = [summarize_cross_case(payload) for payload in cross_case_payloads]
    cross_case_summaries = [row for row in cross_case_summaries if row is not None]

    latest_snapshot = trend.get("latest_snapshot", {})
    enhancement_case = comparison.get("enhancement_case", {})
    current_state = {
        "case_id": enhancement_case.get("case_id"),
        "latest_label": latest_snapshot.get("label"),
        "best_background": enhancement_case.get("active_margin", {}).get("best_background_compound_id"),
        "active_best_background_gap": enhancement_case.get("active_margin", {}).get(
            "known_active_to_best_background_gap"
        ),
        "shortlist_ids": enhancement_case.get("shortlist_ids", []),
        "current_tuning": latest_snapshot.get("v3_tuning_snapshot", {}),
    }

    audit_summary = summarize_audit(audit)
    all_pass = all(row.get("overall_pass") for row in cross_case_summaries) if cross_case_summaries else False
    decision = {
        "validation_status": "bounded_cross_case_pass" if all_pass else "needs_more_validation",
        "recommended_next_action": (
            "pause_same_panel_tuning_and_expand_validation"
            if all_pass
            else "debug_failed_compatibility_before_more_tuning"
        ),
        "tuning_recommendation": (
            "do_not_continue_same_panel_tuning_until_a_new_case_or_cross-panel check is added"
            if all_pass
            else "hold_tuning_and_fix_compatibility_first"
        ),
    }

    summary = {
        "generated_at_utc": audit.get("generated_at_utc") or latest_snapshot.get("archived_at_utc"),
        "scope_note": "Enhancement-line validation only. This does not modify or replace frozen benchmark/manuscript claims.",
        "current_state": current_state,
        "rule_audit": audit_summary,
        "cross_case_checks": cross_case_summaries,
        "decision": decision,
        "boundary_notes": [
            "Current enhancement evidence remains bounded to the enhancement line and explicitly checked frozen literature-backed cases.",
            "The current rule audit is still single-panel and should not be generalized as a cross-target or broadly general benchmark claim.",
            "Cross-case compatibility passes indicate bounded stability, not universal improvement.",
        ],
    }

    output_json = (project_root / args.output_json).resolve()
    output_md = (project_root / args.output_md).resolve()
    write_json(output_json, summary)
    write_text(output_md, build_markdown(summary))
    print(f"[validation-summary] wrote json: {output_json}")
    print(f"[validation-summary] wrote markdown: {output_md}")


if __name__ == "__main__":
    main()
