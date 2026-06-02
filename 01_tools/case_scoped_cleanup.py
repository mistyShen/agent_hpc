#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import shutil
import tempfile
from pathlib import Path


TABLE_SPECS = [
    {
        "path": Path("07_results/modules/compound_library_preparation/prepared_library.tsv"),
        "field": "library_id",
    },
    {
        "path": Path("07_results/modules/classical_docking/docking_results.tsv"),
        "field": "case_id",
    },
    {
        "path": Path("07_results/modules/ai_reranking/reranked_candidates.tsv"),
        "field": "case_id",
    },
    {
        "path": Path("07_results/modules/filtering/filtered_candidates.tsv"),
        "field": "case_id",
    },
    {
        "path": Path("07_results/modules/clustering_and_prioritization/clustered_priorities.tsv"),
        "field": "case_id",
    },
]

DOCKING_CASE_DIRS = [
    Path("07_results/modules/classical_docking/ligands"),
    Path("07_results/modules/classical_docking/poses"),
    Path("07_results/modules/classical_docking/logs"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove stale single-case rows before a partial rerun.")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--library-id", required=True)
    parser.add_argument("--project-root", default=".")
    return parser.parse_args()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, list(reader)


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f"{path.name}.",
        suffix=".tmp",
        delete=False,
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def cleanup_table(path: Path, field: str, match_value: str) -> dict[str, object]:
    if not path.exists():
        return {
            "path": str(path),
            "field": field,
            "match_value": match_value,
            "status": "missing",
            "removed_row_count": 0,
        }
    fieldnames, rows = read_rows(path)
    kept_rows = [row for row in rows if row.get(field, "") != match_value]
    removed_count = len(rows) - len(kept_rows)
    write_rows(path, fieldnames, kept_rows)
    return {
        "path": str(path),
        "field": field,
        "match_value": match_value,
        "status": "updated",
        "removed_row_count": removed_count,
    }


def cleanup_case_dir(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "status": "missing"}
    shutil.rmtree(path)
    return {"path": str(path), "status": "removed"}


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    case_id = args.case_id
    library_id = args.library_id

    table_results = []
    for spec in TABLE_SPECS:
        match_value = library_id if spec["field"] == "library_id" else case_id
        table_results.append(cleanup_table(project_root / spec["path"], spec["field"], match_value))

    dir_results = []
    for base_dir in DOCKING_CASE_DIRS:
        dir_results.append(cleanup_case_dir(project_root / base_dir / case_id))

    payload = {
        "project_root": str(project_root),
        "case_id": case_id,
        "library_id": library_id,
        "table_cleanup": table_results,
        "directory_cleanup": dir_results,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
