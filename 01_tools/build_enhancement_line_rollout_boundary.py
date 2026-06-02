#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a formal rollout-boundary summary for the enhancement line."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_line_rollout_boundary.json",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_line_rollout_boundary.md",
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
    lines.append("# Enhancement Line Rollout Boundary")
    lines.append("")
    lines.append(f"- Generated at: `{summary['generated_at_utc']}`")
    lines.append("- Scope: rollout-policy summary for the enhancement line only.")
    lines.append("- Boundary: this document does not alter frozen manuscript / benchmark claims or default frozen workflow policy.")
    lines.append("")
    lines.append("## Current Rollout Decision")
    lines.append("")
    lines.append(f"- Rollout status: `{summary['rollout_status']}`")
    lines.append(f"- Current decision: `{summary['current_decision']}`")
    lines.append(f"- Headline: `{summary['bounded_headline']}`")
    lines.append("")
    lines.append("## Allowed Rollout Levels")
    lines.append("")
    for item in summary["allowed_rollout_levels"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Blocked Rollout Levels")
    lines.append("")
    for item in summary["blocked_rollout_levels"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Current Evidence Boundary")
    lines.append("")
    lines.append(f"- Material-on-panel cases: `{', '.join(summary['material_cases']) if summary['material_cases'] else 'none'}`")
    lines.append(f"- Weak-on-panel cases: `{', '.join(summary['weak_cases']) if summary['weak_cases'] else 'none'}`")
    lines.append(f"- Failed shortlist-preservation cases: `{', '.join(summary['failed_cases']) if summary['failed_cases'] else 'none'}`")
    lines.append(f"- Non-BRD4 checked surfaces: `{', '.join(summary['non_brd4_cases']) if summary['non_brd4_cases'] else 'none'}`")
    lines.append("")
    lines.append("## Current Gating Policy")
    lines.append("")
    lines.append(f"- Gating mode: `{summary['gating_mode']}`")
    lines.append(f"- Coverage threshold: `{summary['coverage_threshold']}`")
    lines.append(f"- Gated penalties: `{', '.join(summary['gated_penalties'])}`")
    lines.append(f"- Ungated v3 terms: `{', '.join(summary['ungated_terms'])}`")
    lines.append("")
    lines.append("## Preconditions For Broader Rollout")
    lines.append("")
    for item in summary["preconditions_for_broader_rollout"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Stop Conditions")
    lines.append("")
    for item in summary["stop_conditions"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## References")
    lines.append("")
    for key, value in summary["references"].items():
        lines.append(f"- `{key}` -> `{value}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()

    baseline = read_json(project_root / "09_reports" / "enhancement_line_baseline_package.json")
    gating = read_json(
        project_root / "09_reports" / "enhancement_case_aware_gating_implementation_summary.json"
    )
    readiness = read_json(project_root / "09_reports" / "enhancement_expansion_readiness.json")
    promotion_review = read_json_optional(project_root / "09_reports" / "enhancement_boundary_promotion_review_BRD3.json")

    gating_policy = gating.get("gating", {})
    threshold_note = gating.get("threshold_note", {})
    promotion_decision = (promotion_review or {}).get("decision", {})
    has_interim_promotion = bool(promotion_decision.get("retire_brd4_only_internal_reading"))

    summary = {
        "generated_at_utc": baseline.get("generated_at_utc"),
        "rollout_status": (
            "enhancement_line_interim_brd4_brd3_boundary_with_challenges_logged"
            if has_interim_promotion and baseline.get("failed_cases")
            else (
                "enhancement_line_boundary_fixed_with_challenge_logged"
                if baseline.get("failed_cases")
                else "enhancement_line_boundary_fixed"
            )
        ),
        "current_decision": (
            "promote_to_interim_brd4_brd3_boundary__block_full_bet_family_claim"
            if has_interim_promotion
            else (
                "maintain_existing_boundary__exclude_failed_surfaces_from_rollout_evidence"
                if baseline.get("failed_cases")
                else "allow_enhancement_line_rollout_only__block_frozen_promotion"
            )
        ),
        "bounded_headline": baseline.get("bounded_headline"),
        "allowed_rollout_levels": [
            "Use the current v3 + case-aware gating only inside the enhancement line and isolated enhancement roots.",
            "Use the current package as the audit/handoff baseline for future bounded validation surfaces.",
            (
                "Use the interim BRD4+BRD3 I-BET762-focused material evidence as a bounded enhancement-line boundary, not as a full BET-family claim."
                if has_interim_promotion
                else "Use current weak_on_panel non-BRD4 behavior as evidence that panel-specific penalties remain bounded rather than cross-target default policy."
            ),
        ],
        "blocked_rollout_levels": [
            "Do not promote current v3 behavior into frozen manuscript claims or frozen benchmark headline results.",
            "Do not switch the frozen default reranking backend from v2 to v3 on the basis of the current enhancement evidence.",
            "Do not describe the current enhancement package as a cross-target general improvement.",
            "Do not describe the interim BRD4+BRD3 evidence as full BET-family validation.",
        ],
        "material_cases": baseline.get("material_cases", []),
        "weak_cases": baseline.get("weak_cases", []),
        "failed_cases": baseline.get("failed_cases", []),
        "non_brd4_cases": baseline.get("non_brd4_cases", []),
        "gating_mode": "case_aware_two_mode_gate",
        "coverage_threshold": threshold_note.get("background_flag_coverage_threshold", 0.8),
        "gated_penalties": gating_policy.get("gated_penalties", []),
        "ungated_terms": gating_policy.get("ungated_terms", []),
        "preconditions_for_broader_rollout": [
            "Keep the frozen line untouched while broader rollout remains unapproved.",
            "Require additional bounded validation that materially strengthens the evidence boundary before any frozen/default promotion is considered.",
            "Require that any broader rollout proposal still preserves case-level explainability, rollback ability, and bounded wording.",
            "Treat the current threshold and gating policy as enhancement-line empirical policy until separately validated.",
            "Resolve any shortlist/rank preservation failures before using a new surface to expand the rollout boundary.",
        ],
        "stop_conditions": [
            "Stop any broader rollout attempt if a new bounded validation surface loses known-active shortlist/rank preservation.",
            "Stop any broader rollout attempt if non-BRD4 surfaces begin showing uncontrolled penalty-driven behavior inconsistent with weak_on_panel audits.",
            "Stop any broader rollout attempt if the boundary can no longer be stated more narrowly than a cross-target claim.",
            "Stop any broader rollout attempt if a failed shortlist-preservation surface is being counted as material rollout evidence.",
        ],
        "references": {
            "baseline_package": "09_reports/enhancement_line_baseline_package.md",
            "gating_implementation_summary": "09_reports/enhancement_case_aware_gating_implementation_summary.md",
            "multi_case_validation_summary": "09_reports/enhancement_multi_case_validation_summary.md",
            "non_brd4_validation_summary": "09_reports/enhancement_non_brd4_bounded_validation_summary.md",
            "expansion_readiness": "09_reports/enhancement_expansion_readiness.md",
            "boundary_promotion_review_brd3": "09_reports/enhancement_boundary_promotion_review_BRD3.md",
        },
        "recommended_next_action": readiness.get("recommended_next_action"),
    }

    output_json = (project_root / args.output_json).resolve()
    output_md = (project_root / args.output_md).resolve()
    write_json(output_json, summary)
    write_text(output_md, build_markdown(summary))
    print(f"[rollout-boundary] wrote json: {output_json}")
    print(f"[rollout-boundary] wrote markdown: {output_md}")


if __name__ == "__main__":
    main()
