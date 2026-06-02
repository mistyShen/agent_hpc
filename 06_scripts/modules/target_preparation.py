#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare lightweight target inputs for docking.")
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


def write_cleaned_pdb(source_path: Path, dest_path: Path) -> None:
    """Keep blank-altloc atoms and a single A conformer to avoid duplicate pocket atoms."""
    cleaned_lines: list[str] = []
    with source_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith(("ATOM", "HETATM")):
                altloc = line[16].strip()
                if altloc and altloc != "A":
                    continue
                if altloc == "A":
                    line = f"{line[:16]} {line[17:]}"
            cleaned_lines.append(line)
    dest_path.write_text("".join(cleaned_lines), encoding="utf-8")


def parse_scalar(value: str) -> object:
    raw = value.strip()
    if not raw:
        return ""
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw.strip("\"'")


def load_classical_docking_settings(path: Path) -> dict[str, object]:
    settings: dict[str, object] = {
        "box_source": "centroid_fixed",
        "default_box_size": 12.0,
        "backend": "scaffold_heuristic",
        "backend_env_prefix": "",
    }
    in_modules = False
    in_classical_docking = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if indent == 0:
            in_modules = stripped == "modules:"
            in_classical_docking = False
            continue
        if in_modules and indent == 2 and stripped.endswith(":"):
            in_classical_docking = stripped == "classical_docking:"
            continue
        if in_classical_docking and indent == 4 and ":" in stripped:
            key, value = stripped.split(":", 1)
            settings[key.strip()] = parse_scalar(value)
    return settings


def write_tsv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def merge_rows_by_key(
    existing_rows: list[dict[str, str]],
    new_rows: list[dict[str, object]],
    key_field: str,
) -> list[dict[str, object]]:
    replacement_keys = {str(row[key_field]) for row in new_rows}
    merged: list[dict[str, object]] = [row for row in existing_rows if str(row[key_field]) not in replacement_keys]
    merged.extend(new_rows)
    return merged


def file_signature(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def build_cache_signature(
    input_manifest: Path,
    config_path: Path,
    target_rows: list[dict[str, str]],
    settings: dict[str, object],
) -> dict[str, object]:
    return {
        "input_manifest": file_signature(input_manifest),
        "config": file_signature(config_path),
        "target_count": len(target_rows),
        "target_ids": [row["target_id"] for row in target_rows],
        "manual_box_targets": [
            {
                "target_id": row["target_id"],
                "center_x": row.get("center_x", "").strip(),
                "center_y": row.get("center_y", "").strip(),
                "center_z": row.get("center_z", "").strip(),
                "size_x": row.get("size_x", "").strip(),
                "size_y": row.get("size_y", "").strip(),
                "size_z": row.get("size_z", "").strip(),
            }
            for row in target_rows
            if row.get("center_x", "").strip()
        ],
        "box_source": settings.get("box_source", "centroid_fixed"),
        "default_box_size": settings.get("default_box_size", 12.0),
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


def summarize_pdb(path: Path) -> dict[str, int]:
    atom_count = 0
    hetatm_count = 0
    chains: set[str] = set()
    residues: set[tuple[str, str, str]] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = line[:6].strip()
            if record not in {"ATOM", "HETATM"}:
                continue
            chain_id = line[21].strip() or "_"
            res_name = line[17:20].strip()
            res_seq = line[22:26].strip()
            chains.add(chain_id)
            residues.add((chain_id, res_name, res_seq))
            if record == "ATOM":
                atom_count += 1
            else:
                hetatm_count += 1
    return {
        "atom_count": atom_count,
        "hetatm_count": hetatm_count,
        "chain_count": len(chains),
        "residue_count": len(residues),
    }


def estimate_box_from_pdb(path: Path, default_box_size: float) -> dict[str, float]:
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line[:6].strip() not in {"ATOM", "HETATM"}:
                continue
            xs.append(float(line[30:38].strip()))
            ys.append(float(line[38:46].strip()))
            zs.append(float(line[46:54].strip()))
    if not xs:
        raise SystemExit(f"no ATOM/HETATM coordinates found in target file: {path}")
    return {
        "center_x": round(sum(xs) / len(xs), 3),
        "center_y": round(sum(ys) / len(ys), 3),
        "center_z": round(sum(zs) / len(zs), 3),
        "size_x": round(default_box_size, 3),
        "size_y": round(default_box_size, 3),
        "size_z": round(default_box_size, 3),
    }


def manual_box_from_row(row: dict[str, str]) -> dict[str, float] | None:
    required = ["center_x", "center_y", "center_z", "size_x", "size_y", "size_z"]
    if not all(row.get(field, "").strip() for field in required):
        return None
    return {field: round(float(row[field]), 3) for field in required}


def main() -> int:
    started_at = time.perf_counter()
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_manifest_path = Path(args.run_manifest)
    config_path = Path(args.config)
    input_manifest_path = Path(args.input_manifest)
    run_manifest = load_json(run_manifest_path)
    classical_docking_settings = load_classical_docking_settings(config_path)
    target_rows = read_tsv_rows(input_manifest_path)
    benchmark_case_path = Path("04_metadata/benchmark_cases.tsv")
    benchmark_cases = read_tsv_rows(benchmark_case_path) if benchmark_case_path.exists() else []
    selected_case_ids = selected_case_ids_from_env()
    if selected_case_ids:
        benchmark_cases = [row for row in benchmark_cases if row.get("case_id", "") in selected_case_ids]
        selected_target_ids = {row["target_id"] for row in benchmark_cases}
        target_rows = [row for row in target_rows if row["target_id"] in selected_target_ids]
    related_cases_by_target: dict[str, list[str]] = {}
    for row in benchmark_cases:
        related_cases_by_target.setdefault(row["target_id"], []).append(row["case_id"])
    case_scope_ids = sorted({case_id for case_ids in related_cases_by_target.values() for case_id in case_ids})

    module_dir = output_path.parent
    prepared_dir = module_dir / "prepared_structures"
    prepared_dir.mkdir(parents=True, exist_ok=True)
    prepared_targets_tsv = module_dir / "prepared_targets.tsv"
    docking_manifest_tsv = module_dir / "target_file_manifest.tsv"
    summary_json = module_dir / "target_summary.json"
    report_md = module_dir / "target_preparation_report.md"
    cache_signature = build_cache_signature(
        input_manifest_path,
        config_path,
        target_rows,
        classical_docking_settings,
    )
    existing_done = load_existing_done(output_path)
    primary_outputs = [prepared_targets_tsv, docking_manifest_tsv, summary_json, report_md]
    if (
        existing_done is not None
        and existing_done.get("cache", {}).get("signature") == cache_signature
        and outputs_ready(primary_outputs)
    ):
        if summary_json.exists() and summary_json.stat().st_size > 0:
            cached_summary = load_json(summary_json)
            cached_summary["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
            cached_summary["selected_case_ids"] = case_scope_ids
            cached_summary["partial_rerun_active"] = bool(selected_case_ids)
            write_json(summary_json, cached_summary)
        run_manifest = update_run_manifest(
            run_manifest_path,
            args.module,
            0.0,
            "skipped_cache",
            "lightweight_copy_annotation",
            {
                case_id: {
                    "runtime_seconds": 0.0,
                    "execution_status": "skipped_cache",
                    "backend_mode": "lightweight_copy_annotation",
                    "skipped_cache": True,
                    "skip_reason": "cache_signature_match",
                    "cache_hit_artifact": True,
                }
                for case_id in case_scope_ids
            },
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
                "backend_mode": "lightweight_copy_annotation",
                "skipped_cache": True,
                "skip_reason": "cache_signature_match",
                "selected_case_ids": case_scope_ids,
                "partial_rerun_active": bool(selected_case_ids),
            },
            "cache": {
                "signature": cache_signature,
                "cache_scope": "module",
                "cache_hit": True,
                "cache_hit_artifact": True,
            },
        }
        write_json(output_path, payload)
        print(f"[module] skipped target preparation via cache: {prepared_targets_tsv}")
        print(f"[module] wrote module artifact: {output_path}")
        return 0

    prepared_targets: list[dict[str, object]] = []
    target_manifest_rows: list[dict[str, object]] = []
    reused_target_count = 0
    case_updates: dict[str, dict[str, object]] = {}

    for row in target_rows:
        target_started_at = time.perf_counter()
        source_path = Path(row["structure_path"])
        prepared_path = prepared_dir / f"{row['target_id']}_prepared.pdb"
        receptor_pdbqt_path = prepared_dir / f"{row['target_id']}_prepared.pdbqt"
        reused_prepared = False
        if prepared_path.exists() and source_path.stat().st_mtime_ns <= prepared_path.stat().st_mtime_ns:
            reused_target_count += 1
            reused_prepared = True
        else:
            write_cleaned_pdb(source_path, prepared_path)
        pdb_stats = summarize_pdb(prepared_path)
        manual_box = manual_box_from_row(row)
        box_params = manual_box or estimate_box_from_pdb(
            prepared_path,
            float(classical_docking_settings.get("default_box_size", 12.0)),
        )

        prepared_targets.append(
            {
                "target_id": row["target_id"],
                "species": row["species"],
                "target_type": row["target_type"],
                "structure_source": row["structure_source"],
                "source_structure_path": row["structure_path"],
                "prepared_structure_path": str(prepared_path),
                "receptor_pdbqt_path": str(receptor_pdbqt_path),
                **pdb_stats,
                **box_params,
                "preparation_status": "prepared",
            }
        )
        target_manifest_rows.append(
            {
                "target_id": row["target_id"],
                "prepared_structure_path": str(prepared_path),
                "receptor_pdbqt_path": str(receptor_pdbqt_path),
                "target_type": row["target_type"],
                "chain_count": pdb_stats["chain_count"],
                "residue_count": pdb_stats["residue_count"],
                **box_params,
                "docking_ready": "true",
            }
        )
        for case_id in related_cases_by_target.get(row["target_id"], []):
            case_updates[case_id] = {
                "runtime_seconds": time.perf_counter() - target_started_at,
                "execution_status": "executed",
                "backend_mode": "lightweight_copy_annotation",
                "skipped_cache": False,
                "skip_reason": "",
                "cache_hit_artifact": reused_prepared,
            }

    final_prepared_targets = prepared_targets
    final_target_manifest_rows = target_manifest_rows
    if selected_case_ids and prepared_targets_tsv.exists() and prepared_targets_tsv.stat().st_size > 0:
        final_prepared_targets = merge_rows_by_key(read_tsv_rows(prepared_targets_tsv), prepared_targets, "target_id")
    if selected_case_ids and docking_manifest_tsv.exists() and docking_manifest_tsv.stat().st_size > 0:
        final_target_manifest_rows = merge_rows_by_key(read_tsv_rows(docking_manifest_tsv), target_manifest_rows, "target_id")

    write_tsv(
        prepared_targets_tsv,
        final_prepared_targets,
        [
            "target_id",
            "species",
            "target_type",
            "structure_source",
            "source_structure_path",
            "prepared_structure_path",
            "receptor_pdbqt_path",
            "atom_count",
            "hetatm_count",
            "chain_count",
            "residue_count",
            "center_x",
            "center_y",
            "center_z",
            "size_x",
            "size_y",
            "size_z",
            "preparation_status",
        ],
    )
    write_tsv(
        docking_manifest_tsv,
        final_target_manifest_rows,
        [
            "target_id",
            "prepared_structure_path",
            "receptor_pdbqt_path",
            "target_type",
            "chain_count",
            "residue_count",
            "center_x",
            "center_y",
            "center_z",
            "size_x",
            "size_y",
            "size_z",
            "docking_ready",
        ],
    )

    summary_payload = {
        "module": "target_preparation",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_count": len(final_prepared_targets),
        "prepared_target_count": sum(row["preparation_status"] == "prepared" for row in final_prepared_targets),
        "prepared_targets_tsv": str(prepared_targets_tsv),
        "target_file_manifest_tsv": str(docking_manifest_tsv),
        "box_source": "mixed_manual_and_centroid"
        if any(manual_box_from_row(row) is not None for row in target_rows)
        else classical_docking_settings.get("box_source", "centroid_fixed"),
        "selected_case_ids": case_scope_ids,
        "partial_rerun_active": bool(selected_case_ids),
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8")

    markdown = "\n".join(
        [
            "# Target Preparation",
            "",
            f"- Targets processed: `{len(final_prepared_targets)}`",
            f"- Prepared targets: `{summary_payload['prepared_target_count']}`",
            f"- Reused prepared structures: `{reused_target_count}`",
            f"- Prepared table: `{prepared_targets_tsv}`",
            f"- Docking manifest: `{docking_manifest_tsv}`",
            "",
        ]
    )
    report_md.write_text(markdown + "\n", encoding="utf-8")

    runtime_seconds = round(time.perf_counter() - started_at, 6)
    run_manifest = update_run_manifest(
        run_manifest_path,
        args.module,
        runtime_seconds,
        "executed",
        "lightweight_copy_annotation",
        case_updates,
    )

    payload = {
        "module": args.module,
        "status": "target_preparation_completed",
        "config": args.config,
        "project_root": args.project_root,
        "run_manifest": args.run_manifest,
        "input_manifest": args.input_manifest,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validation": {
            "run_manifest_exists": Path(args.run_manifest).exists(),
            "input_manifest_exists": Path(args.input_manifest).exists(),
            "prepared_targets_written": prepared_targets_tsv.exists(),
            "target_manifest_written": docking_manifest_tsv.exists(),
            "summary_written": summary_json.exists(),
            "report_written": report_md.exists(),
        },
        "run_context": {
            "run_mode": run_manifest.get("mode"),
            "enabled_benchmark_cases": run_manifest.get("counts", {}).get("enabled_benchmark_cases"),
        },
        "execution": {
            "runtime_seconds": runtime_seconds,
            "execution_status": "executed",
            "backend_mode": "lightweight_copy_annotation",
            "skipped_cache": False,
            "skip_reason": "",
            "selected_case_ids": case_scope_ids,
            "partial_rerun_active": bool(selected_case_ids),
        },
        "module_profile": {
            "stage_type": "target_preparation",
            "primary_inputs": ["target metadata", "PDB target file"],
            "primary_outputs": [
                str(prepared_targets_tsv),
                str(docking_manifest_tsv),
                str(summary_json),
                str(report_md),
                args.output,
            ],
            "next_action_hint": "attach structure cleanup, chain selection, and binding-site preparation later",
        },
        "input_summary": {
            "row_count": len(target_rows),
            "preview_ids": [row["target_id"] for row in target_rows[:3]],
        },
        "target_outputs": {
            "prepared_targets_tsv": str(prepared_targets_tsv),
            "target_file_manifest_tsv": str(docking_manifest_tsv),
            "target_summary_json": str(summary_json),
            "target_report_markdown": str(report_md),
            "box_source": classical_docking_settings.get("box_source", "centroid_fixed"),
            "reused_target_count": reused_target_count,
        },
        "cache": {
            "signature": cache_signature,
            "cache_scope": "module_plus_prepared_target_files",
            "cache_hit": False,
            "cache_hit_artifact": reused_target_count > 0,
        },
        "notes": [
            "Target preparation now copies and annotates a small example PDB target set.",
            "Structure preparation is intentionally lightweight and does not alter coordinates in this minimal CPU-only implementation.",
            "Docking box coordinates are estimated from the target atom centroid with a fixed box size.",
        ],
    }

    write_json(output_path, payload)
    print(f"[module] wrote prepared targets table: {prepared_targets_tsv}")
    print(f"[module] wrote target docking manifest: {docking_manifest_tsv}")
    print(f"[module] wrote target summary: {summary_json}")
    print(f"[module] wrote module report: {report_md}")
    print(f"[module] wrote module artifact: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
