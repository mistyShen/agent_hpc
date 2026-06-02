#!/usr/bin/env python3
"""Thin launcher for the local Snakemake scaffold."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch the cpu_ai_drug_design workflow.")
    parser.add_argument("--cores", type=int, default=1, help="Number of CPU cores for Snakemake.")
    parser.add_argument("--dry-run", action="store_true", help="Show the planned DAG without executing rules.")
    parser.add_argument("--profile", default=None, help="Optional Snakemake profile directory.")
    parser.add_argument("--forcerun", nargs="*", default=None, help="Optional Snakemake rules or targets to force.")
    parser.add_argument("--reason", default="manual", help="Free-text reason for this run.")
    args = parser.parse_args()

    snakemake = shutil.which("snakemake")
    if snakemake is None:
        print("snakemake not found in PATH. Install it later, then rerun this launcher.", file=sys.stderr)
        print("Planned command: snakemake --snakefile Snakefile --configfile config.yaml --cores 1")
        return 0

    cmd = [
        snakemake,
        "--snakefile",
        "Snakefile",
        "--configfile",
        "config.yaml",
        "--cores",
        str(args.cores),
        "--rerun-incomplete",
        "--printshellcmds",
    ]
    if args.profile:
        cmd.extend(["--profile", args.profile])
    if args.forcerun:
        cmd.extend(["--forcerun", *args.forcerun])
    if args.dry_run:
        cmd.append("--dry-run")

    print(f"[launcher] reason={args.reason}")
    print("[launcher] command:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
