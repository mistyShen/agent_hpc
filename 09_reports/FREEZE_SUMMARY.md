# Freeze Summary

## Project Goal

Build a CPU-only, Snakemake-driven, recoverable, comparable AI-aided drug-design workflow that can move from scaffold modules to real backends without breaking downstream compatibility.

## Completed Core Capabilities

- `classical_docking` runs real `vina_cpu`
- `ai_reranking` consumes real docking artifacts
- `filtering` consumes real docking and reranking outputs
- `clustering_and_prioritization` consumes the filter keep set and produces final shortlists
- `run_manifest`, `done.json`, case-level execution state, cache/skip, and partial rerun are wired through
- demo-scale multi-case merge and isolation are validated
- two minimal literature-backed BRD4 BD1 cases are fixed:
  - `BRD4_BD1_LIT001`: `filter_keep_count = 1`, `shortlist_count = 1`, `JQ1 rank = 1`
  - `BRD4_BD1_LIT002`: `filter_keep_count = 2`, `shortlist_count = 2`, `I-BET762 rank = 1`
- `filtering v2.1` is frozen for `literature_backed + comparison` cases only

## Validated Boundary

- single-case execution
- heterogeneous-target two-case execution
- heterogeneous-library two-case execution
- three-active-case execution
- case-aware partial rerun isolation at demo scale
- minimal literature-backed recovery on two BRD4 BD1 cases

## Unvalidated Boundary

- larger-scale multi-case benchmark behavior
- literature-backed recovery beyond the current two BRD4 BD1 cases
- stronger benchmark metrics and cross-target comparison evidence
- benchmark-grade clustering and chemistry-aware filtering

## Recommended Next Step

Add the next realistic or literature-backed evidence layer cautiously without changing the frozen BRD4 filtering logic until a clear new comparison need appears.
