# Restore From GitHub

This repository stores the local, lightweight control plane for the HPC work:
scripts, Slurm templates, environment files, metadata, small raw/example inputs,
reports, and recovery notes. Heavy datasets, generated scratch, long-run logs,
and machine-specific environments should remain outside Git and be recreated or
fetched from `/shared` as needed.

## Fresh machine checklist

1. Clone the repository.

   ```bash
   git clone https://github.com/mistyShen/agent_hpc.git
   cd agent_hpc
   ```

2. Check the expected local layout.

   ```bash
   find . -maxdepth 2 -type d | sort
   ```

3. Recreate local Python or Conda environments from the committed environment
   files, not from copied virtual environments.

   ```bash
   conda env create -f 08_envs/environment.cpu.yaml
   ```

4. Before touching remote execution, confirm the HPC target and wrapper access.

   ```bash
   hpc-ping
   hpc-run 'pwd; hostname; test -d /shared/shen && echo shared_ok'
   ```

5. Sync or inspect the remote project root only after confirming paths.

   ```bash
   hpc-run 'ls -lah /shared/shen/cpu_ai_drug_design'
   ```

6. Run local metadata/scaffold checks before submitting work.

   ```bash
   bash 01_tools/run_local_checks.sh
   ```

## What should be committed

- `00_docs/`: design, recovery, schema, and status documentation.
- `01_tools/`, `06_scripts/`, `run_workflow.py`, `Snakefile`, `config.yaml`:
  executable control-plane code.
- `03_data_raw/` and `04_metadata/`: small benchmark inputs and manifests that
  define reproducible cases.
- `08_envs/`: environment and Slurm templates.
- `09_reports/` and small `hpc_0518_outputs/`: lightweight summaries and figures
  that preserve interpretation state.
- `singlecell_workbench/`, `ultimate/`, and `hpc_0518_scripts/`: local project
  code, tests, templates, configs, and Slurm scripts.

## What should stay out of Git

- Local virtual environments such as `.venv/`.
- Cache directories such as `__pycache__/` and `.pytest_cache/`.
- Scratch directories such as `11_tmp/`.
- Long-run logs, lock files, temporary files, and Slurm stdout/stderr.
- Heavy sequencing, structure, matrix, or single-cell data files. Store those
  under `/shared`, and record their paths in manifests or docs.

## Commit discipline

Before pushing, run:

```bash
git status --short
git diff --stat
```

If a new file is needed to resume work on another computer, commit it. If it is
large, machine-specific, or reproducible from `/shared`, document the path and
exclude the file.
