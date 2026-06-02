#!/bin/bash
#SBATCH --job-name=cpu_ai_drug_design
#SBATCH --output=/shared/shen/cpu_ai_drug_design/07_results/logs/slurm.%j.out
#SBATCH --error=/shared/shen/cpu_ai_drug_design/07_results/logs/slurm.%j.err
#SBATCH --partition=comp
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00

set -euo pipefail

source ~/.bashrc
conda activate aml_rna

cd /shared/shen/cpu_ai_drug_design
python run_workflow.py --cores "${SLURM_CPUS_PER_TASK:-1}" --reason "slurm_placeholder"
