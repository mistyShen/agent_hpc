#!/usr/bin/env bash
#SBATCH --job-name=ult_method_tools
#SBATCH --output=/shared/shen/2026/ultimate/logs/%x_%j.out
#SBATCH --error=/shared/shen/2026/ultimate/logs/%x_%j.err
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00

set -euo pipefail

PROJECT_ROOT="${ULTIMATE_ROOT:-/shared/shen/2026/ultimate}"
CORE_ENV="${ULTIMATE_CORE_ENV:-$PROJECT_ROOT/.conda/envs/ultimate-core}"
SCRNA_ENV="${ULTIMATE_SCRNA_ENV:-$PROJECT_ROOT/.conda/envs/ultimate-scrna}"
SCRNA_FALLBACK_ENV="${ULTIMATE_SCRNA_FALLBACK_ENV:-/shared/shen/2026/singlecell_workbench/.conda/envs/scw-py311}"
CONDA_SH="${CONDA_SH:-/share/home/nshen/miniconda3/etc/profile.d/conda.sh}"
INPUT_H5AD="${ULTIMATE_METHOD_TOOLS_INPUT:-/shared/shen/2026/nsclc_virtual_sc/02_processed_scRNA/Lambrechts_all_harmonized.h5ad}"
OUT_DIR="${ULTIMATE_METHOD_TOOLS_OUT:-$PROJECT_ROOT/validations/slurm_method_tools_nsclc}"

mkdir -p "$PROJECT_ROOT/logs" "$PROJECT_ROOT/validations"
source "$CONDA_SH"

if [[ -x "$SCRNA_ENV/bin/python" ]]; then
  PYTHON_BIN="$SCRNA_ENV/bin/python"
elif [[ -x "$SCRNA_FALLBACK_ENV/bin/python" ]]; then
  PYTHON_BIN="$SCRNA_FALLBACK_ENV/bin/python"
else
  PYTHON_BIN=""
fi

write_skip_manifest() {
  mkdir -p "$OUT_DIR/reports"
  "$CORE_ENV/bin/python" - "$OUT_DIR" "$1" "$2" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

out = Path(sys.argv[1])
status = sys.argv[2]
reason = sys.argv[3]
manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "output_dir": str(out),
    "module": "method_tools",
    "status": status,
    "analysis_level": "smoke_backend",
    "is_demo": False,
    "is_stub": True,
    "delivery_allowed": False,
    "validation_evidence_allowed": False,
    "non_delivery_reason": f"validation_not_completed:{reason}",
    "backend_id": "method_tools.default.delivery_manifest_mvp",
    "backend_status": "fully_automatic_mvp",
    "backend_skip_reason": reason,
    "skip_reason": reason,
    "slurm_job_id": os.environ.get("SLURM_JOB_ID", ""),
    "slurm_job_name": os.environ.get("SLURM_JOB_NAME", ""),
    "slurm": {
        "job_id": os.environ.get("SLURM_JOB_ID", ""),
        "job_name": os.environ.get("SLURM_JOB_NAME", ""),
        "submit_dir": os.environ.get("SLURM_SUBMIT_DIR", ""),
    },
}
(out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
(out / "reports" / "methods.md").write_text(
    "# method_tools validation skipped\n\n"
    "analysis_level: `smoke_backend`\n\n"
    "delivery_allowed: `false`\n\n"
    f"reason: {reason}\n",
    encoding="utf-8",
)
(out / "reports" / "report.html").write_text(
    f"<html><body><h1>method_tools validation skipped</h1><p>{reason}</p></body></html>",
    encoding="utf-8",
)
PY
}

if [[ -z "$PYTHON_BIN" ]]; then
  write_skip_manifest "partial:dependency_required" "No Python environment with scanpy/anndata was found"
  exit 0
fi

if [[ ! -s "$INPUT_H5AD" ]]; then
  write_skip_manifest "partial:data_required" "Missing input h5ad: $INPUT_H5AD"
  exit 0
fi

export PYTHONPATH="$PROJECT_ROOT/src"

mkdir -p "$OUT_DIR/config"
cat > "$OUT_DIR/config/project.yaml" <<YAML
project:
  name: slurm_method_tools_nsclc
  organism: human
  output_dir: $OUT_DIR
  server_root: $PROJECT_ROOT
  run_mode: interactive
  overwrite: true
samples:
  items:
    - sample_id: nsclc_method_tools
      condition: internal_validation
      input_path: $INPUT_H5AD
design:
  condition_column: condition
  control: internal_validation
  case: internal_validation
modules:
  method_tools:
    enabled: true
    preset: publication
    input_h5ad: $INPUT_H5AD
    analysis_level: validated_backend
    validation_dataset: NSCLC Lambrechts harmonized h5ad
    max_cells_object: ${ULTIMATE_METHOD_TOOLS_MAX_CELLS:-3000}
    raw:
      enabled: false
      input_type: object
report:
  title: NSCLC method_tools unified backend validation
  style: soft_color
YAML

"$PYTHON_BIN" -m ultimate.cli preflight --config "$OUT_DIR/config/project.yaml" > "$OUT_DIR/preflight_stdout.json"
"$PYTHON_BIN" -m ultimate.cli run --config "$OUT_DIR/config/project.yaml" > "$OUT_DIR/run_stdout.json"
