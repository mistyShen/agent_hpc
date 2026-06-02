#!/usr/bin/env bash
#SBATCH --job-name=0518_primer_artifact
#SBATCH --partition=comp
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=/shared/shen/2026/0518/analysis_dna/primer_artifact/logs/primer_artifact_%j.out
#SBATCH --error=/shared/shen/2026/0518/analysis_dna/primer_artifact/logs/primer_artifact_%j.err

set -euo pipefail
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aml_rna

python /shared/shen/2026/0518/analysis_dna/primer_artifact/scripts/primer_artifact_diagnosis.py \
  --base /shared/shen/2026/0518 \
  --samples A_121 A_122 A_161 A_163 \
  --subsample-pairs 200000 \
  --max-softclip-kmer-fragments 100000
