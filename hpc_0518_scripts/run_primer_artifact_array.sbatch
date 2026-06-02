#!/usr/bin/env bash
#SBATCH --job-name=0518_primer_artifact_arr
#SBATCH --partition=comp
#SBATCH --array=1-4
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=/shared/shen/2026/0518/analysis_dna/primer_artifact/logs/primer_artifact_array_%A_%a.out
#SBATCH --error=/shared/shen/2026/0518/analysis_dna/primer_artifact/logs/primer_artifact_array_%A_%a.err

set -euo pipefail
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aml_rna

samples=(A_121 A_122 A_161 A_163)
sample=${samples[$((SLURM_ARRAY_TASK_ID - 1))]}

python /shared/shen/2026/0518/analysis_dna/primer_artifact/scripts/primer_artifact_diagnosis.py \
  --base /shared/shen/2026/0518 \
  --samples "$sample" \
  --subsample-pairs 200000 \
  --max-softclip-kmer-fragments 100000 \
  --per-sample-output
