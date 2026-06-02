#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a formal handoff package for the current enhancement-line boundary."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_line_handoff_package.json",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_line_handoff_package.md",
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


def format_case_list(case_ids: list[str]) -> str:
    return ", ".join(case_ids) if case_ids else "none"


def build_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Enhancement Line Handoff Package")
    lines.append("")
    lines.append(f"- Generated at: `{summary['generated_at_utc']}`")
    lines.append("- Scope: handoff package for the enhancement line only.")
    lines.append("- Boundary: this package must not alter frozen manuscript, frozen benchmark, or frozen default-policy claims.")
    lines.append("")
    lines.append("## Handoff Status")
    lines.append("")
    lines.append(f"- Handoff status: `{summary['handoff_status']}`")
    lines.append(f"- Approval status: `{summary['approval_status']}`")
    lines.append(f"- Default handoff state: `{summary['default_handoff_state']}`")
    lines.append(f"- Frozen line untouched: `{summary['frozen_line_untouched']}`")
    lines.append(f"- Current bounded headline: `{summary['bounded_headline']}`")
    lines.append(f"- Current rollout decision: `{summary['rollout_decision']}`")
    lines.append("")
    lines.append("## Stable Boundary")
    lines.append("")
    lines.append(f"- Material-on-panel cases: `{format_case_list(summary['material_cases'])}`")
    lines.append(f"- Weak-on-panel cases: `{format_case_list(summary['weak_cases'])}`")
    lines.append(f"- Failed shortlist-preservation cases: `{format_case_list(summary['failed_cases'])}`")
    lines.append(f"- Non-BRD4 bounded surfaces: `{format_case_list(summary['non_brd4_cases'])}`")
    lines.append(f"- Surface inventory: `{summary['surface_inventory']['total_surfaces']} total / {summary['surface_inventory']['material_surface_count']} material / {summary['surface_inventory']['weak_surface_count']} weak / {summary['surface_inventory']['failed_surface_count']} failed`")
    lines.append("")
    lines.append("## Safe Reading")
    lines.append("")
    for item in summary["safe_reading"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Boundary Warnings")
    lines.append("")
    for item in summary["boundary_warnings"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Operator Rules")
    lines.append("")
    for item in summary["operator_rules"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Recommended Next Moves")
    lines.append("")
    for item in summary["recommended_next_moves"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Approved Operating Rules")
    lines.append("")
    for item in summary["approved_operating_rules"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Primary References")
    lines.append("")
    for item in summary["primary_references"]:
        lines.append(f"- `{item['label']}` -> `{item['path']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    report_dir = project_root / "09_reports"

    baseline = read_json(report_dir / "enhancement_line_baseline_package.json")
    rollout = read_json(report_dir / "enhancement_line_rollout_boundary.json")
    gating = read_json(report_dir / "enhancement_case_aware_gating_implementation_summary.json")
    multi = read_json(report_dir / "enhancement_multi_case_validation_summary.json")
    non_brd4 = read_json(report_dir / "enhancement_non_brd4_bounded_validation_summary.json")
    readiness = read_json(report_dir / "enhancement_expansion_readiness.json")
    promotion_review_path = report_dir / "enhancement_boundary_promotion_review_BRD3.json"
    promotion_review = read_json(promotion_review_path) if promotion_review_path.exists() else {}

    material_cases = baseline.get("material_cases", [])
    weak_cases = baseline.get("weak_cases", [])
    failed_cases = baseline.get("failed_cases", [])
    non_brd4_cases = baseline.get("non_brd4_cases", [])
    weak_non_brd4_cases = [case_id for case_id in weak_cases if not case_id.startswith("BRD4_")]
    promotion_decision = promotion_review.get("decision", {})
    has_interim_promotion = bool(promotion_decision.get("retire_brd4_only_internal_reading"))

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "handoff_status": "formal_enhancement_line_handoff_ready",
        "approval_status": "approved",
        "default_handoff_state": True,
        "frozen_line_untouched": baseline.get("frozen_line_untouched", True),
        "bounded_headline": baseline.get("bounded_headline"),
        "rollout_decision": rollout.get("current_decision"),
        "material_cases": material_cases,
        "weak_cases": weak_cases,
        "failed_cases": failed_cases,
        "non_brd4_cases": non_brd4_cases,
        "surface_inventory": {
            "total_surfaces": len(material_cases) + len(weak_cases) + len(failed_cases),
            "material_surface_count": len(material_cases),
            "weak_surface_count": len(weak_cases),
            "failed_surface_count": len(failed_cases),
            "non_brd4_surface_count": len(non_brd4_cases),
        },
        "safe_reading": [
            f"Current enhancement evidence is strongest on `{format_case_list(material_cases)}`.",
            (
                f"BRD3 I-BET762-focused surfaces support the interim reading `{promotion_decision.get('recommended_interim_headline')}`."
                if has_interim_promotion
                else f"Rollout-eligible non-BRD4 surfaces `{format_case_list(weak_non_brd4_cases)}` remain weak_on_panel, which supports the current restrained outside-BRD4 reading."
            ),
            (
                f"Boundary-challenge surfaces `{format_case_list(failed_cases)}` currently fail known-active shortlist/rank preservation and are excluded from rollout-safe evidence."
                if failed_cases
                else "Known-active shortlist and rank preservation remain intact across the currently checked enhancement-only surfaces."
            ),
            "Current case-aware gating should be read as bounded, panel-aware enhancement-line behavior rather than as a generally validated upgrade.",
        ],
        "boundary_warnings": [
            "Do not promote the current v3 package into frozen manuscript or frozen benchmark claims.",
            "Do not switch the frozen default reranking backend from v2 to v3 using the current evidence alone.",
            "Do not describe current non-BRD4 gains as cross-target generalization while material evidence is still limited to BRD3 I-BET762-focused surfaces and challenge cases remain unresolved.",
            "Do not describe the interim BRD4+BRD3 evidence as full BET-family validation.",
            "Treat the current coverage threshold and gating policy as enhancement-line empirical policy until separately validated.",
            "Do not count failed shortlist-preservation surfaces as rollout-safe material evidence.",
        ],
        "operator_rules": [
            "Keep frozen cases and frozen reporting layers untouched.",
            "Use the current enhancement line only inside isolated enhancement roots and bounded validation workflows.",
            "Prefer new bounded validation surfaces or handoff-quality summaries over additional same-panel tuning.",
            "If a new surface loses known-active shortlist or rank preservation, stop and reassess before expanding claims or rollout scope.",
        ],
        "recommended_next_moves": [
            "Use this handoff package as the default starting point for future bounded validation work.",
            "Do not continue same-panel tuning on the current BRD4 surfaces.",
            "Review and disposition any failed shortlist-preservation surface before using it to expand the approved boundary.",
            "If validation continues after that review, prefer a low-variable, literature-backed, non-BRD4 new surface.",
            "If a pause is needed, hand off using the baseline package, rollout boundary, and this handoff package together.",
            f"Source readiness signal at the last readiness rebuild was `{readiness.get('recommended_next_action')}`, but this handoff package should now be read under the current rollout boundary.",
        ],
        "approved_operating_rules": [
            "Treat this JSON as the current default enhancement-line handoff state.",
            "Keep frozen manuscript and frozen benchmark layers untouched.",
            "Do not promote v3 into the frozen default backend on the basis of current evidence.",
            "Treat non-BRD4 surfaces outside the approved BRD3 I-BET762-focused set as weak_on_panel or challenge evidence unless future bounded validation materially changes that reading.",
            "Treat the BRD4+BRD3 I-BET762-focused boundary as the current approved interim enhancement-line reading, not as a frozen or full-family policy.",
            "Exclude failed shortlist-preservation surfaces from the approved rollout-safe evidence set until separately resolved.",
        ],
        "primary_references": [
            {
                "label": "baseline_package",
                "path": "09_reports/enhancement_line_baseline_package.md",
            },
            {
                "label": "rollout_boundary",
                "path": "09_reports/enhancement_line_rollout_boundary.md",
            },
            {
                "label": "gating_implementation_summary",
                "path": "09_reports/enhancement_case_aware_gating_implementation_summary.md",
            },
            {
                "label": "multi_case_validation_summary",
                "path": "09_reports/enhancement_multi_case_validation_summary.md",
            },
            {
                "label": "non_brd4_bounded_validation_summary",
                "path": "09_reports/enhancement_non_brd4_bounded_validation_summary.md",
            },
            {
                "label": "boundary_promotion_review_brd3",
                "path": "09_reports/enhancement_boundary_promotion_review_BRD3.md",
            },
        ],
        "source_snapshots": {
            "baseline_generated_at": baseline.get("generated_at_utc"),
            "rollout_generated_at": rollout.get("generated_at_utc"),
            "gating_generated_at": gating.get("generated_at_utc"),
            "multi_case_generated_at": multi.get("generated_at_utc"),
            "non_brd4_generated_at": non_brd4.get("generated_at_utc"),
            "readiness_generated_at": readiness.get("generated_at_utc"),
            "promotion_review_generated_at": promotion_review.get("generated_at"),
        },
    }

    output_json = project_root / args.output_json
    output_md = project_root / args.output_md
    write_json(output_json, summary)
    write_text(output_md, build_markdown(summary))
    print(f"[handoff-package] wrote json: {output_json}")
    print(f"[handoff-package] wrote markdown: {output_md}")


if __name__ == "__main__":
    main()
