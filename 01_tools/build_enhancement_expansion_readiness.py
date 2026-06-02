#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize whether the enhancement line is ready to expand beyond the current focused panel."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_expansion_readiness.json",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_expansion_readiness.md",
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


def build_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Enhancement Expansion Readiness")
    lines.append("")
    lines.append(f"- Generated at: `{summary['generated_at_utc']}`")
    lines.append("- Scope: Planning/readiness only. This does not change enhancement tuning or frozen benchmark/manuscript claims.")
    lines.append("")
    lines.append("## Current Validation Position")
    lines.append("")
    lines.append(f"- Validation status: `{summary['validation_status']}`")
    lines.append(f"- Material-on-panel cases: `{', '.join(summary['material_cases']) if summary['material_cases'] else 'none'}`")
    lines.append(f"- Weak-on-panel cases: `{', '.join(summary['weak_cases']) if summary['weak_cases'] else 'none'}`")
    lines.append(f"- Failed shortlist-preservation cases: `{', '.join(summary['failed_cases']) if summary['failed_cases'] else 'none'}`")
    lines.append(f"- Non-BRD4 enhancement-only cases: `{', '.join(summary['non_brd4_cases']) if summary['non_brd4_cases'] else 'none'}`")
    lines.append("")
    lines.append("## Existing Case Inventory")
    lines.append("")
    lines.append(f"- Enabled literature-backed cases in metadata: `{summary['enabled_literature_backed_cases_count']}`")
    for row in summary["enabled_literature_backed_cases"]:
        lines.append(
            f"- `{row['case_id']}` -> target `{row['target_id']}`, library `{row['library_id']}`, rerank `{row['rerank_strategy']}`"
        )
    lines.append("")
    lines.append("## Expansion Readiness")
    lines.append("")
    lines.append(f"- Additional non-frozen literature-backed case already present: `{summary['has_additional_nonfrozen_case']}`")
    lines.append(f"- Expansion readiness: `{summary['expansion_readiness']}`")
    lines.append(f"- Recommended next action: `{summary['recommended_next_action']}`")
    lines.append("")
    lines.append("## Constraints")
    lines.append("")
    for item in summary["constraints"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()

    cases = read_tsv(project_root / "04_metadata" / "benchmark_cases.tsv")
    validation = read_json(project_root / "09_reports" / "enhancement_multi_case_validation_summary.json")
    promotion_review = read_json_optional(project_root / "09_reports" / "enhancement_boundary_promotion_review_BRD3.json")

    enabled_literature_cases = [
        row
        for row in cases
        if row.get("enabled", "").lower() == "true" and row.get("case_type") == "literature_backed"
    ]
    nonfrozen_candidates = [
        row
        for row in enabled_literature_cases
        if row["case_id"] not in {"BRD4_BD1_LIT001", "BRD4_BD1_LIT002", "BRD4_BD1_LIT002_V3EXP"}
    ]
    material_cases = [row["case_id"] for row in validation.get("cases", []) if row.get("effect_class") == "material_on_panel"]
    weak_cases = [row["case_id"] for row in validation.get("cases", []) if row.get("effect_class") == "weak_on_panel"]
    failed_cases = [row["case_id"] for row in validation.get("cases", []) if row.get("effect_class") == "failed_shortlist_preservation"]
    non_brd4_cases = [row["case_id"] for row in validation.get("cases", []) if not str(row.get("case_id", "")).startswith("BRD4_")]

    promotion_decision = (promotion_review or {}).get("decision", {})
    has_interim_promotion = bool(promotion_decision.get("retire_brd4_only_internal_reading"))
    summary = {
        "generated_at_utc": validation.get("generated_at_utc"),
        "validation_status": validation.get("current_validation_status"),
        "material_cases": material_cases,
        "weak_cases": weak_cases,
        "failed_cases": failed_cases,
        "non_brd4_cases": non_brd4_cases,
        "enabled_literature_backed_cases_count": len(enabled_literature_cases),
        "enabled_literature_backed_cases": [
            {
                "case_id": row["case_id"],
                "target_id": row["target_id"],
                "library_id": row["library_id"],
                "rerank_strategy": row["rerank_strategy"],
            }
            for row in enabled_literature_cases
        ],
        "has_additional_nonfrozen_case": bool(nonfrozen_candidates),
        "additional_nonfrozen_cases": [row["case_id"] for row in nonfrozen_candidates],
        "expansion_readiness": (
            "interim_brd4_brd3_boundary_ready"
            if has_interim_promotion
            else (
                "reassess_after_failed_surface"
                if failed_cases
                else ("can_expand_with_existing_case" if nonfrozen_candidates else "needs_new_case_or_panel")
            )
        ),
        "recommended_next_action": (
            "formalize_interim_brd4_brd3_boundary_then_validate_non_brd3_surface"
            if has_interim_promotion
            else (
                "pause_boundary_expansion_and_review_failed_surface"
                if failed_cases
                else (
                    "prepare_rollout_boundary_or_add_new_target_family"
                    if len(non_brd4_cases) >= 2
                    else "run_bounded_validation_on_existing_nonfrozen_case"
                )
            )
        ),
        "promotion_review": {
            "available": bool(promotion_review),
            "recommended_interim_headline": promotion_decision.get("recommended_interim_headline"),
            "promote_to_full_bet_family_headline": promotion_decision.get("promote_to_full_bet_family_headline"),
        },
        "constraints": [
            "Do not move enhancement results into frozen manuscript or benchmark claims.",
            "Do not continue indefinite same-panel tuning when no new validation surface is available.",
            "Treat current v3 gains as bounded to the enhancement line and explicitly checked frozen cases only.",
            "If a new surface loses known-active shortlist/rank preservation, treat it as a boundary challenge before any further expansion.",
        ],
    }

    output_json = (project_root / args.output_json).resolve()
    output_md = (project_root / args.output_md).resolve()
    write_json(output_json, summary)
    write_text(output_md, build_markdown(summary))
    print(f"[expansion-readiness] wrote json: {output_json}")
    print(f"[expansion-readiness] wrote markdown: {output_md}")


if __name__ == "__main__":
    main()
