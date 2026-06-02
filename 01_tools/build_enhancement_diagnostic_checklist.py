#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a compact case-level diagnostic checklist for the enhancement line."
    )
    parser.add_argument(
        "--comparison-json",
        default="09_reports/enhancement_line_v2_vs_v3_comparison.json",
        help="Enhancement comparison JSON",
    )
    parser.add_argument(
        "--tracker-json",
        default="09_reports/enhancement_line_iteration_tracker.json",
        help="Enhancement iteration tracker JSON",
    )
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_line_diagnostic_checklist.json",
        help="Checklist JSON output path",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_line_diagnostic_checklist.md",
        help="Checklist markdown output path",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def find_preview_row(top_preview: list[dict[str, object]], compound_id: str) -> dict[str, object]:
    return next((row for row in top_preview if row.get("compound_id") == compound_id), {})


def build_checklist(comparison: dict[str, object], tracker: dict[str, object]) -> dict[str, object]:
    baseline = comparison["baseline_case"]
    enhancement = comparison["enhancement_case"]
    enhancement_diag = enhancement.get("rerank_diagnostics", {})
    top_preview = enhancement_diag.get("top_preview", [])
    if not isinstance(top_preview, list):
        top_preview = []

    enhancement_margin = enhancement.get("active_margin", {})
    best_background_id = str(enhancement_margin.get("best_background_compound_id", ""))
    best_background_preview = find_preview_row(top_preview, best_background_id)

    tracker_metrics = tracker.get("headline_metrics", {})
    tracker_shortlist = tracker.get("shortlist_behavior", {})
    tracker_decision = tracker.get("decision", {})

    comparison_gap = enhancement_margin.get("known_active_to_best_background_gap")
    tracker_gap = tracker_metrics.get("enhancement_active_best_background_gap")
    comparison_shortlist_count = enhancement.get("shortlist_count")
    tracker_shortlist_count = tracker_shortlist.get("enhancement_shortlist_count")

    consistency_checks = {
        "active_margin_matches_tracker": comparison_gap == tracker_gap,
        "shortlist_count_matches_tracker": comparison_shortlist_count == tracker_shortlist_count,
        "known_active_shortlisted_matches_tracker": (
            enhancement_margin.get("known_active_shortlisted")
            == tracker_shortlist.get("enhancement_known_active_shortlisted")
        ),
    }

    quality_gates = {
        "known_active_remains_rank_1": enhancement_margin.get("known_active_rank") == 1,
        "known_active_still_shortlisted": bool(enhancement_margin.get("known_active_shortlisted")),
        "active_margin_improved": bool(tracker_decision.get("did_active_margin_improve")),
        "shortlist_compressed": bool(tracker_decision.get("did_shortlist_compress")),
        "best_background_explained": bool(best_background_preview.get("physchem_flags"))
        or bool(best_background_preview.get("physchem_snapshot")),
        "diagnostic_outputs_consistent": all(consistency_checks.values()),
    }

    attention_items: list[str] = []
    if not quality_gates["known_active_remains_rank_1"]:
        attention_items.append("Known active is no longer rank 1 in the enhancement case.")
    if not quality_gates["known_active_still_shortlisted"]:
        attention_items.append("Known active dropped out of the shortlist.")
    if not quality_gates["active_margin_improved"]:
        attention_items.append("Active-best-background gap did not improve versus baseline.")
    if not quality_gates["shortlist_compressed"]:
        attention_items.append("Shortlist compression did not improve versus baseline.")
    if not quality_gates["best_background_explained"]:
        attention_items.append("Best background still lacks interpretable physchem flags/snapshot.")
    if not quality_gates["diagnostic_outputs_consistent"]:
        attention_items.append("Comparison and tracker outputs are out of sync.")

    overall_status = "healthy" if not attention_items else "needs_attention"

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_files": {
            "comparison_json": "09_reports/enhancement_line_v2_vs_v3_comparison.json",
            "tracker_json": "09_reports/enhancement_line_iteration_tracker.json",
        },
        "scope": {
            "baseline_case_id": baseline["case_id"],
            "enhancement_case_id": enhancement["case_id"],
        },
        "headline": {
            "baseline_active_best_background_gap": baseline.get("active_margin", {}).get(
                "known_active_to_best_background_gap"
            ),
            "enhancement_active_best_background_gap": comparison_gap,
            "enhancement_shortlist_count": comparison_shortlist_count,
            "enhancement_shortlist_ids": enhancement.get("shortlist_ids", []),
            "best_background_compound_id": best_background_id,
        },
        "best_background_diagnostic": {
            "compound_id": best_background_preview.get("compound_id", best_background_id),
            "docking_core": best_background_preview.get("docking_core"),
            "physchem_penalty": best_background_preview.get("physchem_penalty"),
            "physchem_flags": best_background_preview.get("physchem_flags", []),
            "physchem_snapshot": best_background_preview.get("physchem_snapshot", {}),
        },
        "consistency_checks": consistency_checks,
        "quality_gates": quality_gates,
        "attention_items": attention_items,
        "overall_status": overall_status,
        "recommendation": (
            "Continue enhancement-line tuning; current outputs are aligned and explanatory."
            if overall_status == "healthy"
            else "Repair output consistency or missing diagnostics before further tuning."
        ),
    }


def build_markdown(payload: dict[str, object]) -> str:
    scope = payload["scope"]
    headline = payload["headline"]
    best_bg = payload["best_background_diagnostic"]
    consistency = payload["consistency_checks"]
    gates = payload["quality_gates"]
    attention_items = payload["attention_items"]
    lines = [
        "# Enhancement Line Diagnostic Checklist",
        "",
        f"- Generated at: `{payload['generated_at_utc']}`",
        f"- Baseline case: `{scope['baseline_case_id']}`",
        f"- Enhancement case: `{scope['enhancement_case_id']}`",
        "",
        "## Headline",
        "",
        f"- Baseline active-best-background gap: `{headline['baseline_active_best_background_gap']}`",
        f"- Enhancement active-best-background gap: `{headline['enhancement_active_best_background_gap']}`",
        f"- Enhancement shortlist count: `{headline['enhancement_shortlist_count']}`",
        f"- Enhancement shortlist ids: `{', '.join(headline['enhancement_shortlist_ids'])}`",
        f"- Current best background: `{headline['best_background_compound_id']}`",
        "",
        "## Best Background Diagnostic",
        "",
        f"- `compound_id = {best_bg.get('compound_id')}`",
        f"- `docking_core = {best_bg.get('docking_core')}`",
        f"- `physchem_penalty = {best_bg.get('physchem_penalty')}`",
        f"- `physchem_flags = {', '.join(best_bg.get('physchem_flags', [])) or 'none'}`",
        f"- `physchem_snapshot = {json.dumps(best_bg.get('physchem_snapshot', {}), sort_keys=True)}`",
        "",
        "## Consistency Checks",
        "",
        f"- `active_margin_matches_tracker = {consistency['active_margin_matches_tracker']}`",
        f"- `shortlist_count_matches_tracker = {consistency['shortlist_count_matches_tracker']}`",
        f"- `known_active_shortlisted_matches_tracker = {consistency['known_active_shortlisted_matches_tracker']}`",
        "",
        "## Quality Gates",
        "",
        f"- `known_active_remains_rank_1 = {gates['known_active_remains_rank_1']}`",
        f"- `known_active_still_shortlisted = {gates['known_active_still_shortlisted']}`",
        f"- `active_margin_improved = {gates['active_margin_improved']}`",
        f"- `shortlist_compressed = {gates['shortlist_compressed']}`",
        f"- `best_background_explained = {gates['best_background_explained']}`",
        f"- `diagnostic_outputs_consistent = {gates['diagnostic_outputs_consistent']}`",
        "",
        "## Attention Items",
        "",
    ]
    if attention_items:
        lines.extend([f"- {item}" for item in attention_items])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- {payload['recommendation']}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    comparison = load_json(Path(args.comparison_json))
    tracker = load_json(Path(args.tracker_json))
    checklist = build_checklist(comparison, tracker)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_json, checklist)
    output_md.write_text(build_markdown(checklist), encoding="utf-8")
    print(f"[diagnostic-checklist] wrote json: {output_json}")
    print(f"[diagnostic-checklist] wrote markdown: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
