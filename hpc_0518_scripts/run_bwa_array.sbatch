#!/usr/bin/env bash
#SBATCH --job-name=0518_rca_bwa
#SBATCH --partition=comp
#SBATCH --cpus-per-task=8
#SBATCH --mem=40G
#SBATCH --time=24:00:00
#SBATCH --output=/shared/shen/2026/0518/analysis_dna/logs/bwa_%A_%a.out
#SBATCH --error=/shared/shen/2026/0518/analysis_dna/logs/bwa_%A_%a.err

set -euo pipefail
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aml_rna

BASE=/shared/shen/2026/0518
MANIFEST="$BASE/sample_manifest.tsv"
REF=/shared/shen/2026/0311/analysis_rna/ref/hg19.fa
THREADS=${SLURM_CPUS_PER_TASK:-8}
TASK_ID=${SLURM_ARRAY_TASK_ID:-1}

sample=$(awk -F '\t' -v n="$TASK_ID" 'NR == n + 1 {print $1}' "$MANIFEST")
r1=$(awk -F '\t' -v n="$TASK_ID" 'NR == n + 1 {print $2}' "$MANIFEST")
r2=$(awk -F '\t' -v n="$TASK_ID" 'NR == n + 1 {print $3}' "$MANIFEST")
read_pairs=$(awk -F '\t' -v n="$TASK_ID" 'NR == n + 1 {print $4}' "$MANIFEST")
data_type=$(awk -F '\t' -v n="$TASK_ID" 'NR == n + 1 {print $5}' "$MANIFEST")

if [ -z "$sample" ] || [ -z "$r1" ] || [ -z "$r2" ]; then
  echo "No complete manifest row for array task $TASK_ID" >&2
  exit 1
fi

OUTDIR="$BASE/analysis_dna/bam/$sample"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/${sample}.sorted.bam"
TMP="$OUTDIR/${sample}.sorted.tmp.bam"
RG="@RG\tID:${sample}\tSM:${sample}\tPL:ILLUMINA\tLB:X101SC25065539-Z01-J098"

echo "[$(date)] sample=$sample data_type=$data_type read_pairs=$read_pairs"
echo "[$(date)] r1=$r1"
echo "[$(date)] r2=$r2"
echo "[$(date)] bwa=$(command -v bwa) samtools=$(command -v samtools) ref=$REF"

if [ ! -f "$REF.bwt" ]; then
  echo "Missing BWA index for $REF" >&2
  exit 1
fi
if [ ! -s "$r1" ] || [ ! -s "$r2" ]; then
  echo "Missing FASTQ input for $sample" >&2
  exit 1
fi

bwa mem -t "$THREADS" -R "$RG" "$REF" "$r1" "$r2" \
  | samtools sort -@ "$THREADS" -m 3G -o "$TMP" -

mv "$TMP" "$OUT"
samtools index -@ "$THREADS" "$OUT"
samtools quickcheck -v "$OUT"
samtools flagstat -@ "$THREADS" "$OUT" > "$OUTDIR/${sample}.flagstat.txt"
echo "[$(date)] done $sample -> $OUT"
