#!/usr/bin/env bash
#SBATCH --job-name=0518_primer_merge
#SBATCH --partition=comp
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=/shared/shen/2026/0518/analysis_dna/primer_artifact/logs/primer_merge_%j.out
#SBATCH --error=/shared/shen/2026/0518/analysis_dna/primer_artifact/logs/primer_merge_%j.err

set -euo pipefail
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aml_rna

python /shared/shen/2026/0518/analysis_dna/primer_artifact/scripts/merge_primer_artifact_reports.py
