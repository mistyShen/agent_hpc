#!/usr/bin/env python3
"""Validate lightweight benchmark metadata tables."""

from __future__ import annotations

import csv
from pathlib import Path
import sys


REQUIRED_COLUMNS = {
    "04_metadata/datasets.tsv": ["dataset_id", "description", "source_type", "notes"],
    "04_metadata/targets.tsv": ["target_id", "species", "target_type", "structure_source", "structure_path", "notes"],
    "04_metadata/compound_libraries.tsv": ["library_id", "library_type", "source_path", "record_format", "notes"],
    "04_metadata/benchmark_case_truth.tsv": [
        "case_id",
        "compound_id",
        "truth_label",
        "truth_role",
        "reference_source",
        "reference_doi_or_url",
        "notes",
    ],
    "04_metadata/benchmark_cases.tsv": [
        "case_id",
        "case_type",
        "case_tier",
        "run_purpose",
        "primary_metric",
        "target_id",
        "library_id",
        "docking_protocol",
        "rerank_strategy",
        "filter_policy",
        "clustering_policy",
        "report_template",
        "reference_source",
        "reference_doi_or_url",
        "ground_truth_type",
        "known_active_definition",
        "expected_behavior",
        "enabled",
    ],
}

ALLOWED_CASE_TYPES = {"toy", "debug", "realistic", "literature_backed"}


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header row")
        rows = list(reader)
        return reader.fieldnames, rows


def fail(message: str) -> None:
    print(f"[validate_metadata] {message}")


def main() -> int:
    ok = True
    tables: dict[str, list[dict[str, str]]] = {}

    for rel_path, required_cols in REQUIRED_COLUMNS.items():
        path = Path(rel_path)
        if not path.exists():
            fail(f"missing file: {rel_path}")
            ok = False
            continue

        headers, rows = read_rows(path)
        missing_cols = [col for col in required_cols if col not in headers]
        if missing_cols:
            fail(f"{rel_path} missing columns: {', '.join(missing_cols)}")
            ok = False
            continue

        if not rows:
            fail(f"{rel_path} has no data rows")
            ok = False
            continue

        tables[rel_path] = rows

    if not ok:
        return 1

    target_ids = {row["target_id"] for row in tables["04_metadata/targets.tsv"]}
    library_ids = {row["library_id"] for row in tables["04_metadata/compound_libraries.tsv"]}
    benchmark_case_ids = {row["case_id"] for row in tables["04_metadata/benchmark_cases.tsv"]}

    for rel_path, key in [
        ("04_metadata/datasets.tsv", "dataset_id"),
        ("04_metadata/targets.tsv", "target_id"),
        ("04_metadata/compound_libraries.tsv", "library_id"),
        ("04_metadata/benchmark_cases.tsv", "case_id"),
    ]:
        seen: set[str] = set()
        for row in tables[rel_path]:
            value = row[key].strip()
            if not value:
                fail(f"{rel_path} has empty {key}")
                ok = False
                continue
            if value in seen:
                fail(f"{rel_path} has duplicate {key}: {value}")
                ok = False
            seen.add(value)

    for row in tables["04_metadata/benchmark_cases.tsv"]:
        case_id = row["case_id"]
        case_type = row["case_type"].strip()
        case_tier = row["case_tier"].strip()
        run_purpose = row["run_purpose"].strip()
        primary_metric = row["primary_metric"].strip()
        if row["target_id"] not in target_ids:
            fail(f"benchmark case {case_id} references missing target_id={row['target_id']}")
            ok = False
        if row["library_id"] not in library_ids:
            fail(f"benchmark case {case_id} references missing library_id={row['library_id']}")
            ok = False
        if row["enabled"].strip().lower() not in {"true", "false"}:
            fail(f"benchmark case {case_id} has invalid enabled={row['enabled']}")
            ok = False
        if case_type not in ALLOWED_CASE_TYPES:
            fail(f"benchmark case {case_id} has invalid case_type={row['case_type']}")
            ok = False
        if not case_tier:
            fail(f"benchmark case {case_id} has empty case_tier")
            ok = False
        if not run_purpose:
            fail(f"benchmark case {case_id} has empty run_purpose")
            ok = False
        if not primary_metric:
            fail(f"benchmark case {case_id} has empty primary_metric")
            ok = False
        if not row["reference_source"].strip():
            fail(f"benchmark case {case_id} has empty reference_source")
            ok = False
        if not row["reference_doi_or_url"].strip():
            fail(f"benchmark case {case_id} has empty reference_doi_or_url")
            ok = False
        if not row["ground_truth_type"].strip():
            fail(f"benchmark case {case_id} has empty ground_truth_type")
            ok = False
        if not row["known_active_definition"].strip():
            fail(f"benchmark case {case_id} has empty known_active_definition")
            ok = False
        if not row["expected_behavior"].strip():
            fail(f"benchmark case {case_id} has empty expected_behavior")
            ok = False

    for row in tables["04_metadata/benchmark_case_truth.tsv"]:
        case_id = row["case_id"].strip()
        compound_id = row["compound_id"].strip()
        if case_id not in benchmark_case_ids:
            fail(f"benchmark truth row references missing case_id={case_id}")
            ok = False
        if not compound_id:
            fail("benchmark truth row has empty compound_id")
            ok = False
        if row["truth_label"].strip() not in {"known_active", "background"}:
            fail(f"benchmark truth row for case {case_id} has invalid truth_label={row['truth_label']}")
            ok = False

    if not ok:
        return 1

    print("[validate_metadata] metadata tables passed validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
