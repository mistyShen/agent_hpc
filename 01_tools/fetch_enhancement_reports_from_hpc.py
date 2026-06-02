#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ENHANCEMENT_REPORTS = [
    "09_reports/enhancement_line_v2_vs_v3_comparison.json",
    "09_reports/enhancement_line_v2_vs_v3_comparison.md",
    "09_reports/enhancement_line_background_delta.json",
    "09_reports/enhancement_line_background_delta.md",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch the current enhancement-line reports from the isolated HPC workspace."
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Local project root that contains 09_reports/",
    )
    parser.add_argument(
        "--remote-root",
        default="/shared/shen/cpu_ai_drug_design_v3exp",
        help="Remote isolated enhancement workspace root",
    )
    return parser.parse_args()


def run_fetch(local_project_root: Path, remote_root: str, rel_path: str) -> None:
    local_path = local_project_root / rel_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    remote_path = f"{remote_root.rstrip('/')}/{rel_path}"
    subprocess.run(
        ["hpc-get", remote_path, str(local_path)],
        cwd=local_project_root,
        check=True,
    )


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    for rel_path in ENHANCEMENT_REPORTS:
        run_fetch(project_root, args.remote_root, rel_path)
        print(f"[enhancement-fetch] fetched {rel_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
