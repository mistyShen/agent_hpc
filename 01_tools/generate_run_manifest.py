#!/usr/bin/env python3
"""Generate a lightweight benchmark run manifest from TSV metadata."""

from __future__ import annotations

import argparse
import csv
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def enabled_case_count(rows: list[dict[str, str]]) -> int:
    return sum(row.get("enabled", "").strip().lower() == "true" for row in rows)


def count_by_field(rows: list[dict[str, str]], field: str, enabled_only: bool = False) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if enabled_only and row.get("enabled", "").strip().lower() != "true":
            continue
        value = row.get(field, "").strip() or "unspecified"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a lightweight benchmark run manifest.")
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--datasets", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--libraries", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    datasets_path = Path(args.datasets)
    targets_path = Path(args.targets)
    libraries_path = Path(args.libraries)
    cases_path = Path(args.cases)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    datasets = read_tsv(datasets_path)
    targets = read_tsv(targets_path)
    libraries = read_tsv(libraries_path)
    cases = read_tsv(cases_path)

    payload = {
        "project_name": args.project_name,
        "project_root": args.project_root,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "datasets_manifest": str(datasets_path),
            "targets_manifest": str(targets_path),
            "compound_libraries_manifest": str(libraries_path),
            "benchmark_cases_manifest": str(cases_path),
        },
        "counts": {
            "datasets": len(datasets),
            "targets": len(targets),
            "compound_libraries": len(libraries),
            "benchmark_cases": len(cases),
            "enabled_benchmark_cases": enabled_case_count(cases),
            "benchmark_case_type_counts": count_by_field(cases, "case_type"),
            "enabled_benchmark_case_type_counts": count_by_field(cases, "case_type", enabled_only=True),
        },
        "mode": "scaffold_only",
        "schemas": {
            "run_manifest_doc": "00_docs/ARTIFACT_SCHEMAS.md",
            "module_interface_doc": "00_docs/MODULE_INTERFACES.md",
            "metadata_field_doc": "04_metadata/FIELD_REFERENCE.md",
        },
        "execution_state": {
            "modules": {},
            "cases": {row["case_id"]: {} for row in cases if row.get("case_id", "").strip()},
        },
    }

    write_json_atomic(output_path, payload)
    print(f"[generate_run_manifest] wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
