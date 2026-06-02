# Pipeline Overview

## Selected Framework

`Snakemake` is the primary execution framework for this project.

## Why Snakemake

- Native rule graph makes reruns and partial recovery straightforward.
- Central config file keeps project paths and runtime knobs in one place.
- Rule-level logs are easy to standardize.
- Local CPU execution and future Slurm submission are both natural fits.
- Placeholder stage today can evolve into formal benchmark DAG later without replacing the runner.

## Initial Module Order

1. `target_preparation`
2. `compound_library_preparation`
3. `classical_docking`
4. `ai_reranking`
5. `filtering`
6. `clustering_and_prioritization`
7. `report_generation`
8. `benchmark_evaluation`

## Current Scope

- Mixed state: some modules are still scaffold-level, while `classical_docking` and `ai_reranking` now have partial real-backend integration
- No new heavy dependency installation inside this repo
- No large data download
- Benchmark coverage is still toy/debug scale

## Current State Docs

- `00_docs/MODULE_INTERFACES.md`: frozen module interface and backend class
- `00_docs/ARTIFACT_SCHEMAS.md`: run manifest, `done.json`, log, and payload contract
- `00_docs/REAL_BACKEND_STATUS.md`: current real-vs-scaffold module snapshot
- `00_docs/RUN_RECOVERY.md`: failure recovery and partial rerun policy
- `00_docs/BENCHMARK_CASE_SCHEMA_V2.md`: proposed next metadata contract

## Minimal Operations

- `python3 01_tools/check_scaffold.py`: validate the local scaffold shape
- `python3 01_tools/validate_metadata.py`: validate TSV headers, uniqueness, and benchmark references
- `bash 01_tools/run_local_checks.sh`: run structure checks plus workflow dry-run
- `python3 run_workflow.py --dry-run`: inspect the current DAG without executing work
- `bash 01_tools/preflight_hpc.sh`: read-only HPC readiness check
- `bash 01_tools/submit_hpc_dry_run.sh`: submit a Slurm dry-run wrapper on the server
- `bash 01_tools/submit_hpc_scaffold_run.sh`: submit a lightweight non-dry-run scaffold execution
