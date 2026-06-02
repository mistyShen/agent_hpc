# Benchmark Plan

## Goal

Build a CPU-only baseline workflow for AI-assisted drug design that can be executed reproducibly and later compared across targets, compound libraries, docking strategies, reranking heuristics, and prioritization policies.

## Stage 0

- Finalize project structure
- Finalize execution framework
- Define module interfaces
- Keep artifacts lightweight and synthetic

## Stage 1

- Add benchmark metadata templates under `04_metadata`
- Add small synthetic manifests for targets and compounds
- Define success criteria for each module

## Stage 2

- Connect CPU-friendly docking and reranking placeholders to real tools
- Add Slurm execution profile for formal HPC runs
- Add benchmark summary outputs under `09_reports`

## Stage 3

- Add server-side preflight checks before submission
- Add reusable `hpc-sbatch` submission entrypoints for dry-run and low-risk scaffold execution
- Keep formal runs CPU-only unless the benchmark spec explicitly changes

## Minimal Evaluation Questions

- Can each stage be resumed without recomputing completed outputs?
- Are logs and outputs discoverable from a single config?
- Is the same workflow runnable locally and on HPC with only profile/path changes?
