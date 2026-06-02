#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a compact enhancement-line hard-background watchlist."
    )
    parser.add_argument(
        "--flag-impact-json",
        default="09_reports/enhancement_line_flag_impact_summary.json",
        help="Flag impact summary JSON used to derive next-tuning recommendations",
    )
    parser.add_argument(
        "--background-delta-json",
        default="09_reports/enhancement_line_background_delta.json",
        help="Per-compound enhancement background delta JSON",
    )
    parser.add_argument(
        "--output-json",
        default="09_reports/enhancement_line_background_watchlist.json",
        help="Watchlist JSON output",
    )
    parser.add_argument(
        "--output-md",
        default="09_reports/enhancement_line_background_watchlist.md",
        help="Watchlist markdown output",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=4,
        help="Number of top current backgrounds to include in the watchlist",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def classify_row(row: dict[str, object]) -> list[str]:
    labels: list[str] = []
    if row.get("enhancement_rank") == 2:
        labels.append("current_best_background")
    if bool(row.get("baseline_shortlisted")) and not bool(row.get("enhancement_shortlisted")):
        labels.append("removed_from_shortlist")
    if bool(row.get("enhancement_shortlisted")):
        labels.append("still_shortlisted")
    rank_delta = row.get("rank_delta")
    if isinstance(rank_delta, int):
        if rank_delta > 0:
            labels.append("moved_up")
        elif rank_delta < 0:
            labels.append("moved_down")
    if row.get("physchem_flags"):
        labels.append("explained_by_physchem_flags")
    return labels


def build_next_tuning_recommendation(
    best_background_row: dict[str, object] | None,
    flag_summary: dict[str, object],
) -> dict[str, object]:
    strongest_flag = flag_summary.get("strongest_flag_by_average_score_delta")
    flags = []
    if best_background_row:
        raw_flags = best_background_row.get("physchem_flags", [])
        if isinstance(raw_flags, list):
            flags = [str(flag) for flag in raw_flags]

    primary_flag = flags[0] if flags else strongest_flag
    knob_by_flag = {
        "single_ring_background": "single_ring_background_penalty",
        "polyaryl_hydrophobe_background": "polyaryl_hydrophobe_penalty",
        "simple_aromatic_background": "simple_aromatic_penalty",
    }
    knob = knob_by_flag.get(str(primary_flag), "simple_aromatic_penalty")

    rationale_parts = []
    if best_background_row and best_background_row.get("compound_id"):
        rationale_parts.append(
            f"Current best background `{best_background_row['compound_id']}` is still closest to the known active."
        )
    if primary_flag:
        rationale_parts.append(f"It is currently explained most directly by `{primary_flag}`.")
    if strongest_flag and strongest_flag != primary_flag:
        rationale_parts.append(
            f"Aggregate suppression remains strongest for `{strongest_flag}`, so keep that signal stable while nudging the current bottleneck."
        )

    return {
        "target_compound_id": best_background_row.get("compound_id") if best_background_row else None,
        "target_flags": flags,
        "strongest_aggregate_flag": strongest_flag,
        "recommended_knob": knob,
        "recommended_direction": "increase_slightly",
        "rationale": " ".join(rationale_parts).strip(),
    }


def build_payload(
    background_delta: dict[str, object],
    flag_summary: dict[str, object],
    top_n: int,
) -> dict[str, object]:
    rows = background_delta.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    background_rows = [row for row in rows if not row.get("is_known_active")]
    background_rows.sort(
        key=lambda row: (
            row["enhancement_rank"] if row.get("enhancement_rank") is not None else 999999,
            str(row.get("compound_id", "")),
        )
    )
    watchlist_rows = []
    for row in background_rows[:top_n]:
        watchlist_rows.append(
            {
                "compound_id": row.get("compound_id"),
                "baseline_rank": row.get("baseline_rank"),
                "enhancement_rank": row.get("enhancement_rank"),
                "rank_delta": row.get("rank_delta"),
                "baseline_score": row.get("baseline_score"),
                "enhancement_score": row.get("enhancement_score"),
                "score_delta": row.get("score_delta"),
                "baseline_shortlisted": row.get("baseline_shortlisted"),
                "enhancement_shortlisted": row.get("enhancement_shortlisted"),
                "physchem_flags": row.get("physchem_flags", []),
                "watch_labels": classify_row(row),
            }
        )
    best_background_row = background_rows[0] if background_rows else None
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_file": "09_reports/enhancement_line_background_delta.json",
        "known_active_compound_id": background_delta.get("known_active_compound_id"),
        "best_background_compound_id": background_delta.get("best_background_compound_id"),
        "active_best_background_gap": background_delta.get("active_best_background_gap"),
        "next_tuning_recommendation": build_next_tuning_recommendation(
            best_background_row, flag_summary
        ),
        "watchlist_rows": watchlist_rows,
    }


def build_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Enhancement Line Background Watchlist",
        "",
        f"- Generated at: `{payload['generated_at_utc']}`",
        f"- Known active: `{payload['known_active_compound_id']}`",
        f"- Current best background: `{payload['best_background_compound_id']}`",
        f"- Active-best-background gap: `{payload['active_best_background_gap']}`",
        "",
        "## Recommended Next Tuning Move",
        "",
        f"- Recommended knob: `{payload['next_tuning_recommendation']['recommended_knob']}`",
        f"- Recommended direction: `{payload['next_tuning_recommendation']['recommended_direction']}`",
        f"- Target compound: `{payload['next_tuning_recommendation']['target_compound_id']}`",
        f"- Target flags: `{', '.join(payload['next_tuning_recommendation']['target_flags']) or 'none'}`",
        f"- Strongest aggregate flag: `{payload['next_tuning_recommendation']['strongest_aggregate_flag']}`",
        f"- Rationale: {payload['next_tuning_recommendation']['rationale']}",
        "",
        "## Watchlist",
        "",
        "| Compound | Baseline rank | Enhancement rank | Rank delta | Enhancement score | Baseline shortlist | Enhancement shortlist | Flags | Labels |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["watchlist_rows"]:
        lines.append(
            f"| `{row['compound_id']}` | `{row['baseline_rank']}` | `{row['enhancement_rank']}` | "
            f"`{row['rank_delta']}` | `{row['enhancement_score']}` | "
            f"`{row['baseline_shortlisted']}` | `{row['enhancement_shortlisted']}` | "
            f"`{', '.join(row['physchem_flags']) or 'none'}` | `{', '.join(row['watch_labels']) or 'none'}` |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    payload = build_payload(
        load_json(Path(args.background_delta_json)),
        load_json(Path(args.flag_impact_json)),
        args.top_n,
    )
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_json, payload)
    output_md.write_text(build_markdown(payload), encoding="utf-8")
    print(f"[background-watchlist] wrote json: {output_json}")
    print(f"[background-watchlist] wrote markdown: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
