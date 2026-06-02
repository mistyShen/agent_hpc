# Manuscript / Report Outline

## Working Title

CPU-only modular drug-design workflow with real Vina docking, lightweight downstream ranking, and validated demo-scale multi-case recovery

## One-Paragraph Positioning

`cpu_ai_drug_design` is a Snakemake-based CPU-only workflow for target preparation, compound library preparation, docking, reranking, filtering, clustering, reporting, and benchmark evaluation. The current system has moved beyond a pure scaffold because `classical_docking` now runs a real `vina_cpu` backend and downstream modules consume those real artifacts. The present evidence boundary is operational rather than publication-grade: the workflow is validated for single-case execution, heterogeneous two-case execution, three-active-case execution, and case-aware partial rerun isolation at demo scale.

## Audience

- internal project reviews
- milestone reports
- manuscript planning drafts

## Core Message

The workflow is now credible as a reproducible CPU-only execution system with real docking integration and validated recovery behavior, but it is not yet credible as a benchmark-grade scientific comparison system.

## Recommended Section Order

### 1. System Scope

- CPU-only design goal
- modular Snakemake structure
- local/HPC portability

### 2. Current Real Backend Coverage

- real `vina_cpu` docking in `classical_docking`
- lightweight downstream consumption in:
  - `ai_reranking`
  - `filtering`
  - `clustering_and_prioritization`

Primary source:

- `00_docs/REAL_BACKEND_STATUS.md`

### 3. Validated Runtime Boundary

- single-case runtime-state validated
- heterogeneous-target two-case validated
- heterogeneous-library two-case validated
- three-active-case validated
- partial rerun isolation validated
- multi-case merge validated at demo scale

Primary sources:

- `00_docs/RUN_RECOVERY.md`
- `07_results/modules/run_state_checker/workflow_health_summary.json`

### 4. Benchmark Comparison Layer

Use the current fixed comparison table with these columns:

| Case | Target | Library | Type | Tier | Purpose | Metric | Docking | Reranked | Filtered | Keep | Shortlist | Top 1 | Top 2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Primary sources:

- `09_reports/benchmark_comparison.md`
- `09_reports/benchmark_comparison.json`

### 5. Current Results Statement

At the current three-case demo scale:

- all three cases complete end to end
- each case produces docking, reranking, filtering, and shortlist outputs
- shortlist generation remains lightweight and should be treated as operational evidence rather than scientific ranking evidence

### 6. Limitations

- benchmark set remains toy/debug scale
- no realistic or literature-backed claims yet
- no larger-scale multi-case benchmark validation yet
- downstream chemistry/ranking logic is still lightweight

### 7. Near-Term Upgrade Path

1. freeze manuscript/report wording and table structure
2. add benchmark-grade evaluation metrics
3. add realistic or literature-backed cases
4. validate larger-scale multi-case behavior

## Recommended Reusable Tables

### Table A. Module And Backend Status

Source:

- `00_docs/REAL_BACKEND_STATUS.md`

### Table B. Runtime-State Validation Matrix

Source:

- `07_results/modules/run_state_checker/workflow_health_summary.json`

### Table C. Benchmark Comparison Table

Source:

- `09_reports/benchmark_comparison.md`

### Table D. Final Shortlists By Case

Source:

- `09_reports/benchmark_comparison.md`

## Recommended Reusable Summary Paragraph

This workflow has progressed from a runnable prototype to a reproducible CPU-only execution system with real `vina_cpu` docking and lightweight downstream consumers. The current validated boundary includes single-case execution, heterogeneous two-case runs, three-active-case runs, case-aware partial rerun isolation, and demo-scale multi-case merge. The current benchmark layer is suitable for operational comparison and project reporting, but not yet for benchmark-grade scientific claims.
