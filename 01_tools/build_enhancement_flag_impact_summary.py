#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an aggregate physchem-flag impact summary for the enhancement line."
    )
    parser.add_argument(
        "--background-delta-json",
        default="09_reports/enhancement_line_background_delta.json",
        help="Per-compound enhancement background delta JSON",
    )
    parser.add_argument(
        "--comparison-json",
        default="09_reports/enhancement_line_v2_vs_v3_comparison.json",
        help="Enhancement comparison JSON",
    )
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_line_flag_impact_summary.json",
        help="Flag impact summary JSON output",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_line_flag_impact_summary.md",
        help="Flag impact summary markdown output",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_payload(background_delta: dict[str, object], comparison: dict[str, object]) -> dict[str, object]:
    rows = background_delta.get("rows", [])
    if not isinstance(rows, list):
        rows = []

    flag_buckets: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row.get("is_known_active"):
            continue
        flags = row.get("physchem_flags", [])
        if not isinstance(flags, list):
            flags = []
        for flag in flags:
            if flag:
                flag_buckets[str(flag)].append(row)

    flag_summary = []
    for flag, flagged_rows in sorted(flag_buckets.items()):
        score_deltas = [float(r["score_delta"]) for r in flagged_rows if r.get("score_delta") is not None]
        rank_deltas = [int(r["rank_delta"]) for r in flagged_rows if r.get("rank_delta") is not None]
        shortlisted_removed = [
            r["compound_id"]
            for r in flagged_rows
            if bool(r.get("baseline_shortlisted")) and not bool(r.get("enhancement_shortlisted"))
        ]
        best_current = min(
            flagged_rows,
            key=lambda r: (
                r["enhancement_rank"] if r.get("enhancement_rank") is not None else 999999,
                str(r.get("compound_id", "")),
            ),
        )
        flag_summary.append(
            {
                "flag": flag,
                "compound_count": len(flagged_rows),
                "compounds": [r["compound_id"] for r in flagged_rows],
                "average_score_delta": round(sum(score_deltas) / len(score_deltas), 3) if score_deltas else None,
                "max_score_delta": round(max(score_deltas), 3) if score_deltas else None,
                "average_rank_delta": round(sum(rank_deltas) / len(rank_deltas), 3) if rank_deltas else None,
                "shortlist_removed_count": len(shortlisted_removed),
                "shortlist_removed_compounds": shortlisted_removed,
                "best_current_compound_id": best_current.get("compound_id"),
                "best_current_rank": best_current.get("enhancement_rank"),
                "best_current_score": best_current.get("enhancement_score"),
            }
        )

    headline = {
        "best_background_compound_id": background_delta.get("best_background_compound_id"),
        "active_best_background_gap": background_delta.get("active_best_background_gap"),
        "baseline_shortlist_count": comparison.get("baseline_case", {}).get("shortlist_count"),
        "enhancement_shortlist_count": comparison.get("enhancement_case", {}).get("shortlist_count"),
    }

    strongest_flag = None
    if flag_summary:
        strongest_flag = max(
            flag_summary,
            key=lambda row: (
                row["average_score_delta"] if row["average_score_delta"] is not None else -999999,
                row["shortlist_removed_count"],
            ),
        )["flag"]

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_files": {
            "background_delta_json": "09_reports/enhancement_line_background_delta.json",
            "comparison_json": "09_reports/enhancement_line_v2_vs_v3_comparison.json",
        },
        "headline": headline,
        "strongest_flag_by_average_score_delta": strongest_flag,
        "flag_summary": flag_summary,
    }


def build_markdown(payload: dict[str, object]) -> str:
    headline = payload["headline"]
    flag_summary = payload["flag_summary"]
    lines = [
        "# Enhancement Line Flag Impact Summary",
        "",
        f"- Generated at: `{payload['generated_at_utc']}`",
        f"- Best current background: `{headline['best_background_compound_id']}`",
        f"- Active-best-background gap: `{headline['active_best_background_gap']}`",
        f"- Baseline shortlist count: `{headline['baseline_shortlist_count']}`",
        f"- Enhancement shortlist count: `{headline['enhancement_shortlist_count']}`",
        f"- Strongest flag by average score delta: `{payload['strongest_flag_by_average_score_delta']}`",
        "",
        "## Aggregate Flag Table",
        "",
        "| Flag | Compounds | Avg score delta | Max score delta | Avg rank delta | Shortlist removed | Best current compound |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in flag_summary:
        lines.append(
            f"| `{row['flag']}` | `{row['compound_count']}` | `{row['average_score_delta']}` | "
            f"`{row['max_score_delta']}` | `{row['average_rank_delta']}` | "
            f"`{row['shortlist_removed_count']}` | `{row['best_current_compound_id']}` |"
        )
    lines.extend(["", "## Flag Details", ""])
    for row in flag_summary:
        lines.extend(
            [
                f"### `{row['flag']}`",
                "",
                f"- compounds: `{', '.join(row['compounds'])}`",
                f"- shortlist removed: `{', '.join(row['shortlist_removed_compounds']) or 'none'}`",
                f"- best current compound: `{row['best_current_compound_id']}` (rank `{row['best_current_rank']}`, score `{row['best_current_score']}`)",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    background_delta = load_json(Path(args.background_delta_json))
    comparison = load_json(Path(args.comparison_json))
    payload = build_payload(background_delta, comparison)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_json, payload)
    output_md.write_text(build_markdown(payload), encoding="utf-8")
    print(f"[flag-impact] wrote json: {output_json}")
    print(f"[flag-impact] wrote markdown: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
