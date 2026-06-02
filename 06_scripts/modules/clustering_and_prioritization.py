#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate lightweight clustering and prioritization outputs.")
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


def write_tsv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def merge_rows_by_keys(
    existing_rows: list[dict[str, str]],
    new_rows: list[dict[str, object]],
    key_fields: list[str],
) -> list[dict[str, object]]:
    replacement_keys = {tuple(str(row[field]) for field in key_fields) for row in new_rows}
    merged: list[dict[str, object]] = [
        row for row in existing_rows if tuple(str(row[field]) for field in key_fields) not in replacement_keys
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


def parse_simple_yaml_config(path: Path) -> dict[str, object]:
    result: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, result)]
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if not value:
            child: dict[str, object] = {}
            current[key] = child
            stack.append((indent, child))
            continue
        if value.lower() in {"true", "false"}:
            parsed: object = value.lower() == "true"
        elif value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            parsed = int(value)
        else:
            try:
                parsed = float(value)
            except ValueError:
                parsed = value.strip("'\"")
        current[key] = parsed
    return result


def config_value(config: dict[str, object], keys: list[str], default: object) -> object:
    current: object = config
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def load_v3_priority_tuning(config: dict[str, object]) -> dict[str, float | int]:
    return {
        "top1_only_gap": float(
            config_value(config, ["modules", "clustering_and_prioritization", "v3_priority", "top1_only_gap"], 0.75)
        ),
        "top2_gap": float(
            config_value(config, ["modules", "clustering_and_prioritization", "v3_priority", "top2_gap"], 0.35)
        ),
        "mid_gap_shortlist_cap": int(
            config_value(
                config,
                ["modules", "clustering_and_prioritization", "v3_priority", "mid_gap_shortlist_cap"],
                2,
            )
        ),
    }


def build_cache_signature(
    input_manifest: Path,
    config_path: Path,
    docking_results_tsv: Path,
    reranked_tsv: Path,
    filtered_tsv: Path,
    enabled_cases: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "module_source": file_signature(Path(__file__)),
        "input_manifest": file_signature(input_manifest),
        "config": file_signature(config_path),
        "docking_results_tsv": file_signature(docking_results_tsv),
        "reranked_candidates_tsv": file_signature(reranked_tsv),
        "filtered_candidates_tsv": file_signature(filtered_tsv),
        "enabled_case_ids": [row["case_id"] for row in enabled_cases],
        "enabled_case_count": len(enabled_cases),
    }


def stable_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def assign_cluster(smiles: str) -> str:
    if "c1ccccc1" in smiles:
        return "aromatic_ring"
    if "N" in smiles:
        return "amine_like"
    if "O" in smiles:
        return "oxygenated_small_molecule"
    return "other"


def priority_bucket(rank: int) -> str:
    if rank == 1:
        return "tier_1"
    if rank == 2:
        return "tier_2"
    return "tier_3"


def parse_float(value: str) -> float:
    stripped = value.strip()
    if not stripped:
        return 0.0
    return float(stripped)


def parse_int(value: str, default: int = 0) -> int:
    stripped = value.strip()
    if not stripped:
        return default
    return int(stripped)


def rerank_key(row: dict[str, str]) -> tuple[float, float, int]:
    rerank_score = parse_float(row["rerank_score"])
    vina_affinity = parse_float(row.get("vina_affinity_kcal_mol", row["docking_score"]))
    rerank_rank = int(row["rerank_rank"]) if row.get("rerank_rank", "").strip() else 999999
    return (rerank_score, vina_affinity, rerank_rank)


def rerank_key_v3_aware(row: dict[str, str]) -> tuple[float, float, float, int]:
    rerank_score = parse_float(row["rerank_score"])
    vina_affinity = parse_float(row.get("vina_affinity_kcal_mol", row["docking_score"]))
    penalty_proxy = -parse_float(row.get("rerank_bonus", "0"))
    rerank_rank = parse_int(row.get("rerank_rank", ""), 999999)
    return (rerank_score, vina_affinity, penalty_proxy, rerank_rank)


def use_v3_priority_policy(case_row: dict[str, str], case_records: list[dict[str, str]]) -> bool:
    if case_row.get("rerank_strategy", "").strip() == "ai_rerank_v3":
        return True
    return any(row.get("rerank_model", "").strip() == "cpu_docking_rerank_v3" for row in case_records)


def shortlist_cap_v3(case_records: list[dict[str, str]], tuning: dict[str, float | int]) -> int:
    if len(case_records) <= 1:
        return len(case_records)
    top_score = parse_float(case_records[0]["rerank_score"])
    second_score = parse_float(case_records[1]["rerank_score"])
    score_gap = second_score - top_score
    if score_gap >= float(tuning["top1_only_gap"]):
        return 1
    if score_gap >= float(tuning["top2_gap"]):
        return min(int(tuning["mid_gap_shortlist_cap"]), len(case_records))
    return len(case_records)


def top_score_gap(case_records: list[dict[str, str]]) -> float:
    if len(case_records) <= 1:
        return 0.0
    top_score = parse_float(case_records[0]["rerank_score"])
    second_score = parse_float(case_records[1]["rerank_score"])
    return round(second_score - top_score, 3)


def build_case_cache_signature(
    case_row: dict[str, str],
    case_backend_mode: str,
    case_records: list[dict[str, str]],
    v3_priority_tuning: dict[str, float | int],
) -> str:
    payload = {
        "module_source": file_signature(Path(__file__)),
        "case_id": case_row.get("case_id", ""),
        "rerank_strategy": case_row.get("rerank_strategy", ""),
        "filter_policy": case_row.get("filter_policy", ""),
        "clustering_policy": case_row.get("clustering_policy", ""),
        "backend_mode": case_backend_mode,
        "v3_priority_tuning": v3_priority_tuning if case_backend_mode == "filter_keep_then_v3_rerank_margin_then_vina_v2" else {},
        "records": [
            {
                "compound_id": row["compound_id"],
                "standardized_smiles": row.get("standardized_smiles", ""),
                "docking_score": row.get("docking_score", ""),
                "vina_affinity_kcal_mol": row.get("vina_affinity_kcal_mol", ""),
                "rerank_score": row.get("rerank_score", ""),
                "rerank_rank": row.get("rerank_rank", ""),
                "rerank_bonus": row.get("rerank_bonus", ""),
                "rerank_model": row.get("rerank_model", ""),
                "filter_reason": row.get("filter_reason", ""),
            }
            for row in sorted(case_records, key=lambda item: item["compound_id"])
        ],
    }
    return stable_digest(payload)


def main() -> int:
    started_at = time.perf_counter()
    read_started_at = started_at
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_manifest_path = Path(args.run_manifest)
    input_manifest_path = Path(args.input_manifest)
    config_path = Path(args.config)
    config_payload = parse_simple_yaml_config(config_path)
    v3_priority_tuning = load_v3_priority_tuning(config_payload)
    run_manifest = load_json(run_manifest_path)
    benchmark_cases = read_tsv_rows(input_manifest_path)
    docking_results_tsv = Path("07_results/modules/classical_docking/docking_results.tsv")
    reranked_tsv = Path("07_results/modules/ai_reranking/reranked_candidates.tsv")
    filtered_tsv = Path("07_results/modules/filtering/filtered_candidates.tsv")
    docking_rows = read_tsv_rows(docking_results_tsv)
    rerank_rows = read_tsv_rows(reranked_tsv)
    filtered_rows = read_tsv_rows(filtered_tsv)
    filtering_summary_path = Path("07_results/modules/filtering/filter_summary.json")
    evaluation_summary_path = Path("09_reports/benchmark_evaluation.json")
    filtering_summary = load_json(filtering_summary_path) if filtering_summary_path.exists() else None
    evaluation_summary = load_json(evaluation_summary_path) if evaluation_summary_path.exists() else None

    enabled_cases = [row for row in benchmark_cases if row.get("enabled", "").strip().lower() == "true"]
    selected_case_ids = selected_case_ids_from_env()
    if selected_case_ids:
        enabled_cases = [row for row in enabled_cases if row["case_id"] in selected_case_ids]
    backend_mode = "filter_keep_then_rerank_score_then_vina_affinity_v1"
    read_runtime_seconds = time.perf_counter() - read_started_at
    output_rows: list[dict[str, object]] = []
    cluster_counts: dict[str, int] = {}
    kept_candidate_count = 0
    case_priority_policies: list[dict[str, object]] = []
    case_diagnostics: list[dict[str, object]] = []

    docking_by_key = {(row["case_id"], row["compound_id"]): row for row in docking_rows}
    rerank_by_key = {(row["case_id"], row["compound_id"]): row for row in rerank_rows}

    module_dir = output_path.parent
    clustered_tsv = module_dir / "clustered_priorities.tsv"
    summary_json = module_dir / "clustering_summary.json"
    report_md = module_dir / "clustering_report.md"
    primary_outputs = [clustered_tsv, summary_json, report_md]
    cache_signature = build_cache_signature(
        input_manifest_path,
        config_path,
        docking_results_tsv,
        reranked_tsv,
        filtered_tsv,
        enabled_cases,
    )
    existing_done = load_existing_done(output_path)
    existing_summary = load_json(summary_json) if summary_json.exists() and summary_json.stat().st_size > 0 else {}
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
        print(f"[module] reused cached clustering outputs: {clustered_tsv}")
        return 0

    case_updates: dict[str, dict[str, object]] = {}
    scoring_started_at = time.perf_counter()
    existing_case_cache = existing_done.get("case_cache", {}) if existing_done is not None else {}
    existing_clustered_rows = read_tsv_rows(clustered_tsv) if clustered_tsv.exists() and clustered_tsv.stat().st_size > 0 else []
    existing_rows_by_case: dict[str, list[dict[str, str]]] = {}
    for row in existing_clustered_rows:
        existing_rows_by_case.setdefault(row["case_id"], []).append(row)
    existing_case_priority = {
        row["case_id"]: row
        for row in existing_summary.get("case_priority_policies", [])
        if isinstance(row, dict) and "case_id" in row
    } if isinstance(existing_summary, dict) else {}
    existing_case_diagnostics = {
        row["case_id"]: row
        for row in existing_summary.get("case_diagnostics", [])
        if isinstance(row, dict) and "case_id" in row
    } if isinstance(existing_summary, dict) else {}
    case_cache_payload: dict[str, dict[str, object]] = {}
    for case in enabled_cases:
        case_started_at = time.perf_counter()
        case_id = case["case_id"]
        case_backend_mode = backend_mode
        kept_candidates = [
            row
            for row in filtered_rows
            if row["case_id"] == case_id and row.get("filter_decision", "") == "keep"
        ]
        case_records: list[dict[str, str]] = []
        for filtered_row in kept_candidates:
            compound_id = filtered_row["candidate_id"]
            docking_row = docking_by_key.get((case_id, compound_id))
            rerank_row = rerank_by_key.get((case_id, compound_id))
            if docking_row is None or rerank_row is None:
                continue
            case_records.append(
                {
                    **docking_row,
                    "rerank_score": rerank_row["rerank_score"],
                    "rerank_rank": rerank_row["rerank_rank"],
                    "rerank_bonus": rerank_row.get("rerank_bonus", "0"),
                    "rerank_model": rerank_row.get("rerank_model", ""),
                    "filter_reason": filtered_row["filter_reason"],
                }
            )

        v3_priority_policy = use_v3_priority_policy(case, case_records)
        if v3_priority_policy:
            case_backend_mode = "filter_keep_then_v3_rerank_margin_then_vina_v2"
            case_records.sort(key=rerank_key_v3_aware)
            case_shortlist_cap = shortlist_cap_v3(case_records, v3_priority_tuning)
            selected_records = case_records[:case_shortlist_cap]
            selection_reason = "sorted_by_v3_rerank_score_then_vina_then_penalty_with_margin_cap"
        else:
            case_records.sort(key=rerank_key)
            case_shortlist_cap = len(case_records)
            selected_records = case_records
            selection_reason = "sorted_by_filter_keep_then_rerank_score_then_vina_affinity"
        case_signature = build_case_cache_signature(case, case_backend_mode, case_records, v3_priority_tuning)
        cached_case = existing_case_cache.get(case_id, {}) if isinstance(existing_case_cache, dict) else {}
        cached_case_rows = existing_rows_by_case.get(case_id, [])
        if (
            cached_case.get("signature") == case_signature
            and len(cached_case_rows) == len(selected_records)
            and case_id in existing_case_priority
            and case_id in existing_case_diagnostics
        ):
            output_rows.extend(cached_case_rows)
            cached_policy = dict(existing_case_priority[case_id])
            cached_policy["cache_status"] = "hit"
            case_priority_policies.append(cached_policy)
            cached_diag = dict(existing_case_diagnostics[case_id])
            cached_diag["runtime_seconds"] = round(time.perf_counter() - case_started_at, 6)
            cached_diag["cache_status"] = "hit"
            case_diagnostics.append(cached_diag)
            case_runtime_seconds = time.perf_counter() - case_started_at
            case_updates[case_id] = {
                "runtime_seconds": case_runtime_seconds,
                "execution_status": "skipped_cache",
                "backend_mode": case_backend_mode,
                "prioritized_candidate_count": len(cached_case_rows),
                "skipped_cache": True,
                "skip_reason": "case_signature_match",
                "cache_hit_artifact": True,
            }
            case_cache_payload[case_id] = {
                "signature": case_signature,
                "backend_mode": case_backend_mode,
                "shortlist_row_count": len(cached_case_rows),
                "cache_status": "hit",
            }
            continue
        kept_candidate_count += len(selected_records)
        score_gap = top_score_gap(case_records)
        case_priority_policies.append(
            {
                "case_id": case_id,
                "selection_policy": case_backend_mode,
                "filter_keep_input_count": len(case_records),
                "shortlist_count": len(selected_records),
                "shortlist_cap": case_shortlist_cap,
                "top_score_gap": score_gap,
                "v3_priority_policy": v3_priority_policy,
                "v3_priority_tuning": v3_priority_tuning if v3_priority_policy else {},
                "cache_status": "miss",
            }
        )
        case_diagnostics.append(
            {
                "case_id": case_id,
                "selection_policy": case_backend_mode,
                "filter_keep_input_count": len(case_records),
                "shortlist_count": len(selected_records),
                "shortlist_cap": case_shortlist_cap,
                "top_score_gap": score_gap,
                "v3_priority_policy": v3_priority_policy,
                "v3_priority_tuning": v3_priority_tuning if v3_priority_policy else {},
                "runtime_seconds": round(time.perf_counter() - case_started_at, 6),
                "cache_status": "miss",
                "top_preview": [
                    {
                        "compound_id": row["compound_id"],
                        "rerank_score": row["rerank_score"],
                        "vina_affinity_kcal_mol": row.get("vina_affinity_kcal_mol", ""),
                        "rerank_bonus": row.get("rerank_bonus", "0"),
                        "rerank_model": row.get("rerank_model", ""),
                    }
                    for row in case_records[:3]
                ],
            }
        )
        for rank, row in enumerate(selected_records, start=1):
            cluster_id = assign_cluster(row["standardized_smiles"])
            cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1
            output_rows.append(
                {
                    "case_id": row["case_id"],
                    "compound_id": row["compound_id"],
                    "cluster_id": cluster_id,
                    "priority_rank": rank,
                    "priority_tier": priority_bucket(rank),
                    "docking_score": row["docking_score"],
                    "selection_reason": selection_reason,
                }
            )
        case_updates[case_id] = {
            "runtime_seconds": time.perf_counter() - case_started_at,
            "execution_status": "executed",
            "backend_mode": case_backend_mode,
            "prioritized_candidate_count": len(selected_records),
            "skipped_cache": False,
            "skip_reason": "",
            "cache_hit_artifact": False,
        }
        case_cache_payload[case_id] = {
            "signature": case_signature,
            "backend_mode": case_backend_mode,
            "shortlist_row_count": len(selected_records),
            "cache_status": "miss",
        }

    if any(policy["v3_priority_policy"] for policy in case_priority_policies):
        backend_mode = "mixed_v1_and_v3_priority_v2"
    scoring_runtime_seconds = time.perf_counter() - scoring_started_at

    output_started_at = time.perf_counter()
    final_rows: list[dict[str, object]] = output_rows
    if selected_case_ids and clustered_tsv.exists() and clustered_tsv.stat().st_size > 0:
        existing_rows = read_tsv_rows(clustered_tsv)
        final_rows = [row for row in existing_rows if row["case_id"] not in selected_case_ids]
        final_rows.extend(output_rows)

    write_tsv(
        clustered_tsv,
        final_rows,
        [
            "case_id",
            "compound_id",
            "cluster_id",
            "priority_rank",
            "priority_tier",
            "docking_score",
            "selection_reason",
        ],
    )

    runtime_seconds = time.perf_counter() - started_at
    output_runtime_seconds = time.perf_counter() - output_started_at
    run_manifest = update_run_manifest(
        run_manifest_path,
        args.module,
        runtime_seconds,
        "executed",
        backend_mode,
        case_updates,
    )

    summary_payload = {
        "module": "clustering_and_prioritization",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_seconds": round(runtime_seconds, 6),
        "execution_status": "executed",
        "selected_case_ids": [row["case_id"] for row in enabled_cases],
        "partial_rerun_active": bool(selected_case_ids),
        "enabled_case_count": len(enabled_cases),
        "prioritized_candidate_count": len(final_rows),
        "filter_keep_input_count": sum(policy.get("filter_keep_input_count", 0) for policy in case_priority_policies),
        "shortlist_output_count": sum(policy.get("shortlist_count", 0) for policy in case_priority_policies),
        "kept_candidate_count": kept_candidate_count,
        "cluster_counts": cluster_counts,
        "filtering_available": bool(filtering_summary),
        "evaluation_available": bool(evaluation_summary),
        "selection_policy": backend_mode,
        "phase_timings_seconds": {
            "read": round(read_runtime_seconds, 6),
            "scoring": round(scoring_runtime_seconds, 6),
            "output": round(output_runtime_seconds, 6),
        },
        "v3_priority_tuning": v3_priority_tuning,
        "case_priority_policies": case_priority_policies,
        "case_diagnostics": case_diagnostics,
        "output_table": str(clustered_tsv),
    }
    write_json(summary_json, summary_payload)

    markdown_lines = [
        "# Clustering And Prioritization",
        "",
        f"- Runtime seconds: `{round(runtime_seconds, 6)}`",
        f"- Read phase seconds: `{round(read_runtime_seconds, 6)}`",
        f"- Scoring phase seconds: `{round(scoring_runtime_seconds, 6)}`",
        f"- Output phase seconds: `{round(output_runtime_seconds, 6)}`",
        "- Execution status: `executed`",
        f"- Partial rerun active: `{bool(selected_case_ids)}`",
        f"- Enabled benchmark cases: `{len(enabled_cases)}`",
        f"- Filter keep input count: `{sum(policy.get('filter_keep_input_count', 0) for policy in case_priority_policies)}`",
        f"- Shortlist output count: `{sum(policy.get('shortlist_count', 0) for policy in case_priority_policies)}`",
        f"- Prioritized candidates: `{len(final_rows)}`",
        f"- Filtering available: `{bool(filtering_summary)}`",
        f"- Evaluation available: `{bool(evaluation_summary)}`",
        f"- Selection policy: `{backend_mode}`",
        f"- Output table: `{clustered_tsv}`",
        f"- v3 priority tuning: `{json.dumps(v3_priority_tuning, sort_keys=True)}`",
        "",
        "## Case Priority Policies",
        "",
    ]
    for policy in case_priority_policies:
        markdown_lines.append(
            f"- `{policy['case_id']}` -> policy `{policy['selection_policy']}` | filter keep `{policy['filter_keep_input_count']}` | shortlist `{policy['shortlist_count']}` | cap `{policy['shortlist_cap']}` | top gap `{policy['top_score_gap']}` | cache `{policy.get('cache_status', 'unknown')}`"
        )
    markdown_lines.extend(
        [
            "",
            "## Case Diagnostics",
            "",
        ]
    )
    for case_diag in case_diagnostics:
        markdown_lines.append(f"### `{case_diag['case_id']}`")
        markdown_lines.append("")
        markdown_lines.append(f"- Selection policy: `{case_diag['selection_policy']}`")
        markdown_lines.append(f"- Runtime seconds: `{case_diag['runtime_seconds']}`")
        markdown_lines.append(f"- Filter keep size: `{case_diag['filter_keep_input_count']}`")
        markdown_lines.append(f"- Shortlist size: `{case_diag['shortlist_count']}`")
        markdown_lines.append(f"- Shortlist cap: `{case_diag['shortlist_cap']}`")
        markdown_lines.append(f"- Top score gap: `{case_diag['top_score_gap']}`")
        markdown_lines.append(f"- Cache status: `{case_diag.get('cache_status', 'unknown')}`")
        if case_diag.get("v3_priority_policy"):
            markdown_lines.append(
                f"- v3 priority tuning: `{json.dumps(case_diag.get('v3_priority_tuning', {}), sort_keys=True)}`"
            )
        markdown_lines.append("- Top preview:")
        for preview_row in case_diag["top_preview"]:
            markdown_lines.append(
                f"  - `{preview_row['compound_id']}` score `{preview_row['rerank_score']}`"
                f" | vina `{preview_row['vina_affinity_kcal_mol']}`"
                f" | rerank bonus `{preview_row['rerank_bonus']}`"
                f" | model `{preview_row['rerank_model']}`"
            )
        markdown_lines.append("")
    markdown_lines.extend(
        [
            "",
            "## Cluster Counts",
            "",
        ]
    )
    for cluster_id, count in sorted(cluster_counts.items()):
        markdown_lines.append(f"- `{cluster_id}`: `{count}`")
    report_md.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    payload = {
        "module": args.module,
        "status": "clustering_completed",
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
            "filtered_candidates_exists": filtered_tsv.exists(),
            "clustered_table_written": clustered_tsv.exists(),
            "summary_written": summary_json.exists(),
            "report_written": report_md.exists(),
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
            "stage_type": "clustering_and_prioritization",
            "primary_inputs": ["filtered candidates", "reranked candidates", "docking results", "evaluation summary"],
            "primary_outputs": [str(clustered_tsv), str(summary_json), str(report_md), args.output],
            "next_action_hint": "replace heuristic clusters with similarity-aware grouping while keeping the current real shortlist chain intact",
        },
        "input_summary": {
            "row_count": len(enabled_cases),
            "preview_ids": [row["case_id"] for row in enabled_cases[:3]],
        },
        "clustering_outputs": {
            "clustered_priorities_tsv": str(clustered_tsv),
            "clustering_summary_json": str(summary_json),
            "clustering_report_markdown": str(report_md),
            "v3_priority_tuning": v3_priority_tuning,
        },
        "cache": {
            "signature": cache_signature,
            "cache_scope": "module",
            "cache_hit": False,
            "cache_hit_artifact": False,
        },
        "case_cache": case_cache_payload,
        "notes": [
            "This module now prioritizes only candidates kept by filtering and orders them using rerank score first and Vina affinity second.",
            "Cluster assignment remains lightweight and rule-based in this minimal CPU-only version.",
        ],
    }

    write_json(output_path, payload)
    print(f"[module] wrote clustered priorities: {clustered_tsv}")
    print(f"[module] wrote clustering summary: {summary_json}")
    print(f"[module] wrote clustering report: {report_md}")
    print(f"[module] wrote module artifact: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
