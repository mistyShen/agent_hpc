#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/envs/environment.server.yml"
ENV_PREFIX="${1:-$PROJECT_ROOT/.conda/envs/scw-py311}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing environment file: $ENV_FILE" >&2
  exit 1
fi

if [[ ! -f /share/home/nshen/miniconda3/etc/profile.d/conda.sh ]]; then
  echo "Could not find conda activation script under /share/home/nshen/miniconda3" >&2
  exit 1
fi

source /share/home/nshen/miniconda3/etc/profile.d/conda.sh

if command -v mamba >/dev/null 2>&1; then
  CONDA_FRONTEND="mamba"
else
  CONDA_FRONTEND="conda"
fi

mkdir -p "$(dirname "$ENV_PREFIX")"

if [[ -d "$ENV_PREFIX" ]]; then
  "$CONDA_FRONTEND" env update -p "$ENV_PREFIX" -f "$ENV_FILE" --prune
else
  "$CONDA_FRONTEND" env create -p "$ENV_PREFIX" -f "$ENV_FILE"
fi

"$CONDA_FRONTEND" remove -p "$ENV_PREFIX" -y decoupler >/dev/null 2>&1 || true

conda run -p "$ENV_PREFIX" python -m pip install --upgrade pip
conda run -p "$ENV_PREFIX" python -m pip uninstall -y scHPL schpl newick skranger >/dev/null 2>&1 || true
conda run -p "$ENV_PREFIX" python -m pip install --no-deps \
  "configparser>=7,<8" \
  "docker>=7,<8"
conda run -p "$ENV_PREFIX" python -m pip install --no-deps \
  "adjustText>=1.3,<2" \
  "celltypist>=1.6,<2" \
  "decoupler>=2.1.6,<2.2" \
  "docrep>=0.3.2,<0.4" \
  "legendkit>=0.4,<0.5" \
  "marsilea>=0.5.8,<0.6" \
  "scarches>=0.5.10,<0.7" \
  "scar>=4,<5"
conda run -p "$ENV_PREFIX" python -m pip install -e "$PROJECT_ROOT"

echo
echo "Environment ready:"
echo "  prefix: $ENV_PREFIX"
echo "  activate: source /share/home/nshen/miniconda3/etc/profile.d/conda.sh && conda activate $ENV_PREFIX"
echo
conda run -p "$ENV_PREFIX" python - <<'PY'
import importlib
import sys

mods = [
    "scanpy",
    "anndata",
    "mudata",
    "scvi",
    "celltypist",
    "decoupler",
    "scarches",
    "scar",
    "singlecell_workbench",
]
failures = []
for mod in mods:
    try:
        module = importlib.import_module(mod)
        version = getattr(module, "__version__", "unknown")
        print(f"{mod}\t{version}")
    except Exception as exc:
        print(f"{mod}\tERROR\t{type(exc).__name__}: {exc}")
        failures.append(mod)

if failures:
    print(f"Import smoke test failed for: {', '.join(failures)}", file=sys.stderr)
    raise SystemExit(1)
PY
