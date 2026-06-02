#!/bin/bash
#SBATCH --job-name=cpu_ai_drug_run
#SBATCH --output=/shared/shen/cpu_ai_drug_design/07_results/logs/slurm.scaffold_run.%j.out
#SBATCH --error=/shared/shen/cpu_ai_drug_design/07_results/logs/slurm.scaffold_run.%j.err
#SBATCH --partition=comp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:20:00

set -euo pipefail

source ~/.bashrc
conda activate snakemake

cd /shared/shen/cpu_ai_drug_design

python 01_tools/check_scaffold.py
python run_workflow.py --cores 1 --reason "hpc_scaffold_run" --forcerun build_run_manifest run_module
