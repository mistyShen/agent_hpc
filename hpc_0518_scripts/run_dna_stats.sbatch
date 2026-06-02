#!/usr/bin/env bash
#SBATCH --job-name=0518_dna_stats
#SBATCH --partition=comp
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=/shared/shen/2026/0518/analysis_dna/logs/dna_stats_%j.out
#SBATCH --error=/shared/shen/2026/0518/analysis_dna/logs/dna_stats_%j.err

set -euo pipefail
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aml_rna

python /shared/shen/2026/0518/analysis_dna/scripts/compute_dna_mt_stats.py
