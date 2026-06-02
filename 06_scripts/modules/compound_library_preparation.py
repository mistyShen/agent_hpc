#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import time


ATOMIC_WEIGHTS = {
    "B": 10.81,
    "Br": 79.904,
    "C": 12.011,
    "Cl": 35.45,
    "F": 18.998,
    "I": 126.904,
    "N": 14.007,
    "O": 15.999,
    "P": 30.974,
    "S": 32.06,
}

ORGANIC_TOKENS = {"B", "Br", "C", "Cl", "F", "I", "N", "O", "P", "S", "c", "n", "o", "p", "s"}
TOKEN_PATTERN = re.compile(r"Br|Cl|\[[^\]]+\]|[A-Z][a-z]?|[bcnops]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a lightweight compound library table.")
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


def normalize_smiles(smiles: str) -> str:
    return "".join(smiles.strip().split())


def tokenize_smiles(smiles: str) -> list[str]:
    return TOKEN_PATTERN.findall(smiles)


def estimate_properties(smiles: str) -> dict[str, object]:
    tokens = tokenize_smiles(smiles)
    normalized_tokens = []
    aromatic_atoms = 0
    hetero_atoms = 0
    molecular_weight = 0.0

    for token in tokens:
        if token.startswith("["):
            inner = token[1:-1]
            match = re.match(r"([A-Z][a-z]?|[bcnops])", inner)
            if not match:
                continue
            token = match.group(1)
        normalized = token.capitalize() if len(token) == 1 else token
        if token.islower():
            aromatic_atoms += 1
        if normalized in ATOMIC_WEIGHTS:
            normalized_tokens.append(normalized)
            molecular_weight += ATOMIC_WEIGHTS[normalized]
            if normalized not in {"C", "H"}:
                hetero_atoms += 1

    ring_index_count = len(set(re.findall(r"\d", smiles)))
    return {
        "smiles_length": len(smiles),
        "heavy_atom_count": len(normalized_tokens),
        "hetero_atom_count": hetero_atoms,
        "aromatic_atom_count": aromatic_atoms,
        "ring_index_count": ring_index_count,
        "molecular_weight_estimate": round(molecular_weight, 3),
    }


def read_smi_file(path: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            smiles = parts[0]
            compound_id = parts[1] if len(parts) > 1 else f"compound_{idx:04d}"
            records.append({"compound_id": compound_id, "raw_smiles": smiles})
    return records


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


def file_signature(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def build_cache_signature(
    input_manifest: Path,
    config_path: Path,
    selected_libraries: list[dict[str, str]],
    selected_case_ids: list[str],
) -> dict[str, object]:
    return {
        "input_manifest": file_signature(input_manifest),
        "config": file_signature(config_path),
        "selected_case_ids": selected_case_ids,
        "selected_library_ids": [row["library_id"] for row in selected_libraries],
        "library_sources": [
            {
                "library_id": row["library_id"],
                "source_path": file_signature(Path(row["source_path"])),
            }
            for row in selected_libraries
        ],
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


def selected_benchmark_cases(
    run_manifest: dict[str, object],
    selected_case_ids: set[str],
) -> list[dict[str, str]]:
    case_manifest_path = Path(
        str(run_manifest.get("inputs", {}).get("benchmark_cases_manifest", "04_metadata/benchmark_cases.tsv"))
    )
    rows = read_tsv_rows(case_manifest_path) if case_manifest_path.exists() else []
    enabled_rows = [row for row in rows if row.get("enabled", "").strip().lower() == "true"]
    if selected_case_ids:
        enabled_rows = [row for row in enabled_rows if row.get("case_id", "") in selected_case_ids]
    return enabled_rows


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


def main() -> int:
    started_at = time.perf_counter()
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_manifest_path = Path(args.run_manifest)
    input_manifest_path = Path(args.input_manifest)
    config_path = Path(args.config)
    run_manifest = load_json(run_manifest_path)
    library_rows = read_tsv_rows(input_manifest_path)
    if not library_rows:
        raise SystemExit("compound library metadata is empty")
    selected_case_ids = selected_case_ids_from_env()
    benchmark_cases = selected_benchmark_cases(run_manifest, selected_case_ids)
    if selected_case_ids and not benchmark_cases:
        raise SystemExit("selected case scope resolved to zero enabled benchmark cases")

    library_by_id = {row["library_id"]: row for row in library_rows}
    if benchmark_cases:
        selected_library_ids = sorted({row["library_id"] for row in benchmark_cases})
    else:
        selected_library_ids = sorted(library_by_id)
    missing_library_ids = [library_id for library_id in selected_library_ids if library_id not in library_by_id]
    if missing_library_ids:
        raise SystemExit(
            "benchmark case references missing library metadata: " + ", ".join(sorted(missing_library_ids))
        )
    selected_libraries = [library_by_id[library_id] for library_id in selected_library_ids]
    cases_by_library: dict[str, list[str]] = {}
    for row in benchmark_cases:
        cases_by_library.setdefault(row["library_id"], []).append(row["case_id"])
    case_scope_ids = sorted(row["case_id"] for row in benchmark_cases)

    module_dir = output_path.parent
    prepared_tsv = module_dir / "prepared_library.tsv"
    summary_json = module_dir / "library_summary.json"
    report_md = module_dir / "library_preparation_report.md"
    cache_signature = build_cache_signature(
        input_manifest_path,
        config_path,
        selected_libraries,
        case_scope_ids,
    )
    existing_done = load_existing_done(output_path)
    primary_outputs = [prepared_tsv, summary_json, report_md]
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
            cached_summary["selected_library_ids"] = selected_library_ids
            cached_summary["library_count"] = len(selected_library_ids)
            write_json(summary_json, cached_summary)
        run_manifest = update_run_manifest(
            run_manifest_path,
            args.module,
            0.0,
            "skipped_cache",
            "lightweight_smiles_standardization",
            {
                case_id: {
                    "runtime_seconds": 0.0,
                    "execution_status": "skipped_cache",
                    "backend_mode": "lightweight_smiles_standardization",
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
                "backend_mode": "lightweight_smiles_standardization",
                "skipped_cache": True,
                "skip_reason": "cache_signature_match",
                "selected_case_ids": case_scope_ids,
                "partial_rerun_active": bool(selected_case_ids),
                "selected_library_ids": selected_library_ids,
                "library_count": len(selected_library_ids),
            },
            "cache": {
                "signature": cache_signature,
                "cache_scope": "module",
                "cache_hit": True,
                "cache_hit_artifact": True,
            },
        }
        write_json(output_path, payload)
        print(f"[module] skipped compound library preparation via cache: {prepared_tsv}")
        print(f"[module] wrote module artifact: {output_path}")
        return 0

    prepared_rows: list[dict[str, object]] = []
    duplicate_count = 0
    input_record_count = 0
    library_summaries: list[dict[str, object]] = []
    case_updates: dict[str, dict[str, object]] = {}

    for library_meta in selected_libraries:
        library_started_at = time.perf_counter()
        source_path = Path(library_meta["source_path"])
        raw_records = read_smi_file(source_path)
        input_record_count += len(raw_records)
        seen_smiles: set[str] = set()
        library_duplicate_count = 0
        library_prepared_count = 0

        for record in raw_records:
            standardized_smiles = normalize_smiles(record["raw_smiles"])
            if standardized_smiles in seen_smiles:
                duplicate_count += 1
                library_duplicate_count += 1
                continue
            seen_smiles.add(standardized_smiles)
            properties = estimate_properties(standardized_smiles)
            prepared_rows.append(
                {
                    "library_id": library_meta["library_id"],
                    "compound_id": record["compound_id"],
                    "raw_smiles": record["raw_smiles"],
                    "standardized_smiles": standardized_smiles,
                    **properties,
                }
            )
            library_prepared_count += 1

        library_runtime_seconds = time.perf_counter() - library_started_at
        library_summaries.append(
            {
                "library_id": library_meta["library_id"],
                "source_path": library_meta["source_path"],
                "input_record_count": len(raw_records),
                "prepared_record_count": library_prepared_count,
                "duplicate_count": library_duplicate_count,
                "related_case_ids": sorted(cases_by_library.get(library_meta["library_id"], [])),
                "runtime_seconds": round(library_runtime_seconds, 6),
            }
        )
        for case_id in cases_by_library.get(library_meta["library_id"], []):
            case_updates[case_id] = {
                "runtime_seconds": library_runtime_seconds,
                "execution_status": "executed",
                "backend_mode": "lightweight_smiles_standardization",
                "skipped_cache": False,
                "skip_reason": "",
                "cache_hit_artifact": False,
                "library_id": library_meta["library_id"],
            }

    final_prepared_rows: list[dict[str, object]] = prepared_rows
    if selected_case_ids and prepared_tsv.exists() and prepared_tsv.stat().st_size > 0:
        final_prepared_rows = merge_rows_by_keys(read_tsv_rows(prepared_tsv), prepared_rows, ["library_id", "compound_id"])

    write_tsv(
        prepared_tsv,
        final_prepared_rows,
        [
            "library_id",
            "compound_id",
            "raw_smiles",
            "standardized_smiles",
            "smiles_length",
            "heavy_atom_count",
            "hetero_atom_count",
            "aromatic_atom_count",
            "ring_index_count",
            "molecular_weight_estimate",
        ],
    )

    summary_payload = {
        "module": "compound_library_preparation",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "library_id": selected_library_ids[0] if len(selected_library_ids) == 1 else "multiple",
        "library_count": len(selected_library_ids),
        "selected_library_ids": selected_library_ids,
        "input_record_count": input_record_count,
        "prepared_record_count": len(final_prepared_rows),
        "duplicate_count": duplicate_count,
        "source_path": selected_libraries[0]["source_path"] if len(selected_libraries) == 1 else "multiple",
        "output_table": str(prepared_tsv),
        "selected_case_ids": case_scope_ids,
        "partial_rerun_active": bool(selected_case_ids),
        "library_summaries": library_summaries,
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8")

    markdown = "\n".join(
        [
            "# Compound Library Preparation",
            "",
            f"- Libraries prepared: `{len(selected_library_ids)}`",
            f"- Selected libraries: `{', '.join(selected_library_ids) if selected_library_ids else 'none'}`",
            f"- Input records: `{input_record_count}`",
            f"- Prepared records: `{len(final_prepared_rows)}`",
            f"- Duplicates removed: `{duplicate_count}`",
            f"- Output table: `{prepared_tsv}`",
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
        "lightweight_smiles_standardization",
        case_updates,
    )

    payload = {
        "module": args.module,
        "status": "library_preparation_completed",
        "config": args.config,
        "project_root": args.project_root,
        "run_manifest": args.run_manifest,
        "input_manifest": args.input_manifest,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validation": {
            "run_manifest_exists": Path(args.run_manifest).exists(),
            "input_manifest_exists": Path(args.input_manifest).exists(),
            "selected_library_count_gt_zero": len(selected_library_ids) > 0,
            "all_selected_library_sources_exist": all(Path(row["source_path"]).exists() for row in selected_libraries),
            "prepared_table_written": prepared_tsv.exists(),
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
            "backend_mode": "lightweight_smiles_standardization",
            "skipped_cache": False,
            "skip_reason": "",
            "selected_case_ids": case_scope_ids,
            "partial_rerun_active": bool(selected_case_ids),
            "selected_library_ids": selected_library_ids,
        },
        "module_profile": {
            "stage_type": "compound_library_preparation",
            "primary_inputs": ["compound library metadata", "SMILES library file"],
            "primary_outputs": [str(prepared_tsv), str(summary_json), str(report_md), args.output],
            "next_action_hint": "attach chemistry-aware standardization and richer property calculation later",
        },
        "input_summary": {
            "row_count": input_record_count,
            "preview_ids": [row["library_id"] for row in selected_libraries[:3]],
        },
        "library_outputs": {
            "prepared_library_tsv": str(prepared_tsv),
            "library_summary_json": str(summary_json),
            "library_report_markdown": str(report_md),
            "selected_library_ids": selected_library_ids,
            "library_count": len(selected_library_ids),
            "library_summaries": library_summaries,
        },
        "cache": {
            "signature": cache_signature,
            "cache_scope": "module",
            "cache_hit": False,
            "cache_hit_artifact": False,
        },
        "notes": [
            "Compound library preparation now standardizes, deduplicates, and annotates a small SMILES library.",
            "Property calculation is intentionally lightweight and approximate in this minimal CPU-only implementation.",
        ],
    }

    write_json(output_path, payload)
    print(f"[module] wrote prepared library table: {prepared_tsv}")
    print(f"[module] wrote library summary: {summary_json}")
    print(f"[module] wrote module report: {report_md}")
    print(f"[module] wrote module artifact: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
