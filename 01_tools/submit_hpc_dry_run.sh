#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-/shared/shen/cpu_ai_drug_design}"
SCRIPT_PATH="${PROJECT_ROOT}/08_envs/slurm.dry_run.sbatch"

echo "[submit_hpc_dry_run] project_root=${PROJECT_ROOT}"
echo "[submit_hpc_dry_run] script=${SCRIPT_PATH}"
echo "[submit_hpc_dry_run] expected_env=snakemake"
hpc-sbatch "${SCRIPT_PATH}"
