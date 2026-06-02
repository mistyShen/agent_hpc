#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a multi-case enhancement validation summary bounded to enhancement-only evidence."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_multi_case_validation_summary.json",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_multi_case_validation_summary.md",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_optional(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return read_json(path)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


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

    known_active_rank = first_non_none(current.get("known_active_rank"), (case_summary or {}).get("known_active_rank"))
    known_active_shortlisted = first_non_none(
        current.get("known_active_shortlisted"),
        (case_summary or {}).get("known_active_shortlisted"),
    )
    shortlist_count = first_non_none(current.get("shortlist_count"), (case_summary or {}).get("shortlist_count"))
    best_background_compound_id = first_non_none(
        current.get("best_background_compound_id"),
        (case_summary or {}).get("best_background_compound_id"),
    )
    active_best_background_gap = first_non_none(
        current.get("active_best_background_gap"),
        (case_summary or {}).get("active_best_background_gap"),
    )
    known_active_compound_id = first_non_none(
        current.get("known_active_compound_id"),
        (case_summary or {}).get("known_active_compound_id"),
    )

    failure_reasons: list[str] = []
    if not known_active_shortlisted:
        failure_reasons.append("known_active_not_shortlisted")
    if (shortlist_count or 0) < 1:
        failure_reasons.append("empty_shortlist")
    if known_active_rank != 1:
        failure_reasons.append("known_active_rank_not_top1")

    rollout_preserved = not failure_reasons

    if not rollout_preserved:
        effect_class = "failed_shortlist_preservation"
        interpretation = "Current v3 rerank separation may improve, but this surface fails bounded rollout criteria because known-active shortlist/rank preservation is not intact."
    elif positive:
        effect_class = "material_on_panel"
        interpretation = "Current v3 penalties materially widen the active-best-background gap on this focused panel."
    else:
        effect_class = "weak_on_panel"
        interpretation = "Current v3 penalties preserve shortlist/rank on this panel, but the audited penalty family does not materially change the gap."

    top_preview = case_summary.get("top_rerank", []) if case_summary else current.get("top_rerank", [])

    return {
        "case_id": case_id,
        "known_active_compound_id": known_active_compound_id,
        "known_active_rank": known_active_rank,
        "known_active_shortlisted": known_active_shortlisted,
        "shortlist_count": shortlist_count,
        "best_background_compound_id": best_background_compound_id,
        "active_best_background_gap": active_best_background_gap,
        "best_background_flags": current.get("best_background_flags", []),
        "rollout_preserved": rollout_preserved,
        "failure_reasons": failure_reasons,
        "effect_class": effect_class,
        "dominant_driver": dominant,
        "material_drivers": material,
        "interpretation": interpretation,
        "top_rerank_preview": top_preview[:3],
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Enhancement Multi-Case Validation Summary")
    lines.append("")
    lines.append(f"- Generated at: `{summary['generated_at_utc']}`")
    lines.append("- Scope: Enhancement-line synthesis only. This does not modify or replace frozen benchmark/manuscript claims.")
    lines.append("- Boundary: Conclusions below are limited to the explicitly checked enhancement-only surfaces and bounded frozen-case compatibility checks.")
    lines.append("")
    lines.append("## Current Readout")
    lines.append("")
    lines.append(f"- Current validation status: `{summary['current_validation_status']}`")
    lines.append(f"- Expansion readiness: `{summary['expansion_readiness']}`")
    lines.append(f"- Recommended next action: `{summary['recommended_next_action']}`")
    lines.append("")
    lines.append("## Case Table")
    lines.append("")
    lines.append("| Case | Known active | Shortlist count | Rollout preserved | Best background | Active-best-background gap | Effect class | Dominant driver |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for case in summary["cases"]:
        dominant = case.get("dominant_driver") or {}
        lines.append(
            f"| `{case['case_id']}` | `{case['known_active_compound_id']}` | `{case['shortlist_count']}` | `{case['rollout_preserved']}` | "
            f"`{case['best_background_compound_id']}` | `{case['active_best_background_gap']}` | "
            f"`{case['effect_class']}` | `{dominant.get('variant_name', 'none')}` |"
        )
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


def candidate_audit_paths(report_dir: Path, case_id: str) -> list[Path]:
    base_case = case_id.removesuffix("_V3EXP")
    short_suffix = base_case.split("_")[-1]
    candidates = [
        report_dir / f"enhancement_line_rule_audit_{base_case}.json",
        report_dir / f"enhancement_line_rule_audit_{short_suffix}.json",
        report_dir / "enhancement_line_rule_audit.json",
    ]
    seen: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.append(path)
    return seen


def discover_cases(project_root: Path, report_dir: Path) -> list[dict[str, Any]]:
    case_rows = read_tsv(project_root / "04_metadata" / "benchmark_cases.tsv")
    discovered: list[dict[str, Any]] = []
    for row in case_rows:
        case_id = row.get("case_id", "")
        if row.get("enabled", "").lower() != "true":
            continue
        if row.get("rerank_strategy") != "ai_rerank_v3":
            continue
        case_summary_path = report_dir / f"enhancement_case_{case_id}_summary.json"
        if not case_summary_path.exists():
            continue
        audit_path = next((path for path in candidate_audit_paths(report_dir, case_id) if path.exists()), None)
        if audit_path is None:
            continue
        discovered.append(
            {
                "case_id": case_id,
                "case_summary": read_json(case_summary_path),
                "audit": read_json(audit_path),
            }
        )
    discovered.sort(key=lambda item: item["case_id"])
    return discovered


def review_case_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    v3 = evidence["v3"]
    case_id = evidence["enhancement_case_id"]
    return {
        "case_id": case_id,
        "known_active_compound_id": evidence["known_active"],
        "known_active_rank": v3["best_known_active_rank"],
        "known_active_shortlisted": v3["shortlist_contains_known_active"],
        "shortlist_count": v3["shortlist_count"],
        "best_background_compound_id": v3["best_background"],
        "active_best_background_gap": v3["active_best_background_gap"],
        "best_background_flags": [],
        "rollout_preserved": True,
        "failure_reasons": [],
        "effect_class": "material_on_panel",
        "dominant_driver": {
            "variant_name": "promotion_review_material_signal",
            "gap_loss_vs_current": None,
            "contribution_class": "review_supported_material_signal",
        },
        "material_drivers": [],
        "interpretation": "Promotion review classifies this surface as a shortlist-preserving material signal.",
        "top_rerank_preview": [],
        "evidence_source": "09_reports/enhancement_boundary_promotion_review_BRD3.json",
    }


def append_promotion_review_cases(cases: list[dict[str, Any]], review: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not review or not review.get("decision", {}).get("retire_brd4_only_internal_reading"):
        return cases
    existing = {case["case_id"] for case in cases}
    expanded = list(cases)
    for evidence in review.get("positive_evidence", []):
        case_id = evidence.get("enhancement_case_id")
        if case_id and case_id not in existing:
            expanded.append(review_case_summary(evidence))
            existing.add(case_id)
    expanded.sort(key=lambda item: item["case_id"])
    return expanded


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    report_dir = project_root / "09_reports"

    readiness = read_json(report_dir / "enhancement_expansion_readiness.json")
    promotion_review = read_json_optional(report_dir / "enhancement_boundary_promotion_review_BRD3.json")
    discovered = discover_cases(project_root, report_dir)
    cases = [
        summarize_case(item["case_id"], item["audit"], item["case_summary"])
        for item in discovered
    ]
    cases = append_promotion_review_cases(cases, promotion_review)

    material_cases = [case["case_id"] for case in cases if case["effect_class"] == "material_on_panel"]
    weak_cases = [case["case_id"] for case in cases if case["effect_class"] == "weak_on_panel"]
    failed_cases = [case["case_id"] for case in cases if case["effect_class"] == "failed_shortlist_preservation"]
    non_brd4_cases = [case["case_id"] for case in cases if not case["case_id"].startswith("BRD4_")]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "current_validation_status": (
            "bounded_multi_surface_readout_with_boundary_challenge"
            if failed_cases
            else "bounded_multi_surface_readout"
        ),
        "expansion_readiness": readiness.get("expansion_readiness"),
        "recommended_next_action": "pause_same_panel_tuning_and_expand_validation_or_prepare_rollout_boundary",
        "cases": cases,
        "synthesis_notes": [
            f"Current v3 behavior remains panel-sensitive across the checked enhancement-only surfaces: material on `{', '.join(material_cases) if material_cases else 'none'}`, weak on `{', '.join(weak_cases) if weak_cases else 'none'}`.",
            (
                f"Boundary-challenge surfaces `{', '.join(failed_cases)}` currently improve rerank separation but fail shortlist/rank preservation, so they are excluded from rollout-safe material evidence."
                if failed_cases
                else "The checked enhancement-only surfaces still preserve known-active shortlist/rank behavior while showing different margin gains depending on panel composition."
            ),
            (
                f"Non-BRD4 bounded surfaces are now present (`{', '.join(non_brd4_cases)}`), but they should still be read as bounded evidence rather than cross-target generalization."
                if non_brd4_cases
                else "No non-BRD4 enhancement-only surface has been summarized into this multi-case view yet."
            ),
            (
                f"The BRD3 promotion review supports the interim boundary `{promotion_review.get('decision', {}).get('recommended_interim_headline')}` while still rejecting a full BET-family headline."
                if promotion_review
                else "No promotion review override is currently attached to this summary."
            ),
            "The current penalty family should therefore still be treated as enhancement-line, bounded, and panel-aware rather than as a generally validated improvement.",
        ],
        "boundary_notes": [
            "This summary remains bounded to the enhancement line and the explicitly checked literature-backed enhancement-only surfaces.",
            "Material results on BRD4 and BRD3 I-BET762-focused surfaces should not yet be generalized as full BET-family, cross-target, or universal reranking improvement.",
            "Weak-on-panel behavior on checked enhancement-only surfaces remains evidence against broad claims and in favor of bounded rollout logic.",
            "Any surface that fails known-active shortlist/rank preservation must be treated as a boundary challenge rather than as rollout-safe evidence.",
        ],
    }

    output_json = project_root / args.output_json
    output_md = project_root / args.output_md
    write_json(output_json, summary)
    write_text(output_md, build_markdown(summary))


if __name__ == "__main__":
    main()
