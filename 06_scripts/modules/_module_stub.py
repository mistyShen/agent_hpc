#!/usr/bin/env python3
"""Reusable placeholder framework for scaffold modules."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a placeholder artifact for a workflow module.")
    parser.add_argument("--module", required=True, help="Module name.")
    parser.add_argument("--config", required=True, help="Path to project config.")
    parser.add_argument("--project-root", required=True, help="Formal project root for this execution context.")
    parser.add_argument("--run-manifest", required=True, help="Run manifest JSON path.")
    parser.add_argument("--input-manifest", required=True, help="Module-specific metadata manifest path.")
    parser.add_argument("--output", required=True, help="Path to output artifact.")
    return parser.parse_args()


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def build_payload(args: argparse.Namespace, spec: dict[str, object]) -> dict[str, object]:
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_manifest_path = Path(args.run_manifest)
    input_manifest_path = Path(args.input_manifest)

    manifest_payload: dict[str, object] | None = None
    input_rows: list[dict[str, str]] = []

    validation = {
        "run_manifest_exists": run_manifest_path.exists(),
        "input_manifest_exists": input_manifest_path.exists(),
    }

    if validation["run_manifest_exists"]:
        manifest_payload = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    if validation["input_manifest_exists"]:
        input_rows = read_tsv_rows(input_manifest_path)

    status = "scaffold_placeholder" if all(validation.values()) else "scaffold_placeholder_with_missing_inputs"
    counts = manifest_payload.get("counts", {}) if isinstance(manifest_payload, dict) else {}

    return {
        "module": args.module,
        "status": status,
        "config": args.config,
        "project_root": args.project_root,
        "run_manifest": args.run_manifest,
        "input_manifest": args.input_manifest,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validation": validation,
        "run_context": {
            "run_mode": manifest_payload.get("mode") if manifest_payload else None,
            "enabled_benchmark_cases": counts.get("enabled_benchmark_cases") if isinstance(counts, dict) else None,
        },
        "module_profile": {
            "stage_type": spec["stage_type"],
            "primary_inputs": spec["primary_inputs"],
            "primary_outputs": spec["primary_outputs"],
            "next_action_hint": spec["next_action_hint"],
        },
        "input_summary": {
            "row_count": len(input_rows),
            "preview_ids": [
                row.get(spec["preview_key"], "")
                for row in input_rows[:3]
                if row.get(spec["preview_key"], "")
            ],
        },
        "notes": [
            spec["note"],
            "Replace this placeholder with real CPU-only logic later.",
        ],
    }


def run_module(spec: dict[str, object]) -> int:
    args = parse_args()
    payload = build_payload(args, spec)
    Path(args.output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"[module] wrote placeholder artifact: {args.output}")
    print(f"[module] stage_type={spec['stage_type']}")
    return 0


if __name__ == "__main__":
    raise SystemExit("Import this module from a concrete workflow module.")
