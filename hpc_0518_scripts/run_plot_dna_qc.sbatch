#!/usr/bin/env bash
#SBATCH --job-name=0518_dna_plots
#SBATCH --partition=comp
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/shared/shen/2026/0518/analysis_dna/logs/dna_plots_%j.out
#SBATCH --error=/shared/shen/2026/0518/analysis_dna/logs/dna_plots_%j.err

set -euo pipefail
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aml_rna

python /shared/shen/2026/0518/analysis_dna/scripts/plot_dna_qc_figures.py
