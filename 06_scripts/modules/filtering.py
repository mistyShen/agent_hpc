#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate lightweight filtered candidate outputs.")
    parser.add_argument("--module", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--input-manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def merge_rows_by_keys(
    existing_rows: list[dict[str, str]],
    new_rows: list[dict[str, str]],
    key_fields: list[str],
) -> list[dict[str, str]]:
    replacement_keys = {tuple(row[field] for field in key_fields) for row in new_rows}
    merged: list[dict[str, str]] = [
        row for row in existing_rows if tuple(row[field] for field in key_fields) not in replacement_keys
    ]
    merged.extend(new_rows)
    return merged


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f"{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(json.dumps(payload, indent=2) + "\n")
        handle.flush()
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def file_signature(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def build_cache_signature(
    input_manifest: Path,
    config_path: Path,
    docking_results_tsv: Path,
    reranked_tsv: Path,
    prepared_library_tsv: Path,
    enabled_cases: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "input_manifest": file_signature(input_manifest),
        "config": file_signature(config_path),
        "docking_results_tsv": file_signature(docking_results_tsv),
        "reranked_candidates_tsv": file_signature(reranked_tsv),
        "prepared_library_tsv": file_signature(prepared_library_tsv),
        "enabled_case_ids": [row["case_id"] for row in enabled_cases],
        "enabled_case_count": len(enabled_cases),
    }


def outputs_ready(paths: list[Path]) -> bool:
    return all(path.exists() and path.stat().st_size > 0 for path in paths)


def selected_case_ids_from_env() -> set[str]:
    selected: set[str] = set()
    for key in ("WORKFLOW_CASE_ID", "WORKFLOW_CASE_IDS"):
        raw = os.environ.get(key, "").strip()
        if not raw:
            continue
        for item in raw.split(","):
            case_id = item.strip()
            if case_id:
                selected.add(case_id)
    return selected


def load_existing_done(path: Path) -> dict[str, object] | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    return load_json(path)


def update_run_manifest(
    run_manifest_path: Path,
    module_name: str,
    runtime_seconds: float,
    execution_status: str,
    backend_mode: str,
    case_updates: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    lock_path = run_manifest_path.with_suffix(run_manifest_path.suffix + ".lock")
    with lock_path.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        payload = load_json(run_manifest_path)
        execution_state = payload.setdefault("execution_state", {})
        modules = execution_state.setdefault("modules", {})
        modules[module_name] = {
            "runtime_seconds": round(runtime_seconds, 6),
            "execution_status": execution_status,
            "backend_mode": backend_mode,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        cases = execution_state.setdefault("cases", {})
        for case_id, case_payload in (case_updates or {}).items():
            case_state = cases.setdefault(case_id, {})
            case_state[module_name] = {
                **case_payload,
                "runtime_seconds": round(float(case_payload.get("runtime_seconds", 0.0)), 6),
                "backend_mode": str(case_payload.get("backend_mode", backend_mode)),
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        write_json_atomic(run_manifest_path, payload)
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    return payload


def parse_float(value: str) -> float | None:
    stripped = value.strip()
    if not stripped:
        return None
    return float(stripped)


def priority_tier_from_rank(rank: int | None) -> str:
    if rank == 1:
        return "high"
    if rank == 2:
        return "medium"
    return "backup"


def count_case_ids(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        case_id = row["case_id"]
        counts[case_id] = counts.get(case_id, 0) + 1
    return dict(sorted(counts.items()))


def join_key(row: dict[str, str]) -> tuple[str, str]:
    return row["case_id"], row["compound_id"]


def use_literature_filter_v2(case_row: dict[str, str]) -> bool:
    return (
        case_row.get("case_type", "").strip() == "literature_backed"
        and case_row.get("run_purpose", "").strip() == "comparison"
    )


def filter_policy(case_row: dict[str, str]) -> dict[str, float]:
    if use_literature_filter_v2(case_row):
        return {
            "max_vina_affinity": -6.5,
            "relative_vina_window": 2.0,
            "max_rerank_rank": 3,
            "min_molecular_weight": 50.0,
            "max_molecular_weight": 600.0,
            "min_heavy_atoms": 4.0,
            "max_heavy_atoms": 60.0,
        }
    case_type = case_row.get("case_type", "").strip()
    run_purpose = case_row.get("run_purpose", "").strip()
    if case_type in {"realistic", "literature_backed"} or run_purpose == "comparison":
        return {
            "max_rerank_score": -1.55,
            "max_vina_affinity": -0.90,
            "min_molecular_weight": 50.0,
            "max_molecular_weight": 600.0,
            "min_heavy_atoms": 4.0,
            "max_heavy_atoms": 60.0,
        }
    return {
        "max_rerank_score": -1.45,
        "max_vina_affinity": -0.75,
        "min_molecular_weight": 30.0,
        "max_molecular_weight": 600.0,
        "min_heavy_atoms": 3.0,
        "max_heavy_atoms": 60.0,
    }


def evaluate_candidate(
    case_row: dict[str, str],
    docking_row: dict[str, str] | None,
    rerank_row: dict[str, str] | None,
    library_row: dict[str, str] | None,
    case_best_vina_affinity: float | None = None,
) -> tuple[str, str]:
    required = {
        "docking_row": docking_row is not None,
        "rerank_row": rerank_row is not None,
        "library_row": library_row is not None,
    }
    for key, present in required.items():
        if not present:
            return "exclude_missing_or_anomalous", f"missing_{key}"

    assert docking_row is not None
    assert rerank_row is not None
    assert library_row is not None

    vina_affinity = parse_float(docking_row.get("vina_affinity_kcal_mol", ""))
    rerank_score = parse_float(rerank_row.get("rerank_score", ""))
    rerank_rank_raw = rerank_row.get("rerank_rank", "").strip()
    rerank_rank = int(rerank_rank_raw) if rerank_rank_raw else None
    molecular_weight = parse_float(library_row.get("molecular_weight_estimate", ""))
    heavy_atoms = parse_float(library_row.get("heavy_atom_count", ""))
    ligand_path = docking_row.get("ligand_pdbqt_path", "").strip()
    pose_path = docking_row.get("pose_pdbqt_path", "").strip()

    if vina_affinity is None:
        return "exclude_missing_or_anomalous", "missing_vina_affinity_kcal_mol"
    if rerank_score is None:
        return "exclude_missing_or_anomalous", "missing_rerank_score"
    if molecular_weight is None or heavy_atoms is None:
        return "exclude_missing_or_anomalous", "missing_physchem_property"
    if not ligand_path or not pose_path:
        return "exclude_missing_or_anomalous", "missing_docking_artifact_path"

    ligand_file = Path(ligand_path)
    pose_file = Path(pose_path)
    if not ligand_file.exists() or not pose_file.exists():
        return "exclude_missing_or_anomalous", "missing_docking_artifact_file"
    if ligand_file.stat().st_size == 0 or pose_file.stat().st_size == 0:
        return "exclude_missing_or_anomalous", "empty_docking_artifact_file"

    thresholds = filter_policy(case_row)
    if vina_affinity > thresholds["max_vina_affinity"]:
        return "exclude_by_rule", "vina_affinity_above_threshold"
    if use_literature_filter_v2(case_row):
        if case_best_vina_affinity is None:
            return "exclude_missing_or_anomalous", "missing_case_best_vina_affinity"
        relative_window = float(thresholds["relative_vina_window"])
        if vina_affinity < case_best_vina_affinity - relative_window:
            return "exclude_by_rule", "vina_affinity_outside_case_relative_window"
        if rerank_rank is None:
            return "exclude_missing_or_anomalous", "missing_rerank_rank"
        if rerank_rank > int(thresholds["max_rerank_rank"]):
            return "exclude_by_rule", "rerank_rank_above_threshold"
    elif rerank_score > thresholds["max_rerank_score"]:
        return "exclude_by_rule", "rerank_score_above_threshold"
    if molecular_weight < thresholds["min_molecular_weight"] or molecular_weight > thresholds["max_molecular_weight"]:
        return "exclude_by_rule", "molecular_weight_out_of_range"
    if heavy_atoms < thresholds["min_heavy_atoms"] or heavy_atoms > thresholds["max_heavy_atoms"]:
        return "exclude_by_rule", "heavy_atom_count_out_of_range"

    if use_literature_filter_v2(case_row):
        return "keep", "passes_literature_comparison_filter_v2_1"
    return "keep", "passes_lightweight_real_filter_v1"


def main() -> int:
    started_at = time.perf_counter()
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_manifest_path = Path(args.run_manifest)
    input_manifest_path = Path(args.input_manifest)
    config_path = Path(args.config)
    run_manifest = load_json(run_manifest_path)
    benchmark_cases = read_tsv_rows(input_manifest_path)
    docking_results_tsv = Path("07_results/modules/classical_docking/docking_results.tsv")
    reranked_tsv = Path("07_results/modules/ai_reranking/reranked_candidates.tsv")
    prepared_library_tsv = Path("07_results/modules/compound_library_preparation/prepared_library.tsv")
    docking_rows = read_tsv_rows(docking_results_tsv)
    rerank_rows = read_tsv_rows(reranked_tsv)
    library_rows = read_tsv_rows(prepared_library_tsv)
    enabled_cases = [row for row in benchmark_cases if row.get("enabled", "").strip().lower() == "true"]
    selected_case_ids = selected_case_ids_from_env()
    if selected_case_ids:
        enabled_cases = [row for row in enabled_cases if row["case_id"] in selected_case_ids]
    backend_mode = "lightweight_real_filter_v1"

    docking_by_key = {join_key(row): row for row in docking_rows}
    rerank_by_key = {join_key(row): row for row in rerank_rows}
    library_by_key = {(row["library_id"], row["compound_id"]): row for row in library_rows}

    module_dir = output_path.parent
    candidates_tsv = module_dir / "filtered_candidates.tsv"
    summary_json = module_dir / "filter_summary.json"
    report_md = module_dir / "filtering_report.md"
    primary_outputs = [candidates_tsv, summary_json, report_md]
    cache_signature = build_cache_signature(
        input_manifest_path,
        config_path,
        docking_results_tsv,
        reranked_tsv,
        prepared_library_tsv,
        enabled_cases,
    )
    existing_done = load_existing_done(output_path)
    if (
        existing_done is not None
        and existing_done.get("cache", {}).get("signature") == cache_signature
        and outputs_ready(primary_outputs)
    ):
        skipped_case_updates = {
            case["case_id"]: {
                "runtime_seconds": 0.0,
                "execution_status": "skipped_cache",
                "backend_mode": backend_mode,
                "skipped_cache": True,
                "skip_reason": "cache_signature_match",
                "cache_hit_artifact": True,
            }
            for case in enabled_cases
        }
        run_manifest = update_run_manifest(
            run_manifest_path,
            args.module,
            0.0,
            "skipped_cache",
            backend_mode,
            skipped_case_updates,
        )
        payload = {
            **existing_done,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "run_context": {
                "run_mode": run_manifest.get("mode"),
                "enabled_benchmark_cases": run_manifest.get("counts", {}).get("enabled_benchmark_cases"),
            },
            "execution": {
                "runtime_seconds": 0.0,
                "execution_status": "skipped_cache",
                "backend_mode": backend_mode,
                "skipped_cache": True,
                "skip_reason": "cache_signature_match",
                "selected_case_ids": [row["case_id"] for row in enabled_cases],
            },
            "cache": {
                "signature": cache_signature,
                "cache_scope": "module",
                "cache_hit": True,
                "cache_hit_artifact": True,
            },
        }
        write_json(output_path, payload)
        print(f"[module] reused cached filtering outputs: {candidates_tsv}")
        return 0

    rows: list[dict[str, str]] = []
    decision_counts = {
        "keep": 0,
        "exclude_missing_or_anomalous": 0,
        "exclude_by_rule": 0,
    }
    kept_rows: list[dict[str, str]] = []
    case_updates: dict[str, dict[str, object]] = {}

    for case in enabled_cases:
        case_started_at = time.perf_counter()
        case_id = case["case_id"]
        target_id = case["target_id"]
        library_id = case["library_id"]
        case_backend_mode = (
            "literature_comparison_filter_v2" if use_literature_filter_v2(case) else "lightweight_real_filter_v1"
        )
        case_rerank_rows = [
            row for row in rerank_rows if row["case_id"] == case_id and row["library_id"] == library_id
        ]
        case_rerank_rows.sort(key=lambda row: float(row["rerank_rank"]))
        case_best_vina_affinity = None
        if use_literature_filter_v2(case):
            case_vina_values = [
                parse_float(docking_by_key[(case_id, row["compound_id"])].get("vina_affinity_kcal_mol", ""))
                for row in case_rerank_rows
                if (case_id, row["compound_id"]) in docking_by_key
            ]
            case_vina_values = [value for value in case_vina_values if value is not None]
            case_best_vina_affinity = min(case_vina_values) if case_vina_values else None
        for rerank_row in case_rerank_rows:
            compound_id = rerank_row["compound_id"]
            docking_row = docking_by_key.get((case_id, compound_id))
            library_row = library_by_key.get((library_id, compound_id))
            decision, reason = evaluate_candidate(
                case,
                docking_row,
                rerank_row,
                library_row,
                case_best_vina_affinity=case_best_vina_affinity,
            )
            rank = int(rerank_row["rerank_rank"]) if rerank_row.get("rerank_rank", "").strip() else None
            row = {
                "case_id": case_id,
                "target_id": target_id,
                "library_id": library_id,
                "candidate_id": compound_id,
                "priority_tier": priority_tier_from_rank(rank),
                "filter_decision": decision,
                "filter_reason": reason,
            }
            rows.append(row)
            decision_counts[decision] += 1
            if decision == "keep":
                kept_rows.append(row)
        case_rows = [row for row in rows if row["case_id"] == case_id]
        case_updates[case_id] = {
            "runtime_seconds": time.perf_counter() - case_started_at,
            "execution_status": "executed",
            "backend_mode": case_backend_mode,
            "evaluated_candidate_count": len(case_rows),
            "kept_candidate_count": sum(1 for row in case_rows if row["filter_decision"] == "keep"),
            "skipped_cache": False,
            "skip_reason": "",
            "cache_hit_artifact": False,
        }

    if any(use_literature_filter_v2(case) for case in enabled_cases):
        backend_mode = "mixed_v1_and_literature_comparison_v2"

    final_rows = rows
    if selected_case_ids and candidates_tsv.exists() and candidates_tsv.stat().st_size > 0:
        final_rows = merge_rows_by_keys(read_tsv_rows(candidates_tsv), rows, ["case_id", "candidate_id"])

    write_tsv(
        candidates_tsv,
        final_rows,
        [
            "case_id",
            "target_id",
            "library_id",
            "candidate_id",
            "priority_tier",
            "filter_decision",
            "filter_reason",
        ],
    )

    runtime_seconds = time.perf_counter() - started_at
    run_manifest = update_run_manifest(
        run_manifest_path,
        args.module,
        runtime_seconds,
        "executed",
        backend_mode,
        case_updates,
    )

    summary_payload = {
        "module": "filtering",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_seconds": round(runtime_seconds, 6),
        "execution_status": "executed",
        "selected_case_ids": [row["case_id"] for row in enabled_cases],
        "partial_rerun_active": bool(selected_case_ids),
        "enabled_benchmark_case_count": len(enabled_cases),
        "candidate_count": len(kept_rows),
        "evaluated_candidate_count": len(final_rows),
        "decision_counts": decision_counts,
        "candidates_per_case": count_case_ids(kept_rows),
        "filter_policy": backend_mode,
        "consumed_inputs": {
            "docking_results": "07_results/modules/classical_docking/docking_results.tsv",
            "reranked_candidates": "07_results/modules/ai_reranking/reranked_candidates.tsv",
            "prepared_library": "07_results/modules/compound_library_preparation/prepared_library.tsv",
            "benchmark_cases": args.input_manifest,
        },
        "source_run_manifest": args.run_manifest,
    }
    write_json(summary_json, summary_payload)

    markdown_lines = [
        "# Filtering",
        "",
        f"- Filter policy: `{backend_mode}`",
        f"- Runtime seconds: `{round(runtime_seconds, 6)}`",
        "- Execution status: `executed`",
        f"- Partial rerun active: `{bool(selected_case_ids)}`",
        f"- Enabled benchmark cases: `{len(enabled_cases)}`",
        f"- Evaluated candidates: `{len(final_rows)}`",
        f"- Kept candidates: `{decision_counts['keep']}`",
        f"- Excluded for missing/anomalous values: `{decision_counts['exclude_missing_or_anomalous']}`",
        f"- Excluded by score/rule: `{decision_counts['exclude_by_rule']}`",
        "",
        "## Kept Candidates Per Case",
        "",
    ]
    for case_id, count in count_case_ids(kept_rows).items():
        markdown_lines.append(f"- `{case_id}`: `{count}`")
    report_md.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    payload = {
        "module": args.module,
        "status": "filtering_completed",
        "config": args.config,
        "project_root": args.project_root,
        "run_manifest": args.run_manifest,
        "input_manifest": args.input_manifest,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validation": {
            "run_manifest_exists": Path(args.run_manifest).exists(),
            "input_manifest_exists": Path(args.input_manifest).exists(),
            "docking_results_exists": docking_results_tsv.exists(),
            "reranked_candidates_exists": reranked_tsv.exists(),
            "prepared_library_exists": prepared_library_tsv.exists(),
            "filtered_candidates_written": candidates_tsv.exists(),
            "filter_summary_written": summary_json.exists(),
            "filter_report_written": report_md.exists(),
        },
        "run_context": {
            "run_mode": run_manifest.get("mode"),
            "enabled_benchmark_cases": run_manifest.get("counts", {}).get("enabled_benchmark_cases"),
        },
        "execution": {
            "runtime_seconds": round(runtime_seconds, 6),
            "execution_status": "executed",
            "backend_mode": backend_mode,
            "skipped_cache": False,
            "skip_reason": "",
            "selected_case_ids": [row["case_id"] for row in enabled_cases],
            "partial_rerun_active": bool(selected_case_ids),
        },
        "module_profile": {
            "stage_type": "filtering",
            "primary_inputs": ["benchmark case metadata", "docking results", "reranked candidates", "prepared library"],
            "primary_outputs": [str(candidates_tsv), str(summary_json), str(report_md), args.output],
            "next_action_hint": "extend this lightweight filter with case-aware comparison policies before adding heavier chemistry filters",
        },
        "input_summary": {
            "row_count": len(benchmark_cases),
            "preview_ids": [row["case_id"] for row in benchmark_cases[:3]],
        },
        "filter_outputs": {
            "filtered_candidates_tsv": str(candidates_tsv),
            "filter_summary_json": str(summary_json),
            "filter_report_markdown": str(report_md),
            "candidate_count": len(kept_rows),
            "evaluated_candidate_count": len(final_rows),
        },
        "cache": {
            "signature": cache_signature,
            "cache_scope": "module",
            "cache_hit": False,
            "cache_hit_artifact": False,
        },
        "notes": [
            "Filtering now consumes real docking affinity, rerank score, lightweight physicochemical fields, and benchmark case metadata.",
            "Decisions are explicitly separated into keep, missing_or_anomalous exclusion, and rule-based exclusion.",
        ],
    }

    write_json(output_path, payload)
    print(f"[module] wrote filtered candidates: {candidates_tsv}")
    print(f"[module] wrote filter summary: {summary_json}")
    print(f"[module] wrote filter report: {report_md}")
    print(f"[module] wrote module artifact: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
