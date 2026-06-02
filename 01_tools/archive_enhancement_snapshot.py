#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive the current enhancement-line state into a compact local history."
    )
    parser.add_argument("--project-root", default=".", help="Project root containing 09_reports/")
    parser.add_argument(
        "--history-json",
        default="09_reports/enhancement_line_snapshot_history.json",
        help="Snapshot history JSON path",
    )
    parser.add_argument(
        "--trend-json",
        default="09_reports/enhancement_line_trend_summary.json",
        help="Derived trend summary JSON path",
    )
    parser.add_argument(
        "--trend-md",
        default="09_reports/enhancement_line_trend_summary.md",
        help="Derived trend summary markdown path",
    )
    parser.add_argument(
        "--label",
        default="auto",
        help="Optional short label for this snapshot",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_history(path: Path) -> list[dict[str, object]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_config_v3_tuning(project_root: Path) -> dict[str, object]:
    tuning: dict[str, object] = {}
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        return tuning
    lines = config_path.read_text(encoding="utf-8").splitlines()
    in_v3 = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "v3:":
            in_v3 = True
            continue
        if in_v3:
            if not line.startswith("      "):
                break
            if ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            value = value.strip()
            try:
                tuning[key.strip()] = float(value)
            except ValueError:
                tuning[key.strip()] = value
    return tuning


def derive_auto_label(tuning: dict[str, object]) -> str:
    poly = tuning.get("polyaryl_hydrophobe_penalty")
    single = tuning.get("single_ring_background_penalty")
    simple = tuning.get("simple_aromatic_penalty")
    parts = []
    if poly is not None:
        parts.append(f"poly{poly}")
    if single is not None:
        parts.append(f"single{single}")
    if simple is not None:
        parts.append(f"simple{simple}")
    return "_".join(parts) if parts else "auto"


def build_snapshot(project_root: Path, label: str, tuning: dict[str, object]) -> dict[str, object]:
    comparison = load_json(project_root / "09_reports/enhancement_line_v2_vs_v3_comparison.json")
    tracker = load_json(project_root / "09_reports/enhancement_line_iteration_tracker.json")
    checklist = load_json(project_root / "09_reports/enhancement_line_diagnostic_checklist.json")
    flag_summary = load_json(project_root / "09_reports/enhancement_line_flag_impact_summary.json")
    watchlist = load_json(project_root / "09_reports/enhancement_line_background_watchlist.json")

    enhancement = comparison["enhancement_case"]
    active_margin = enhancement.get("active_margin", {})
    tracker_headline = tracker.get("headline_metrics", {})
    watchlist_rows = watchlist.get("watchlist_rows", [])
    if not isinstance(watchlist_rows, list):
        watchlist_rows = []
    effective_label = derive_auto_label(tuning) if label == "auto" else label

    return {
        "archived_at_utc": datetime.now(timezone.utc).isoformat(),
        "label": effective_label,
        "baseline_case_id": comparison["baseline_case"]["case_id"],
        "enhancement_case_id": enhancement["case_id"],
        "enhancement_shortlist_count": enhancement.get("shortlist_count"),
        "enhancement_shortlist_ids": enhancement.get("shortlist_ids", []),
        "best_background_compound_id": active_margin.get("best_background_compound_id"),
        "active_best_background_gap": active_margin.get("known_active_to_best_background_gap"),
        "top12_rerank_gap": tracker_headline.get("enhancement_top12_rerank_gap"),
        "shortlist_compression_ratio": tracker_headline.get("enhancement_shortlist_compression_ratio"),
        "strongest_flag_by_average_score_delta": flag_summary.get("strongest_flag_by_average_score_delta"),
        "watchlist_top_compounds": [row.get("compound_id") for row in watchlist_rows[:3]],
        "next_tuning_recommendation": watchlist.get("next_tuning_recommendation", {}),
        "checklist_status": checklist.get("overall_status"),
        "v3_tuning_snapshot": tuning,
    }


def upsert_snapshot(history: list[dict[str, object]], snapshot: dict[str, object]) -> list[dict[str, object]]:
    if history:
        last = history[-1]
        same_state = (
            last.get("best_background_compound_id") == snapshot.get("best_background_compound_id")
            and last.get("active_best_background_gap") == snapshot.get("active_best_background_gap")
            and last.get("enhancement_shortlist_count") == snapshot.get("enhancement_shortlist_count")
            and last.get("top12_rerank_gap") == snapshot.get("top12_rerank_gap")
        )
        if same_state:
            updated = dict(last)
            updated.update(snapshot)
            history[-1] = updated
            return history
    history.append(snapshot)
    return history


def build_trend_summary(history: list[dict[str, object]]) -> dict[str, object]:
    latest = history[-1] if history else {}
    first = history[0] if history else {}
    previous = history[-2] if len(history) >= 2 else {}
    return {
        "snapshot_count": len(history),
        "latest_snapshot": latest,
        "first_snapshot": first,
        "previous_snapshot": previous,
        "improvement_since_first": {
            "active_best_background_gap": (
                round(float(latest["active_best_background_gap"]) - float(first["active_best_background_gap"]), 3)
                if history and latest.get("active_best_background_gap") is not None and first.get("active_best_background_gap") is not None
                else None
            ),
            "top12_rerank_gap": (
                round(float(latest["top12_rerank_gap"]) - float(first["top12_rerank_gap"]), 3)
                if history and latest.get("top12_rerank_gap") is not None and first.get("top12_rerank_gap") is not None
                else None
            ),
        },
        "delta_since_previous": {
            "active_best_background_gap": (
                round(float(latest["active_best_background_gap"]) - float(previous["active_best_background_gap"]), 3)
                if len(history) >= 2 and latest.get("active_best_background_gap") is not None and previous.get("active_best_background_gap") is not None
                else None
            ),
            "top12_rerank_gap": (
                round(float(latest["top12_rerank_gap"]) - float(previous["top12_rerank_gap"]), 3)
                if len(history) >= 2 and latest.get("top12_rerank_gap") is not None and previous.get("top12_rerank_gap") is not None
                else None
            ),
            "best_background_changed": (
                latest.get("best_background_compound_id") != previous.get("best_background_compound_id")
                if len(history) >= 2
                else None
            ),
        },
        "current_attention_target": {
            "compound_id": (latest.get("watchlist_top_compounds") or [None])[0],
            "best_background_compound_id": latest.get("best_background_compound_id"),
            "strongest_flag_by_average_score_delta": latest.get("strongest_flag_by_average_score_delta"),
            "recommended_knob": (latest.get("next_tuning_recommendation") or {}).get("recommended_knob"),
            "recommended_direction": (latest.get("next_tuning_recommendation") or {}).get("recommended_direction"),
        },
        "history": history,
    }


def build_trend_markdown(payload: dict[str, object]) -> str:
    latest = payload.get("latest_snapshot", {})
    first = payload.get("first_snapshot", {})
    previous = payload.get("previous_snapshot", {})
    improvement = payload.get("improvement_since_first", {})
    previous_delta = payload.get("delta_since_previous", {})
    attention = payload.get("current_attention_target", {})
    history = payload.get("history", [])
    lines = [
        "# Enhancement Line Trend Summary",
        "",
        f"- Snapshot count: `{payload.get('snapshot_count')}`",
        f"- Latest best background: `{latest.get('best_background_compound_id')}`",
        f"- Latest active-best-background gap: `{latest.get('active_best_background_gap')}`",
        f"- Latest shortlist ids: `{', '.join(latest.get('enhancement_shortlist_ids', []))}`",
        f"- Strongest flag: `{latest.get('strongest_flag_by_average_score_delta')}`",
        f"- Latest label: `{latest.get('label')}`",
        "",
        "## Improvement Since First Snapshot",
        "",
        f"- Active-best-background gap delta: `{improvement.get('active_best_background_gap')}`",
        f"- Top1-Top2 rerank gap delta: `{improvement.get('top12_rerank_gap')}`",
        "",
        "## Delta Since Previous Snapshot",
        "",
        f"- Previous best background: `{previous.get('best_background_compound_id')}`",
        f"- Active-best-background gap delta: `{previous_delta.get('active_best_background_gap')}`",
        f"- Top1-Top2 rerank gap delta: `{previous_delta.get('top12_rerank_gap')}`",
        f"- Best background changed: `{previous_delta.get('best_background_changed')}`",
        "",
        "## Current Attention Target",
        "",
        f"- Current top watch target: `{attention.get('compound_id')}`",
        f"- Current best background: `{attention.get('best_background_compound_id')}`",
        f"- Strongest aggregate flag: `{attention.get('strongest_flag_by_average_score_delta')}`",
        f"- Recommended next knob: `{attention.get('recommended_knob')}`",
        f"- Recommended direction: `{attention.get('recommended_direction')}`",
        "",
        "## Snapshot Table",
        "",
        "| Archived at | Label | Best background | Active-best-background gap | Top1-Top2 gap | Shortlist count | Status |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in history:
        lines.append(
            f"| `{row.get('archived_at_utc')}` | `{row.get('label')}` | `{row.get('best_background_compound_id')}` | "
            f"`{row.get('active_best_background_gap')}` | `{row.get('top12_rerank_gap')}` | "
            f"`{row.get('enhancement_shortlist_count')}` | `{row.get('checklist_status')}` |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    history_path = project_root / args.history_json
    trend_json_path = project_root / args.trend_json
    trend_md_path = project_root / args.trend_md

    tuning = load_config_v3_tuning(project_root)
    snapshot = build_snapshot(project_root, args.label, tuning)
    history = load_history(history_path)
    history = upsert_snapshot(history, snapshot)
    trend_summary = build_trend_summary(history)

    history_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(history_path, history)
    write_json(trend_json_path, trend_summary)
    trend_md_path.write_text(build_trend_markdown(trend_summary), encoding="utf-8")

    print(f"[enhancement-archive] wrote history: {history_path}")
    print(f"[enhancement-archive] wrote trend json: {trend_json_path}")
    print(f"[enhancement-archive] wrote trend markdown: {trend_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
