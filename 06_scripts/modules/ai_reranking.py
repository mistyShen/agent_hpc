#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a lightweight AI reranking scaffold.")
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
        elif re.fullmatch(r"-?\d+", value):
            parsed = int(value)
        elif re.fullmatch(r"-?\d+\.\d+", value):
            parsed = float(value)
        else:
            parsed = value.strip("'\"")
        current[key] = parsed
    return result


def build_cache_signature(
    input_manifest: Path,
    config_path: Path,
    docking_results_tsv: Path,
    docking_summary_json: Path,
    prepared_library_tsv: Path,
    enabled_cases: list[dict[str, str]],
    rerank_backend: str,
) -> dict[str, object]:
    return {
        "module_source": file_signature(Path(__file__)),
        "input_manifest": file_signature(input_manifest),
        "config": file_signature(config_path),
        "docking_results_tsv": file_signature(docking_results_tsv),
        "docking_summary_json": file_signature(docking_summary_json),
        "prepared_library_tsv": file_signature(prepared_library_tsv),
        "rerank_backend": rerank_backend,
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


def rerank_bonus(smiles: str) -> float:
    bonus = 0.0
    if "N" in smiles:
        bonus -= 0.45
    if "O" in smiles:
        bonus -= 0.20
    if "c1ccccc1" in smiles:
        bonus -= 0.30
    bonus += 0.03 * len(smiles)
    return round(bonus, 3)


def parse_float(value: str, default: float = 0.0) -> float:
    stripped = value.strip()
    if not stripped:
        return default
    return float(stripped)


def count_pdbqt_records(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith(("ATOM", "HETATM")):
                count += 1
    return count


def read_torsdof(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("TORSDOF"):
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1])
    return 0


def optional_path(value: str) -> Path | None:
    stripped = value.strip()
    if not stripped:
        return None
    return Path(stripped)


def safe_file_signature(path: Path | None) -> dict[str, object]:
    if path is None:
        return {"path": "", "exists": False}
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def config_value(config: dict[str, object], keys: list[str], default: object) -> object:
    current: object = config
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def load_v3_tuning(config: dict[str, object]) -> dict[str, float]:
    return {
        "missing_ligand_penalty": float(
            config_value(config, ["modules", "ai_reranking", "v3", "missing_ligand_penalty"], 0.35)
        ),
        "missing_pose_penalty": float(
            config_value(config, ["modules", "ai_reranking", "v3", "missing_pose_penalty"], 0.65)
        ),
        "atom_delta_weight": float(
            config_value(config, ["modules", "ai_reranking", "v3", "atom_delta_weight"], 0.015)
        ),
        "torsdof_threshold": float(
            config_value(config, ["modules", "ai_reranking", "v3", "torsdof_threshold"], 12.0)
        ),
        "torsdof_weight": float(
            config_value(config, ["modules", "ai_reranking", "v3", "torsdof_weight"], 0.025)
        ),
        "small_mw_floor": float(
            config_value(config, ["modules", "ai_reranking", "v3", "small_mw_floor"], 180.0)
        ),
        "small_mw_weight": float(
            config_value(config, ["modules", "ai_reranking", "v3", "small_mw_weight"], 0.01)
        ),
        "hetero_floor": float(
            config_value(config, ["modules", "ai_reranking", "v3", "hetero_floor"], 2.0)
        ),
        "hetero_weight": float(
            config_value(config, ["modules", "ai_reranking", "v3", "hetero_weight"], 0.45)
        ),
        "aromatic_fraction_threshold": float(
            config_value(config, ["modules", "ai_reranking", "v3", "aromatic_fraction_threshold"], 0.75)
        ),
        "aromatic_fraction_weight": float(
            config_value(config, ["modules", "ai_reranking", "v3", "aromatic_fraction_weight"], 2.0)
        ),
        "simple_aromatic_penalty": float(
            config_value(config, ["modules", "ai_reranking", "v3", "simple_aromatic_penalty"], 0.25)
        ),
        "polyaryl_hydrophobe_penalty": float(
            config_value(config, ["modules", "ai_reranking", "v3", "polyaryl_hydrophobe_penalty"], 0.0)
        ),
        "single_ring_background_penalty": float(
            config_value(config, ["modules", "ai_reranking", "v3", "single_ring_background_penalty"], 0.2)
        ),
    }


def load_v3_case_gating(config: dict[str, object]) -> dict[str, object]:
    return {
        "enabled": bool(
            config_value(config, ["modules", "ai_reranking", "v3", "case_aware_gating_enabled"], True)
        ),
        "focused_flag_coverage_threshold": float(
            config_value(
                config,
                ["modules", "ai_reranking", "v3", "focused_flag_coverage_threshold"],
                0.8,
            )
        ),
    }


def docking_context_bonus(row: dict[str, str]) -> tuple[float, dict[str, object]]:
    ligand_path = optional_path(row.get("ligand_pdbqt_path", ""))
    pose_path = optional_path(row.get("pose_pdbqt_path", ""))
    vina_affinity = parse_float(row.get("vina_affinity_kcal_mol", ""), parse_float(row["docking_score"]))
    ligand_atoms = count_pdbqt_records(ligand_path) if ligand_path is not None else 0
    pose_atoms = count_pdbqt_records(pose_path) if pose_path is not None else 0
    torsdof = read_torsdof(ligand_path) if ligand_path is not None else 0
    bonus = 0.0
    if row.get("engine_mode", "") == "vina_cpu":
        bonus -= 0.35
    if ligand_path is not None and ligand_path.exists() and ligand_path.stat().st_size > 0:
        bonus -= 0.15
    if pose_path is not None and pose_path.exists() and pose_path.stat().st_size > 0:
        bonus -= 0.15
    if ligand_atoms and pose_atoms:
        atom_delta = abs(ligand_atoms - pose_atoms)
        bonus += min(atom_delta, 12) * 0.02
    bonus += min(torsdof, 12) * 0.03
    bonus += abs(vina_affinity) * 0.05
    bonus = round(bonus, 3)
    return bonus, {
        "vina_affinity_kcal_mol": round(vina_affinity, 3),
        "ligand_pdbqt_path": str(ligand_path) if ligand_path is not None else "",
        "pose_pdbqt_path": str(pose_path) if pose_path is not None else "",
        "ligand_pdbqt_present": ligand_path.exists() if ligand_path is not None else False,
        "pose_pdbqt_present": pose_path.exists() if pose_path is not None else False,
        "ligand_atom_count": ligand_atoms,
        "pose_atom_count": pose_atoms,
        "ligand_torsdof": torsdof,
    }


def physchem_lookup_rows(prepared_library_rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row["library_id"], row["compound_id"]): row for row in prepared_library_rows}


def parse_known_active_definition(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("compound_id="):
        return raw.split("=", 1)[1]
    return raw


def docking_core_score(row: dict[str, str]) -> float:
    vina_affinity = row.get("vina_affinity_kcal_mol", "").strip()
    if vina_affinity:
        return parse_float(vina_affinity)
    return parse_float(row["docking_score"])


def artifact_penalty_v3(row: dict[str, str], tuning: dict[str, float]) -> tuple[float, dict[str, object]]:
    ligand_path = optional_path(row.get("ligand_pdbqt_path", ""))
    pose_path = optional_path(row.get("pose_pdbqt_path", ""))
    ligand_present = bool(ligand_path is not None and ligand_path.exists() and ligand_path.stat().st_size > 0)
    pose_present = bool(pose_path is not None and pose_path.exists() and pose_path.stat().st_size > 0)
    ligand_atoms = count_pdbqt_records(ligand_path) if ligand_present else 0
    pose_atoms = count_pdbqt_records(pose_path) if pose_present else 0
    torsdof = read_torsdof(ligand_path) if ligand_present else 0
    penalty = 0.0
    if not ligand_present:
        penalty += tuning["missing_ligand_penalty"]
    if not pose_present:
        penalty += tuning["missing_pose_penalty"]
    if ligand_atoms and pose_atoms:
        atom_delta = abs(ligand_atoms - pose_atoms)
        penalty += min(atom_delta, 12) * tuning["atom_delta_weight"]
    if torsdof > tuning["torsdof_threshold"]:
        penalty += min(torsdof - tuning["torsdof_threshold"], 8) * tuning["torsdof_weight"]
    return round(penalty, 3), {
        "ligand_pdbqt_present": ligand_present,
        "pose_pdbqt_present": pose_present,
        "ligand_atom_count": ligand_atoms,
        "pose_atom_count": pose_atoms,
        "ligand_torsdof": torsdof,
    }


def physchem_penalty_v3(
    library_row: dict[str, str] | None,
    tuning: dict[str, float],
    case_panel_gating: dict[str, object] | None = None,
) -> tuple[float, dict[str, object]]:
    if library_row is None:
        return 0.0, {
            "physchem_row_present": False,
            "molecular_weight_estimate": "",
            "heavy_atom_count": "",
            "hetero_atom_count": "",
            "aromatic_atom_count": "",
            "ring_index_count": "",
            "aromatic_fraction": "",
            "simple_aromatic_background": False,
            "polyaryl_hydrophobe_background": False,
        }
    molecular_weight = parse_float(library_row.get("molecular_weight_estimate", ""), 0.0)
    heavy_atom_count = parse_float(library_row.get("heavy_atom_count", ""), 0.0)
    hetero_atom_count = parse_float(library_row.get("hetero_atom_count", ""), 0.0)
    aromatic_atom_count = parse_float(library_row.get("aromatic_atom_count", ""), 0.0)
    ring_index_count = parse_float(library_row.get("ring_index_count", ""), 0.0)
    aromatic_fraction = (aromatic_atom_count / heavy_atom_count) if heavy_atom_count > 0 else 0.0
    panel_multipliers = {
        "simple_aromatic_penalty": 1.0,
        "polyaryl_hydrophobe_penalty": 1.0,
        "single_ring_background_penalty": 1.0,
    }
    if isinstance(case_panel_gating, dict):
        panel_multipliers.update(case_panel_gating.get("panel_specific_penalty_multipliers", {}))
    penalty = 0.0
    # v3 stays lightweight but now penalizes very small or hetero-poor aromatic backgrounds.
    if molecular_weight < tuning["small_mw_floor"]:
        penalty += min(tuning["small_mw_floor"] - molecular_weight, 80.0) * tuning["small_mw_weight"]
    if molecular_weight > 550.0:
        penalty += min(molecular_weight - 550.0, 150.0) * 0.005
    if heavy_atom_count > 40.0:
        penalty += min(heavy_atom_count - 40.0, 20.0) * 0.04
    if hetero_atom_count < tuning["hetero_floor"]:
        penalty += min(tuning["hetero_floor"] - hetero_atom_count, 2.0) * tuning["hetero_weight"]
    if aromatic_atom_count >= 8.0 and aromatic_fraction > tuning["aromatic_fraction_threshold"]:
        penalty += min(aromatic_fraction - tuning["aromatic_fraction_threshold"], 0.25) * tuning["aromatic_fraction_weight"]
    simple_aromatic_background = hetero_atom_count <= 1.0 and aromatic_atom_count >= 8.0 and ring_index_count <= 2.0
    if simple_aromatic_background:
        penalty += tuning["simple_aromatic_penalty"] * panel_multipliers["simple_aromatic_penalty"]
    polyaryl_hydrophobe_background = (
        hetero_atom_count <= 1.0
        and ring_index_count >= 2.0
        and aromatic_atom_count >= 8.0
        and aromatic_fraction > 0.7
    )
    if polyaryl_hydrophobe_background:
        penalty += tuning["polyaryl_hydrophobe_penalty"] * panel_multipliers["polyaryl_hydrophobe_penalty"]
    single_ring_background = ring_index_count <= 1.0 and aromatic_atom_count >= 6.0 and molecular_weight < 150.0
    if single_ring_background:
        penalty += tuning["single_ring_background_penalty"] * panel_multipliers["single_ring_background_penalty"]
    return round(penalty, 3), {
        "physchem_row_present": True,
        "molecular_weight_estimate": round(molecular_weight, 3),
        "heavy_atom_count": int(heavy_atom_count),
        "hetero_atom_count": int(hetero_atom_count),
        "aromatic_atom_count": int(aromatic_atom_count),
        "ring_index_count": int(ring_index_count),
        "aromatic_fraction": round(aromatic_fraction, 3),
        "simple_aromatic_background": simple_aromatic_background,
        "polyaryl_hydrophobe_background": polyaryl_hydrophobe_background,
        "single_ring_background": single_ring_background,
        "panel_specific_gating_mode": (case_panel_gating or {}).get("mode", "panel_specific_v3_full"),
        "applied_panel_multipliers": panel_multipliers,
        "background_flag_coverage": (case_panel_gating or {}).get("background_flag_coverage"),
        "simple_aromatic_background_count": (case_panel_gating or {}).get("simple_aromatic_background_count"),
        "polyaryl_hydrophobe_background_count": (case_panel_gating or {}).get("polyaryl_hydrophobe_background_count"),
        "single_ring_background_count": (case_panel_gating or {}).get("single_ring_background_count"),
    }


def classify_panel_background_row(library_row: dict[str, str]) -> dict[str, object]:
    heavy_atom_count = parse_float(library_row.get("heavy_atom_count", ""), 0.0)
    hetero_atom_count = parse_float(library_row.get("hetero_atom_count", ""), 0.0)
    aromatic_atom_count = parse_float(library_row.get("aromatic_atom_count", ""), 0.0)
    ring_index_count = parse_float(library_row.get("ring_index_count", ""), 0.0)
    molecular_weight = parse_float(library_row.get("molecular_weight_estimate", ""), 0.0)
    aromatic_fraction = (aromatic_atom_count / heavy_atom_count) if heavy_atom_count > 0 else 0.0
    simple_aromatic_background = hetero_atom_count <= 1.0 and aromatic_atom_count >= 8.0 and ring_index_count <= 2.0
    polyaryl_hydrophobe_background = (
        hetero_atom_count <= 1.0
        and ring_index_count >= 2.0
        and aromatic_atom_count >= 8.0
        and aromatic_fraction > 0.7
    )
    single_ring_background = ring_index_count <= 1.0 and aromatic_atom_count >= 6.0 and molecular_weight < 150.0
    return {
        "compound_id": library_row["compound_id"],
        "simple_aromatic_background": simple_aromatic_background,
        "polyaryl_hydrophobe_background": polyaryl_hydrophobe_background,
        "single_ring_background": single_ring_background,
        "any_background_flag": bool(
            simple_aromatic_background or polyaryl_hydrophobe_background or single_ring_background
        ),
    }


def build_case_panel_gating(
    case_row: dict[str, str],
    case_library_rows: list[dict[str, str]],
    case_library_type: str,
    gating_config: dict[str, object],
) -> dict[str, object]:
    known_active = parse_known_active_definition(case_row.get("known_active_definition", ""))
    background_rows = [row for row in case_library_rows if row.get("compound_id") != known_active]
    profiled_rows = [classify_panel_background_row(row) for row in background_rows]
    simple_count = sum(1 for row in profiled_rows if row["simple_aromatic_background"])
    polyaryl_count = sum(1 for row in profiled_rows if row["polyaryl_hydrophobe_background"])
    single_ring_count = sum(1 for row in profiled_rows if row["single_ring_background"])
    flagged_count = sum(1 for row in profiled_rows if row["any_background_flag"])
    background_count = len(profiled_rows)
    background_flag_coverage = round((flagged_count / background_count), 3) if background_count else 0.0
    threshold = float(gating_config.get("focused_flag_coverage_threshold", 0.8))
    enabled = bool(gating_config.get("enabled", False))
    use_full = enabled and case_library_type == "focused" and background_flag_coverage >= threshold
    mode = "panel_specific_v3_full" if use_full else "panel_specific_v3_off"
    multiplier = 1.0 if use_full else 0.0
    return {
        "enabled": enabled,
        "mode": mode,
        "library_type": case_library_type,
        "background_count": background_count,
        "flagged_background_count": flagged_count,
        "background_flag_coverage": background_flag_coverage,
        "simple_aromatic_background_count": simple_count,
        "polyaryl_hydrophobe_background_count": polyaryl_count,
        "single_ring_background_count": single_ring_count,
        "focused_flag_coverage_threshold": threshold,
        "panel_specific_penalty_multipliers": {
            "simple_aromatic_penalty": multiplier,
            "polyaryl_hydrophobe_penalty": multiplier,
            "single_ring_background_penalty": multiplier,
        },
    }


def reserved_case_adjustment_v3(case_row: dict[str, str]) -> tuple[float, dict[str, object]]:
    return 0.0, {
        "case_adjustment_enabled": False,
        "case_type": case_row.get("case_type", ""),
        "run_purpose": case_row.get("run_purpose", ""),
    }


def score_row_v2(row: dict[str, str]) -> dict[str, object]:
    docking_score = parse_float(row["docking_score"])
    chemistry_bonus = rerank_bonus(row["standardized_smiles"])
    context_bonus, context = docking_context_bonus(row)
    rerank_score = round(docking_score + chemistry_bonus + context_bonus, 3)
    return {
        "rerank_bonus": round(chemistry_bonus + context_bonus, 3),
        "rerank_score": rerank_score,
        "rerank_model": "cpu_docking_rerank_v2",
        "rerank_diagnostics": {
            "docking_core": round(docking_score, 3),
            "chemistry_bonus": round(chemistry_bonus, 3),
            "context_bonus": round(context_bonus, 3),
        },
        "rerank_inputs": context,
    }


def score_row_v3(
    row: dict[str, str],
    case_row: dict[str, str],
    library_row: dict[str, str] | None,
    tuning: dict[str, float],
    case_panel_gating: dict[str, object] | None = None,
) -> dict[str, object]:
    docking_core = docking_core_score(row)
    artifact_penalty, artifact_context = artifact_penalty_v3(row, tuning)
    physchem_penalty, physchem_context = physchem_penalty_v3(library_row, tuning, case_panel_gating=case_panel_gating)
    case_adjustment, case_context = reserved_case_adjustment_v3(case_row)
    # Lower rerank scores are better, so penalties must move candidates back toward zero.
    rerank_score = round(docking_core + artifact_penalty + physchem_penalty + case_adjustment, 3)
    total_penalty = round(artifact_penalty + physchem_penalty + case_adjustment, 3)
    return {
        "rerank_bonus": -total_penalty,
        "rerank_score": rerank_score,
        "rerank_model": "cpu_docking_rerank_v3",
        "rerank_diagnostics": {
            "docking_core": round(docking_core, 3),
            "artifact_penalty": artifact_penalty,
            "physchem_penalty": physchem_penalty,
            "case_adjustment": case_adjustment,
            "total_penalty": total_penalty,
        },
        "rerank_inputs": {
            "artifact": artifact_context,
            "physchem": physchem_context,
            "case": {
                **case_context,
                "panel_specific_gating_mode": (case_panel_gating or {}).get("mode", "panel_specific_v3_full"),
                "background_flag_coverage": (case_panel_gating or {}).get("background_flag_coverage"),
            },
        },
    }


def summarize_v3_preview_row(row: dict[str, object], rank: int) -> dict[str, object]:
    diagnostics = row.get("rerank_diagnostics", {})
    inputs = row.get("rerank_inputs", {})
    physchem_inputs = inputs.get("physchem", {}) if isinstance(inputs, dict) else {}
    triggered_flags: list[str] = []
    for flag_name in (
        "simple_aromatic_background",
        "polyaryl_hydrophobe_background",
        "single_ring_background",
    ):
        if isinstance(physchem_inputs, dict) and physchem_inputs.get(flag_name):
            triggered_flags.append(flag_name)
    return {
        "compound_id": row["compound_id"],
        "rerank_score": row["rerank_score"],
        "rerank_rank": rank,
        "rerank_model": row["rerank_model"],
        "rerank_bonus": row["rerank_bonus"],
        "rerank_diagnostics": diagnostics,
        "physchem_flags": triggered_flags,
        "physchem_snapshot": {
            "molecular_weight_estimate": physchem_inputs.get("molecular_weight_estimate") if isinstance(physchem_inputs, dict) else None,
            "hetero_atom_count": physchem_inputs.get("hetero_atom_count") if isinstance(physchem_inputs, dict) else None,
            "aromatic_atom_count": physchem_inputs.get("aromatic_atom_count") if isinstance(physchem_inputs, dict) else None,
            "ring_index_count": physchem_inputs.get("ring_index_count") if isinstance(physchem_inputs, dict) else None,
            "aromatic_fraction": physchem_inputs.get("aromatic_fraction") if isinstance(physchem_inputs, dict) else None,
        },
    }


def backend_for_case(case_row: dict[str, str], configured_backend: str) -> str:
    strategy = case_row.get("rerank_strategy", "").strip()
    if strategy == "ai_rerank_v3":
        return "cpu_docking_rerank_v3"
    return configured_backend


def build_case_cache_signature(
    case_row: dict[str, str],
    case_backend_mode: str,
    docking_rows: list[dict[str, str]],
    library_by_key: dict[tuple[str, str], dict[str, str]],
    v3_tuning: dict[str, float],
    v3_case_gating: dict[str, object] | None = None,
) -> str:
    docking_payload: list[dict[str, object]] = []
    for row in sorted(docking_rows, key=lambda item: item["compound_id"]):
        ligand_path = optional_path(row.get("ligand_pdbqt_path", ""))
        pose_path = optional_path(row.get("pose_pdbqt_path", ""))
        library_row = library_by_key.get((row["library_id"], row["compound_id"]))
        docking_payload.append(
            {
                "compound_id": row["compound_id"],
                "standardized_smiles": row.get("standardized_smiles", ""),
                "docking_score": row.get("docking_score", ""),
                "vina_affinity_kcal_mol": row.get("vina_affinity_kcal_mol", ""),
                "engine_mode": row.get("engine_mode", ""),
                "ligand_pdbqt": safe_file_signature(ligand_path),
                "pose_pdbqt": safe_file_signature(pose_path),
                "library": {
                    "molecular_weight_estimate": library_row.get("molecular_weight_estimate", "") if library_row else "",
                    "heavy_atom_count": library_row.get("heavy_atom_count", "") if library_row else "",
                    "hetero_atom_count": library_row.get("hetero_atom_count", "") if library_row else "",
                    "aromatic_atom_count": library_row.get("aromatic_atom_count", "") if library_row else "",
                    "ring_index_count": library_row.get("ring_index_count", "") if library_row else "",
                },
            }
        )
    payload = {
        "module_source": file_signature(Path(__file__)),
        "case_id": case_row.get("case_id", ""),
        "case_type": case_row.get("case_type", ""),
        "run_purpose": case_row.get("run_purpose", ""),
        "rerank_strategy": case_row.get("rerank_strategy", ""),
        "backend_mode": case_backend_mode,
        "v3_tuning": v3_tuning if case_backend_mode == "cpu_docking_rerank_v3" else {},
        "v3_case_gating": v3_case_gating if case_backend_mode == "cpu_docking_rerank_v3" else {},
        "docking_rows": docking_payload,
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
    run_manifest = load_json(run_manifest_path)
    benchmark_cases = read_tsv_rows(input_manifest_path)
    docking_results_tsv = Path("07_results/modules/classical_docking/docking_results.tsv")
    docking_rows = read_tsv_rows(docking_results_tsv)
    docking_summary_path = Path("07_results/modules/classical_docking/docking_summary.json")
    docking_summary = load_json(docking_summary_path) if docking_summary_path.exists() else None
    prepared_library_tsv = Path("07_results/modules/compound_library_preparation/prepared_library.tsv")
    prepared_library_rows = read_tsv_rows(prepared_library_tsv) if prepared_library_tsv.exists() else []
    library_by_key = physchem_lookup_rows(prepared_library_rows)
    compound_libraries_tsv = Path("04_metadata/compound_libraries.tsv")
    compound_library_rows = read_tsv_rows(compound_libraries_tsv) if compound_libraries_tsv.exists() else []
    compound_library_by_id = {row["library_id"]: row for row in compound_library_rows}
    config_payload = parse_simple_yaml_config(config_path)

    enabled_cases = [row for row in benchmark_cases if row.get("enabled", "").strip().lower() == "true"]
    selected_case_ids = selected_case_ids_from_env()
    if selected_case_ids:
        enabled_cases = [row for row in enabled_cases if row["case_id"] in selected_case_ids]
    configured_backend = str(
        config_value(config_payload, ["modules", "ai_reranking", "backend"], "cpu_docking_rerank_v2")
    )
    v3_tuning = load_v3_tuning(config_payload)
    v3_case_gating_config = load_v3_case_gating(config_payload)
    module_dir = output_path.parent
    reranked_tsv = module_dir / "reranked_candidates.tsv"
    summary_json = module_dir / "reranking_summary.json"
    report_md = module_dir / "ai_reranking_report.md"
    primary_outputs = [reranked_tsv, summary_json, report_md]
    cache_signature = build_cache_signature(
        input_manifest_path,
        config_path,
        docking_results_tsv,
        docking_summary_path,
        prepared_library_tsv,
        enabled_cases,
        configured_backend,
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
                "backend_mode": configured_backend,
                "result_row_count": len([row for row in docking_rows if row["case_id"] == case["case_id"]]),
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
            configured_backend,
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
                "backend_mode": configured_backend,
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
        print(f"[module] reused cached reranking outputs: {reranked_tsv}")
        return 0

    read_runtime_seconds = time.perf_counter() - read_started_at

    output_rows: list[dict[str, object]] = []
    top_hits: list[dict[str, object]] = []
    case_diagnostics: list[dict[str, object]] = []
    real_docking_rows = 0
    case_updates: dict[str, dict[str, object]] = {}
    scoring_started_at = time.perf_counter()
    existing_case_cache = existing_done.get("case_cache", {}) if existing_done is not None else {}
    existing_rerank_rows = read_tsv_rows(reranked_tsv) if reranked_tsv.exists() and reranked_tsv.stat().st_size > 0 else []
    existing_rows_by_case: dict[str, list[dict[str, str]]] = {}
    for row in existing_rerank_rows:
        existing_rows_by_case.setdefault(row["case_id"], []).append(row)
    existing_top_hits = {
        row["case_id"]: row
        for row in existing_summary.get("top_hits", [])
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
        case_rows = [row for row in docking_rows if row["case_id"] == case["case_id"]]
        case_backend_mode = backend_for_case(case, configured_backend)
        case_library_type = compound_library_by_id.get(case["library_id"], {}).get("library_type", "")
        case_library_rows = [row for row in prepared_library_rows if row["library_id"] == case["library_id"]]
        case_panel_gating = build_case_panel_gating(
            case,
            case_library_rows,
            case_library_type,
            v3_case_gating_config,
        )
        case_signature = build_case_cache_signature(
            case,
            case_backend_mode,
            case_rows,
            library_by_key,
            v3_tuning,
            v3_case_gating=case_panel_gating,
        )
        cached_case = existing_case_cache.get(case["case_id"], {}) if isinstance(existing_case_cache, dict) else {}
        cached_case_rows = existing_rows_by_case.get(case["case_id"], [])
        if (
            cached_case.get("signature") == case_signature
            and len(cached_case_rows) == len(case_rows)
            and case["case_id"] in existing_case_diagnostics
        ):
            output_rows.extend(cached_case_rows)
            if case["case_id"] in existing_top_hits:
                top_hits.append(existing_top_hits[case["case_id"]])
            case_runtime_seconds = time.perf_counter() - case_started_at
            cached_diag = dict(existing_case_diagnostics[case["case_id"]])
            cached_diag["runtime_seconds"] = round(case_runtime_seconds, 6)
            cached_diag["scoring_runtime_seconds"] = 0.0
            cached_diag["cache_status"] = "hit"
            case_diagnostics.append(cached_diag)
            case_updates[case["case_id"]] = {
                "runtime_seconds": case_runtime_seconds,
                "scoring_runtime_seconds": 0.0,
                "execution_status": "skipped_cache",
                "backend_mode": case_backend_mode,
                "result_row_count": len(cached_case_rows),
                "skipped_cache": True,
                "skip_reason": "case_signature_match",
                "cache_hit_artifact": True,
            }
            case_cache_payload[case["case_id"]] = {
                "signature": case_signature,
                "backend_mode": case_backend_mode,
                "row_count": len(cached_case_rows),
                "cache_status": "hit",
            }
            continue
        scored_rows = []
        case_scoring_started_at = time.perf_counter()
        for row in case_rows:
            library_row = library_by_key.get((row["library_id"], row["compound_id"]))
            if case_backend_mode == "cpu_docking_rerank_v3":
                score_payload = score_row_v3(
                    row,
                    case,
                    library_row,
                    v3_tuning,
                    case_panel_gating=case_panel_gating,
                )
            else:
                score_payload = score_row_v2(row)
            if row.get("engine_mode", "") == "vina_cpu":
                real_docking_rows += 1
            scored_rows.append(
                {
                    **row,
                    **score_payload,
                }
            )
        scored_rows.sort(key=lambda row: float(row["rerank_score"]))
        case_scoring_runtime_seconds = time.perf_counter() - case_scoring_started_at
        for rank, row in enumerate(scored_rows, start=1):
            output_rows.append(
                {
                    "case_id": row["case_id"],
                    "target_id": row["target_id"],
                    "library_id": row["library_id"],
                    "compound_id": row["compound_id"],
                    "standardized_smiles": row["standardized_smiles"],
                    "docking_score": row["docking_score"],
                    "rerank_bonus": row["rerank_bonus"],
                    "rerank_score": row["rerank_score"],
                    "rerank_rank": rank,
                    "rerank_model": row["rerank_model"],
                }
            )
        if scored_rows:
            top_row = scored_rows[0]
            top_hits.append(
                {
                    "case_id": case["case_id"],
                    "top_compound_id": top_row["compound_id"],
                    "top_rerank_score": top_row["rerank_score"],
                    "rerank_model": top_row["rerank_model"],
                }
            )
            top_preview = [summarize_v3_preview_row(row, idx + 1) for idx, row in enumerate(scored_rows[:3])]
        else:
            top_preview = []
        if case_backend_mode == "cpu_docking_rerank_v3":
            v3_rows = scored_rows[: min(len(scored_rows), 5)]
            avg_artifact_penalty = round(
                sum(float(row["rerank_diagnostics"]["artifact_penalty"]) for row in v3_rows) / len(v3_rows), 3
            ) if v3_rows else 0.0
            avg_physchem_penalty = round(
                sum(float(row["rerank_diagnostics"]["physchem_penalty"]) for row in v3_rows) / len(v3_rows), 3
            ) if v3_rows else 0.0
        else:
            avg_artifact_penalty = 0.0
            avg_physchem_penalty = 0.0
        case_diagnostics.append(
            {
                "case_id": case["case_id"],
                "rerank_model": case_backend_mode,
                "row_count": len(scored_rows),
                "runtime_seconds": round(time.perf_counter() - case_started_at, 6),
                "scoring_runtime_seconds": round(case_scoring_runtime_seconds, 6),
                "cache_status": "miss",
                "top_preview": top_preview,
                "v3_component_averages": {
                    "artifact_penalty": avg_artifact_penalty,
                    "physchem_penalty": avg_physchem_penalty,
                },
                "v3_case_panel_gating": case_panel_gating if case_backend_mode == "cpu_docking_rerank_v3" else {},
            }
        )
        case_runtime_seconds = time.perf_counter() - case_started_at
        case_updates[case["case_id"]] = {
            "runtime_seconds": case_runtime_seconds,
            "scoring_runtime_seconds": case_scoring_runtime_seconds,
            "execution_status": "executed",
            "backend_mode": case_backend_mode,
            "result_row_count": len(scored_rows),
            "skipped_cache": False,
            "skip_reason": "",
            "cache_hit_artifact": False,
        }
        case_cache_payload[case["case_id"]] = {
            "signature": case_signature,
            "backend_mode": case_backend_mode,
            "row_count": len(scored_rows),
            "cache_status": "miss",
        }

    scoring_runtime_seconds = time.perf_counter() - scoring_started_at

    output_started_at = time.perf_counter()
    final_rows: list[dict[str, object]] = output_rows
    if selected_case_ids and reranked_tsv.exists() and reranked_tsv.stat().st_size > 0:
        final_rows = merge_rows_by_keys(read_tsv_rows(reranked_tsv), output_rows, ["case_id", "compound_id"])

    write_tsv(
        reranked_tsv,
        final_rows,
        [
            "case_id",
            "target_id",
            "library_id",
            "compound_id",
            "standardized_smiles",
            "docking_score",
            "rerank_bonus",
            "rerank_score",
            "rerank_rank",
            "rerank_model",
        ],
    )

    runtime_seconds = time.perf_counter() - started_at
    output_runtime_seconds = time.perf_counter() - output_started_at
    run_manifest = update_run_manifest(
        run_manifest_path,
        args.module,
        runtime_seconds,
        "executed",
        configured_backend,
        case_updates,
    )

    active_rerank_models = sorted({str(row["rerank_model"]) for row in output_rows})

    summary_payload = {
        "module": "ai_reranking",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "enabled_case_count": len(enabled_cases),
        "reranked_row_count": len(final_rows),
        "rerank_model": configured_backend,
        "active_rerank_models": active_rerank_models,
        "runtime_seconds": round(runtime_seconds, 6),
        "execution_status": "executed",
        "selected_case_ids": [row["case_id"] for row in enabled_cases],
        "partial_rerun_active": bool(selected_case_ids),
        "docking_summary_available": bool(docking_summary),
        "real_docking_rows_consumed": real_docking_rows,
        "docking_engine_mode": docking_summary.get("engine_mode") if docking_summary else "",
        "phase_timings_seconds": {
            "read": round(read_runtime_seconds, 6),
            "scoring": round(scoring_runtime_seconds, 6),
            "output": round(output_runtime_seconds, 6),
        },
        "v3_tuning": v3_tuning,
        "v3_case_gating": v3_case_gating_config,
        "top_hits": top_hits,
        "case_diagnostics": case_diagnostics,
        "output_table": str(reranked_tsv),
    }
    write_json(summary_json, summary_payload)

    markdown_lines = [
        "# AI Reranking",
        "",
        f"- Configured rerank backend: `{configured_backend}`",
        f"- Active rerank models: `{', '.join(active_rerank_models)}`",
        f"- Runtime seconds: `{round(runtime_seconds, 6)}`",
        f"- Read phase seconds: `{round(read_runtime_seconds, 6)}`",
        f"- Scoring phase seconds: `{round(scoring_runtime_seconds, 6)}`",
        f"- Output phase seconds: `{round(output_runtime_seconds, 6)}`",
        "- Execution status: `executed`",
        f"- Partial rerun active: `{bool(selected_case_ids)}`",
        f"- Enabled benchmark cases: `{len(enabled_cases)}`",
        f"- Reranked rows: `{len(final_rows)}`",
        f"- Docking summary available: `{bool(docking_summary)}`",
        f"- Real docking rows consumed: `{real_docking_rows}`",
        f"- Docking engine mode: `{docking_summary.get('engine_mode') if docking_summary else ''}`",
        f"- Output table: `{reranked_tsv}`",
        f"- v3 tuning: `{json.dumps(v3_tuning, sort_keys=True)}`",
        f"- v3 case gating: `{json.dumps(v3_case_gating_config, sort_keys=True)}`",
        "",
        "## Top Hits",
        "",
    ]
    for hit in top_hits:
        case_id = hit["case_id"]
        top_compound_id = hit["top_compound_id"]
        top_rerank_score = hit["top_rerank_score"]
        rerank_model = hit["rerank_model"]
        markdown_lines.append(
            f"- `{case_id}` -> `{top_compound_id}` rerank score `{top_rerank_score}` via `{rerank_model}`"
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
        markdown_lines.append(f"- Rerank model: `{case_diag['rerank_model']}`")
        markdown_lines.append(f"- Row count: `{case_diag['row_count']}`")
        markdown_lines.append(f"- Runtime seconds: `{case_diag.get('runtime_seconds', 0.0)}`")
        markdown_lines.append(f"- Scoring runtime seconds: `{case_diag.get('scoring_runtime_seconds', 0.0)}`")
        markdown_lines.append(f"- Cache status: `{case_diag.get('cache_status', 'unknown')}`")
        if case_diag["rerank_model"] == "cpu_docking_rerank_v3":
            averages = case_diag.get("v3_component_averages", {"artifact_penalty": 0.0, "physchem_penalty": 0.0})
            markdown_lines.append(
                f"- Mean top-window artifact penalty: `{averages['artifact_penalty']}`"
            )
            markdown_lines.append(
                f"- Mean top-window physchem penalty: `{averages['physchem_penalty']}`"
            )
        markdown_lines.append("- Top preview:")
        for preview_row in case_diag.get("top_preview", []):
            diag = preview_row["rerank_diagnostics"]
            if case_diag["rerank_model"] == "cpu_docking_rerank_v3":
                markdown_lines.append(
                    f"  - `{preview_row['compound_id']}` rank `{preview_row['rerank_rank']}` score `{preview_row['rerank_score']}`"
                    f" | docking `{diag['docking_core']}` | artifact penalty `{diag['artifact_penalty']}`"
                    f" | physchem penalty `{diag['physchem_penalty']}`"
                )
            else:
                markdown_lines.append(
                    f"  - `{preview_row['compound_id']}` rank `{preview_row['rerank_rank']}` score `{preview_row['rerank_score']}`"
                    f" | docking `{diag['docking_core']}` | chemistry bonus `{diag['chemistry_bonus']}`"
                    f" | context bonus `{diag['context_bonus']}`"
                )
        markdown_lines.append("")
    report_md.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    payload = {
        "module": args.module,
        "status": "reranking_completed",
        "config": args.config,
        "project_root": args.project_root,
        "run_manifest": args.run_manifest,
        "input_manifest": args.input_manifest,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validation": {
            "run_manifest_exists": Path(args.run_manifest).exists(),
            "input_manifest_exists": Path(args.input_manifest).exists(),
            "docking_results_exists": docking_results_tsv.exists(),
            "reranked_table_written": reranked_tsv.exists(),
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
            "backend_mode": configured_backend,
            "skipped_cache": False,
            "skip_reason": "",
            "selected_case_ids": [row["case_id"] for row in enabled_cases],
            "partial_rerun_active": bool(selected_case_ids),
        },
        "module_profile": {
            "stage_type": "ai_reranking",
            "primary_inputs": ["docking results", "benchmark cases"],
            "primary_outputs": [str(reranked_tsv), str(summary_json), str(report_md), args.output],
            "next_action_hint": "keep extending the docking-aware rerank features while staying CPU-only",
        },
        "input_summary": {
            "row_count": len(enabled_cases),
            "preview_ids": [row["case_id"] for row in enabled_cases[:3]],
        },
        "reranking_outputs": {
            "reranked_candidates_tsv": str(reranked_tsv),
            "reranking_summary_json": str(summary_json),
            "reranking_report_markdown": str(report_md),
            "rerank_model": configured_backend,
            "v3_tuning": v3_tuning,
        },
        "cache": {
            "signature": cache_signature,
            "cache_scope": "module",
            "cache_hit": False,
            "cache_hit_artifact": False,
        },
        "case_cache": case_cache_payload,
        "notes": [
            "This module now consumes real docking outputs when available, including Vina affinity and ligand/pose PDBQT artifacts.",
            "The rerank remains lightweight and CPU-only by combining docking affinity with simple artifact-quality signals and small chemistry heuristics.",
            "An enhancement-line v3 backend is available but remains disabled by default so the frozen benchmark/manuscript result line is not changed automatically.",
        ],
    }

    write_json(output_path, payload)
    print(f"[module] wrote reranked candidates: {reranked_tsv}")
    print(f"[module] wrote reranking summary: {summary_json}")
    print(f"[module] wrote reranking report: {report_md}")
    print(f"[module] wrote module artifact: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
