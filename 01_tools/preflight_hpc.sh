#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-/shared/shen/cpu_ai_drug_design}"

hpc-run "
set -euo pipefail
echo '[preflight] project_root=${PROJECT_ROOT}'
for path in \
  '${PROJECT_ROOT}' \
  '${PROJECT_ROOT}/config.yaml' \
  '${PROJECT_ROOT}/Snakefile' \
  '${PROJECT_ROOT}/01_tools/generate_run_manifest.py' \
  '${PROJECT_ROOT}/04_metadata/targets.tsv' \
  '${PROJECT_ROOT}/08_envs/slurm.run_workflow.sbatch'
do
  if [ -e \"\$path\" ]; then
    echo \"EXISTS \$path\"
  else
    echo \"MISSING \$path\"
  fi
done

if command -v conda >/dev/null 2>&1; then
  echo '[preflight] conda=present'
else
  echo '[preflight] conda=missing'
fi

if command -v python >/dev/null 2>&1; then
  echo \"[preflight] python=\$(python --version 2>&1)\"
else
  echo '[preflight] python=missing'
fi

if conda activate snakemake >/dev/null 2>&1; then
  echo \"[preflight] snakemake_env_python=\$(python --version 2>&1)\"
  if command -v snakemake >/dev/null 2>&1; then
    echo \"[preflight] snakemake=\$(snakemake --version 2>&1)\"
  else
    echo '[preflight] snakemake=missing_in_snakemake_env'
  fi
else
  echo '[preflight] snakemake_env=activate_failed'
fi

if [ -f \"${PROJECT_ROOT}/config.yaml\" ]; then
  echo '[preflight] server_root from config:'
  grep -n 'server_root:' \"${PROJECT_ROOT}/config.yaml\" || true
fi
"
