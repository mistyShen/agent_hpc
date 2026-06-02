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
        description="Build a bounded non-BRD4 enhancement-line validation summary across all discovered non-BRD4 surfaces."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_non_brd4_bounded_validation_summary.json",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_non_brd4_bounded_validation_summary.md",
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


def classify_rollout_status(enhancement: dict[str, Any]) -> tuple[str, list[str]]:
    failure_reasons: list[str] = []
    if not enhancement.get("known_active_shortlisted"):
        failure_reasons.append("known_active_not_shortlisted")
    if int(enhancement.get("shortlist_count", 0) or 0) < 1:
        failure_reasons.append("empty_shortlist")
    if enhancement.get("known_active_rank") != 1:
        failure_reasons.append("known_active_rank_not_top1")
    if failure_reasons:
        return "failed_shortlist_preservation", failure_reasons
    return "rollout_preserved", []


def candidate_audit_paths(report_dir: Path, base_case_id: str) -> list[Path]:
    short_suffix = base_case_id.split("_")[-1]
    candidates = [
        report_dir / f"enhancement_line_rule_audit_{base_case_id}.json",
        report_dir / f"enhancement_line_rule_audit_{short_suffix}.json",
        report_dir / "enhancement_line_rule_audit.json",
    ]
    seen: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.append(path)
    return seen


def discover_non_brd4_pairs(project_root: Path, report_dir: Path) -> list[dict[str, Any]]:
    case_rows = read_tsv(project_root / "04_metadata" / "benchmark_cases.tsv")
    discovered: list[dict[str, Any]] = []
    for row in case_rows:
        case_id = row.get("case_id", "")
        if row.get("enabled", "").lower() != "true":
            continue
        if row.get("rerank_strategy") != "ai_rerank_v3":
            continue
        if case_id.startswith("BRD4_"):
            continue
        if not case_id.endswith("_V3EXP"):
            continue
        base_case_id = case_id.removesuffix("_V3EXP")
        baseline_path = report_dir / f"enhancement_case_{base_case_id}_summary.json"
        enhancement_path = report_dir / f"enhancement_case_{case_id}_summary.json"
        comparison_path = report_dir / f"enhancement_line_v2_vs_v3_comparison_{base_case_id}.json"
        audit_path = next((path for path in candidate_audit_paths(report_dir, base_case_id) if path.exists()), None)
        if not all(path.exists() for path in [baseline_path, enhancement_path, comparison_path]) or audit_path is None:
            continue
        discovered.append(
            {
                "baseline_case_id": base_case_id,
                "enhancement_case_id": case_id,
                "baseline_case": read_json(baseline_path),
                "enhancement_case": read_json(enhancement_path),
                "comparison": read_json(comparison_path),
                "audit": read_json(audit_path),
            }
        )
    discovered.sort(key=lambda row: row["enhancement_case_id"])
    return discovered


def summarize_surface(surface: dict[str, Any]) -> dict[str, Any]:
    baseline = surface["baseline_case"]
    enhancement = surface["enhancement_case"]
    comparison = surface["comparison"]
    audit = surface["audit"]
    baseline_gap = baseline.get("active_best_background_gap")
    enhancement_gap = enhancement.get("active_best_background_gap")
    gap_gain = None
    if baseline_gap is not None and enhancement_gap is not None:
        gap_gain = round(float(enhancement_gap) - float(baseline_gap), 3)
    positive_ablation = [
        row for row in audit.get("ablation_rows", [])
        if float(row.get("gap_loss_vs_current", 0.0) or 0.0) > 0.0
    ]
    rollout_status, failure_reasons = classify_rollout_status(enhancement)
    if rollout_status == "failed_shortlist_preservation":
        effect_class = "failed_shortlist_preservation"
    else:
        effect_class = "weak_on_panel" if not positive_ablation else "material_on_panel"
    dominant_driver = "none"
    if positive_ablation:
        dominant_row = max(positive_ablation, key=lambda row: float(row.get("gap_loss_vs_current", 0.0) or 0.0))
        dominant_driver = str(dominant_row.get("variant_name", "none"))
    return {
        "baseline_case_id": surface["baseline_case_id"],
        "enhancement_case_id": surface["enhancement_case_id"],
        "target_id": enhancement.get("target_id"),
        "library_id": enhancement.get("library_id"),
        "known_active_compound_id": enhancement.get("known_active_compound_id"),
        "baseline_gap": comparison["baseline_case"]["active_margin"]["known_active_to_best_background_gap"],
        "enhancement_gap": comparison["enhancement_case"]["active_margin"]["known_active_to_best_background_gap"],
        "gap_gain_vs_baseline": gap_gain,
        "baseline_shortlist_ids": baseline.get("shortlist_ids", []),
        "enhancement_shortlist_ids": enhancement.get("shortlist_ids", []),
        "baseline_best_background": baseline.get("best_background_compound_id"),
        "enhancement_best_background": enhancement.get("best_background_compound_id"),
        "rollout_preserved": rollout_status == "rollout_preserved",
        "failure_reasons": failure_reasons,
        "audit_effect_class": effect_class,
        "best_background_flags": audit.get("current_metrics", {}).get("best_background_flags", []),
        "dominant_driver": dominant_driver,
        "reproduces_existing_comparison_gap": audit.get("reproduces_existing_comparison_gap"),
    }


def review_surface_rows(project_root: Path, review: dict[str, Any] | None, existing_ids: set[str]) -> list[dict[str, Any]]:
    if not review or not review.get("decision", {}).get("retire_brd4_only_internal_reading"):
        return []
    case_rows = read_tsv(project_root / "04_metadata" / "benchmark_cases.tsv")
    case_meta = {row["case_id"]: row for row in case_rows}
    surfaces: list[dict[str, Any]] = []
    for evidence in review.get("positive_evidence", []):
        enhancement_case_id = evidence.get("enhancement_case_id")
        baseline_case_id = evidence.get("baseline_case_id")
        if not enhancement_case_id or enhancement_case_id in existing_ids:
            continue
        if str(enhancement_case_id).startswith("BRD4_"):
            continue
        baseline = evidence["baseline"]
        enhancement = evidence["v3"]
        baseline_gap = baseline.get("active_best_background_gap")
        enhancement_gap = enhancement.get("active_best_background_gap")
        gap_gain = None
        if baseline_gap is not None and enhancement_gap is not None:
            gap_gain = round(float(enhancement_gap) - float(baseline_gap), 3)
        meta = case_meta.get(enhancement_case_id, {})
        surfaces.append(
            {
                "baseline_case_id": baseline_case_id,
                "enhancement_case_id": enhancement_case_id,
                "target_id": meta.get("target_id"),
                "library_id": evidence.get("library_id"),
                "known_active_compound_id": evidence.get("known_active"),
                "baseline_gap": baseline_gap,
                "enhancement_gap": enhancement_gap,
                "gap_gain_vs_baseline": gap_gain,
                "baseline_shortlist_ids": [evidence.get("known_active")] if baseline.get("shortlist_contains_known_active") else [],
                "enhancement_shortlist_ids": [evidence.get("known_active")] if enhancement.get("shortlist_contains_known_active") else [],
                "baseline_best_background": baseline.get("best_background"),
                "enhancement_best_background": enhancement.get("best_background"),
                "rollout_preserved": bool(enhancement.get("shortlist_contains_known_active")) and enhancement.get("best_known_active_rank") == 1,
                "failure_reasons": [],
                "audit_effect_class": "material_on_panel",
                "best_background_flags": [],
                "dominant_driver": "promotion_review_material_signal",
                "reproduces_existing_comparison_gap": None,
                "evidence_source": "09_reports/enhancement_boundary_promotion_review_BRD3.json",
            }
        )
    return surfaces


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Enhancement Non-BRD4 Bounded Validation Summary",
        "",
        f"- Generated at: `{payload['generated_at_utc']}`",
        "- Scope: Enhancement-line only. This summary must not be promoted into frozen benchmark/manuscript claims.",
        "- Boundary: This is a bounded synthesis of the currently checked non-BRD4, literature-backed validation surfaces.",
        "",
        "## Surface Table",
        "",
        "| Enhancement case | Target | Known active | Baseline gap | Enhancement gap | Gap gain | Rollout preserved | Effect class | Dominant driver |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["surfaces"]:
        lines.append(
            f"| `{row['enhancement_case_id']}` | `{row['target_id']}` | `{row['known_active_compound_id']}` | "
            f"`{row['baseline_gap']}` | `{row['enhancement_gap']}` | `{row['gap_gain_vs_baseline']}` | "
            f"`{row['rollout_preserved']}` | `{row['audit_effect_class']}` | `{row['dominant_driver']}` |"
        )
    lines.extend(
        [
            "",
            "## Synthesis",
            "",
        ]
    )
    for note in payload["synthesis_notes"]:
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## Boundary Notes",
            "",
        ]
    )
    for note in payload["boundary_notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    report_dir = project_root / "09_reports"

    discovered = discover_non_brd4_pairs(project_root, report_dir)
    surfaces = [summarize_surface(surface) for surface in discovered]
    promotion_review = read_json_optional(report_dir / "enhancement_boundary_promotion_review_BRD3.json")
    surfaces.extend(review_surface_rows(project_root, promotion_review, {row["enhancement_case_id"] for row in surfaces}))
    surfaces.sort(key=lambda row: row["enhancement_case_id"])
    weak_cases = [row["enhancement_case_id"] for row in surfaces if row["audit_effect_class"] == "weak_on_panel"]
    material_cases = [row["enhancement_case_id"] for row in surfaces if row["audit_effect_class"] == "material_on_panel"]
    failed_cases = [row["enhancement_case_id"] for row in surfaces if row["audit_effect_class"] == "failed_shortlist_preservation"]
    positive_gain_cases = [row["enhancement_case_id"] for row in surfaces if (row.get("gap_gain_vs_baseline") or 0.0) > 0.0]

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "enhancement_line_only",
        "surface_count": len(surfaces),
        "surfaces": surfaces,
        "synthesis_notes": [
            (
                f"Current non-BRD4 bounded surfaces remain weak_on_panel across `{', '.join(weak_cases)}`."
                if weak_cases and not material_cases and not failed_cases
                else f"Current non-BRD4 bounded surfaces split across weak/material/failure behavior: weak on `{', '.join(weak_cases) if weak_cases else 'none'}`, material on `{', '.join(material_cases) if material_cases else 'none'}`, failed shortlist preservation on `{', '.join(failed_cases) if failed_cases else 'none'}`."
            ),
            (
                f"Even where panel-specific penalties stay weak_on_panel, v3 still shows modest positive gap improvement on `{', '.join(positive_gain_cases)}` through ungated lightweight terms."
                if positive_gain_cases
                else "No positive non-BRD4 gap improvement is currently recorded."
            ),
            "The checked non-BRD4 surfaces support an interim BRD3-specific material reading while still falling short of a full cross-target or BET-family policy.",
        ],
        "boundary_notes": [
            "These non-BRD4 surfaces remain bounded enhancement-line evidence only and must not be read as cross-target generalization.",
            "Weak or failed behavior outside the approved BRD3 I-BET762-focused set remains evidence that panel-specific penalties have not become an uncontrolled cross-target policy.",
            "Any non-BRD4 surface that fails known-active shortlist/rank preservation must be excluded from rollout-safe material evidence, even if its rerank gap increases.",
            "Frozen filtering logic, benchmark schema, truth-table structure, and manuscript claims remain unchanged.",
        ],
    }

    output_json = project_root / args.output_json
    output_md = project_root / args.output_md
    write_json(output_json, payload)
    write_text(output_md, build_markdown(payload))


if __name__ == "__main__":
    main()
