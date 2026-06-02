#!/usr/bin/env python3
"""Lightweight scaffold validation for the CPU-only project."""

from __future__ import annotations

import subprocess
from pathlib import Path
import sys


REQUIRED_PATHS = [
    Path("README.md"),
    Path("config.yaml"),
    Path("Snakefile"),
    Path("run_workflow.py"),
    Path("00_docs/PROJECT_STRUCTURE.md"),
    Path("00_docs/PIPELINE_OVERVIEW.md"),
    Path("00_docs/BENCHMARK_PLAN.md"),
    Path("00_docs/MODULE_INTERFACES.md"),
    Path("00_docs/ARTIFACT_SCHEMAS.md"),
    Path("01_tools/generate_run_manifest.py"),
    Path("01_tools/validate_metadata.py"),
    Path("04_metadata/datasets.tsv"),
    Path("04_metadata/targets.tsv"),
    Path("04_metadata/compound_libraries.tsv"),
    Path("04_metadata/benchmark_cases.tsv"),
    Path("04_metadata/FIELD_REFERENCE.md"),
    Path("01_tools/preflight_hpc.sh"),
    Path("01_tools/submit_hpc_dry_run.sh"),
    Path("01_tools/submit_hpc_scaffold_run.sh"),
    Path("06_scripts/modules/_module_stub.py"),
    Path("08_envs/slurm.run_workflow.sbatch"),
    Path("08_envs/slurm.dry_run.sbatch"),
    Path("08_envs/slurm.scaffold_run.sbatch"),
    Path("08_envs/slurm/config.yaml"),
]


def main() -> int:
    missing = [str(path) for path in REQUIRED_PATHS if not path.exists()]
    if missing:
        print("[check_scaffold] missing paths:")
        for path in missing:
            print(path)
        return 1

    result = subprocess.run(
        [sys.executable, "01_tools/validate_metadata.py"],
        check=False,
    )
    if result.returncode != 0:
        print("[check_scaffold] metadata validation failed")
        return result.returncode

    print("[check_scaffold] scaffold looks structurally complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
