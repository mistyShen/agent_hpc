#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a lightweight scaffold classical docking step.")
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
        "backend": "scaffold_heuristic",
        "backend_env_prefix": "",
        "vina_cpu": 1,
        "vina_exhaustiveness": 8,
        "vina_num_modes": 1,
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


def docking_score(compound: dict[str, str], target: dict[str, str], case: dict[str, str]) -> float:
    mw = float(compound["molecular_weight_estimate"])
    heavy_atoms = int(compound["heavy_atom_count"])
    aromatic_atoms = int(compound["aromatic_atom_count"])
    hetero_atoms = int(compound["hetero_atom_count"])
    chain_count = int(target["chain_count"])
    residue_count = int(target["residue_count"])
    protocol_bias = 0.5 if case["docking_protocol"] == "cpu_placeholder" else 0.0
    raw = (
        0.08 * mw
        + 0.6 * heavy_atoms
        + 0.35 * aromatic_atoms
        + 0.25 * hetero_atoms
        + 0.4 * chain_count
        + 0.02 * residue_count
        + protocol_bias
    )
    return round(-raw, 3)


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def require_success(result: subprocess.CompletedProcess[str], step: str) -> None:
    if result.returncode == 0:
        return
    message = [
        f"{step} failed with exit code {result.returncode}",
        f"command: {' '.join(result.args)}",
    ]
    if result.stdout.strip():
        message.append(f"stdout:\n{result.stdout.strip()}")
    if result.stderr.strip():
        message.append(f"stderr:\n{result.stderr.strip()}")
    raise SystemExit("\n".join(message))


def parse_vina_affinity(log_path: Path) -> float:
    for line in log_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or not stripped[0].isdigit():
            continue
        parts = stripped.split()
        if len(parts) >= 2 and parts[0] == "1":
            return round(float(parts[1]), 3)
    raise SystemExit(f"could not parse vina affinity from log: {log_path}")


def file_signature(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def build_cache_signature(
    input_manifest: Path,
    config_path: Path,
    prepared_library_tsv: Path,
    target_manifest_tsv: Path,
    enabled_cases: list[dict[str, str]],
    settings: dict[str, object],
) -> dict[str, object]:
    return {
        "input_manifest": file_signature(input_manifest),
        "config": file_signature(config_path),
        "prepared_library_tsv": file_signature(prepared_library_tsv),
        "target_manifest_tsv": file_signature(target_manifest_tsv),
        "enabled_case_ids": [row["case_id"] for row in enabled_cases],
        "enabled_case_count": len(enabled_cases),
        "requested_backend": str(settings.get("backend", "scaffold_heuristic")),
        "vina_cpu": settings.get("vina_cpu", 1),
        "vina_exhaustiveness": settings.get("vina_exhaustiveness", 8),
        "vina_num_modes": settings.get("vina_num_modes", 1),
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


def build_backend_env(settings: dict[str, object]) -> dict[str, str]:
    env_prefix = Path(str(settings["backend_env_prefix"]))
    env = os.environ.copy()
    env["PATH"] = f"{env_prefix / 'bin'}:{env.get('PATH', '')}"
    env["BABEL_LIBDIR"] = str(env_prefix / "lib" / "openbabel" / "2.4.1")
    env["BABEL_DATADIR"] = str(env_prefix / "share" / "openbabel" / "2.4.1")
    ld_library_path = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = (
        f"{env_prefix / 'lib'}:{ld_library_path}" if ld_library_path else str(env_prefix / "lib")
    )
    return env


def require_output_file(path: Path, step: str, result: subprocess.CompletedProcess[str]) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    message = [
        f"{step} did not create expected non-empty file: {path}",
        f"command: {' '.join(result.args)}",
    ]
    if result.stdout.strip():
        message.append(f"stdout:\n{result.stdout.strip()}")
    if result.stderr.strip():
        message.append(f"stderr:\n{result.stderr.strip()}")
    raise SystemExit("\n".join(message))


def ligand_converter_path(env_bin: Path) -> Path:
    mglobabel = env_bin / "mglobabel"
    if mglobabel.exists():
        return mglobabel
    return env_bin / "obabel"


def backend_available(settings: dict[str, object]) -> bool:
    env_prefix = str(settings.get("backend_env_prefix", "")).strip()
    if not env_prefix:
        return False
    env_bin = Path(env_prefix) / "bin"
    required = [
        env_bin / "vina",
        ligand_converter_path(env_bin),
        env_bin / "prepare_receptor4.py",
        env_bin / "pythonsh",
    ]
    return all(path.exists() for path in required)


def prepare_receptor_if_needed(target: dict[str, str], settings: dict[str, object]) -> None:
    receptor_pdbqt = Path(target["receptor_pdbqt_path"])
    if receptor_pdbqt.exists():
        return
    receptor_pdbqt.parent.mkdir(parents=True, exist_ok=True)
    env_bin = Path(str(settings["backend_env_prefix"])) / "bin"
    backend_env = build_backend_env(settings)
    result = run_command(
        [
            str(env_bin / "pythonsh"),
            str(env_bin / "prepare_receptor4.py"),
            "-r",
            target["prepared_structure_path"],
            "-o",
            str(receptor_pdbqt),
            "-A",
            "hydrogens",
        ],
        env=backend_env,
    )
    require_success(result, "receptor pdbqt preparation")
    require_output_file(receptor_pdbqt, "receptor pdbqt preparation", result)


def prepare_ligand_files(
    compound: dict[str, str],
    ligand_dir: Path,
    settings: dict[str, object],
) -> tuple[Path, Path, bool]:
    env_bin = Path(str(settings["backend_env_prefix"])) / "bin"
    backend_env = build_backend_env(settings)
    ligand_dir.mkdir(parents=True, exist_ok=True)
    ligand_smiles = ligand_dir / f"{compound['compound_id']}.smi"
    ligand_pdbqt = ligand_dir / f"{compound['compound_id']}.pdbqt"
    smiles_payload = f"{compound['standardized_smiles']} {compound['compound_id']}\n"
    if ligand_smiles.exists():
        existing_smiles_payload = ligand_smiles.read_text(encoding="utf-8")
    else:
        existing_smiles_payload = None
    if existing_smiles_payload != smiles_payload:
        ligand_smiles.write_text(smiles_payload, encoding="utf-8")
    pdbqt_cache_valid = (
        ligand_pdbqt.exists()
        and ligand_pdbqt.stat().st_size > 0
        and existing_smiles_payload == smiles_payload
        and ligand_pdbqt.stat().st_mtime_ns >= ligand_smiles.stat().st_mtime_ns
    )
    if pdbqt_cache_valid:
        return ligand_smiles, ligand_pdbqt, True
    converter = ligand_converter_path(env_bin)
    to_pdbqt = run_command(
        [
            str(converter),
            "-ismi",
            str(ligand_smiles),
            "-opdbqt",
            "-O",
            str(ligand_pdbqt),
            "--gen3d",
        ],
        env=backend_env,
    )
    require_success(to_pdbqt, "ligand pdbqt conversion")
    require_output_file(ligand_pdbqt, "ligand pdbqt conversion", to_pdbqt)
    return ligand_smiles, ligand_pdbqt, False


def run_vina_docking(
    case: dict[str, str],
    compound: dict[str, str],
    target: dict[str, str],
    module_dir: Path,
    settings: dict[str, object],
) -> dict[str, object]:
    env_bin = Path(str(settings["backend_env_prefix"])) / "bin"
    ligand_dir = module_dir / "ligands" / case["case_id"]
    pose_dir = module_dir / "poses" / case["case_id"]
    log_dir = module_dir / "logs" / case["case_id"]
    pose_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    prepare_receptor_if_needed(target, settings)
    _, ligand_pdbqt, ligand_cache_hit = prepare_ligand_files(compound, ligand_dir, settings)

    pose_path = pose_dir / f"{compound['compound_id']}_pose.pdbqt"
    log_path = log_dir / f"{compound['compound_id']}.log"
    ligand_mtime_ns = ligand_pdbqt.stat().st_mtime_ns
    pose_cache_ready = pose_path.exists() and pose_path.stat().st_size > 0
    log_cache_ready = log_path.exists() and log_path.stat().st_size > 0
    artifact_cache_fresh = (
        ligand_cache_hit
        and
        pose_cache_ready
        and log_cache_ready
        and pose_path.stat().st_mtime_ns >= ligand_mtime_ns
        and log_path.stat().st_mtime_ns >= ligand_mtime_ns
    )
    if artifact_cache_fresh:
        affinity = parse_vina_affinity(log_path)
        return {
            "docking_score": affinity,
            "pose_rank": 1,
            "engine_mode": "vina_cpu",
            "backend_name": "autodock_vina",
            "receptor_pdbqt_path": target["receptor_pdbqt_path"],
            "ligand_pdbqt_path": str(ligand_pdbqt),
            "pose_pdbqt_path": str(pose_path),
            "vina_affinity_kcal_mol": affinity,
            "artifact_cache_hit": True,
            "ligand_cache_hit": ligand_cache_hit,
        }
    vina = run_command(
        [
            str(env_bin / "vina"),
            "--receptor",
            target["receptor_pdbqt_path"],
            "--ligand",
            str(ligand_pdbqt),
            "--center_x",
            str(target["center_x"]),
            "--center_y",
            str(target["center_y"]),
            "--center_z",
            str(target["center_z"]),
            "--size_x",
            str(target["size_x"]),
            "--size_y",
            str(target["size_y"]),
            "--size_z",
            str(target["size_z"]),
            "--cpu",
            str(settings.get("vina_cpu", 1)),
            "--exhaustiveness",
            str(settings.get("vina_exhaustiveness", 8)),
            "--num_modes",
            str(settings.get("vina_num_modes", 1)),
            "--out",
            str(pose_path),
            "--log",
            str(log_path),
        ]
    )
    require_success(vina, "vina docking")
    require_output_file(pose_path, "vina docking", vina)
    require_output_file(log_path, "vina docking", vina)
    affinity = parse_vina_affinity(log_path)
    return {
        "docking_score": affinity,
        "pose_rank": 1,
        "engine_mode": "vina_cpu",
        "backend_name": "autodock_vina",
        "receptor_pdbqt_path": target["receptor_pdbqt_path"],
        "ligand_pdbqt_path": str(ligand_pdbqt),
        "pose_pdbqt_path": str(pose_path),
        "vina_affinity_kcal_mol": affinity,
        "artifact_cache_hit": False,
        "ligand_cache_hit": ligand_cache_hit,
    }


def main() -> int:
    started_at = time.perf_counter()
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_manifest_path = Path(args.run_manifest)
    config_path = Path(args.config)
    input_manifest_path = Path(args.input_manifest)
    run_manifest = load_json(run_manifest_path)
    settings = load_classical_docking_settings(config_path)
    benchmark_cases = read_tsv_rows(input_manifest_path)
    prepared_library_tsv = Path("07_results/modules/compound_library_preparation/prepared_library.tsv")
    target_manifest_tsv = Path("07_results/modules/target_preparation/target_file_manifest.tsv")
    compounds = read_tsv_rows(prepared_library_tsv)
    targets = read_tsv_rows(target_manifest_tsv)

    compounds_by_library: dict[str, list[dict[str, str]]] = {}
    for row in compounds:
        compounds_by_library.setdefault(row["library_id"], []).append(row)

    targets_by_id = {row["target_id"]: row for row in targets}

    results_rows: list[dict[str, object]] = []
    enabled_cases = [row for row in benchmark_cases if row.get("enabled", "").strip().lower() == "true"]
    selected_case_ids = selected_case_ids_from_env()
    if selected_case_ids:
        enabled_cases = [row for row in enabled_cases if row["case_id"] in selected_case_ids]
    requested_backend = str(settings.get("backend", "scaffold_heuristic"))
    active_backend = requested_backend
    if requested_backend == "vina_cpu" and not backend_available(settings):
        active_backend = "scaffold_heuristic"

    module_dir = output_path.parent
    docking_results_tsv = module_dir / "docking_results.tsv"
    summary_json = module_dir / "docking_summary.json"
    report_md = module_dir / "classical_docking_report.md"
    primary_outputs = [docking_results_tsv, summary_json, report_md]
    cache_signature = build_cache_signature(
        input_manifest_path,
        config_path,
        prepared_library_tsv,
        target_manifest_tsv,
        enabled_cases,
        settings,
    )
    existing_done = load_existing_done(output_path)
    existing_case_ids = [row["case_id"] for row in enabled_cases]
    if (
        existing_done is not None
        and existing_done.get("cache", {}).get("signature") == cache_signature
        and existing_done.get("docking_outputs", {}).get("engine_mode") == active_backend
        and outputs_ready(primary_outputs)
    ):
        skipped_case_updates = {
            case_id: {
                "runtime_seconds": 0.0,
                "execution_status": "skipped_cache",
                "backend_mode": active_backend,
                "artifact_cache_hit": True,
                "skipped_cache": True,
                "skip_reason": "cache_signature_match",
                "cache_hit_artifact": True,
            }
            for case_id in existing_case_ids
        }
        run_manifest = update_run_manifest(
            run_manifest_path,
            args.module,
            0.0,
            "skipped_cache",
            active_backend,
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
                "backend_mode": active_backend,
                "skipped_cache": True,
                "skip_reason": "cache_signature_match",
                "selected_case_ids": existing_case_ids,
            },
            "cache": {
                "signature": cache_signature,
                "cache_scope": "module_and_case_artifacts",
                "cache_hit": True,
                "cache_hit_artifact": True,
            },
        }
        write_json(output_path, payload)
        print(f"[module] reused cached docking outputs: {docking_results_tsv}")
        return 0

    case_updates: dict[str, dict[str, object]] = {}
    cached_case_count = 0
    cached_result_count = 0
    ligand_cache_hit_count = 0

    for case in enabled_cases:
        case_started_at = time.perf_counter()
        target = targets_by_id[case["target_id"]]
        library_compounds = compounds_by_library[case["library_id"]]
        case_cache_hits = 0
        for compound in library_compounds:
            if active_backend == "vina_cpu":
                docking_result = run_vina_docking(case, compound, target, output_path.parent, settings)
                if docking_result.get("artifact_cache_hit"):
                    case_cache_hits += 1
                    cached_result_count += 1
                if docking_result.get("ligand_cache_hit"):
                    ligand_cache_hit_count += 1
            else:
                score = docking_score(compound, target, case)
                docking_result = {
                    "docking_score": score,
                    "pose_rank": 1,
                    "engine_mode": "scaffold_heuristic",
                    "backend_name": "scaffold_heuristic",
                    "receptor_pdbqt_path": target.get("receptor_pdbqt_path", ""),
                    "ligand_pdbqt_path": "",
                    "pose_pdbqt_path": "",
                    "vina_affinity_kcal_mol": "",
                    "artifact_cache_hit": False,
                    "ligand_cache_hit": False,
                }
            results_rows.append(
                {
                    "case_id": case["case_id"],
                    "target_id": case["target_id"],
                    "library_id": case["library_id"],
                    "compound_id": compound["compound_id"],
                    "prepared_structure_path": target["prepared_structure_path"],
                    "standardized_smiles": compound["standardized_smiles"],
                    "docking_protocol": case["docking_protocol"],
                    "receptor_pdbqt_path": docking_result["receptor_pdbqt_path"],
                    "ligand_pdbqt_path": docking_result["ligand_pdbqt_path"],
                    "pose_pdbqt_path": docking_result["pose_pdbqt_path"],
                    "docking_score": docking_result["docking_score"],
                    "vina_affinity_kcal_mol": docking_result["vina_affinity_kcal_mol"],
                    "pose_rank": docking_result["pose_rank"],
                    "backend_name": docking_result["backend_name"],
                    "engine_mode": docking_result["engine_mode"],
                }
            )
        case_runtime_seconds = time.perf_counter() - case_started_at
        case_execution_status = "executed"
        if active_backend == "vina_cpu" and library_compounds and case_cache_hits == len(library_compounds):
            case_execution_status = "skipped_cache"
            cached_case_count += 1
        case_updates[case["case_id"]] = {
            "runtime_seconds": case_runtime_seconds,
            "execution_status": case_execution_status,
            "backend_mode": active_backend,
            "result_row_count": len(library_compounds),
            "artifact_cache_hit_count": case_cache_hits,
            "skipped_cache": case_execution_status == "skipped_cache",
            "skip_reason": "all_case_artifacts_cached" if case_execution_status == "skipped_cache" else "",
            "cache_hit_artifact": case_cache_hits > 0,
        }

    results_rows.sort(key=lambda row: (row["case_id"], row["docking_score"]))

    final_rows: list[dict[str, object]] = results_rows
    if selected_case_ids and docking_results_tsv.exists() and docking_results_tsv.stat().st_size > 0:
        final_rows = merge_rows_by_keys(read_tsv_rows(docking_results_tsv), results_rows, ["case_id", "compound_id"])

    write_tsv(
        docking_results_tsv,
        final_rows,
        [
            "case_id",
            "target_id",
            "library_id",
            "compound_id",
            "prepared_structure_path",
            "standardized_smiles",
            "docking_protocol",
            "receptor_pdbqt_path",
            "ligand_pdbqt_path",
            "pose_pdbqt_path",
            "docking_score",
            "vina_affinity_kcal_mol",
            "pose_rank",
            "backend_name",
            "engine_mode",
        ],
    )

    top_hits: list[dict[str, object]] = []
    for case in enabled_cases:
        case_results = [row for row in final_rows if row["case_id"] == case["case_id"]]
        if case_results:
            top_hits.append(
                {
                    "case_id": case["case_id"],
                    "top_compound_id": case_results[0]["compound_id"],
                    "top_docking_score": case_results[0]["docking_score"],
                    "case_execution_status": case_updates.get(case["case_id"], {}).get("execution_status"),
                }
            )

    runtime_seconds = time.perf_counter() - started_at
    module_execution_status = "executed"
    if active_backend == "vina_cpu" and enabled_cases and cached_case_count == len(enabled_cases):
        module_execution_status = "skipped_cache"
    run_manifest = update_run_manifest(
        run_manifest_path,
        args.module,
        runtime_seconds,
        module_execution_status,
        active_backend,
        case_updates,
    )

    summary_payload = {
        "module": "classical_docking",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "enabled_case_count": len(enabled_cases),
        "result_row_count": len(final_rows),
        "requested_backend": requested_backend,
        "engine_mode": active_backend,
        "runtime_seconds": round(runtime_seconds, 6),
        "execution_status": module_execution_status,
        "selected_case_ids": existing_case_ids,
        "partial_rerun_active": bool(selected_case_ids),
        "cached_case_count": cached_case_count,
        "cached_result_count": cached_result_count,
        "ligand_cache_hit_count": ligand_cache_hit_count,
        "top_hits": top_hits,
        "output_table": str(docking_results_tsv),
    }
    write_json(summary_json, summary_payload)

    markdown_lines = [
        "# Classical Docking",
        "",
        f"- Requested backend: `{requested_backend}`",
        f"- Engine mode: `{active_backend}`",
        f"- Runtime seconds: `{round(runtime_seconds, 6)}`",
        f"- Execution status: `{module_execution_status}`",
        f"- Partial rerun active: `{bool(selected_case_ids)}`",
        f"- Enabled benchmark cases: `{len(enabled_cases)}`",
        f"- Result rows: `{len(final_rows)}`",
        f"- Cached cases: `{cached_case_count}`",
        f"- Cached docking results: `{cached_result_count}`",
        f"- Ligand cache hits: `{ligand_cache_hit_count}`",
        f"- Output table: `{docking_results_tsv}`",
        "",
        "## Top Hits",
        "",
    ]
    for hit in top_hits:
        markdown_lines.append(
            f"- `{hit['case_id']}` -> `{hit['top_compound_id']}` score `{hit['top_docking_score']}`"
        )
    report_md.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    payload = {
        "module": args.module,
        "status": "docking_completed",
        "config": args.config,
        "project_root": args.project_root,
        "run_manifest": args.run_manifest,
        "input_manifest": args.input_manifest,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validation": {
            "run_manifest_exists": Path(args.run_manifest).exists(),
            "input_manifest_exists": Path(args.input_manifest).exists(),
            "prepared_library_exists": Path("07_results/modules/compound_library_preparation/prepared_library.tsv").exists(),
            "target_manifest_exists": Path("07_results/modules/target_preparation/target_file_manifest.tsv").exists(),
            "docking_results_written": docking_results_tsv.exists(),
            "summary_written": summary_json.exists(),
            "report_written": report_md.exists(),
        },
        "run_context": {
            "run_mode": run_manifest.get("mode"),
            "enabled_benchmark_cases": run_manifest.get("counts", {}).get("enabled_benchmark_cases"),
        },
        "execution": {
            "runtime_seconds": round(runtime_seconds, 6),
            "execution_status": module_execution_status,
            "backend_mode": active_backend,
            "skipped_cache": module_execution_status == "skipped_cache",
            "skip_reason": "cache_signature_match" if module_execution_status == "skipped_cache" else "",
            "selected_case_ids": existing_case_ids,
            "partial_rerun_active": bool(selected_case_ids),
        },
        "module_profile": {
            "stage_type": "classical_docking",
            "primary_inputs": ["prepared library table", "target file manifest", "benchmark cases"],
            "primary_outputs": [str(docking_results_tsv), str(summary_json), str(report_md), args.output],
            "next_action_hint": "tune docking boxes and ligand preparation once the minimal vina path is stable",
        },
        "input_summary": {
            "row_count": len(enabled_cases),
            "preview_ids": [row["case_id"] for row in enabled_cases[:3]],
        },
        "docking_outputs": {
            "docking_results_tsv": str(docking_results_tsv),
            "docking_summary_json": str(summary_json),
            "docking_report_markdown": str(report_md),
            "engine_mode": active_backend,
            "requested_backend": requested_backend,
        },
        "cache": {
            "signature": cache_signature,
            "cache_scope": "module_and_case_artifacts",
            "cache_hit": module_execution_status == "skipped_cache",
            "cached_case_count": cached_case_count,
            "cached_result_count": cached_result_count,
            "ligand_cache_hit_count": ligand_cache_hit_count,
            "cache_hit_artifact": cached_result_count > 0,
        },
        "notes": [
            "The classical docking module preserves the original scaffold heuristic fallback.",
            "When backend=vina_cpu and the configured backend environment is available, docking uses AutoDock Vina with CPU-only execution.",
        ],
    }

    write_json(output_path, payload)
    print(f"[module] wrote docking results: {docking_results_tsv}")
    print(f"[module] wrote docking summary: {summary_json}")
    print(f"[module] wrote docking report: {report_md}")
    print(f"[module] wrote module artifact: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
